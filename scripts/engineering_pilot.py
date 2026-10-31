"""Bounded FLNET engineering check. Never reads the reserved TEST directory."""

from pathlib import Path
import argparse, copy, hashlib, json, platform, re, resource, time
from collections import Counter
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import average_precision_score, confusion_matrix

from research_workspace import workspace_root, contained_path

ROOT = workspace_root()
VERSION = "engineering-smoke-v1-portable"
META = ["src_ip", "dst_ip", "src_port", "dst_port", "protocol", "timestamp", "label"]
UNCERTAIN = ["flow_iat_min", "fwd_iat_min", "bwd_iat_min"]
LABELS = {"Normal": 0, "DDoS-bot": 1, "DDoS-tcp": 1, "DDoS-stomp": 1, "DDoS-dyn": 1}
CONFIG = dict(
    version=VERSION,
    purpose="engineering_only_not_confirmatory",
    seed=20261031,
    group_sampling_denominator=64,
    validation_group_modulus=5,
    rounds=3,
    local_epochs=1,
    batch_size=256,
    hidden_units=16,
    cpu_threads=2,
    sgd_lr=0.01,
    adam_lr=0.001,
    adam_betas=[0.9, 0.999],
    adam_eps=1e-8,
    weight_decay=0.0,
    local_optimizer_state="reset_every_round",
    client_participation="all_ten",
    loss="unweighted_BCEWithLogitsLoss",
    aggregation="local_fit_row_count_weighted_model_average",
    scaler="pooled_fit_only_standardization_engineering_reference",
    device="cpu",
    dtype="float32",
    threshold=0.5,
    feature_exclusions=META + UNCERTAIN,
    reserved_test_read=False,
    deduplication=False,
    rebalancing=False,
)


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + "\n")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def connection_key(src, dst, sport, dport, protocol):
    endpoints = sorted(
        [(str(src).strip(), str(sport).strip()), (str(dst).strip(), str(dport).strip())]
    )
    return json.dumps([endpoints, str(protocol).strip()], separators=(",", ":"))


def group_choice(key):
    encoded = key.encode()
    sample = hashlib.sha256(b"flnet-smoke-sample-20261031\0" + encoded).digest()
    if int.from_bytes(sample[:8], "big") % CONFIG["group_sampling_denominator"]:
        return None
    role_hash = hashlib.sha256(b"flnet-smoke-role-20261031\0" + encoded).digest()
    role = (
        "validation"
        if int.from_bytes(role_hash[:8], "big") % CONFIG["validation_group_modulus"] == 0
        else "fit"
    )
    return hashlib.sha256(encoded).hexdigest(), role


def fit_scaler(fit_features):
    mean = np.mean(fit_features, axis=0, dtype=np.float64)
    scale = np.std(fit_features, axis=0, dtype=np.float64)
    scale[scale == 0] = 1.0
    return mean, scale


def weighted_average(states, counts):
    if len(states) != len(counts) or not states or min(counts) <= 0:
        raise ValueError("Invalid client weights")
    total = sum(counts)
    return {
        name: sum(
            state[name].double() * (count / total) for state, count in zip(states, counts)
        ).to(states[0][name].dtype)
        for name in states[0]
    }


def self_test():
    a = connection_key("a", "b", "123", "456", "2048")
    b = connection_key("b", "a", "456", "123", "2048")
    assert a == b
    assert a != connection_key("a", "b", "456", "123", "2048")
    assert group_choice(a) == group_choice(b)
    # Deliberately unequal clients detect equal-weight averaging mistakes.
    states = [{"x": torch.tensor([1.0, 3.0])}, {"x": torch.tensor([5.0, 7.0])}]
    assert torch.equal(weighted_average(states, [1, 3])["x"], torch.tensor([4.0, 6.0]))
    assert torch.equal(weighted_average(states[::-1], [3, 1])["x"], torch.tensor([4.0, 6.0]))
    # Known fit-only moments, including a constant column.
    mean, scale = fit_scaler(np.array([[1.0, 4.0], [3.0, 4.0]]))
    np.testing.assert_array_equal(mean, [2.0, 4.0])
    np.testing.assert_array_equal(scale, [1.0, 1.0])
    print(
        "PASS: reversed endpoints, port identity, unequal client weights, permutation, scaler moments"
    )


