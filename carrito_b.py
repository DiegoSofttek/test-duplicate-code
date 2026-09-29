from carrito_utils import procesar_orden_compra_compartido


def procesar_orden_compra(carrito, cliente, configuracion_tienda):
    return procesar_orden_compra_compartido(carrito, cliente, configuracion_tienda)
