"""Render an audit as escaped standalone HTML and Quarto source."""

from collections import Counter
import html
import json
from research_workspace import workspace_root


def main():
    root = workspace_root()
    directory = root / "reports/dataset-audit"
    audit = json.loads((directory / "audit.json").read_text())
    if audit["status"] != "complete":
        raise ValueError("Finish the audit before rendering")
    rows = []
    for dataset in sorted(audit["dataset_totals"]):
        files = [f for f in audit["files"] if f["dataset"] == dataset]
        counts = Counter()
        for file in files:
            counts.update(file["labels"])
        for label, count in sorted(counts.items()):
            rows.append((dataset, label, count))
    message = (
        "This report describes development files. Test inspection is limited to headers. "
        "Fingerprint matches are duplicate candidates and need confirmation before removal. "
        "No final evaluation split or model-performance conclusion follows from this audit."
    )
    source = (
        "# Development data audit\n\n"
        + message
        + "\n\n| Dataset | Label | Records |\n|---|---|---:|\n"
    )
    source += "".join(
        "| " + " | ".join(str(x).replace("|", " / ").replace("\n", " ") for x in row) + " |\n"
        for row in rows
    )
    source += "\nFull field diagnostics and environment records are in `audit.json`.\n"
    table = "<table><tr><th>Dataset</th><th>Label</th><th>Records</th></tr>"
    table += (
        "".join(
            "<tr>" + "".join("<td>" + html.escape(str(x)) + "</td>" for x in row) + "</tr>"
            for row in rows
        )
        + "</table>"
    )
    body = (
        "<h1>Development data audit</h1><p>"
        + html.escape(message)
        + "</p>"
        + table
        + "<p>Full diagnostics are in audit.json.</p>"
    )
    css = "body{font:18px/1.6 system-ui;max-width:1000px;margin:3em auto;padding:0 1em}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:.4em .8em}"
    (directory / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Development data audit</title><style>'
        + css
        + "</style><body>"
        + body
        + "</body></html>"
    )
    (directory / "dataset-audit.qmd").write_text(
        "---\ntitle: Development data audit\nformat: html\nexecute:\n  enabled: false\n---\n\n"
        + source
    )
    print("Rendered reports/dataset-audit/index.html and dataset-audit.qmd")


if __name__ == "__main__":
    main()
