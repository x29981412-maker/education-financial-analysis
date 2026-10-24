"""输入保留原始行号；金额在读取时转换为整数分。"""

from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


FIELDS = ("record_id", "date", "amount", "currency", "reference", "project_id", "counterparty")


def text(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).casefold().split())


def cents(value: str) -> int:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("金额无法解析") from exc
    if not number.is_finite() or number == 0:
        raise ValueError("金额必须为非零有限数")
    if number != number.quantize(Decimal("0.01")):
        raise ValueError("金额精度超过分，未自动四舍五入")
    return int(number * 100)


def money(value: int) -> str:
    return f"{Decimal(value) / 100:.2f}"


def parse_date(value: str) -> date:
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("日期无效，须为YYYY-MM-DD且日期存在") from exc


@dataclass(frozen=True)
class Record:
    record_id: str
    date: date
    amount: int
    currency: str
    reference: str
    project_id: str
    counterparty: str
    source: str
    row: int


@dataclass(frozen=True)
class Issue:
    source: str
    row: int
    record_id: str
    reason: str
    raw_amount: str


@dataclass
class InputData:
    records: list[Record]
    issues: list[Issue]
    raw_rows: int
    sha256: str


def read_records(path: Path, source: str) -> InputData:
    raw = path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = set(FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path.name} 缺少字段：{', '.join(sorted(missing))}")
        rows = list(reader)
    ids = Counter((r.get("record_id") or "").strip() for r in rows)
    records, issues = [], []
    for row_number, raw_row in enumerate(rows, 2):
        values = {key: (raw_row.get(key) or "").strip() for key in FIELDS}
        record_id = values["record_id"]
        try:
            if not record_id:
                raise ValueError("记录编号为空")
            if ids[record_id] > 1:
                raise ValueError("记录编号重复，相关行全部隔离")
            currency = values["currency"].upper()
            if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
                raise ValueError("币种须为三个英文字母")
            records.append(Record(record_id, parse_date(values["date"]),
                                  cents(values["amount"]), currency,
                                  text(values["reference"]), text(values["project_id"]),
                                  text(values["counterparty"]), source, row_number))
        except (ValueError, InvalidOperation) as exc:
            issues.append(Issue(source, row_number, record_id, str(exc), values["amount"]))
    return InputData(sorted(records, key=lambda r: r.record_id), issues, len(rows),
                     hashlib.sha256(raw).hexdigest())


def write_csv(path: Path, rows: list[dict], fields: list[str] | tuple[str, ...] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = fields or (list(rows[0]) if rows else [])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
