"""固定种子的业务样例；标签单独保存，不参与匹配。"""

from __future__ import annotations

import random
from datetime import date, timedelta
from pathlib import Path

from .data import FIELDS, money, write_csv


def generate(folder: Path, seed: int = 47):
    rng = random.Random(seed)
    ledger, bank, truth, scenarios = [], [], [], []

    def add(side, day, amount, ref, project, payer):
        prefix = "L" if side is ledger else "B"
        row = dict(zip(FIELDS, (f"{prefix}{len(side) + 1:04d}", day.isoformat(),
                               money(amount), "CNY", ref, project, payer)))
        side.append(row)
        return row["record_id"]

    def label(name, left, right):
        truth.append({"scenario": name, "ledger_ids": "|".join(sorted(left)),
                      "bank_ids": "|".join(sorted(right))})

    origin = date(2026, 6, 1)
    for i in range(120):
        day = origin + timedelta(days=rng.randrange(25))
        amount = rng.randrange(12000, 65000) * 100 + rng.randrange(100)
        args = (day, amount, f"RC{i:04d}", f"P{i % 20:03d}", f"付款方{i:03d}")
        label("单笔收款", [add(ledger, *args)], [add(bank, *args)])
    for i in range(12):
        args = (origin + timedelta(days=i + 3), -rng.randrange(5000, 15000) * 100,
                f"RF{i:04d}", f"退款项目{i:02d}", f"退款方{i:02d}")
        label("退款", [add(ledger, *args)], [add(bank, *args)])
    for i in range(12):
        day = origin + timedelta(days=i + 1)
        parts = [rng.randrange(3000, 9000) * 100 for _ in range(3)]
        ref, project, payer = f"AG{i:04d}", f"分期项目{i:02d}", f"分期付款方{i:02d}"
        left = [add(ledger, day, amount, ref, project, payer) for amount in parts]
        label("合并入账", left, [add(bank, day + timedelta(days=1), sum(parts), ref, project, payer)])
    for i in range(8):
        day, amount = origin + timedelta(days=i + 2), (28000 + 131 * i) * 100
        ref, project, payer = f"SP{i:04d}", f"拆分项目{i:02d}", f"拆分付款方{i:02d}"
        left = add(ledger, day, amount, ref, project, payer)
        right = [add(bank, day, amount // 2, ref, project, payer),
                 add(bank, day + timedelta(days=1), amount - amount // 2, ref, project, payer)]
        label("拆分到账", [left], right)
    for i in range(12):
        day = date(2026, 6, 30)
        amount = (19000 + 79 * i) * 100
        ref, project, payer = f"TM{i:04d}", f"期后项目{i:02d}", f"期后付款方{i:02d}"
        left = add(ledger, day, amount, ref, project, payer)
        right = add(bank, day + timedelta(days=1 + i % 5), amount, ref, project, payer)
        label("期后到账", [left], [right])
    for i in range(20):
        day, amount = origin + timedelta(days=15), (12000 + i % 4 * 500) * 100
        project, payer = f"编号缺失项目{i:02d}", f"编号缺失付款方{i:02d}"
        left = add(ledger, day, amount, f"ID{i:04d}", project, payer)
        label("身份补充", [left], [add(bank, day + timedelta(days=2), amount, "", project, payer)])
    for i in range(10):
        day, amount = origin + timedelta(days=20), (20000 + i * 1000) * 100
        project, payer = f"同额项目{i:02d}", f"同额付款方{i:02d}"
        left = [add(ledger, day, amount, "", project, payer) for _ in range(2)]
        right = [add(bank, day, amount, "", project, payer) for _ in range(2)]
        rng.shuffle(right)
        for a, b in zip(left, right):
            label("同日同额歧义", [a], [b])
    for i in range(8):
        add(ledger, origin + timedelta(days=25), (16000 + i * 400) * 100,
            f"UL{i:03d}", f"待收项目{i:02d}", f"待收付款方{i:02d}")
    for i in range(6):
        add(bank, origin + timedelta(days=27), -(50 + i * 10) * 100,
            f"FEE{i:03d}", "", "银行费用")
    for i in range(4):
        args = (origin + timedelta(days=24), (17000 + i * 1000) * 100,
                f"DIFF{i:03d}", f"金额差异项目{i:02d}", f"金额差异付款方{i:02d}")
        add(ledger, *args)
        add(bank, args[0], args[1] - 5000, *args[2:])
    args = (origin + timedelta(days=23), 1850000, "DUP01", "重复样例项目", "重复样例付款方")
    add(ledger, *args)
    add(bank, *args)
    bank.append(dict(bank[-1]))
    for field, value in (("date", "2026-06-31"), ("amount", "123.456"), ("currency", "")):
        add(bank, origin + timedelta(days=22), 99900, "", "数据质量样例", "样例付款方")
        bank[-1][field] = value
    for side in (ledger, bank):
        rng.shuffle(side)
    write_csv(folder / "ledger.csv", ledger, FIELDS)
    write_csv(folder / "bank.csv", bank, FIELDS)
    write_csv(folder / "truth.csv", truth)
    counts = {}
    for row in truth:
        counts[row["scenario"]] = counts.get(row["scenario"], 0) + 1
    for name, count in counts.items():
        scenarios.append({"scenario": name, "true_groups": count})
    write_csv(folder / "scenario_counts.csv", scenarios)
