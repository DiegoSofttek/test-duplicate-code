from database import get_connection, fetch_data
from logger import log_activity
from report_common import generate_report

def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}

def generate_expenses_report():
    return generate_report(
        get_connection,
        table="expenses",
        log_name="ReportExpenses",
        label_inicio="Iniciando generación de reporte de gastos",
        label_fin="Reporte finalizado exitosamente",
    )
