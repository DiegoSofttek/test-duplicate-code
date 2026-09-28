from database import get_connection, fetch_data
from logger import log_activity

def generate_sales_report():
    log_activity("ReportSales", "Iniciando generación de reporte de ventas")
    conn = get_connection()
    
    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")
        
    raw_data = fetch_data("SELECT * FROM sales WHERE month = 'current'")
    
    total_amount = 0
    completed_count = 0
    
    for record in raw_data:
        if record["status"] == "completed":
            total_amount += record["amount"]
            completed_count += 1
            
    summary = f"Reporte Generado: {completed_count} transacciones, Total: ${total_amount}"
    log_activity("ReportSales", "Reporte finalizado exitosamente")
    
    return summary