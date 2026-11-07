from database import get_connection, fetch_data
from logger import log_activity
from report_calculations import calculate_report_totals

def generate_expenses_report():
    log_activity("ReportExpenses", "Iniciando generación de reporte de gastos")
    conn = get_connection()
    
    if conn.get("status") != "connected":
        raise Exception("No hay conexión a la base de datos")
        
    raw_data = fetch_data("SELECT * FROM expenses WHERE month = 'current'")
    
    procesados, total_amount, _metricas = calculate_report_totals(raw_data)
    completed_count = len(procesados)
            
    summary = f"Reporte Generado: {completed_count} transacciones, Total: ${total_amount}"
    log_activity("ReportExpenses", "Reporte finalizado exitosamente")
    
    return summary
