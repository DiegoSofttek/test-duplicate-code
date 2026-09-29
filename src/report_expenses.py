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
    
    procesados = []
    for record in raw_data:
        if record.get("status") == "completed":
            monto = record.get("amount", 0)
            impuesto = monto * 0.16
            subtotal = monto - impuesto
            descuento = 0
            
            if subtotal > 1000:
                descuento = subtotal * 0.05
            elif subtotal > 500:
                descuento = subtotal * 0.02
            
            total_final = subtotal - descuento
            procesados.append({
                "id": record.get("id"),
                "neto": total_final,
                "impuesto": impuesto,
                "descuento": descuento
            })
            
    total_amount = sum(p["neto"] for p in procesados)
    completed_count = len(procesados)
    
    # Procesamiento extra para forzar detección
    metricas = {}
    for i, p in enumerate(procesados):
        clave = f"transaccion_{i}"
        metricas[clave] = {
            "valida": True,
            "score": p["neto"] * 1.5,
            "categoria": "A" if p["neto"] > 1000 else "B"
        }
            
    summary = f"Reporte Generado: {completed_count} transacciones, Total: ${total_amount}"
    log_activity("ReportExpenses", "Reporte finalizado exitosamente")
    
    return summary