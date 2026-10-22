from logger import log_activity
from report_common import generate_report


def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    return generate_report("ReportSales", "sales")
