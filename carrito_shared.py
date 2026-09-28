import datetime


def procesar_orden_compra(carrito, cliente, configuracion_tienda):
    total_sin_iva = 0
    total_descuentos = 0
    peso_total = 0
    productos_procesados = []

    # 1. Procesamiento de productos y subtotales
    for item in carrito:
        if not item.get("activo", True):
            continue

        precio_base = item.get("precio", 0)
        cantidad = item.get("cantidad", 1)
        peso = item.get("peso_kg", 0)
        descuento_porcentaje = item.get("descuento", 0)

        # Calcular montos del item
        subtotal_item = precio_base * cantidad
        descuento_item = subtotal_item * (descuento_porcentaje / 100.0)
        subtotal_con_descuento = subtotal_item - descuento_item

        # Impuestos (ej. 16% IVA normal, 8% frontera)
        tasa_iva = 0.08 if configuracion_tienda.get("zona_fronteriza") else 0.16
        iva_item = subtotal_con_descuento * tasa_iva

        total_item = subtotal_con_descuento + iva_item

        # Acumuladores
        total_sin_iva += subtotal_item
        total_descuentos += descuento_item
        peso_total += (peso * cantidad)

        productos_procesados.append({
            "sku": item.get("sku", "UNKNOWN"),
            "nombre": item.get("nombre", "Producto Sin Nombre"),
            "precio_unitario": precio_base,
            "cantidad": cantidad,
            "subtotal": subtotal_item,
            "descuento_aplicado": descuento_item,
            "iva": iva_item,
            "total_final": total_item
        })

    # 2. Cálculo de costo de envío
    costo_envio = 0
    if peso_total > 0:
        tarifa_base = configuracion_tienda.get("tarifa_envio_base", 150.0)
        costo_envio = tarifa_base

        # Recargo por exceso de peso (más de 10kg)
        if peso_total > 10.0:
            kilos_extra = peso_total - 10.0
            costo_envio += (kilos_extra * 15.50)  # $15.50 por kilo extra

        # Envío gratis si la compra supera cierto monto
        monto_minimo_envio_gratis = configuracion_tienda.get("minimo_envio_gratis", 2000.0)
        if (total_sin_iva - total_descuentos) >= monto_minimo_envio_gratis:
            costo_envio = 0

    # 3. Totales finales
    subtotal_general = total_sin_iva - total_descuentos
    iva_general = sum(p["iva"] for p in productos_procesados)
    gran_total = subtotal_general + iva_general + costo_envio

    # 4. Generación de recibo
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    numero_orden = f"ORD-{cliente.get('id', '000')}-{int(datetime.datetime.now().timestamp())}"

    return {
        "metadata": {
            "fecha": fecha_actual,
            "orden": numero_orden,
            "cliente_id": cliente.get("id"),
            "cliente_email": cliente.get("email")
        },
        "resumen_financiero": {
            "subtotal_bruto": round(total_sin_iva, 2),
            "total_descuentos": round(total_descuentos, 2),
            "subtotal_neto": round(subtotal_general, 2),
            "total_iva": round(iva_general, 2),
            "costo_envio": round(costo_envio, 2),
            "gran_total": round(gran_total, 2)
        },
        "logistica": {
            "peso_total_kg": round(peso_total, 2),
            "requiere_envio": peso_total > 0
        },
        "detalle_articulos": productos_procesados
    }
