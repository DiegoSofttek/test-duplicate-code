from report_common import generate_report


def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}


def generate_expenses_report():
    return generate_report(
        log_name="ReportExpenses",
        table="expenses",
        start_message="Iniciando generación de reporte de gastos",
        connect=get_connection,
    )
