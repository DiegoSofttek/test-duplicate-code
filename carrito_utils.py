def calcular_impuestos_y_totales(carrito):
    """Calcula impuestos y totales para un carrito de compras."""
    total_sin_iva = 0
    productos_procesados = []

    for item in carrito:
        if item.get("activo", True):
            precio = item.get("precio", 0)
            cantidad = item.get("cantidad", 1)
            subtotal = precio * cantidad
            total_sin_iva += subtotal

            productos_procesados.append({
                "id": item.get("id"),
                "subtotal": subtotal,
                "iva": subtotal * 0.16,
                "total": subtotal * 1.16,
            })

    return {
        "total_bruto": total_sin_iva,
        "total_neto": total_sin_iva * 1.16,
        "detalle": productos_procesados,
    }
