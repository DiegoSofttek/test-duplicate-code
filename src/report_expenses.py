from database import get_connection, fetch_data
from logger import log_activity
from report_utils import build_report_summary


def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}


def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    raw_data = fetch_data("SELECT * FROM expenses WHERE month = 'current'")
    summary = build_report_summary(raw_data)

    log_activity("ReportExpenses", "Reporte finalizado exitosamente")

    return summary
