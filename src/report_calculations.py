"""Shared financial calculations for dashboard reports (US-3 AC-1).

Applies the 16% tax and the tiered discount (5% above subtotal 1000,
2% above subtotal 500, strict boundaries) to completed records.
"""


def calculate_report_totals(records):
    """Process completed records and return (procesados, total_amount, metricas).

    procesados: list of {"id", "neto", "impuesto", "descuento"} for completed records.
    total_amount: sum of "neto" over procesados.
    metricas: per-transaction metrics {"valida", "score", "categoria"}.
    """
    procesados = []
    for record in records:
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

    metricas = {}
    for i, p in enumerate(procesados):
        metricas[f"transaccion_{i}"] = {
            "valida": True,
            "score": p["neto"] * 1.5,
            "categoria": "A" if p["neto"] > 1000 else "B"
        }

    return procesados, total_amount, metricas
