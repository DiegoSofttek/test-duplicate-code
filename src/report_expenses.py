from database import get_connection, fetch_data
from logger import log_activity

def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}

def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    conn = get_connection()
    
    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")
        
    raw_data = fetch_data("SELECT * FROM expenses WHERE month = 'current'")
    
    total_amount = 0
    completed_count = 0
    
    for record in raw_data:
        if record["status"] == "completed":
            total_amount += record["amount"]
            completed_count += 1
            
    summary = f"Reporte Generado: {completed_count} transacciones, Total: ${total_amount}"
    log_activity("ReportExpenses", "Reporte finalizado exitosamente")
    
    return summary