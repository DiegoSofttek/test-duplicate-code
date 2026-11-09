"""Unit tests for subtask-3-1 (extract report calculation logic).

Targets: generate_sales_report (src/report_sales.py) and generate_expenses_report
(src/report_expenses.py). This file adds src/ to sys.path so the `database` and
`logger` top-level imports resolve, so it can be run from the repository root.

The shared calculation helper does not exist yet, so its name and signature are
unknown. The tax/discount/totals behaviour is therefore exercised through the
public report functions and their summary string. Helper-call assertions are
omitted until the helper exists. Test IDs are preserved from the Explorer test
plan and appear in each test's docstring.

All functions under test are synchronous; no waiting or flushing is required.
"""
import importlib
import math
import os
import re
import sys
import unittest
from unittest.mock import Mock, call, patch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

import database  # noqa: E402
import report_expenses  # noqa: E402
import report_sales  # noqa: E402

CONEXION_OK = {"status": "connected"}
CONEXION_CAIDA = {"status": "disconnected"}
MENSAJE_SIN_CONEXION = "No hay conexión a la base de datos"
REGISTRO_1500 = {"id": 1, "amount": 1500, "status": "completed"}
REGISTRO_800 = {"id": 3, "amount": 800, "status": "completed"}
REGISTRO_PENDIENTE = {"id": 2, "amount": 3200, "status": "pending"}


def _total(resumen):
    match = re.search(r"Total: \$(-?\d+(?:\.\d+)?)", resumen)
    if match is None:
        raise AssertionError(f"Total no encontrado en resumen: {resumen!r}")
    return float(match.group(1))


def _conteo(resumen):
    match = re.search(r"^Reporte Generado: (\d+) transacciones", resumen)
    if match is None:
        raise AssertionError(f"Conteo no encontrado en resumen: {resumen!r}")
    return int(match.group(1))


def _ejecutar(modulo, generador, registros):
    """Run a report generator with a connected database and fixed records."""
    with patch.object(modulo, "get_connection", return_value=CONEXION_OK), \
            patch.object(modulo, "fetch_data", return_value=registros):
        return generador()


def _subtotal(monto):
    """Subtotal computed exactly as the reports do (amount - amount*0.16)."""
    return monto - monto * 0.16


def _monto_en_limite(subtotal_objetivo, por_debajo_o_igual):
    """Return an amount whose subtotal is the closest achievable float to
    subtotal_objetivo on the requested side: <= the target when
    por_debajo_o_igual is True, otherwise > the target. Exact equality is not
    always reachable in floating point (one ulp of the amount can move the
    subtotal by more than one ulp of the target), so the nearest float on each
    side of the boundary is used instead."""
    base = subtotal_objetivo / 0.84
    candidatos = [base]
    arriba = abajo = base
    for _ in range(64):
        arriba = math.nextafter(arriba, math.inf)
        abajo = math.nextafter(abajo, -math.inf)
        candidatos.extend((arriba, abajo))
    if por_debajo_o_igual:
        validos = [m for m in candidatos if _subtotal(m) <= subtotal_objetivo]
        if validos:
            return max(validos, key=_subtotal)
    else:
        validos = [m for m in candidatos if _subtotal(m) > subtotal_objetivo]
        if validos:
            return min(validos, key=_subtotal)
    raise AssertionError(
        f"No se encontró monto cerca del límite de subtotal {subtotal_objetivo}")


