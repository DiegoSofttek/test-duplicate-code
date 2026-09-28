from carrito_shared import procesar_orden_compra_compartida


def procesar_orden_compra(carrito, cliente, configuracion_tienda):
    return procesar_orden_compra_compartida(carrito, cliente, configuracion_tienda)
