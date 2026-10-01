from database import get_connection
from logger import log_activity
from report_common import generate_financial_report


def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}


def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    summary = generate_financial_report("SELECT * FROM expenses WHERE month = 'current'")
    log_activity("ReportExpenses", "Reporte finalizado exitosamente")

    return summary
