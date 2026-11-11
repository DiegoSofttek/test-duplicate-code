"""
Unit tests for subtask-3-1: Extract report calculation logic.

Covers User Story #3 acceptance criteria:
  - AC-1: sales and expenses reports use a centralized tax/discount calculation.
  - AC-2: the expenses report uses the shared database.get_connection directly.

Run from the repository root with:
    python -m unittest discover -s src -p "test_report_subtask-3-1.py"
"""

import math
import re
import unittest
from unittest import mock

import database
import logger
import report_expenses
import report_sales


SALES_START = "Iniciando generación de reporte de ventas"
SALES_END = "Reporte finalizado exitosamente"
EXPENSES_START = "Iniciando generación de reporte de gastos"
EXPENSES_END = "Reporte finalizado exitosamente"

TOTAL_PATTERN = re.compile(r"^Reporte Generado: (\d+) transacciones, Total: \$(.+)$")


def _parse_summary(summary):
    match = TOTAL_PATTERN.match(summary)
    if match is None:
        raise AssertionError(f"Unexpected summary format: {summary!r}")
    return int(match.group(1)), float(match.group(2))


def _connected():
    return {"status": "connected", "db_name": "finanzas_prod"}


class _ReportTestBase(unittest.TestCase):
    """Patches fetch_data, get_connection and log_activity in both report modules."""

    def setUp(self):
        self.sales_fetch = mock.patch.object(report_sales, "fetch_data").start()
        self.sales_conn = mock.patch.object(report_sales, "get_connection").start()
        self.sales_log = mock.patch.object(report_sales, "log_activity").start()
        self.expenses_fetch = mock.patch.object(report_expenses, "fetch_data").start()
        self.expenses_conn = mock.patch.object(report_expenses, "get_connection").start()
        self.expenses_log = mock.patch.object(report_expenses, "log_activity").start()

        self.sales_conn.return_value = _connected()
        self.expenses_conn.return_value = _connected()
        self.sales_fetch.return_value = []
        self.expenses_fetch.return_value = []
        self.addCleanup(mock.patch.stopall)

    def _run_sales(self, records):
        self.sales_fetch.return_value = records
        return report_sales.generate_sales_report()

    def _run_expenses(self, records):
        self.expenses_fetch.return_value = records
        return report_expenses.generate_expenses_report()


class TestSalesSummaryCompletedRecords(_ReportTestBase):
    """TC-01 (AC-1)"""

    def test_TC_01_sales_summary_counts_only_completed_records_and_totals_net(self):
        records = [
            {"id": 1, "amount": 1500, "status": "completed"},
            {"id": 2, "amount": 3200, "status": "pending"},
            {"id": 3, "amount": 800, "status": "completed"},
        ]

        count, total = _parse_summary(self._run_sales(records))

        self.assertEqual(count, 2)
        self.assertAlmostEqual(total, 1855.56, places=2)


class TestExpensesMatchesSales(_ReportTestBase):
    """TC-02 (AC-1)"""

    def test_TC_02_expenses_summary_equals_sales_summary_for_same_input(self):
        records = [
            {"id": 1, "amount": 1500, "status": "completed"},
            {"id": 2, "amount": 3200, "status": "pending"},
            {"id": 3, "amount": 800, "status": "completed"},
        ]

        sales_summary = self._run_sales(records)
        expenses_summary = self._run_expenses(records)

        self.assertEqual(expenses_summary, sales_summary)


class TestDiscountTierBoundaries(_ReportTestBase):
    """TC-03 (AC-1)"""

    def _amount_for_subtotal(self, subtotal, strictly_above):
        # Find a float amount whose post-tax subtotal (amount - amount * 0.16,
        # the same arithmetic the report uses) lies on the required side of the
        # threshold: strictly above it when strictly_above is True, otherwise
        # at or below it. Exact equality is not always representable in float.
        amount = subtotal / 0.84
        for _ in range(200):
            current = amount - amount * 0.16
            if strictly_above:
                if current > subtotal:
                    return amount
                amount = math.nextafter(amount, math.inf)
            else:
                if current <= subtotal:
                    return amount
                amount = math.nextafter(amount, -math.inf)
        return subtotal / 0.84

    def _net_for_subtotal(self, subtotal, strictly_above=False):
        amount = self._amount_for_subtotal(subtotal, strictly_above)
        summary = self._run_sales([{"id": 1, "amount": amount, "status": "completed"}])
        _, total = _parse_summary(summary)
        return total

    def test_TC_03_subtotal_1001_gets_five_percent_discount(self):
        net = self._net_for_subtotal(1001, strictly_above=True)
        self.assertAlmostEqual(net, 1001 * 0.95, places=6)

    def test_TC_03_subtotal_1000_gets_two_percent_discount(self):
        net = self._net_for_subtotal(1000)
        self.assertAlmostEqual(net, 1000 * 0.98, places=6)

    def test_TC_03_subtotal_501_gets_two_percent_discount(self):
        net = self._net_for_subtotal(501, strictly_above=True)
        self.assertAlmostEqual(net, 501 * 0.98, places=6)

    def test_TC_03_subtotal_500_gets_no_discount(self):
        net = self._net_for_subtotal(500)
        self.assertAlmostEqual(net, 500, places=6)


class TestTaxAppliedBeforeDiscount(_ReportTestBase):
    """TC-04 (AC-1)"""

    def test_TC_04_tax_is_sixteen_percent_applied_before_two_percent_discount(self):
        summary = self._run_sales([{"id": 1, "amount": 1000, "status": "completed"}])

        count, total = _parse_summary(summary)

        self.assertEqual(count, 1)
        # tax = 160, subtotal = 840, discount = 16.8, net = 823.2
        self.assertAlmostEqual(total, 823.2, places=6)


