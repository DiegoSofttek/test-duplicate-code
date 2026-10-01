from database import get_connection, fetch_data
from logger import log_activity
from report_utils import process_completed_records


def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    raw_data = fetch_data("SELECT * FROM sales WHERE month = 'current'")
    completed_count, total_amount, _ = process_completed_records(raw_data)

    summary = f"Reporte Generado: {completed_count} transacciones, Total: ${total_amount}"
    log_activity("ReportSales", "Reporte finalizado exitosamente")

    return summary
