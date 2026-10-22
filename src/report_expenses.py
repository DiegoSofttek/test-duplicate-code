from database import get_connection
from logger import log_activity
from report_common import generate_report_summary


def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}


def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    conn = get_connection()

    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")

    return generate_report_summary(
        report_name="reporte de gastos",
        query="SELECT * FROM expenses WHERE month = 'current'",
        module_name="ReportExpenses"
    )
