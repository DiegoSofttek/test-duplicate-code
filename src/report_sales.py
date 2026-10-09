from logger import log_activity
from report_common import generate_monthly_report_summary


def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    summary = generate_monthly_report_summary(
        "SELECT * FROM sales WHERE month = 'current'"
    )
    log_activity("ReportSales", "Reporte finalizado exitosamente")

    return summary
