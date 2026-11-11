IVA_RATE = 0.16


def calcular_resumen_transacciones(raw_data):
    """Apply the shared tax/discount rules to completed records.

    Returns a tuple (completed_count, total_amount) where total_amount is the
    sum of the net amount (after tax and discount) of every completed record.
    """
    procesados = []
    for record in raw_data:
        if record.get("status") == "completed":
            monto = record.get("amount", 0)
            impuesto = monto * IVA_RATE
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

    return completed_count, total_amount
