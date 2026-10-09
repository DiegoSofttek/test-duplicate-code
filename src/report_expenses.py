from logger import log_activity
from report_common import generate_monthly_report_summary


def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    summary = generate_monthly_report_summary(
        "SELECT * FROM expenses WHERE month = 'current'"
    )
    log_activity("ReportExpenses", "Reporte finalizado exitosamente")

    return summary