def prepare(out):
    inventory = json.loads((ROOT / "config/split-proposal.json").read_text())
    if inventory.get("unmapped_development_labels", {}).get("flnet2023"):
        raise ValueError("Unmapped FLNET development labels require review before sampling")
    sources = [
        f
        for f in inventory["files"]
        if f["dataset"] == "flnet2023" and f["source_role"] == "development"
    ]
    assert len(sources) == 14
    frames, cache, collisions, observed = [], {}, {}, []
    columns = None
    start = time.monotonic()
    for item in sorted(sources, key=lambda f: f["path"]):
        relative = item["path"]
        if not re.fullmatch(
            r"datasets/flnet2023/extracted/(?:DDoS|Normal)/Dataset-\d+(?:-[A-Za-z]+)?\.csv",
            relative,
        ):
            raise ValueError("Source outside approved development allowlist")
        path = contained_path(ROOT, relative)
        assert sha(path) == item["sha256"], "Source changed"
        offset = selected_count = 0
        for raw in pd.read_csv(
            path, dtype=str, keep_default_na=False, chunksize=100000, on_bad_lines="error"
        ):
            if columns is None:
                columns = list(raw.columns)
            assert columns == list(raw.columns), "Inconsistent schema"
            selected, identifiers, roles = [], [], []
            for row, values in enumerate(
                raw[["src_ip", "dst_ip", "src_port", "dst_port", "protocol"]].itertuples(
                    index=False, name=None
                )
            ):
                key = connection_key(*values)
                if key not in cache:
                    cache[key] = group_choice(key)
                choice = cache[key]
                if choice is not None:
                    group_id, role = choice
                    if group_id in collisions:
                        assert collisions[group_id] == key, "Digest collision"
                    else:
                        collisions[group_id] = key
                    selected.append(row)
                    identifiers.append(group_id)
                    roles.append(role)
            frame = raw.iloc[selected].copy()
            frame["_source_path"] = relative
            frame["_source_row"] = np.asarray(selected, dtype=np.int64) + offset + 1
            frame["_client_id"] = item["client_id"]
            frame["_group_id"] = identifiers
            frame["_role"] = roles
            frames.append(frame)
            offset += len(raw)
            selected_count += len(frame)
        observed.append(
            dict(path=relative, sha256=item["sha256"], rows=offset, selected=selected_count)
        )
        print(json.dumps(dict(source=path.name, selected=selected_count)), flush=True)
    data = pd.concat(frames, ignore_index=True)
    assert set(data["_client_id"]) == set(range(1, 11))
    assert set(data["label"]) == set(LABELS)
    assert data.groupby("_group_id")["_role"].nunique().max() == 1
    # Compare full stored records, not just a non-cryptographic row hash.
    exact = {
        role: set(data.loc[data["_role"].eq(role), columns].itertuples(index=False, name=None))
        for role in ["fit", "validation"]
    }
    cross_role_records = len(exact["fit"] & exact["validation"])
    assert cross_role_records == 0
    feature_names = [c for c in columns if c not in META + UNCERTAIN]
    features = data[feature_names].apply(pd.to_numeric, errors="raise").to_numpy(dtype=np.float64)
    assert np.isfinite(features).all()
    target = data["label"].map(LABELS).to_numpy(dtype=np.int64)
    fit = data["_role"].eq("fit").to_numpy()
    mean, scale = fit_scaler(features[fit])
    scaled = ((features - mean) / scale).astype(np.float32)
    assert np.isfinite(scaled).all()
    # Validation changes cannot alter the selected fit inputs or moments.
    perturbed = features.copy()
    perturbed[~fit] = 1e30
    alt_mean, alt_scale = fit_scaler(perturbed[fit])
    np.testing.assert_array_equal(mean, alt_mean)
    np.testing.assert_array_equal(scale, alt_scale)
    groups_by_role = {
        r: int(data.loc[data["_role"].eq(r), "_group_id"].nunique()) for r in ["fit", "validation"]
    }
    counts = []
    for (client, role, label), count in (
        data.groupby(["_client_id", "_role", "label"]).size().items()
    ):
        counts.append(dict(client=int(client), role=role, label=label, rows=int(count)))
    for client in range(1, 11):
        assert ((data["_client_id"].to_numpy() == client) & fit).any()
        assert ((data["_client_id"].to_numpy() == client) & ~fit).any()
    data.to_parquet(out / "selected-records.parquet", index=False)
    np.savez_compressed(
        out / "prepared-arrays.npz",
        X=scaled,
        y=target,
        fit=fit,
        client=data["_client_id"].to_numpy(dtype=np.int16),
    )
    dump(
        out / "scaler.json",
        dict(
            scope="pooled_fit_rows_only_engineering_reference",
            features=feature_names,
            mean=mean.tolist(),
            scale=scale.tolist(),
        ),
    )
    report = dict(
        scope="FLNET development only",
        config=CONFIG,
        sources=observed,
        selected_rows=len(data),
        selected_groups=int(data["_group_id"].nunique()),
        groups_by_role=groups_by_role,
        rows_by_role={k: int(v) for k, v in data["_role"].value_counts().items()},
        client_role_labels=counts,
        feature_count=len(feature_names),
        excluded_predictors=META + UNCERTAIN,
        cross_role_groups=0,
        cross_role_identical_full_records=cross_role_records,
        validation_perturbation_scaler_check="passed",
        all_ten_clients_in_both_roles=True,
        reserved_test_opened=False,
        duration_seconds=round(time.monotonic() - start, 3),
        files={
            name: sha(out / name)
            for name in ["selected-records.parquet", "prepared-arrays.npz", "scaler.json"]
        },
    )
    dump(out / "preparation.json", report)
    return report


