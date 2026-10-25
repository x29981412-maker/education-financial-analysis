import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import calculate, divide, load_data


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.data, self.rows = load_data()

    def test_selected_data_and_identities(self):
        _, checks, _ = calculate(self.data)
        self.assertEqual(sum(v is not None for m in self.data.values() for v in m.values()), 76)
        self.assertEqual(len(checks), 22)
        self.assertTrue(all(r["difference_usd_thousands"] == 0 for r in checks))

    def test_omitting_fx_is_detected(self):
        self.data["fx_effect"][2025] = Decimal(0)
        _, checks, _ = calculate(self.data)
        row = next(r for r in checks if r["year"] == 2025 and r["check"] == "现金流组成与汇率影响")
        self.assertEqual(row["difference_usd_thousands"], Decimal(-9836))
        self.assertEqual(row["status"], "待核实")

    def test_restricted_cash_cannot_be_omitted(self):
        self.data["restricted_noncurrent"][2025] = Decimal(0)
        _, checks, _ = calculate(self.data)
        row = next(r for r in checks if r["year"] == 2025 and r["check"] == "受限现金口径衔接")
        self.assertEqual(row["difference_usd_thousands"], Decimal(-24030))

    def test_missing_balance_is_not_zero(self):
        indicators, _, _ = calculate(self.data)
        self.assertIsNone(indicators[0]["current_ratio"])
        self.assertIsNone(divide(Decimal(1), Decimal(0)))

    def test_cashflow_bridge_and_profit_scope(self):
        indicators, _, bridge = calculate(self.data)
        self.assertEqual(sum(r["usd_thousands"] for r in bridge[:3]), Decimal(-226051))
        self.assertEqual(indicators[-1]["net_income_usd_million"], Decimal("375.833"))


if __name__ == "__main__":
    unittest.main()
