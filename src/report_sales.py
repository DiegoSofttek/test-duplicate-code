from database import calculate_report_data, fetch_data, get_connection
from logger import log_activity


def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    raw_data = fetch_data("SELECT * FROM sales WHERE month = 'current'")
    calculation = calculate_report_data(raw_data)
    summary = (
        f"Reporte Generado: {calculation['completed_count']} transacciones, "
        f"Total: ${calculation['total_amount']}"
    )
    log_activity("ReportSales", "Reporte finalizado exitosamente")

    return summary
