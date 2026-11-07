"""Unit tests for subtask-3-1: shared report calculation in report_sales / report_expenses.

Covers User Story #3 (AC-1: centralized 16% tax and tiered discounts used by
sales and expenses reports; AC-2: report_expenses uses the shared database
get_connection instead of a local redefinition).

Run from the repository root with:
    python -m unittest discover -s src -p "test_report_subtask-3-1.py"
"""
import re
import unittest
from unittest import mock

import database
import main_dashboard
import report_expenses
import report_sales


# Fixture returned by the (patched) fetch_data: id2 is pending and must be excluded.
FIXTURE = [
    {"id": 1, "amount": 1500, "status": "completed"},
    {"id": 2, "amount": 3200, "status": "pending"},
    {"id": 3, "amount": 800, "status": "completed"},
]

SUMMARY_PATTERN = re.compile(r"^Reporte Generado: (\d+) transacciones, Total: \$(-?[0-9.]+)$")


def _run_report(report_module, generate_name, registros=None):
    """Runs a report with patched data access and logging; returns (summary, log_mock)."""
    registros = FIXTURE if registros is None else registros
    with mock.patch.object(report_module, "get_connection", return_value={"status": "connected"}), \
         mock.patch.object(report_module, "fetch_data", return_value=registros), \
         mock.patch.object(report_module, "log_activity") as log_mock:
        summary = getattr(report_module, generate_name)()
    return summary, log_mock


def _parse_summary(summary):
    match = SUMMARY_PATTERN.match(summary)
    if match is None:
        raise AssertionError(f"Unexpected summary format: {summary!r}")
    return int(match.group(1)), float(match.group(2))


class TestSalesReportAC1(unittest.TestCase):
    """AC-1: generate_sales_report returns the centralized calculation summary."""

    def test_TC_3_05_sales_report_returns_expected_summary(self):
        """TC-3-05: generate_sales_report returns 2 transactions with total 1855.56 for the fixture."""
        summary, _ = _run_report(report_sales, "generate_sales_report")
        count, total = _parse_summary(summary)
        self.assertEqual(count, 2)
        self.assertAlmostEqual(total, 1855.56, places=2)


class TestExpensesReportAC1(unittest.TestCase):
    """AC-1: generate_expenses_report applies the same calculation as sales."""

    def test_TC_3_06_expenses_report_matches_sales_for_identical_input(self):
        """TC-3-06: Identical fixture yields identical summary; only the log module name differs."""
        sales_summary, sales_log = _run_report(report_sales, "generate_sales_report")
        expenses_summary, expenses_log = _run_report(report_expenses, "generate_expenses_report")

        self.assertEqual(expenses_summary, sales_summary)

        sales_modules = {call.args[0] for call in sales_log.call_args_list}
        expenses_modules = {call.args[0] for call in expenses_log.call_args_list}
        self.assertEqual(sales_modules, {"ReportSales"})
        self.assertEqual(expenses_modules, {"ReportExpenses"})


class TestExpensesConnectionAC2(unittest.TestCase):
    """AC-2: expenses report uses the shared database module connection."""

    def test_TC_3_07_expenses_report_has_no_local_get_connection(self):
        """TC-3-07: report_expenses.get_connection is the shared database.get_connection."""
        self.assertIs(report_expenses.get_connection, database.get_connection)

    def test_TC_3_08_expenses_report_fetches_connection_once_and_guards_status(self):
        """TC-3-08: Connection is fetched once; a non-connected status raises the guard exception."""
        with mock.patch.object(report_expenses, "get_connection",
                               return_value={"status": "connected"}) as conn_mock, \
             mock.patch.object(report_expenses, "fetch_data", return_value=FIXTURE), \
             mock.patch.object(report_expenses, "log_activity"):
            report_expenses.generate_expenses_report()
        conn_mock.assert_called_once_with()

        with mock.patch.object(report_expenses, "get_connection",
                               return_value={"status": "disconnected"}), \
             mock.patch.object(report_expenses, "fetch_data", return_value=FIXTURE) as fetch_mock, \
             mock.patch.object(report_expenses, "log_activity"):
            with self.assertRaises(Exception) as ctx:
                report_expenses.generate_expenses_report()
        self.assertEqual(str(ctx.exception), "No hay conexión a la base de datos")
        fetch_mock.assert_not_called()


class TestLogMessagesAC1(unittest.TestCase):
    """AC-1 regression: log messages are preserved after the refactor."""

    def test_TC_3_09_log_messages_preserved(self):
        """TC-3-09: Start and finish messages are logged with the original module names."""
        _, sales_log = _run_report(report_sales, "generate_sales_report")
        _, expenses_log = _run_report(report_expenses, "generate_expenses_report")

        self.assertEqual(
            sales_log.call_args_list,
            [
                mock.call("ReportSales", "Iniciando generación de reporte de ventas"),
                mock.call("ReportSales", "Reporte finalizado exitosamente"),
            ],
        )
        self.assertEqual(
            expenses_log.call_args_list,
            [
                mock.call("ReportExpenses", "Iniciando generación de reporte de gastos"),
                mock.call("ReportExpenses", "Reporte finalizado exitosamente"),
            ],
        )


class TestDashboardIntegrationAC1(unittest.TestCase):
    """AC-1 regression: dashboard runs both reports in order."""

    def test_TC_3_10_dashboard_runs_both_reports_in_order(self):
        """TC-3-10: run_dashboard calls the sales report, then the expenses report, once each."""
        manager = mock.Mock()
        with mock.patch.object(main_dashboard, "generate_sales_report", return_value="ventas") as sales_mock, \
             mock.patch.object(main_dashboard, "generate_expenses_report", return_value="gastos") as expenses_mock:
            manager.attach_mock(sales_mock, "sales")
            manager.attach_mock(expenses_mock, "expenses")
            main_dashboard.run_dashboard()
        sales_mock.assert_called_once_with()
        expenses_mock.assert_called_once_with()
        self.assertEqual(
            [name for name, _, _ in manager.mock_calls],
            ["sales", "expenses"],
        )


if __name__ == "__main__":
    unittest.main()
