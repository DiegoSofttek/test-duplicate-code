from report_common import generate_report

def _get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}

def generate_expenses_report():
    return generate_report("ReportExpenses", "expenses", "gastos", _get_connection)
