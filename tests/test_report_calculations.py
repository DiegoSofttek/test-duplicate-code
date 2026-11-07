"""Unit tests for the financial report calculations (subtask-3-1, User Story #3).

Covers the 16% tax and tiered 2%/5% discount behavior shared by the sales and
expenses reports, the removal of the local get_connection in report_expenses,
and preservation of the disconnected-DB and logging behavior.

Run from the repository root:
    python -m unittest tests.test_report_calculations -v
"""
import inspect
import os
import re
import sys
import unittest
from unittest import mock

_SRC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import database  # noqa: E402
import report_expenses  # noqa: E402
import report_sales  # noqa: E402


SUMMARY_RE = re.compile(r"^Reporte Generado: (\d+) transacciones, Total: \$(-?[\d.]+)$")


def parse_summary(summary):
    match = SUMMARY_RE.match(summary)
    if match is None:
        raise AssertionError(f"Unexpected summary format: {summary!r}")
    return int(match.group(1)), float(match.group(2))


def expected_net(amount):
    """Reference math from the spec: 16% tax, then strict-tier discount on subtotal."""
    tax = amount * 0.16
    subtotal = amount - tax
    if subtotal > 1000:
        discount = subtotal * 0.05
    elif subtotal > 500:
        discount = subtotal * 0.02
    else:
        discount = 0
    return subtotal - discount


class _ReportTestMixin:
    """Runs the same assertions against both report modules."""

    module = None  # set by subclasses
    module_name = None  # log module label

    def run_report(self, records, get_conn_status="connected"):
        with mock.patch.object(self.module, "fetch_data", return_value=records), \
                mock.patch.object(self.module, "get_connection",
                                  return_value={"status": get_conn_status}), \
                mock.patch.object(self.module, "log_activity"):
            return self.generate()


class SalesReportCalculationTests(_ReportTestMixin, unittest.TestCase):
    """UT-subtask-3-1-US-3-AC-1 (sales report)."""

    module = report_sales

    def generate(self):
        return report_sales.generate_sales_report()

    def test_tax_and_5_percent_discount_above_subtotal_1000(self):
        # RC-3-1-01: amount 1500 -> tax 240, subtotal 1260, discount 63, net 1197
        summary = self.run_report([{"id": 1, "amount": 1500, "status": "completed"}])
        count, total = parse_summary(summary)
        self.assertEqual(count, 1)
        self.assertAlmostEqual(total, 1197.0, places=6)

    def test_2_percent_discount_for_subtotal_in_500_to_1000(self):
        # RC-3-1-02: amount 800 -> tax 128, subtotal 672, discount 13.44, net 658.56
        summary = self.run_report([{"id": 3, "amount": 800, "status": "completed"}])
        count, total = parse_summary(summary)
        self.assertEqual(count, 1)
        self.assertAlmostEqual(total, 658.56, places=6)

    def test_discount_tier_boundaries_are_strict(self):
        # RC-3-1-03: exact subtotal 1000/500 needs non-representable amounts, so
        # check values just on either side of each boundary.
        cases = [
            (1190, 0.02),  # subtotal 999.6 -> 2% tier
            (1191, 0.05),  # subtotal 1000.44 -> 5% tier
            (595, 0.0),    # subtotal 499.8 -> no discount
            (596, 0.02),   # subtotal 500.64 -> 2% tier
        ]
        for amount, rate in cases:
            with self.subTest(amount=amount, rate=rate):
                summary = self.run_report([{"id": 1, "amount": amount, "status": "completed"}])
                _, total = parse_summary(summary)
                subtotal = amount * 0.84
                self.assertAlmostEqual(total, subtotal * (1 - rate), places=6)

    def test_non_completed_records_are_excluded(self):
        # RC-3-1-04
        records = [
            {"id": 1, "amount": 1500, "status": "completed"},
            {"id": 2, "amount": 3200, "status": "pending"},
            {"id": 3, "amount": 800, "status": "cancelled"},
        ]
        count, total = parse_summary(self.run_report(records))
        self.assertEqual(count, 1)
        self.assertAlmostEqual(total, 1197.0, places=6)

    def test_missing_amount_defaults_to_zero(self):
        # RC-3-1-05
        count, total = parse_summary(
            self.run_report([{"id": 9, "status": "completed"}])
        )
        self.assertEqual(count, 1)
        self.assertEqual(total, 0)

    def test_empty_dataset_summary(self):
        # RC-3-1-06
        self.assertEqual(
            self.run_report([]),
            "Reporte Generado: 0 transacciones, Total: $0",
        )

    def test_logs_start_and_finish_messages(self):
        # RC-3-1-11
        records = [{"id": 1, "amount": 1500, "status": "completed"}]
        with mock.patch.object(report_sales, "fetch_data", return_value=records), \
                mock.patch.object(report_sales, "get_connection",
                                  return_value={"status": "connected"}), \
                mock.patch.object(report_sales, "log_activity") as log_mock:
            report_sales.generate_sales_report()
        log_mock.assert_any_call("ReportSales", "Iniciando generación de reporte de ventas")
        log_mock.assert_any_call("ReportSales", "Reporte finalizado exitosamente")

    def test_disconnected_database_raises_and_skips_fetch(self):
        # RC-3-1-10 (sales side)
        with mock.patch.object(report_sales, "get_connection",
                               return_value={"status": "down"}), \
                mock.patch.object(report_sales, "fetch_data") as fetch_mock, \
                mock.patch.object(report_sales, "log_activity"):
            with self.assertRaises(Exception) as ctx:
                report_sales.generate_sales_report()
        self.assertEqual(str(ctx.exception), "No hay conexión a la base de datos")
        fetch_mock.assert_not_called()


