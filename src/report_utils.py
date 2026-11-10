IMPUESTO_TASA = 0.16


def calcular_descuento(subtotal):
    """Tiered discount: 5% above 1000, 2% above 500 (up to 1000), otherwise 0%."""
    if subtotal > 1000:
        return subtotal * 0.05
    if subtotal > 500:
        return subtotal * 0.02
    return 0


def procesar_registros_completados(raw_data):
    """Apply the 16% tax and tiered discount to completed records.

    Returns a tuple (procesados, metricas) where procesados is the list of
    per-transaction results and metricas holds the per-transaction metrics.
    """
    procesados = []
    for record in raw_data:
        if record.get("status") == "completed":
            monto = record.get("amount", 0)
            impuesto = monto * IMPUESTO_TASA
            subtotal = monto - impuesto
            descuento = calcular_descuento(subtotal)

            total_final = subtotal - descuento
            procesados.append({
                "id": record.get("id"),
                "neto": total_final,
                "impuesto": impuesto,
                "descuento": descuento
            })

    metricas = {}
    for i, p in enumerate(procesados):
        clave = f"transaccion_{i}"
        metricas[clave] = {
            "valida": True,
            "score": p["neto"] * 1.5,
            "categoria": "A" if p["neto"] > 1000 else "B"
        }

    return procesados, metricas
