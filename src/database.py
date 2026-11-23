def get_connection():
    print("Conectando a la base de datos principal...")
    return {"status": "connected", "db_name": "finanzas_prod"}


def fetch_data(query: str):
    print(f"Ejecutando query: {query}")
    return [
        {"id": 1, "amount": 1500, "status": "completed"},
        {"id": 2, "amount": 3200, "status": "pending"},
        {"id": 3, "amount": 800, "status": "completed"}
    ]


def calculate_report_data(raw_data):
    """Calculate completed-report records, totals, and their derived metrics."""
    processed_records = []
    for record in raw_data:
        if record.get("status") != "completed":
            continue

        amount = record.get("amount", 0)
        tax = amount * 0.16
        subtotal = amount - tax
        if subtotal > 1000:
            discount = subtotal * 0.05
        elif subtotal > 500:
            discount = subtotal * 0.02
        else:
            discount = 0

        processed_records.append({
            "id": record.get("id"),
            "neto": subtotal - discount,
            "impuesto": tax,
            "descuento": discount,
        })

    metrics = {}
    for index, record in enumerate(processed_records):
        metrics[f"transaccion_{index}"] = {
            "valida": True,
            "score": record["neto"] * 1.5,
            "categoria": "A" if record["neto"] > 1000 else "B",
        }

    return {
        "processed_records": processed_records,
        "total_amount": sum(record["neto"] for record in processed_records),
        "completed_count": len(processed_records),
        "metrics": metrics,
    }
