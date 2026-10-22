from database import get_connection
from logger import log_activity
from report_common import generate_report_summary


def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    return generate_report_summary(
        report_name="reporte de ventas",
        query="SELECT * FROM sales WHERE month = 'current'",
        module_name="ReportSales"
    )
