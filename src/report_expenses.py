from logger import log_activity
from report_common import generate_report


def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    return generate_report("ReportExpenses", "expenses")
