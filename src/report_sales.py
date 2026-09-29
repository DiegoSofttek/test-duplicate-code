from database import get_connection, fetch_data
from logger import log_activity
from report_utils import build_report_summary


def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    raw_data = fetch_data("SELECT * FROM sales WHERE month = 'current'")
    summary = build_report_summary(raw_data)

    log_activity("ReportSales", "Reporte finalizado exitosamente")

    return summary
