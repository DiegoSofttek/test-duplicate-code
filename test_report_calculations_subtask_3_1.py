"""Unit tests for subtask-3-1 report calculation consolidation."""

import ast
import importlib
import os
import sys
import unittest
from unittest.mock import Mock, patch


SRC_DIRECTORY = os.path.join(os.path.dirname(__file__), "src")
if SRC_DIRECTORY not in sys.path:
    sys.path.insert(0, SRC_DIRECTORY)

import database
import report_expenses
import report_sales


class ReportCalculationConsolidationTests(unittest.TestCase):
    """Verify the shared financial-report calculation contract."""

    REPORT_RECORDS = [
        {"id": "no-discount", "amount": 100, "status": "completed"},
        {"id": "two-percent", "amount": 700, "status": "completed"},
        {"id": "five-percent", "amount": 1500, "status": "completed"},
        {"id": "ignored", "amount": 5000, "status": "pending"},
    ]
    TWO_COMPLETED_RECORDS = [
        {"id": "two-percent", "amount": 700, "status": "completed"},
        {"id": "five-percent", "amount": 1500, "status": "completed"},
        {"id": "ignored", "amount": 5000, "status": "pending"},
    ]
    EXPECTED_TWO_COMPLETED_SUMMARY = (
        "Reporte Generado: 2 transacciones, Total: $1773.24"
    )

    @staticmethod
    def _calculation_helper():
        """Return the canonical calculation function required by the refactor."""
        return database.calculate_report_data

    @staticmethod
    def _connected_connection():
        return {"status": "connected"}

    def test_subtask_3_1_T01_shared_helper_calculates_tiers_and_metrics(self):
        """subtask-3-1-T01: the helper applies all tiers only to completed rows."""
        result = self._calculation_helper()(self.REPORT_RECORDS)

        self.assertEqual(3, result["completed_count"])
        self.assertAlmostEqual(1857.24, result["total_amount"])
        self.assertEqual(
            ["no-discount", "two-percent", "five-percent"],
            [record["id"] for record in result["processed_records"]],
        )

        expected_records = [
            (84.0, 16.0, 0.0),
            (576.24, 112.0, 11.76),
            (1197.0, 240.0, 63.0),
        ]
        for processed, (net, tax, discount) in zip(
            result["processed_records"], expected_records
        ):
            self.assertAlmostEqual(net, processed["neto"])
            self.assertAlmostEqual(tax, processed["impuesto"])
            self.assertAlmostEqual(discount, processed["descuento"])

        self.assertEqual(
            {
                "transaccion_0": {"valida": True, "score": 126.0, "categoria": "B"},
                "transaccion_1": {
                    "valida": True,
                    "score": 864.36,
                    "categoria": "B",
                },
                "transaccion_2": {
                    "valida": True,
                    "score": 1795.5,
                    "categoria": "A",
                },
            },
            result["metrics"],
        )

    def test_subtask_3_1_T02_sales_delegates_to_shared_helper(self):
        """subtask-3-1-T02: sales uses the canonical helper for its summary."""
        helper = self._calculation_helper()
        self.assertIs(helper, report_sales.calculate_report_data)

        with (
            patch.object(report_sales, "get_connection", return_value=self._connected_connection()),
            patch.object(report_sales, "fetch_data", return_value=self.TWO_COMPLETED_RECORDS),
            patch.object(report_sales, "log_activity"),
            patch.object(report_sales, "calculate_report_data", wraps=helper) as delegated_helper,
        ):
            summary = report_sales.generate_sales_report()

        self.assertEqual(self.EXPECTED_TWO_COMPLETED_SUMMARY, summary)
        delegated_helper.assert_called_once_with(self.TWO_COMPLETED_RECORDS)

    def test_subtask_3_1_T03_expenses_delegates_to_shared_helper(self):
        """subtask-3-1-T03: expenses passes its records to the same helper."""
        helper = self._calculation_helper()
        self.assertIs(helper, report_expenses.calculate_report_data)

        with (
            patch.object(report_expenses, "get_connection", return_value=self._connected_connection()),
            patch.object(report_expenses, "fetch_data", return_value=self.TWO_COMPLETED_RECORDS),
            patch.object(report_expenses, "log_activity"),
            patch.object(report_expenses, "calculate_report_data", wraps=helper) as delegated_helper,
        ):
            summary = report_expenses.generate_expenses_report()

        self.assertEqual(self.EXPECTED_TWO_COMPLETED_SUMMARY, summary)
        delegated_helper.assert_called_once_with(self.TWO_COMPLETED_RECORDS)

    def test_subtask_3_1_T04_reports_have_equivalent_summaries_for_equivalent_data(self):
        """subtask-3-1-T04: sales and expenses expose identical shared-rule totals."""
        records = list(self.TWO_COMPLETED_RECORDS)
        with (
            patch.object(report_sales, "get_connection", return_value=self._connected_connection()),
            patch.object(report_sales, "fetch_data", return_value=records),
            patch.object(report_sales, "log_activity"),
            patch.object(report_expenses, "get_connection", return_value=self._connected_connection()),
            patch.object(report_expenses, "fetch_data", return_value=records),
            patch.object(report_expenses, "log_activity"),
        ):
            sales_summary = report_sales.generate_sales_report()
            expenses_summary = report_expenses.generate_expenses_report()

        self.assertEqual(self.EXPECTED_TWO_COMPLETED_SUMMARY, sales_summary)
        self.assertEqual(sales_summary, expenses_summary)

    def test_subtask_3_1_T05_expenses_uses_shared_connection_provider(self):
        """subtask-3-1-T05: expenses re-exports database connection without a local definition."""
        self.assertIs(database.get_connection, report_expenses.get_connection)
        source_path = os.path.join(SRC_DIRECTORY, "report_expenses.py")
        with open(source_path, encoding="utf-8") as source_file:
            module_tree = ast.parse(source_file.read(), filename=source_path)
        self.assertNotIn(
            "get_connection",
            [node.name for node in module_tree.body if isinstance(node, ast.FunctionDef)],
        )

        disconnected_connection = Mock(return_value={"status": "disconnected"})
        fetch_data = Mock()
        with (
            patch.object(report_expenses, "get_connection", disconnected_connection),
            patch.object(report_expenses, "fetch_data", fetch_data),
            patch.object(report_expenses, "log_activity"),
        ):
            with self.assertRaisesRegex(Exception, "No hay conexión a la base de datos"):
                report_expenses.generate_expenses_report()

        disconnected_connection.assert_called_once_with()
        fetch_data.assert_not_called()


if __name__ == "__main__":
    unittest.main()
