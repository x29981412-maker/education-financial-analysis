from __future__ import annotations

import csv
import random
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from receipts.data import FIELDS, InputData, Record, cents, parse_date, read_records, write_csv
from receipts.experiment import run_experiment
from receipts.matching import Policy, check_partition, reconcile


START, END = date(2026, 6, 1), date(2026, 6, 30)


def record(i, amount="100.00", day="2026-06-15", ref="R1", project="P1", payer="C1", currency="CNY", source="ledger"):
    return Record(i, date.fromisoformat(day), cents(amount), currency, ref, project, payer, source, 2)


def run(left, right, name="cautious", window=5):
    return reconcile(InputData(left, [], len(left), ""), InputData(right, [], len(right), ""),
                     START, END, Policy(name, window))


class InputTests(unittest.TestCase):
    def test_date_contract(self):
        self.assertEqual(parse_date("2024-02-29"), date(2024, 2, 29))
        for value in ("20260601", "2026-06-31", "2026-6-1", "2026-W23-1"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "日期无效"):
                parse_date(value)

    def test_money_is_exact(self):
        self.assertEqual(cents("1.01") + cents("2.02"), 303)
        self.assertEqual(cents("-8.50"), -850)

    def test_invalid_money_is_not_rounded(self):
        for value in ("0", "NaN", "Infinity", "1.001", "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cents(value)

    def test_all_duplicate_ids_are_quarantined(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.csv"
            row = dict(zip(FIELDS, ("L1", "2026-06-10", "100.00", "CNY", "R1", "P1", "C1")))
            write_csv(path, [row, row], FIELDS)
            data = read_records(path, "ledger")
            self.assertEqual(len(data.records), 0)
            self.assertEqual([i.row for i in data.issues], [2, 3])

    def test_missing_columns_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.csv"
            path.write_text("record_id,date\nL1,2026-06-01\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "缺少字段"):
                read_records(path, "ledger")


class MatchingTests(unittest.TestCase):
    def test_exact_match(self):
        result = run([record("L1")], [record("B1", source="bank")])
        self.assertEqual(result.matches[0].method, "reference")

    def test_conflicting_identity_is_not_overridden_by_reference(self):
        result = run([record("L1")], [record("B1", payer="OTHER", source="bank")])
        self.assertFalse(result.matches)

    def test_amount_variance_remains_visible(self):
        result = run([record("L1")], [record("B1", amount="99.99", source="bank")])
        self.assertFalse(result.matches)
        self.assertIn("不一致", result.review[0]["reason"])

    def test_missing_reference_can_use_unique_identity(self):
        result = run([record("L1")], [record("B1", ref="", source="bank")])
        self.assertEqual(result.matches[0].method, "identity")

    def test_two_nonempty_conflicting_references_do_not_fall_back(self):
        result = run([record("L1")], [record("B1", ref="R2", source="bank")])
        self.assertFalse(result.matches)

    def test_same_amount_distinct_payers_are_separated(self):
        result = run([record("L1", ref="", payer="A"), record("L2", ref="", payer="B")],
                     [record("B1", ref="", payer="B", source="bank"), record("B2", ref="", payer="A", source="bank")])
        self.assertEqual({(m.ledger, m.bank) for m in result.matches},
                         {(("L1",), ("B2",)), (("L2",), ("B1",))})

    def test_ambiguous_pairs_stay_unmatched(self):
        result = run([record("L1", ref=""), record("L2", ref="")],
                     [record("B1", ref="", source="bank"), record("B2", ref="", source="bank")])
        self.assertFalse(result.matches)
        self.assertEqual(len(result.review), 2)

    def test_grouped_receipt(self):
        result = run([record("L1", "40"), record("L2", "60")], [record("B1", source="bank")])
        self.assertEqual(result.matches[0].ledger, ("L1", "L2"))

    def test_split_bank_receipt(self):
        result = run([record("L1")], [record("B1", "40", source="bank"), record("B2", "60", source="bank")])
        self.assertEqual(result.matches[0].bank, ("B1", "B2"))

    def test_groups_require_common_business_scope(self):
        result = run([record("L1", "40", project="P1"), record("L2", "60", project="P2")],
                     [record("B1", source="bank")])
        self.assertFalse(result.matches)

    def test_overlapping_groups_are_not_chosen_arbitrarily(self):
        result = run([record("L1", "40"), record("L2", "60"), record("L3", "60")],
                     [record("B1", source="bank")])
        self.assertFalse(result.matches)

    def test_refunds_keep_direction(self):
        result = run([record("L1", "-100")], [record("B1", "100", source="bank")])
        self.assertFalse(result.matches)

    def test_currency_is_not_implicitly_converted(self):
        result = run([record("L1")], [record("B1", currency="USD", source="bank")])
        self.assertFalse(result.matches)
        self.assertEqual(len(result.controls), 2)

    def test_subsequent_receipt_does_not_change_current_bank_total(self):
        result = run([record("L1", day="2026-06-30")],
                     [record("B1", day="2026-07-02", source="bank")])
        self.assertEqual(len(result.matches), 1)
        self.assertEqual(result.controls[0]["bank_current"], 0)
        self.assertEqual(result.controls[0]["subsequent_settlement"], 10000)
        self.assertEqual(result.controls[0]["control_residual"], 0)

    def test_date_window_is_inclusive(self):
        self.assertEqual(len(run([record("L1", day="2026-06-30")],
                                 [record("B1", day="2026-07-05", source="bank")]).matches), 1)
        self.assertFalse(run([record("L1", day="2026-06-30")],
                             [record("B1", day="2026-07-06", source="bank")]).matches)

    def test_order_does_not_change_pairing(self):
        left = [record("L1", ref=""), record("L2", ref="", payer="C2")]
        right = [record("B1", ref="", source="bank"), record("B2", ref="", payer="C2", source="bank")]
        first, second = run(left, right), run(list(reversed(left)), list(reversed(right)))
        self.assertEqual(first.matches, second.matches)

    def test_empty_input(self):
        result = run([], [])
        self.assertEqual(result.matches, [])
        self.assertEqual(result.controls, [])

    def test_invalid_policy_parameters_fail(self):
        for args in (("unknown", 5, 4), ("cautious", -1, 4), ("cautious", 5, 9)):
            with self.assertRaises(ValueError):
                Policy(*args)

    def test_groups_do_not_net_receipts_and_refunds(self):
        result = run([record("L1", "100"), record("L2", "-40")],
                     [record("B1", "60", source="bank")])
        self.assertFalse(result.matches)

    def test_group_limit_leaves_large_buckets_for_review(self):
        result = run([record(f"L{i}", "10") for i in range(13)],
                     [record("B1", "130", source="bank")])
        self.assertFalse(result.matches)
        self.assertEqual(len(result.review), 13)

    def test_invalid_period_fails(self):
        with self.assertRaises(ValueError):
            reconcile(InputData([], [], 0, ""), InputData([], [], 0, ""), END, START)

    def test_outside_period_is_not_in_totals(self):
        result = run([record("L1", day="2026-05-31")],
                     [record("B1", day="2026-05-31", source="bank")])
        self.assertFalse(result.controls)
        self.assertEqual(len(result.out_of_scope), 2)


class ExperimentTests(unittest.TestCase):
    def test_repeat_run_preserves_generated_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run_experiment(root)
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            run_experiment(root)
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_empty_check_keeps_output_headers(self):
        from receipts.cli import main
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            write_csv(root / "ledger.csv", [], FIELDS)
            write_csv(root / "bank.csv", [], FIELDS)
            output = root / "output"
            main(["check", "--ledger", str(root / "ledger.csv"), "--bank", str(root / "bank.csv"),
                  "--output", str(output), "--start", "2026-06-01", "--cutoff", "2026-06-30"])
            with (output / "row_trace.csv").open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                self.assertIn("record_id", reader.fieldnames)
                self.assertEqual(list(reader), [])

    def test_seeded_experiment_and_source_accounting(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = run_experiment(root)
            rows = {row["policy"]: row for row in manifest["policies"]}
            self.assertEqual(rows["cautious"]["wrong_groups"], 0)
            self.assertGreater(rows["cautious"]["matched_groups"], rows["reference"]["matched_groups"])
            self.assertGreater(rows["amount_date"]["wrong_groups"], 0)
            self.assertEqual(manifest["bank"]["raw_rows"] - manifest["bank"]["valid_rows"], manifest["excluded_rows"])
            with (root / "results" / "cautious" / "row_trace.csv").open(encoding="utf-8-sig", newline="") as f:
                trace = list(csv.DictReader(f))
            self.assertEqual(len(trace), manifest["ledger"]["valid_rows"] + manifest["bank"]["valid_rows"])

    def test_multiple_seeds_preserve_constraints(self):
        from receipts.simulation import generate
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            for seed in (3, 17, 29, 71, 103):
                generate(path, seed)
                left, right = read_records(path / "ledger.csv", "ledger"), read_records(path / "bank.csv", "bank")
                for policy in ("reference", "cautious", "amount_date"):
                    with self.subTest(seed=seed, policy=policy):
                        check_partition(reconcile(left, right, START, END, Policy(policy)))


if __name__ == "__main__":
    unittest.main()
