"""Unit tests for the report calculation consolidation (subtask-3-1, US#3).

Covers UT-subtask-3-1-01 .. UT-subtask-3-1-16 against src/report_sales.py,
src/report_expenses.py and src/main_dashboard.py.

The tests exercise the public report functions and mock the database and
logging collaborators, so they do not depend on the internal loop or on the
name of the shared helper (which is not yet defined). Expected values are
computed from the business rule: 16% tax, then 5% discount when the subtotal
is > 1000, 2% when it is > 500 and <= 1000, otherwise 0%.
"""
import contextlib
import io
import os
import re
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
for path in (REPO_ROOT, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

import database  # noqa: E402
import report_expenses  # noqa: E402
import report_sales  # noqa: E402
import main_dashboard  # noqa: E402

SALES_MODULE = "report_sales"
EXPENSES_MODULE = "report_expenses"

FIXTURE = [
    {"id": 1, "amount": 1500, "status": "completed"},
    {"id": 2, "amount": 3200, "status": "pending"},
    {"id": 3, "amount": 800, "status": "completed"},
]

SUMMARY_RE = re.compile(
    r"^Reporte Generado: (\d+) transacciones, Total: \$(-?[\d.]+)$"
)


def expected_net(amount):
    """Reference oracle for the business rule (test-local, not production code)."""
    impuesto = amount * 0.16
    subtotal = amount - impuesto
    if subtotal > 1000:
        descuento = subtotal * 0.05
    elif subtotal > 500:
        descuento = subtotal * 0.02
    else:
        descuento = 0
    return subtotal - descuento


def parse_summary(summary):
    match = SUMMARY_RE.match(summary)
    if match is None:
        raise AssertionError(f"Unexpected summary format: {summary!r}")
    return int(match.group(1)), float(match.group(2))


class ReportTestBase(unittest.TestCase):
    def setUp(self):
        self._patches = []
        self.log_mock = self._start(mock.patch("logger.log_activity"))
        # Reports import log_activity by name; patch their namespaces too.
        self._start(mock.patch.object(report_sales, "log_activity"))
        self._start(mock.patch.object(report_expenses, "log_activity"))

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()

    def _start(self, patcher):
        m = patcher.start()
        self._patches.append(patcher)
        return m

    def _connected(self, module_name):
        return self._start(
            mock.patch.object(
                sys.modules[module_name],
                "get_connection",
                return_value={"status": "connected", "db_name": "finanzas_prod"},
            )
        )

    def _fetch(self, module_name, records):
        return self._start(
            mock.patch.object(
                sys.modules[module_name], "fetch_data", return_value=records
            )
        )


class SharedCalculationTests(ReportTestBase):
    """Tax and tiered discount behavior, observed through the sales report."""

    def _net_for(self, amount):
        self._connected(SALES_MODULE)
        self._fetch(SALES_MODULE, [{"id": 1, "amount": amount, "status": "completed"}])
        _, total = parse_summary(report_sales.generate_sales_report())
        return total

    def test_01_applies_16_percent_tax_and_subtotal(self):
        # UT-subtask-3-1-01 | US#3 AC-1
        amount = 300
        # 16% tax -> subtotal 252, no discount tier applies -> net 252.
        self.assertAlmostEqual(self._net_for(amount), amount * 0.84, places=6)

    def test_02_five_percent_discount_above_1000_subtotal(self):
        # UT-subtask-3-1-02 | US#3 AC-1
        # amount 1500 -> tax 240, subtotal 1260, discount 63, net 1197
        self.assertAlmostEqual(self._net_for(1500), 1197.0, places=6)
        self.assertAlmostEqual(self._net_for(1500), expected_net(1500), places=6)

    def test_03_two_percent_discount_in_500_to_1000_range(self):
        # UT-subtask-3-1-03 | US#3 AC-1
        # amount 800 -> tax 128, subtotal 672, discount 13.44, net 658.56
        self.assertAlmostEqual(self._net_for(800), 658.56, places=6)
        self.assertAlmostEqual(self._net_for(800), expected_net(800), places=6)

    def test_04_no_discount_at_or_below_500_subtotal(self):
        # UT-subtask-3-1-04 | US#3 AC-1
        # amount 300 -> subtotal 252 (<= 500) -> net equals subtotal
        self.assertAlmostEqual(self._net_for(300), 252.0, places=6)

    def test_05_subtotal_at_1000_boundary_uses_2_percent_tier(self):
        # UT-subtask-3-1-05 | US#3 AC-1
        # amount 1190 -> subtotal 999.6 (just under 1000) -> 2% tier.
        # amount 1191 -> subtotal 1000.44 (just over 1000) -> 5% tier.
        self.assertAlmostEqual(self._net_for(1190), expected_net(1190), places=6)
        self.assertAlmostEqual(self._net_for(1190), 999.6 * 0.98, places=6)
        self.assertAlmostEqual(self._net_for(1191), 1000.44 * 0.95, places=6)

    def test_06_subtotal_at_500_boundary_yields_no_discount(self):
        # UT-subtask-3-1-06 | US#3 AC-1
        # amount 595 -> subtotal 499.8 (<= 500) -> no discount.
        # amount 596 -> subtotal 500.64 (> 500) -> 2% tier.
        self.assertAlmostEqual(self._net_for(595), 499.8, places=6)
        self.assertAlmostEqual(self._net_for(596), 500.64 * 0.98, places=6)

    def test_07_non_completed_records_are_excluded(self):
        # UT-subtask-3-1-07 | US#3 AC-1
        self._connected(SALES_MODULE)
        self._fetch(SALES_MODULE, FIXTURE)
        count, total = parse_summary(report_sales.generate_sales_report())
        self.assertEqual(count, 2)
        # Pending record id 2 (amount 3200) must not contribute to the total.
        self.assertAlmostEqual(total, 1197.0 + 658.56, places=2)

    def test_08_missing_amount_defaults_to_zero(self):
        # UT-subtask-3-1-08 | US#3 AC-1
        self._connected(SALES_MODULE)
        self._fetch(SALES_MODULE, [{"id": 9, "status": "completed"}])
        count, total = parse_summary(report_sales.generate_sales_report())
        self.assertEqual(count, 1)
        self.assertAlmostEqual(total, 0.0, places=6)

    @unittest.skip(
        "UT-subtask-3-1-09: per-transaction metricas are built locally and not "
        "returned; enable once the shared helper exposes them."
    )
    def test_09_per_transaction_metrics_preserved(self):
        # UT-subtask-3-1-09 | US#3 AC-1
        pass


class SalesReportTests(ReportTestBase):
    def test_10_sales_report_summary_for_fixture(self):
        # UT-subtask-3-1-10 | US#3 AC-1
        self._connected(SALES_MODULE)
        fetch = self._fetch(SALES_MODULE, FIXTURE)
        summary = report_sales.generate_sales_report()
        count, total = parse_summary(summary)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(total, 1855.56, places=2)
        fetch.assert_called_once()

    def test_12_empty_dataset_returns_zero_count_and_total(self):
        # UT-subtask-3-1-12 | US#3 AC-1
        self._connected(SALES_MODULE)
        self._fetch(SALES_MODULE, [])
        summary = report_sales.generate_sales_report()
        self.assertIn("0 transacciones", summary)
        self.assertIn("Total: $0", summary)

    def test_12b_all_pending_dataset_returns_zero_count_and_total(self):
        # UT-subtask-3-1-12 | US#3 AC-1
        self._connected(SALES_MODULE)
        self._fetch(SALES_MODULE, [{"id": 2, "amount": 3200, "status": "pending"}])
        summary = report_sales.generate_sales_report()
        self.assertIn("0 transacciones", summary)
        self.assertIn("Total: $0", summary)

    def test_13_non_connected_status_raises(self):
        # UT-subtask-3-1-13 | US#3 AC-1
        self._start(
            mock.patch.object(
                report_sales, "get_connection", return_value={"status": "down"}
            )
        )
        fetch = self._fetch(SALES_MODULE, FIXTURE)
        with self.assertRaises(Exception) as ctx:
            report_sales.generate_sales_report()
        self.assertEqual(str(ctx.exception), "No hay conexión a la base de datos")
        fetch.assert_not_called()


class ExpensesReportTests(ReportTestBase):
    def test_11_expenses_matches_sales_for_identical_input(self):
        # UT-subtask-3-1-11 | US#3 AC-1
        self._connected(SALES_MODULE)
        self._fetch(SALES_MODULE, FIXTURE)
        sales_summary = report_sales.generate_sales_report()

        self._connected(EXPENSES_MODULE)
        self._fetch(EXPENSES_MODULE, FIXTURE)
        expenses_summary = report_expenses.generate_expenses_report()

        self.assertEqual(parse_summary(expenses_summary), parse_summary(sales_summary))

    def test_12_expenses_empty_dataset_returns_zero(self):
        # UT-subtask-3-1-12 | US#3 AC-1
        self._connected(EXPENSES_MODULE)
        self._fetch(EXPENSES_MODULE, [])
        summary = report_expenses.generate_expenses_report()
        self.assertIn("0 transacciones", summary)
        self.assertIn("Total: $0", summary)

    def test_13_expenses_non_connected_status_raises(self):
        # UT-subtask-3-1-13 | US#3 AC-1
        self._start(
            mock.patch.object(
                report_expenses, "get_connection", return_value={"status": "down"}
            )
        )
        fetch = self._fetch(EXPENSES_MODULE, FIXTURE)
        with self.assertRaises(Exception) as ctx:
            report_expenses.generate_expenses_report()
        self.assertEqual(str(ctx.exception), "No hay conexión a la base de datos")
        fetch.assert_not_called()

    def test_14_no_local_get_connection_definition(self):
        # UT-subtask-3-1-14 | US#3 AC-2
        self.assertIs(report_expenses.get_connection, database.get_connection)

    def test_15_expenses_report_fetches_connection_from_shared_module(self):
        # UT-subtask-3-1-15 | US#3 AC-2
        conn = self._connected(EXPENSES_MODULE)
        self._fetch(EXPENSES_MODULE, FIXTURE)
        report_expenses.generate_expenses_report()
        conn.assert_called_once_with()


class DashboardTests(ReportTestBase):
    def test_16_dashboard_runs_both_reports_and_prints_summaries(self):
        # UT-subtask-3-1-16 | US#3 AC-1, AC-2
        self._connected(SALES_MODULE)
        self._connected(EXPENSES_MODULE)
        self._fetch(SALES_MODULE, FIXTURE)
        self._fetch(EXPENSES_MODULE, FIXTURE)

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            main_dashboard.run_dashboard()
        output = buffer.getvalue()

        ventas = re.search(r"^Ventas: (.+)$", output, re.MULTILINE)
        gastos = re.search(r"^Gastos: (.+)$", output, re.MULTILINE)
        self.assertIsNotNone(ventas)
        self.assertIsNotNone(gastos)
        ventas_count, ventas_total = parse_summary(ventas.group(1))
        self.assertEqual(ventas_count, 2)
        self.assertAlmostEqual(ventas_total, 1855.56, places=2)
        gastos_count, gastos_total = parse_summary(gastos.group(1))
        self.assertEqual(gastos_count, 2)
        self.assertAlmostEqual(gastos_total, 1855.56, places=2)


if __name__ == "__main__":
    unittest.main()
