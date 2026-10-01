from database import get_connection
from logger import log_activity
from report_common import generate_financial_report


def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    summary = generate_financial_report("SELECT * FROM sales WHERE month = 'current'")
    log_activity("ReportSales", "Reporte finalizado exitosamente")

    return summary
