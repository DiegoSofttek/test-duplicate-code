from database import fetch_data
from logger import log_activity


def process_completed_records(raw_data):
    """Procesa registros completados: calcula impuesto, subtotal, descuento y total neto."""
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
    return procesados


def build_metrics(procesados):
    """Construye métricas adicionales a partir de los registros procesados."""
    metricas = {}
    for i, p in enumerate(procesados):
        clave = f"transaccion_{i}"
        metricas[clave] = {
            "valida": True,
            "score": p["neto"] * 1.5,
            "categoria": "A" if p["neto"] > 1000 else "B"
        }
    return metricas


def generate_report_summary(report_name, query, module_name):
    """Genera un resumen de reporte para la consulta dada."""
    log_activity(module_name, f"Iniciando generación de {report_name}")
    raw_data = fetch_data(query)
    procesados = process_completed_records(raw_data)
    total_amount = sum(p["neto"] for p in procesados)
    completed_count = len(procesados)
    build_metrics(procesados)
    summary = f"Reporte Generado: {completed_count} transacciones, Total: ${total_amount}"
    log_activity(module_name, "Reporte finalizado exitosamente")
    return summary