def metrics(model, X, y, client):
    with torch.no_grad():
        logits = model(X).squeeze(1)
        probability = torch.sigmoid(logits).numpy()
        loss = torch.nn.functional.binary_cross_entropy_with_logits(
            logits, torch.tensor(y, dtype=torch.float32)
        ).item()
    assert np.isfinite(probability).all() and np.isfinite(loss)

    def summary(mask):
        truth, p = y[mask], probability[mask]
        tn, fp, fn, tp = confusion_matrix(truth, p >= 0.5, labels=[0, 1]).ravel()
        return dict(
            n=int(len(truth)),
            positives=int(truth.sum()),
            tn=int(tn),
            fp=int(fp),
            fn=int(fn),
            tp=int(tp),
            recall=float(tp / (tp + fn)) if tp + fn else None,
            fpr=float(fp / (fp + tn)) if fp + tn else None,
            average_precision=float(average_precision_score(truth, p))
            if len(np.unique(truth)) == 2
            else None,
        )

    return dict(
        loss=loss,
        pooled=summary(np.ones(len(y), dtype=bool)),
        clients={str(c): summary(client == c) for c in sorted(np.unique(client))},
    )


def train(out):
    assert CONFIG["local_epochs"] == 1, "This bounded implementation supports one local epoch"
    torch.set_num_threads(CONFIG["cpu_threads"])
    torch.use_deterministic_algorithms(True)
    arrays = np.load(out / "prepared-arrays.npz")
    X = torch.from_numpy(arrays["X"])
    y = torch.from_numpy(arrays["y"].astype(np.float32))
    client = arrays["client"]
    fit = arrays["fit"]
    torch.manual_seed(CONFIG["seed"])
    template = torch.nn.Sequential(
        torch.nn.Linear(X.shape[1], CONFIG["hidden_units"]),
        torch.nn.ReLU(),
        torch.nn.Linear(CONFIG["hidden_units"], 1),
    )
    initial = copy.deepcopy(template.state_dict())
    results = {}
    for optimizer_name in ["sgd", "adam"]:
        global_model = copy.deepcopy(template)
        global_model.load_state_dict(initial)
        history = [
            dict(
                round=0, validation=metrics(global_model, X[~fit], arrays["y"][~fit], client[~fit])
            )
        ]
        started = time.monotonic()
        order_digest = hashlib.sha256()
        for round_id in range(1, CONFIG["rounds"] + 1):
            broadcast = copy.deepcopy(global_model.state_dict())
            states, counts, client_logs = [], [], []
            round_start = time.monotonic()
            for cid in range(1, 11):
                local = copy.deepcopy(global_model)
                assert all(torch.equal(local.state_dict()[k], v) for k, v in broadcast.items())
                if optimizer_name == "sgd":
                    optimizer = torch.optim.SGD(
                        local.parameters(),
                        lr=CONFIG["sgd_lr"],
                        momentum=0,
                        weight_decay=0,
                        foreach=False,
                    )
                else:
                    optimizer = torch.optim.Adam(
                        local.parameters(),
                        lr=CONFIG["adam_lr"],
                        betas=tuple(CONFIG["adam_betas"]),
                        eps=CONFIG["adam_eps"],
                        weight_decay=0,
                        foreach=False,
                        fused=False,
                    )
                indices = np.flatnonzero(fit & (client == cid))
                generator = np.random.default_rng(CONFIG["seed"] + round_id * 100 + cid)
                order = generator.permutation(indices)
                order_digest.update(order.astype("<i8").tobytes())
                loss_sum = 0.0
                local_start = time.monotonic()
                for begin in range(0, len(order), CONFIG["batch_size"]):
                    batch = order[begin : begin + CONFIG["batch_size"]]
                    optimizer.zero_grad(set_to_none=True)
                    loss = torch.nn.functional.binary_cross_entropy_with_logits(
                        local(X[batch]).squeeze(1), y[batch]
                    )
                    assert torch.isfinite(loss)
                    loss.backward()
                    optimizer.step()
                    loss_sum += loss.item() * len(batch)
                state = copy.deepcopy(local.state_dict())
                assert all(torch.isfinite(v).all() for v in state.values())
                states.append(state)
                counts.append(len(indices))
                client_logs.append(
                    dict(
                        client=cid,
                        fit_rows=len(indices),
                        mean_training_loss=loss_sum / len(indices),
                        seconds=round(time.monotonic() - local_start, 4),
                    )
                )
            global_model.load_state_dict(weighted_average(states, counts))
            assert all(torch.isfinite(v).all() for v in global_model.state_dict().values())
            history.append(
                dict(
                    round=round_id,
                    clients=client_logs,
                    seconds=round(time.monotonic() - round_start, 4),
                    validation=metrics(global_model, X[~fit], arrays["y"][~fit], client[~fit]),
                )
            )
            print(
                json.dumps(
                    dict(
                        optimizer=optimizer_name,
                        round=round_id,
                        validation_loss=history[-1]["validation"]["loss"],
                    )
                ),
                flush=True,
            )
        torch.save(global_model.state_dict(), out / f"{optimizer_name}-round{CONFIG['rounds']}.pt")
        results[optimizer_name] = dict(
            rounds=history,
            seconds=round(time.monotonic() - started, 4),
            batch_order_sha256=order_digest.hexdigest(),
            checkpoint_sha256=sha(out / f"{optimizer_name}-round{CONFIG['rounds']}.pt"),
        )
    assert results["sgd"]["batch_order_sha256"] == results["adam"]["batch_order_sha256"]
    assert results["sgd"]["rounds"][0]["validation"] == results["adam"]["rounds"][0]["validation"]
    output = dict(
        purpose="engineering_only_not_optimizer_ranking",
        config=CONFIG,
        runs=results,
        parameters=sum(p.numel() for p in template.parameters()),
        peak_process_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        * (1 if platform.system() == "Darwin" else 1024),
        matched_initialization=True,
        matched_batch_orders=True,
        environment=dict(
            python=platform.python_version(),
            torch=torch.__version__,
            numpy=np.__version__,
            pandas=pd.__version__,
            platform=platform.platform(),
        ),
        script_sha256=sha(Path(__file__)),
        limitations=[
            "One seed and three rounds; hyperparameters not tuned.",
            "Pooled fit-only scaling is an engineering reference, not a deployed federated preprocessing protocol.",
            "Connection grouping does not establish capture independence or future-traffic validity.",
            "Clients execute sequentially on one CPU; elapsed time is not distributed deployment latency.",
            "Reserved test files were not read. Sellier treatment is not implemented.",
        ],
    )
    dump(out / "training.json", output)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        return
    out = ROOT / "runs" / VERSION
    out.mkdir(parents=True, exist_ok=False)
    dump(out / "config.json", CONFIG)
    prepare(out)
    train(out)
    dump(
        out / "COMPLETE.json",
        dict(
            status="complete",
            purpose="engineering_only",
            files={p.name: sha(p) for p in out.iterdir() if p.is_file()},
        ),
    )
    print(str(out), flush=True)


if __name__ == "__main__":
    main()
