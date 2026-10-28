from database import get_connection as _db_get_connection
from report_common import generate_report


def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}


def generate_expenses_report():
    return generate_report(
        table="expenses",
        log_name="ReportExpenses",
        start_message="Iniciando generación de reporte de gastos",
        get_conn=get_connection,
    )