class ExpensesReportCalculationTests(_ReportTestMixin, unittest.TestCase):
    """UT-subtask-3-1-US-3-AC-1 (expenses report)."""

    module = report_expenses

    def generate(self):
        return report_expenses.generate_expenses_report()

    def test_tax_and_5_percent_discount_above_subtotal_1000(self):
        # RC-3-1-01
        summary = self.run_report([{"id": 1, "amount": 1500, "status": "completed"}])
        count, total = parse_summary(summary)
        self.assertEqual(count, 1)
        self.assertAlmostEqual(total, 1197.0, places=6)

    def test_2_percent_discount_for_subtotal_in_500_to_1000(self):
        # RC-3-1-02
        summary = self.run_report([{"id": 3, "amount": 800, "status": "completed"}])
        _, total = parse_summary(summary)
        self.assertAlmostEqual(total, 658.56, places=6)

    def test_discount_tier_boundaries_are_strict(self):
        # RC-3-1-03
        cases = [(1190, 0.02), (1191, 0.05), (595, 0.0), (596, 0.02)]
        for amount, rate in cases:
            with self.subTest(amount=amount, rate=rate):
                summary = self.run_report([{"id": 1, "amount": amount, "status": "completed"}])
                _, total = parse_summary(summary)
                self.assertAlmostEqual(total, (amount * 0.84) * (1 - rate), places=6)

    def test_non_completed_records_are_excluded(self):
        # RC-3-1-04
        records = [
            {"id": 1, "amount": 1500, "status": "completed"},
            {"id": 2, "amount": 3200, "status": "pending"},
        ]
        count, total = parse_summary(self.run_report(records))
        self.assertEqual(count, 1)
        self.assertAlmostEqual(total, 1197.0, places=6)

    def test_missing_amount_defaults_to_zero(self):
        # RC-3-1-05
        count, total = parse_summary(
            self.run_report([{"id": 9, "status": "completed"}])
        )
        self.assertEqual(count, 1)
        self.assertEqual(total, 0)

    def test_empty_dataset_summary(self):
        # RC-3-1-06
        self.assertEqual(
            self.run_report([]),
            "Reporte Generado: 0 transacciones, Total: $0",
        )

    def test_logs_start_and_finish_messages(self):
        # RC-3-1-11
        records = [{"id": 1, "amount": 1500, "status": "completed"}]
        with mock.patch.object(report_expenses, "fetch_data", return_value=records), \
                mock.patch.object(report_expenses, "get_connection",
                                  return_value={"status": "connected"}), \
                mock.patch.object(report_expenses, "log_activity") as log_mock:
            report_expenses.generate_expenses_report()
        log_mock.assert_any_call("ReportExpenses", "Iniciando generación de reporte de gastos")
        log_mock.assert_any_call("ReportExpenses", "Reporte finalizado exitosamente")

    def test_disconnected_database_raises_and_skips_fetch(self):
        # RC-3-1-10 (expenses side)
        with mock.patch.object(report_expenses, "get_connection",
                               return_value={"status": "down"}), \
                mock.patch.object(report_expenses, "fetch_data") as fetch_mock, \
                mock.patch.object(report_expenses, "log_activity"):
            with self.assertRaises(Exception) as ctx:
                report_expenses.generate_expenses_report()
        self.assertEqual(str(ctx.exception), "No hay conexión a la base de datos")
        fetch_mock.assert_not_called()


class ReportConsistencyTests(unittest.TestCase):
    """UT-subtask-3-1-US-3-AC-1 (cross-report consistency) and AC-2 (shared connection)."""

    RECORDS = [
        {"id": 1, "amount": 1500, "status": "completed"},
        {"id": 2, "amount": 3200, "status": "pending"},
        {"id": 3, "amount": 800, "status": "completed"},
        {"id": 4, "amount": 1191, "status": "completed"},
        {"id": 5, "status": "completed"},
    ]

    def test_sales_and_expenses_produce_identical_summaries(self):
        # RC-3-1-07
        with mock.patch.object(report_sales, "fetch_data", return_value=self.RECORDS), \
                mock.patch.object(report_sales, "get_connection",
                                  return_value={"status": "connected"}), \
                mock.patch.object(report_sales, "log_activity"):
            sales_summary = report_sales.generate_sales_report()
        with mock.patch.object(report_expenses, "fetch_data", return_value=self.RECORDS), \
                mock.patch.object(report_expenses, "get_connection",
                                  return_value={"status": "connected"}), \
                mock.patch.object(report_expenses, "log_activity"):
            expenses_summary = report_expenses.generate_expenses_report()
        self.assertEqual(sales_summary, expenses_summary)

    def test_expenses_report_uses_shared_database_get_connection(self):
        # RC-3-1-09 (AC-2): identity with the shared module function
        self.assertIs(report_expenses.get_connection, database.get_connection)

    def test_expenses_report_does_not_define_get_connection_locally(self):
        # RC-3-1-09 (AC-2): no local definition in report_expenses.py
        source = inspect.getsource(report_expenses)
        self.assertNotRegex(
            source,
            re.compile(r"^def get_connection\(", re.MULTILINE),
            msg="local get_connection still defined",
        )

    def test_sample_dataset_end_to_end(self):
        # RC-3-1-12: database.fetch_data sample -> 2 completed records (1500, 800)
        with mock.patch.object(report_sales, "log_activity"), \
                mock.patch.object(report_sales, "get_connection",
                                  return_value={"status": "connected"}), \
                mock.patch("builtins.print"):
            summary = report_sales.generate_sales_report()
        count, total = parse_summary(summary)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(total, 1855.56, places=2)


if __name__ == "__main__":
    unittest.main()
