"""先处理可唯一确认的关系；金额相同但关系不明的记录保留待查。"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations

from .data import InputData, Record, money


@dataclass(frozen=True)
class Policy:
    name: str = "cautious"
    window: int = 5
    max_group: int = 4

    def __post_init__(self):
        if self.name not in {"reference", "cautious", "amount_date"}:
            raise ValueError("未知核对策略")
        if not 0 <= self.window <= 31 or not 2 <= self.max_group <= 6:
            raise ValueError("日期窗口或组合上限超出允许范围")


@dataclass(frozen=True)
class Match:
    ledger: tuple[str, ...]
    bank: tuple[str, ...]
    method: str


@dataclass
class Result:
    ledger: list[Record]
    bank: list[Record]
    matches: list[Match]
    review: list[dict]
    controls: list[dict]
    out_of_scope: list[Record]
    policy: Policy
    cutoff: date


def compatible(a: Record, b: Record, window: int) -> bool:
    return (a.currency == b.currency and a.amount * b.amount > 0
            and abs((a.date - b.date).days) <= window)


def identity(a: Record, b: Record) -> bool:
    return bool(a.project_id and a.counterparty and a.project_id == b.project_id
                and a.counterparty == b.counterparty)


def reference_agrees(a: Record, b: Record) -> bool:
    return bool(a.reference and a.reference == b.reference)


def identity_conflicts(a: Record, b: Record) -> bool:
    return bool((a.project_id and b.project_id and a.project_id != b.project_id)
                or (a.counterparty and b.counterparty and a.counterparty != b.counterparty))


def reconcile(ledger: InputData, bank: InputData, start: date, cutoff: date,
              policy: Policy = Policy()) -> Result:
    if start > cutoff:
        raise ValueError("期间起点晚于截止日")
    ls = [r for r in ledger.records if start <= r.date <= cutoff]
    bs = [r for r in bank.records if start <= r.date <= cutoff + timedelta(days=policy.window)]
    out = [r for r in ledger.records if r not in ls] + [r for r in bank.records if r not in bs]
    remaining_l = {r.record_id: r for r in ls}
    remaining_b = {r.record_id: r for r in bs}
    matches = []

    def accept(candidates: list[Match]):
        # 相互冲突的候选整组留下，不按文件顺序抢占记录。
        counts_l = Counter(i for c in candidates for i in c.ledger)
        counts_b = Counter(i for c in candidates for i in c.bank)
        for match in sorted(candidates, key=lambda c: (c.ledger, c.bank)):
            if all(counts_l[i] == 1 for i in match.ledger) and all(counts_b[i] == 1 for i in match.bank):
                matches.append(match)
                for i in match.ledger:
                    del remaining_l[i]
                for i in match.bank:
                    del remaining_b[i]

    exact = [Match((a.record_id,), (b.record_id,), "reference")
             for a in remaining_l.values() for b in remaining_b.values()
             if compatible(a, b, policy.window) and a.amount == b.amount
             and reference_agrees(a, b) and not identity_conflicts(a, b)]
    accept(exact)

    if policy.name != "reference":
        # 组合只在共同业务编号、项目和付款方内搜索；上限约束搜索规模。
        groups_l, groups_b = defaultdict(list), defaultdict(list)
        for records, groups in ((remaining_l, groups_l), (remaining_b, groups_b)):
            for record in records.values():
                if record.reference and record.project_id and record.counterparty:
                    key = (record.currency, record.reference, record.project_id, record.counterparty)
                    groups[key].append(record)
        candidates = []
        for key in sorted(groups_l.keys() & groups_b.keys()):
            left, right = groups_l[key], groups_b[key]
            for many, singles, reverse in ((left, right, False), (right, left, True)):
                if len(many) > 12:
                    continue
                for single in singles:
                    pool = [r for r in many if compatible(r, single, policy.window)]
                    for size in range(2, min(policy.max_group, len(pool)) + 1):
                        for group in combinations(pool, size):
                            if sum(r.amount for r in group) == single.amount:
                                ids = tuple(sorted(r.record_id for r in group))
                                candidates.append(Match((single.record_id,) if reverse else ids,
                                                        ids if reverse else (single.record_id,), "group"))
        accept(candidates)

        if policy.name == "cautious":
            candidates = [Match((a.record_id,), (b.record_id,), "identity")
                          for a in remaining_l.values() for b in remaining_b.values()
                          if compatible(a, b, policy.window) and a.amount == b.amount
                          and identity(a, b)
                          and not (a.reference and b.reference and a.reference != b.reference)]
            accept(candidates)
        else:
            # 比较用基线：同金额候选中优先选日期最近者，不检查业务身份。
            pairs = sorted((abs((a.date - b.date).days), a.record_id, b.record_id)
                           for a in remaining_l.values() for b in remaining_b.values()
                           if compatible(a, b, policy.window) and a.amount == b.amount)
            for _, a, b in pairs:
                if a in remaining_l and b in remaining_b:
                    matches.append(Match((a,), (b,), "amount_date"))
                    del remaining_l[a]
                    del remaining_b[b]

    review = []
    for a in remaining_l.values():
        candidates = [b for b in remaining_b.values() if compatible(a, b, policy.window)
                      and (reference_agrees(a, b) or a.amount == b.amount)]
        reason = ("编号对应但金额或身份不一致" if any(reference_agrees(a, b) for b in candidates)
                  else "同金额候选尚不能唯一确认" if candidates else "未找到对应入账")
        review.append({"ledger_id": a.record_id, "ledger_row": a.row,
                       "currency": a.currency, "amount": money(a.amount), "reason": reason,
                       "bank_candidates": "|".join(b.record_id for b in candidates)})

    lm, bm = {r.record_id: r for r in ls}, {r.record_id: r for r in bs}
    controls = []
    for currency in sorted({r.currency for r in ls + bs}):
        ledger_total = sum(r.amount for r in ls if r.currency == currency)
        bank_total = sum(r.amount for r in bs if r.currency == currency and r.date <= cutoff)
        matched_difference = sum(
            sum(lm[i].amount for i in m.ledger)
            - sum(bm[i].amount for i in m.bank if bm[i].date <= cutoff)
            for m in matches if lm[m.ledger[0]].currency == currency)
        unmatched_l = sum(r.amount for r in remaining_l.values() if r.currency == currency)
        unmatched_b = sum(r.amount for r in remaining_b.values()
                          if r.currency == currency and r.date <= cutoff)
        residual = ledger_total - bank_total - matched_difference - unmatched_l + unmatched_b
        controls.append({"currency": currency, "ledger_current": ledger_total,
                         "bank_current": bank_total, "raw_difference": ledger_total - bank_total,
                         "subsequent_settlement": matched_difference,
                         "ledger_unmatched": unmatched_l, "bank_unmatched": unmatched_b,
                         "control_residual": residual})
    result = Result(ls, bs, sorted(matches, key=lambda m: (m.ledger, m.bank)), review,
                    controls, out, policy, cutoff)
    check_partition(result)
    return result


def check_partition(result: Result):
    used_l = [i for m in result.matches for i in m.ledger]
    used_b = [i for m in result.matches for i in m.bank]
    if len(used_l) != len(set(used_l)) or len(used_b) != len(set(used_b)):
        raise AssertionError("记录被重复匹配")
    lm, bm = {r.record_id: r for r in result.ledger}, {r.record_id: r for r in result.bank}
    for m in result.matches:
        records = [lm[i] for i in m.ledger] + [bm[i] for i in m.bank]
        if len({r.currency for r in records}) != 1:
            raise AssertionError("跨币种匹配")
        if sum(lm[i].amount for i in m.ledger) != sum(bm[i].amount for i in m.bank):
            raise AssertionError("匹配组金额不相等")
    if any(row["control_residual"] != 0 for row in result.controls):
        raise AssertionError("差异分解不守恒")
