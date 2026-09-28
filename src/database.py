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