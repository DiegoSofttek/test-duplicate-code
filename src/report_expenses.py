from database import calculate_report_data, fetch_data, get_connection
from logger import log_activity


def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    raw_data = fetch_data("SELECT * FROM expenses WHERE month = 'current'")
    calculation = calculate_report_data(raw_data)
    summary = (
        f"Reporte Generado: {calculation['completed_count']} transacciones, "
        f"Total: ${calculation['total_amount']}"
    )
    log_activity("ReportExpenses", "Reporte finalizado exitosamente")

    return summary
