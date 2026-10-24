"""策略比较、输入留痕与核对底稿。"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .data import InputData, money, read_records, write_csv
from .matching import Policy, Result, reconcile
from .simulation import generate


POLICY_LABELS = {"reference": "编号唯一核对", "cautious": "编号与身份分层核对", "amount_date": "金额日期优先"}


def evaluate(result: Result, truth: list[dict]) -> dict:
    expected = {(tuple(sorted(row["ledger_ids"].split("|"))), tuple(sorted(row["bank_ids"].split("|"))))
                for row in truth}
    predicted = {(m.ledger, m.bank) for m in result.matches}
    correct = len(predicted & expected)
    matched_l = {i for m in result.matches for i in m.ledger}
    bank = {r.record_id: r for r in result.bank}
    subsequent = sum(1 for m in result.matches if any(bank[i].date > result.cutoff for i in m.bank))
    return {"policy": result.policy.name, "strategy": POLICY_LABELS[result.policy.name],
            "window_days": result.policy.window, "ledger_records": len(result.ledger),
            "bank_records": len(result.bank), "matched_groups": len(predicted),
            "correct_groups": correct, "wrong_groups": len(predicted) - correct,
            "precision": round(correct / len(predicted), 6) if predicted else "",
            "group_recall": round(correct / len(expected), 6) if expected else "",
            "ledger_coverage": round(len(matched_l) / len(result.ledger), 6) if result.ledger else "",
            "unresolved_ledger": len(result.ledger) - len(matched_l),
            "subsequent_groups": subsequent}


def export_result(result: Result, ledger: InputData, bank: InputData, folder: Path):
    lm, bm = {r.record_id: r for r in result.ledger}, {r.record_id: r for r in result.bank}
    matches = []
    membership = {}
    for n, match in enumerate(result.matches, 1):
        match_id = f"M{n:04d}"
        after = any(bm[i].date > result.cutoff for i in match.bank)
        row = {"match_id": match_id, "ledger_ids": "|".join(match.ledger),
               "bank_ids": "|".join(match.bank), "method": match.method,
               "currency": lm[match.ledger[0]].currency,
               "ledger_amount": money(sum(lm[i].amount for i in match.ledger)),
               "bank_amount": money(sum(bm[i].amount for i in match.bank)),
               "cutoff_status": "期后到账证据" if after else "当期双方记录"}
        matches.append(row)
        for source, ids in (("ledger", match.ledger), ("bank", match.bank)):
            for i in ids:
                membership[source, i] = (match_id, row["cutoff_status"])
    write_csv(folder / "matches.csv", matches,
              ("match_id", "ledger_ids", "bank_ids", "method", "currency", "ledger_amount", "bank_amount", "cutoff_status"))
    write_csv(folder / "review_queue.csv", result.review,
              ("ledger_id", "ledger_row", "currency", "amount", "reason", "bank_candidates"))
    controls = [{key: value if key == "currency" else money(value) for key, value in row.items()}
                for row in result.controls]
    write_csv(folder / "control.csv", controls,
              ("currency", "ledger_current", "bank_current", "raw_difference", "subsequent_settlement",
               "ledger_unmatched", "bank_unmatched", "control_residual"))
    trace = []
    active = {(r.source, r.record_id) for r in result.ledger + result.bank}
    for data in (ledger, bank):
        for r in data.records:
            match_id, status = membership.get((r.source, r.record_id), ("", "待核对"))
            if (r.source, r.record_id) not in active:
                status = "范围外"
            elif r.source == "bank" and r.date > result.cutoff and not match_id:
                status = "期后未匹配"
            trace.append({"source": r.source, "row": r.row, "record_id": r.record_id,
                          "date": r.date.isoformat(), "currency": r.currency, "amount": money(r.amount),
                          "reference": r.reference, "project_id": r.project_id,
                          "counterparty": r.counterparty, "match_id": match_id, "status": status})
    trace_fields = ("source", "row", "record_id", "date", "currency", "amount", "reference",
                    "project_id", "counterparty", "match_id", "status")
    write_csv(folder / "row_trace.csv", trace, trace_fields)
    unmatched_b = [row for row in trace if row["source"] == "bank" and row["status"] == "待核对"]
    write_csv(folder / "bank_unmatched.csv", unmatched_b,
              trace_fields)


def run_experiment(root: Path, seed: int = 47) -> dict:
    data = root / "data"
    generate(data, seed)
    ledger, bank = read_records(data / "ledger.csv", "ledger"), read_records(data / "bank.csv", "bank")
    with (data / "truth.csv").open(encoding="utf-8-sig", newline="") as stream:
        truth = list(csv.DictReader(stream))
    summaries, results = [], {}
    for policy in ("reference", "cautious", "amount_date"):
        result = reconcile(ledger, bank, date(2026, 6, 1), date(2026, 6, 30), Policy(policy))
        export_result(result, ledger, bank, root / "results" / policy)
        summaries.append(evaluate(result, truth))
        results[policy] = result
    write_csv(root / "results" / "summary.csv", summaries)
    sensitivity = []
    for window in (1, 3, 5, 7):
        result = reconcile(ledger, bank, date(2026, 6, 1), date(2026, 6, 30), Policy("cautious", window))
        sensitivity.append(evaluate(result, truth))
    write_csv(root / "results" / "sensitivity.csv", sensitivity)
    write_csv(root / "results" / "input_issues.csv", [asdict(i) for i in ledger.issues + bank.issues],
              ("source", "row", "record_id", "reason", "raw_amount"))
    manifest = {"seed": seed, "period_start": "2026-06-01", "cutoff": "2026-06-30",
                "amount_unit": "CNY, integer cents internally", "data_kind": "synthetic",
                "ledger": {"raw_rows": ledger.raw_rows, "valid_rows": len(ledger.records), "sha256": ledger.sha256},
                "bank": {"raw_rows": bank.raw_rows, "valid_rows": len(bank.records), "sha256": bank.sha256},
                "excluded_rows": len(ledger.issues) + len(bank.issues), "max_group": 4,
                "policies": summaries, "sensitivity": sensitivity}
    target = root / "results" / "manifest.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    from .narrative import write_report
    write_report(root, manifest)
    return manifest