class TestNonCompletedRecordsExcluded(_ReportTestBase):
    """TC-05 (AC-1)"""

    def test_TC_05_pending_and_other_statuses_do_not_change_count_or_total(self):
        completed_only = [{"id": 1, "amount": 1000, "status": "completed"}]
        mixed = completed_only + [
            {"id": 2, "amount": 5000, "status": "pending"},
            {"id": 3, "amount": 7000, "status": "cancelled"},
        ]

        expected = _parse_summary(self._run_sales(completed_only))
        actual = _parse_summary(self._run_sales(mixed))

        self.assertEqual(actual[0], expected[0])
        self.assertAlmostEqual(actual[1], expected[1], places=6)


class TestMissingAmountDefaultsToZero(_ReportTestBase):
    """TC-06 (AC-1)"""

    def test_TC_06_completed_record_without_amount_is_counted_with_zero_net(self):
        records = [
            {"id": 1, "amount": 1000, "status": "completed"},
            {"id": 2, "status": "completed"},
        ]
        baseline = _parse_summary(
            self._run_sales([{"id": 1, "amount": 1000, "status": "completed"}])
        )

        count, total = _parse_summary(self._run_sales(records))

        self.assertEqual(count, baseline[0] + 1)
        self.assertAlmostEqual(total, baseline[1], places=6)


class TestEmptyDataset(_ReportTestBase):
    """TC-07 (AC-1)"""

    def test_TC_07_empty_dataset_yields_zero_transactions_and_zero_total(self):
        summary = self._run_sales([])

        self.assertEqual(summary, "Reporte Generado: 0 transacciones, Total: $0")


class TestSharedHelperUsage(_ReportTestBase):
    """TC-08 (AC-1)

    The shared helper name is not defined in the repository yet. The test looks
    for a callable bound under the same name in both report modules that is not
    defined by the report modules, database, or logger. If none exists, the test
    is skipped explicitly.
    """

    def _find_shared_helper_names(self):
        excluded_modules = {"report_sales", "report_expenses", "database", "logger"}
        names = []
        for name, value in vars(report_sales).items():
            if name.startswith("_") or name not in vars(report_expenses):
                continue
            if vars(report_expenses)[name] is not value:
                continue
            if not callable(value) or isinstance(value, type):
                continue
            if getattr(value, "__module__", None) in excluded_modules:
                continue
            names.append(name)
        return names

    def test_TC_08_both_reports_call_shared_helper_once_per_run(self):
        helper_names = self._find_shared_helper_names()
        if not helper_names:
            self.skipTest(
                "Shared calculation helper is not defined in both report modules yet"
            )
        self.assertEqual(len(helper_names), 1, f"Ambiguous helpers: {helper_names}")
        helper_name = helper_names[0]

        records = [{"id": 1, "amount": 1500, "status": "completed"}]
        sales_helper = mock.patch.object(
            report_sales, helper_name, wraps=getattr(report_sales, helper_name)
        ).start()
        expenses_helper = mock.patch.object(
            report_expenses, helper_name, wraps=getattr(report_expenses, helper_name)
        ).start()

        self._run_sales(records)
        self._run_expenses(records)

        self.assertEqual(sales_helper.call_count, 1)
        self.assertEqual(expenses_helper.call_count, 1)


class TestExpensesSharedConnection(unittest.TestCase):
    """TC-09 (AC-2)"""

    def test_TC_09_expenses_module_uses_shared_database_get_connection(self):
        self.assertIs(report_expenses.get_connection, database.get_connection)

    def test_TC_09_get_connection_is_not_redefined_locally_in_expenses(self):
        local = vars(report_expenses).get("get_connection")
        self.assertIsNotNone(local)
        self.assertNotEqual(getattr(local, "__module__", None), "report_expenses")


class TestExpensesConnectionFailure(_ReportTestBase):
    """TC-10 (AC-2)"""

    def test_TC_10_expenses_raises_when_shared_connection_is_not_connected(self):
        self.expenses_conn.return_value = {"status": "down"}

        with self.assertRaises(Exception) as ctx:
            report_expenses.generate_expenses_report()

        self.assertEqual(str(ctx.exception), "No hay conexión a la base de datos")
        self.expenses_fetch.assert_not_called()


class TestSalesConnectionFailure(_ReportTestBase):
    """TC-11 (AC-1)"""

    def test_TC_11_sales_raises_when_connection_is_not_connected(self):
        self.sales_conn.return_value = {"status": "down"}

        with self.assertRaises(Exception) as ctx:
            report_sales.generate_sales_report()

        self.assertEqual(str(ctx.exception), "No hay conexión a la base de datos")
        self.sales_fetch.assert_not_called()


class TestLogActivityModuleNames(_ReportTestBase):
    """TC-12 (AC-1)"""

    def test_TC_12_sales_logs_start_and_finish_with_report_sales_module_name(self):
        self._run_sales([{"id": 1, "amount": 1000, "status": "completed"}])

        self.assertEqual(
            self.sales_log.call_args_list,
            [
                mock.call("ReportSales", SALES_START),
                mock.call("ReportSales", SALES_END),
            ],
        )

    def test_TC_12_expenses_logs_start_and_finish_with_report_expenses_module_name(self):
        self._run_expenses([{"id": 1, "amount": 1000, "status": "completed"}])

        self.assertEqual(
            self.expenses_log.call_args_list,
            [
                mock.call("ReportExpenses", EXPENSES_START),
                mock.call("ReportExpenses", EXPENSES_END),
            ],
        )


if __name__ == "__main__":
    unittest.main()
