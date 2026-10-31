"""Create tiny synthetic fixtures. They are not network captures or research data."""

from pathlib import Path
import argparse
import csv
import json
from engineering_pilot import connection_key, group_choice

HEADER = [
    "src_ip",
    "dst_ip",
    "src_port",
    "dst_port",
    "protocol",
    "timestamp",
    "flow_duration",
    "tot_fwd_pkts",
    "flow_iat_min",
    "fwd_iat_min",
    "bwd_iat_min",
    "label",
]
ATTACKS = {
    1: ("BOT", "DDoS-bot"),
    5: ("STOMP", "DDoS-stomp"),
    9: ("DYN", "DDoS-dyn"),
    10: ("TCP", "DDoS-tcp"),
}


def synthetic_rows(client, label):
    rows, counts = [], {"fit": 0, "validation": 0}
    attack = label != "Normal"
    # Select fixture identities that exercise both roles with the real grouping code.
    for port in range(1025, 60999):
        src = f"192.0.2.{client}"
        dst = "198.51.100.2" if attack else "198.51.100.1"
        choice = group_choice(connection_key(src, dst, port, 443, 2048))
        if choice is None or counts[choice[1]] >= 8:
            continue
        counts[choice[1]] += 1
        rows.append(
            [
                src,
                dst,
                port,
                443,
                2048,
                "2023-05-13 15:00:00",
                20 + port % 3 if attack else 2 + port % 3,
                10 if attack else 1,
                0,
                0,
                0,
                label,
            ]
        )
        if min(counts.values()) == 8:
            return rows
    raise RuntimeError("Could not construct fixture support")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(HEADER)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / "SYNTHETIC_ONLY.json").write_text(
        json.dumps({"purpose": "software integration test, not scientific evidence"}) + "\n"
    )
    base = root / "datasets/flnet2023/extracted"
    common = synthetic_rows(1, "Normal")[0]
    for client in range(1, 11):
        # A shared observation at two clients exercises global grouping.
        normal = synthetic_rows(client, "Normal")
        if client == 2:
            normal.append(common)
        write_csv(base / "Normal" / f"Dataset-{client}.csv", normal)
        if client in ATTACKS:
            suffix, label = ATTACKS[client]
            write_csv(
                base / "DDoS" / f"Dataset-{client}-{suffix}.csv", synthetic_rows(client, label)
            )
    write_csv(base / "TEST/reserved.csv", [])
    cic = root / "datasets/cicddos2019/extracted"
    write_csv(cic / "01-12/fixture.csv", [r[:-1] + ["BENIGN"] for r in synthetic_rows(3, "Normal")])
    write_csv(cic / "03-11/reserved.csv", [])
    print(root)


if __name__ == "__main__":
    main()
