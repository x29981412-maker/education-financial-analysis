"""逐行回查下载的港交所原始年报。原PDF不在仓库重新分发。"""

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent


def verify(path):
    metadata = json.loads((ROOT / "data" / "sources.json").read_text(encoding="utf-8"))
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["primary"]["sha256"]:
        raise ValueError("PDF校验值不一致，请确认下载的是sources.json所列版本")
    pdf = PdfReader(path)
    with (ROOT / "data" / "financials.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    results = []
    cache = {}
    for row in rows:
        page = int(row["pdf_page"])
        if page not in cache:
            cache[page] = [" ".join(line.split()) for line in pdf.pages[page - 1].extract_text().splitlines()]
        expected = [int(row[f"fy{y}"]) for y in (2023, 2024, 2025) if row[f"fy{y}"].strip()]
        label = row["source_label"]
        found = False
        for line in cache[page]:
            if not line.startswith(label + " "):
                continue
            tail = line[len(label):]
            values = re.findall(r"\(?-?\d[\d,]*\)?|—", tail)
            if len(values) != len(expected):
                continue
            actual = [0 if v == "—" else -int(v[1:-1].replace(",", "")) if v.startswith("(")
                      else int(v.replace(",", "")) for v in values]
            if actual == expected:
                found = True
                break
        if not found:
            raise ValueError(f"原文不一致：第{page}页 {label} {expected}")
        results.append({"metric": row["metric"], "pdf_page": page, "checked_values": len(expected), "status": "原文一致"})
    (ROOT / "results").mkdir(exist_ok=True)
    with (ROOT / "results" / "source_verification.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(results)
    print(f"原PDF校验值一致，逐行核对{len(results)}个指标、{sum(r['checked_values'] for r in results)}个披露值。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path, help="从sources.json链接下载的港交所年报PDF")
    verify(parser.parse_args().pdf)