class ReportCalculationSubtask31Tests(unittest.TestCase):

    # AC-1 -------------------------------------------------------------

    def test_sub31_t01_single_record_tax_and_tier_discount(self):
        """SUB31-T01: A single completed record of 1500 yields net 1197.00 (tax
        240, 5% discount on subtotal 1260) and 800 yields net 658.56 (tax 128, 2%
        discount on subtotal 672). Only the net total is observable through the
        report summary. (AC-1)"""
        casos = [
            (REGISTRO_1500, 1197.00),
            (REGISTRO_800, 658.56),
        ]
        for registro, neto_esperado in casos:
            with self.subTest(amount=registro["amount"]):
                resumen = _ejecutar(report_sales, report_sales.generate_sales_report,
                                    [registro])
                self.assertEqual(_conteo(resumen), 1)
                self.assertAlmostEqual(_total(resumen), neto_esperado, places=2)

    def test_sub31_t02_boundary_exactly_500_and_1000(self):
        """SUB31-T02: A subtotal at the 500 boundary (not strictly above 500) gets
        no discount, so net equals subtotal (about 500.00). A subtotal at the 1000
        boundary (not strictly above 1000) takes the 2% tier (net about 980.00).
        Amounts are the nearest achievable floats on each side of the boundary
        via _monto_en_limite. (AC-1)"""
        monto_500 = _monto_en_limite(500.0, por_debajo_o_igual=True)
        subtotal_500 = _subtotal(monto_500)
        self.assertLessEqual(subtotal_500, 500.0)
        resumen_500 = _ejecutar(report_sales, report_sales.generate_sales_report,
                                [{"id": 4, "amount": monto_500, "status": "completed"}])
        self.assertAlmostEqual(_total(resumen_500), subtotal_500, places=6)
        self.assertAlmostEqual(_total(resumen_500), 500.00, places=2)

        monto_1000 = _monto_en_limite(1000.0, por_debajo_o_igual=True)
        subtotal_1000 = _subtotal(monto_1000)
        self.assertGreater(subtotal_1000, 500.0)
        self.assertLessEqual(subtotal_1000, 1000.0)
        resumen_1000 = _ejecutar(report_sales, report_sales.generate_sales_report,
                                 [{"id": 5, "amount": monto_1000, "status": "completed"}])
        self.assertAlmostEqual(_total(resumen_1000), subtotal_1000 * 0.98, places=6)
        self.assertAlmostEqual(_total(resumen_1000), 980.00, places=2)

    def test_sub31_t03_just_above_tier_boundaries(self):
        """SUB31-T03: Subtotals just above 1000 (about 1000.5) take the 5% tier
        and just above 500 (about 500.5) take the 2% tier. (AC-1)"""
        casos = [
            (1000.5, 1000.5 * 0.95),
            (500.5, 500.5 * 0.98),
        ]
        for subtotal, neto_esperado in casos:
            with self.subTest(subtotal=subtotal):
                registro = {"id": 9, "amount": subtotal / 0.84, "status": "completed"}
                resumen = _ejecutar(report_sales, report_sales.generate_sales_report,
                                    [registro])
                self.assertAlmostEqual(_total(resumen), neto_esperado, places=2)

    def test_sub31_t04_non_completed_records_are_excluded(self):
        """SUB31-T04: A pending record is excluded from the count and total, so
        only the completed 1500 record contributes (count 1, net 1197.00). (AC-1)"""
        resumen = _ejecutar(report_sales, report_sales.generate_sales_report,
                            [REGISTRO_1500, REGISTRO_PENDIENTE])
        self.assertEqual(_conteo(resumen), 1)
        self.assertAlmostEqual(_total(resumen), 1197.00, places=2)

    def test_sub31_t05_missing_amount_defaults_to_zero(self):
        """SUB31-T05: A completed record without amount contributes 0 to the
        total (count 1, total 0). PARTIAL: the id-None part is not asserted
        because the id does not appear in the report summary string. (AC-1)"""
        resumen = _ejecutar(report_sales, report_sales.generate_sales_report,
                            [{"status": "completed"}])
        self.assertEqual(_conteo(resumen), 1)
        self.assertEqual(_total(resumen), 0)

    def test_sub31_t06_empty_record_list_yields_zero_totals(self):
        """SUB31-T06: An empty record list yields zero transactions and total
        0. (AC-1)"""
        resumen = _ejecutar(report_sales, report_sales.generate_sales_report, [])
        self.assertEqual(_conteo(resumen), 0)
        self.assertEqual(_total(resumen), 0)

    def test_sub31_t08_sales_report_summary_for_fixture(self):
        """SUB31-T08: generate_sales_report over the fixture (completed 1500 and
        800 plus pending 3200) reports 2 transactions and a net total of about
        1855.56. The helper-call assertion is omitted because the helper name is
        not defined yet. (AC-1)"""
        resumen = _ejecutar(report_sales, report_sales.generate_sales_report,
                            [REGISTRO_1500, REGISTRO_PENDIENTE, REGISTRO_800])
        self.assertEqual(_conteo(resumen), 2)
        self.assertAlmostEqual(_total(resumen), 1855.56, places=2)

    def test_sub31_t09_expenses_report_matches_sales_for_same_input(self):
        """SUB31-T09: generate_expenses_report returns the same summary as
        generate_sales_report for identical records. The helper-call assertion is
        omitted because the helper name is not defined yet. (AC-1)"""
        registros = [REGISTRO_1500, REGISTRO_PENDIENTE, REGISTRO_800]
        resumen_ventas = _ejecutar(report_sales, report_sales.generate_sales_report,
                                   registros)
        resumen_gastos = _ejecutar(report_expenses,
                                   report_expenses.generate_expenses_report,
                                   registros)
        self.assertEqual(resumen_gastos, resumen_ventas)

    def test_sub31_t10_connection_failure_raises_and_skips_fetch(self):
        """SUB31-T10: A disconnected database makes both reports raise an Exception
        with the Spanish message and skip fetch_data. (AC-1, behaviour preserved)"""
        for modulo, generador in (
            (report_sales, report_sales.generate_sales_report),
            (report_expenses, report_expenses.generate_expenses_report),
        ):
            with self.subTest(modulo=modulo.__name__):
                with patch.object(modulo, "get_connection",
                                  return_value=CONEXION_CAIDA), \
                        patch.object(modulo, "fetch_data") as fetch:
                    with self.assertRaises(Exception) as contexto:
                        generador()
                    self.assertEqual(str(contexto.exception), MENSAJE_SIN_CONEXION)
                    fetch.assert_not_called()

    def test_sub31_t13_start_and_finish_are_logged_per_module(self):
        """SUB31-T13: Each report logs its start and finish messages under its own
        module name (ReportSales or ReportExpenses). (AC-1, regression guard)"""
        casos = (
            (report_sales, report_sales.generate_sales_report, "ReportSales",
             "Iniciando generación de reporte de ventas"),
            (report_expenses, report_expenses.generate_expenses_report,
             "ReportExpenses", "Iniciando generación de reporte de gastos"),
        )
        for modulo, generador, nombre, inicio in casos:
            with self.subTest(modulo=nombre):
                with patch.object(modulo, "log_activity") as log, \
                        patch.object(modulo, "get_connection", return_value=CONEXION_OK), \
                        patch.object(modulo, "fetch_data", return_value=[]):
                    generador()
                self.assertEqual(log.call_args_list, [
                    call(nombre, inicio),
                    call(nombre, "Reporte finalizado exitosamente"),
                ])

    # AC-2 -------------------------------------------------------------

    def test_sub31_t11_expenses_module_has_no_local_get_connection(self):
        """SUB31-T11: report_expenses reuses database.get_connection and its source
        no longer defines get_connection locally. (AC-2)"""
        self.assertIs(report_expenses.get_connection, database.get_connection)
        with open(report_expenses.__file__, encoding="utf-8") as archivo:
            codigo = archivo.read()
        self.assertNotIn("def get_connection", codigo)

    def test_sub31_t12_expenses_report_calls_shared_get_connection_once(self):
        """SUB31-T12: generate_expenses_report obtains the connection through the
        shared database.get_connection exactly once per call. The module is
        reloaded under the patch so that its import binding is exercised. (AC-2)"""
        conexion = Mock(return_value=CONEXION_OK)
        try:
            with patch("database.get_connection", conexion):
                importlib.reload(report_expenses)
                with patch.object(report_expenses, "fetch_data", return_value=[]):
                    report_expenses.generate_expenses_report()
            self.assertEqual(conexion.call_count, 1)
        finally:
            importlib.reload(report_expenses)


if __name__ == "__main__":
    unittest.main()
