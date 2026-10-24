"""命令行入口。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .data import read_records, write_csv
from .experiment import export_result, run_experiment
from .matching import Policy, reconcile


def main(argv=None):
    parser = argparse.ArgumentParser(description="项目台账与银行流水核对")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="生成模拟样例并运行策略比较")
    demo.add_argument("--root", type=Path, default=Path.cwd())
    demo.add_argument("--seed", type=int, default=47)
    check = sub.add_parser("check", help="按统一字段检查自己的CSV文件")
    check.add_argument("--ledger", type=Path, required=True)
    check.add_argument("--bank", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--start", type=date.fromisoformat, required=True)
    check.add_argument("--cutoff", type=date.fromisoformat, required=True)
    check.add_argument("--policy", choices=("reference", "cautious", "amount_date"), default="cautious")
    check.add_argument("--window", type=int, default=5)
    args = parser.parse_args(argv)
    if args.command == "demo":
        manifest = run_experiment(args.root, args.seed)
        for row in manifest["policies"]:
            print(f"{row['strategy']}: 匹配 {row['matched_groups']} 组，错误 {row['wrong_groups']} 组，"
                  f"待核对台账 {row['unresolved_ledger']} 条")
    else:
        ledger, bank = read_records(args.ledger, "ledger"), read_records(args.bank, "bank")
        result = reconcile(ledger, bank, args.start, args.cutoff, Policy(args.policy, args.window))
        export_result(result, ledger, bank, args.output)
        write_csv(args.output / "input_issues.csv", [asdict(i) for i in ledger.issues + bank.issues],
                  ("source", "row", "record_id", "reason", "raw_amount"))
        print(f"匹配 {len(result.matches)} 组；待核对台账 {len(result.review)} 条；"
              f"输入隔离 {len(ledger.issues) + len(bank.issues)} 行。")
