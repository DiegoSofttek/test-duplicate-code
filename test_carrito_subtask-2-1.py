"""Unit tests for subtask-2-1 (robust cart processing).

Target: procesar_orden_compra in carrito_a.py (canonical module). carrito_b.py
and carrito_c.py are duplicates and are checked for parity only in CART-T22.
Test IDs are preserved from the Explorer test plan and appear in each test's
docstring. The function is synchronous and pure except for the clock, which is
controlled by patching the `datetime` name used inside carrito_a.
"""
import datetime
import unittest
from unittest.mock import Mock, patch

import carrito_a
import carrito_b
import carrito_c
from carrito_a import procesar_orden_compra

FECHA_FIJA = datetime.datetime(2024, 1, 15, 10, 30, 0)
CONFIG_ESTANDAR = {}
CONFIG_FRONTERA = {"zona_fronteriza": True}
CLIENTE = {"id": 42, "email": "cliente@example.com"}


def _reloj_fijo():
    """Module double for carrito_a.datetime that returns a fixed 'now'."""
    reloj = Mock()
    reloj.datetime.now.return_value = FECHA_FIJA
    return reloj


def _resumen(resultado):
    return resultado["resumen_financiero"]


def _detalle_por_sku(resultado, sku):
    for articulo in resultado["detalle_articulos"]:
        if articulo["sku"] == sku:
            return articulo
    raise AssertionError(f"SKU {sku} no encontrado en detalle_articulos")


class CartProcessingSubtask21Tests(unittest.TestCase):

    # AC-1 -------------------------------------------------------------

    def test_cart_t01_border_zone_applies_8_percent_iva_on_single_item(self):
        """CART-T01: Border zone single item 100, qty 1, no discount, peso 0
        yields 8% IVA and total 108.00 with no shipping. (AC-1)"""
        carrito = [{"sku": "A1", "nombre": "Libro", "precio": 100, "cantidad": 1}]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_FRONTERA)
        resumen = _resumen(resultado)
        self.assertEqual(resumen["total_iva"], 8.00)
        self.assertEqual(_detalle_por_sku(resultado, "A1")["iva"], 8.00)
        self.assertEqual(_detalle_por_sku(resultado, "A1")["total_final"], 108.00)
        self.assertEqual(resumen["gran_total"], 108.00)
        self.assertEqual(resumen["costo_envio"], 0)
        self.assertFalse(resultado["logistica"]["requiere_envio"])

    def test_cart_t02_standard_zone_applies_16_percent_iva_on_single_item(self):
        """CART-T02: Standard zone (zona_fronteriza absent or False) with the
        same single item yields 16% IVA (16.00) and gran_total 116.00. (AC-1)"""
        carrito = [{"sku": "A1", "nombre": "Libro", "precio": 100, "cantidad": 1}]
        for configuracion in (CONFIG_ESTANDAR, {"zona_fronteriza": False}):
            with self.subTest(configuracion=configuracion):
                resultado = procesar_orden_compra(carrito, CLIENTE, configuracion)
                self.assertEqual(_resumen(resultado)["total_iva"], 16.00)
                self.assertEqual(_resumen(resultado)["gran_total"], 116.00)

    def test_cart_t03_discount_is_applied_before_iva(self):
        """CART-T03: Precio 200, cantidad 2, descuento 10% in standard zone gives
        bruto 400.00, descuentos 40.00, neto 360.00 and IVA 57.60 on the
        post-discount amount. (AC-1)"""
        carrito = [{"sku": "D1", "precio": 200, "cantidad": 2, "descuento": 10}]
        resumen = _resumen(procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR))
        self.assertEqual(resumen["subtotal_bruto"], 400.00)
        self.assertEqual(resumen["total_descuentos"], 40.00)
        self.assertEqual(resumen["subtotal_neto"], 360.00)
        self.assertEqual(resumen["total_iva"], 57.60)

    def test_cart_t04_totals_are_sums_of_items_with_mixed_discounts(self):
        """CART-T04: Multiple items with mixed discounts in the border zone have
        totals equal to the sums of per-item values, rounded to 2 decimals. (AC-1)"""
        carrito = [
            {"sku": "M1", "precio": 100, "cantidad": 1, "descuento": 0},
            {"sku": "M2", "precio": 250, "cantidad": 2, "descuento": 20},
            {"sku": "M3", "precio": 33.33, "cantidad": 3, "descuento": 5},
        ]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_FRONTERA)
        items = resultado["detalle_articulos"]
        resumen = _resumen(resultado)
        esperado_bruto = round(sum(i["subtotal"] for i in items), 2)
        esperado_desc = round(sum(i["descuento_aplicado"] for i in items), 2)
        esperado_iva = round(sum(i["iva"] for i in items), 2)
        self.assertEqual(resumen["subtotal_bruto"], esperado_bruto)
        self.assertEqual(resumen["total_descuentos"], esperado_desc)
        self.assertEqual(resumen["total_iva"], esperado_iva)
        self.assertAlmostEqual(resumen["subtotal_neto"],
                               round(esperado_bruto - esperado_desc, 2), places=2)

    def test_cart_t05_inactive_item_is_excluded_from_all_totals(self):
        """CART-T05: An item with activo False is absent from detalle_articulos
        and does not contribute to subtotal, discounts, IVA, or weight. (AC-1)"""
        carrito = [
            {"sku": "ON", "precio": 100, "cantidad": 1, "descuento": 0, "peso_kg": 0},
            {"sku": "OFF", "precio": 500, "cantidad": 3, "descuento": 10,
             "peso_kg": 5, "activo": False},
        ]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR)
        resumen = _resumen(resultado)
        skus = [a["sku"] for a in resultado["detalle_articulos"]]
        self.assertEqual(skus, ["ON"])
        self.assertEqual(resumen["subtotal_bruto"], 100.00)
        self.assertEqual(resumen["total_descuentos"], 0.00)
        self.assertEqual(resumen["total_iva"], 16.00)
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 0.00)

    def test_cart_t06_empty_cart_returns_zero_totals(self):
        """CART-T06: An empty cart returns all money fields 0.00, costo_envio
        0.00, requiere_envio False, and an empty detalle_articulos. (AC-1, AC-2)"""
        resultado = procesar_orden_compra([], CLIENTE, CONFIG_ESTANDAR)
        resumen = _resumen(resultado)
        for campo in ("subtotal_bruto", "total_descuentos", "subtotal_neto",
                      "total_iva", "costo_envio", "gran_total"):
            with self.subTest(campo=campo):
                self.assertEqual(resumen[campo], 0.00)
        self.assertFalse(resultado["logistica"]["requiere_envio"])
        self.assertEqual(resultado["detalle_articulos"], [])

    def test_cart_t07_missing_optional_fields_use_defaults(self):
        """CART-T07: An item with only precio gets sku UNKNOWN, nombre
        'Producto Sin Nombre', cantidad 1, descuento 0, and peso 0. (AC-1)"""
        resultado = procesar_orden_compra([{"precio": 100}], CLIENTE, CONFIG_ESTANDAR)
        articulo = resultado["detalle_articulos"][0]
        self.assertEqual(articulo["sku"], "UNKNOWN")
        self.assertEqual(articulo["nombre"], "Producto Sin Nombre")
        self.assertEqual(articulo["cantidad"], 1)
        self.assertEqual(articulo["descuento_aplicado"], 0)
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 0)

    # AC-2 -------------------------------------------------------------

    def test_cart_t08_zero_weight_has_no_shipping_cost(self):
        """CART-T08: Zero total weight with a nonzero price gives costo_envio
        0.00 and requiere_envio False; no base rate is applied. (AC-2)"""
        carrito = [{"sku": "Z", "precio": 100, "cantidad": 1, "peso_kg": 0}]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR)
        self.assertEqual(_resumen(resultado)["costo_envio"], 0.00)
        self.assertFalse(resultado["logistica"]["requiere_envio"])

    def test_cart_t09_light_order_pays_default_base_rate(self):
        """CART-T09: Light order (peso 5, net 500) with default config pays the
        150.00 base rate; gran_total = 500 + IVA + 150. (AC-2)"""
        carrito = [{"sku": "L", "precio": 500, "cantidad": 1, "peso_kg": 5}]
        resumen = _resumen(procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR))
        self.assertEqual(resumen["costo_envio"], 150.00)
        self.assertEqual(resumen["gran_total"],
                         round(500 + resumen["total_iva"] + 150, 2))

    def test_cart_t10_custom_base_rate_is_used(self):
        """CART-T10: A custom tarifa_envio_base of 200 is charged for a light
        order. (AC-2)"""
        carrito = [{"sku": "L", "precio": 500, "cantidad": 1, "peso_kg": 5}]
        resultado = procesar_orden_compra(
            carrito, CLIENTE, {"tarifa_envio_base": 200}
        )
        self.assertEqual(_resumen(resultado)["costo_envio"], 200.00)

    def test_cart_t11_weight_exactly_10kg_has_no_surcharge(self):
        """CART-T11: Weight exactly 10 kg with net below threshold charges only
        the base rate of 150.00 (surcharge uses strict > 10). (AC-2)"""
        carrito = [{"sku": "W", "precio": 100, "cantidad": 1, "peso_kg": 10}]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR)
        self.assertEqual(_resumen(resultado)["costo_envio"], 150.00)

    def test_cart_t12_excess_weight_adds_15_50_per_extra_kilo(self):
        """CART-T12: Weight 12 kg with net below threshold costs 181.00
        (150 + 2 x 15.50) and gran_total 297.00. (AC-2)"""
        carrito = [{"sku": "W", "precio": 100, "cantidad": 1, "peso_kg": 12}]
        resumen = _resumen(procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR))
        self.assertEqual(resumen["costo_envio"], 181.00)
        self.assertEqual(resumen["gran_total"], 297.00)

    def test_cart_t13_surcharge_uses_aggregate_weight_across_items(self):
        """CART-T13: Weight from items with quantities (6 kg x 2 = 12 kg) is
        surcharged on the aggregate weight, giving 181.00. (AC-2)"""
        carrito = [
            {"sku": "P1", "precio": 50, "cantidad": 2, "peso_kg": 6},
            {"sku": "P2", "precio": 50, "cantidad": 1, "peso_kg": 0},
        ]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR)
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 12.00)
        self.assertEqual(_resumen(resultado)["costo_envio"], 181.00)

    def test_cart_t14_net_exactly_at_default_threshold_ships_free(self):
        """CART-T14: Net subtotal exactly 2000 (default threshold) gives free
        shipping; gran_total = 2000 + 320 IVA = 2320.00. (AC-2)"""
        carrito = [{"sku": "F", "precio": 2000, "cantidad": 1, "peso_kg": 1}]
        resumen = _resumen(procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR))
        self.assertEqual(resumen["costo_envio"], 0.00)
        self.assertEqual(resumen["gran_total"], 2320.00)

    def test_cart_t15_net_just_below_threshold_pays_base_rate(self):
        """CART-T15: Net subtotal 1999.99 is below the threshold, so the base
        rate of 150.00 applies. (AC-2)"""
        carrito = [{"sku": "F", "precio": 1999.99, "cantidad": 1, "peso_kg": 1}]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR)
        self.assertEqual(_resumen(resultado)["costo_envio"], 150.00)

    def test_cart_t16_threshold_uses_net_after_discount_not_gross(self):
        """CART-T16: Gross 2100 with a discount leaving net 1900 is below the
        2000 threshold, so shipping is 150.00 and not free. (AC-2)"""
        carrito = [{"sku": "F", "precio": 2100, "cantidad": 1,
                    "descuento": 200 / 2100 * 100, "peso_kg": 1}]
        resumen = _resumen(procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR))
        self.assertEqual(resumen["subtotal_bruto"], 2100.00)
        self.assertAlmostEqual(resumen["subtotal_neto"], 1900.00, places=2)
        self.assertEqual(resumen["costo_envio"], 150.00)

    def test_cart_t17_custom_free_shipping_threshold_is_used(self):
        """CART-T17: A custom minimo_envio_gratis of 500 makes a net of 500
        ship free. (AC-2)"""
        carrito = [{"sku": "F", "precio": 500, "cantidad": 1, "peso_kg": 1}]
        resultado = procesar_orden_compra(
            carrito, CLIENTE, {"minimo_envio_gratis": 500}
        )
        self.assertEqual(_resumen(resultado)["costo_envio"], 0.00)

    def test_cart_t18_free_shipping_overrides_excess_weight_surcharge(self):
        """CART-T18: Weight 12 kg with net >= 2000 gives costo_envio 0.00, so
        the excess-weight surcharge is discarded. (AC-2)"""
        carrito = [{"sku": "F", "precio": 2000, "cantidad": 1, "peso_kg": 12}]
        resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR)
        self.assertEqual(_resumen(resultado)["costo_envio"], 0.00)

    # AC-1 metadata ----------------------------------------------------

    def test_cart_t19_metadata_has_formatted_date_order_number_and_client(self):
        """CART-T19: With a patched clock, fecha uses '%Y-%m-%d %H:%M:%S', orden
        is 'ORD-<id>-<int timestamp>', and cliente_id and cliente_email are
        echoed. (AC-1)"""
        carrito = [{"sku": "A", "precio": 10, "cantidad": 1}]
        with patch("carrito_a.datetime", _reloj_fijo()):
            resultado = procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR)
        metadata = resultado["metadata"]
        self.assertEqual(metadata["fecha"], "2024-01-15 10:30:00")
        self.assertEqual(metadata["orden"],
                         f"ORD-42-{int(FECHA_FIJA.timestamp())}")
        self.assertEqual(metadata["cliente_id"], 42)
        self.assertEqual(metadata["cliente_email"], "cliente@example.com")

    def test_cart_t20_missing_client_id_uses_placeholder_in_order_number(self):
        """CART-T20: A client without an id produces an order number using
        'ORD-000-<timestamp>'. (AC-1)"""
        carrito = [{"sku": "A", "precio": 10, "cantidad": 1}]
        with patch("carrito_a.datetime", _reloj_fijo()):
            resultado = procesar_orden_compra(carrito, {}, CONFIG_ESTANDAR)
        self.assertEqual(resultado["metadata"]["orden"],
                         f"ORD-000-{int(FECHA_FIJA.timestamp())}")
        self.assertIsNone(resultado["metadata"]["cliente_id"])

    def test_cart_t21_accumulated_float_values_are_rounded_to_2_decimals(self):
        """CART-T21: Accumulated float values (0.1 + 0.2 style) are reported
        rounded to 2 decimals. (AC-1)"""
        carrito = [
            {"sku": "R1", "precio": 0.1, "cantidad": 1},
            {"sku": "R2", "precio": 0.2, "cantidad": 1},
        ]
        resumen = _resumen(procesar_orden_compra(carrito, CLIENTE, CONFIG_ESTANDAR))
        self.assertEqual(resumen["subtotal_bruto"], 0.30)
        self.assertEqual(resumen["subtotal_neto"], 0.30)
        self.assertEqual(resumen["total_iva"], 0.05)
        self.assertEqual(resumen["gran_total"], 0.35)

    def test_cart_t22_duplicate_modules_match_carrito_a_output(self):
        """CART-T22: carrito_b and carrito_c return the same output as carrito_a
        on shared fixtures, excluding time-dependent fields. (AC-1, AC-2)"""
        carrito = [
            {"sku": "P1", "nombre": "X", "precio": 1200, "cantidad": 2,
             "peso_kg": 6.5, "descuento": 5},
            {"sku": "P2", "precio": 33.33, "cantidad": 1, "peso_kg": 0,
             "activo": False},
        ]
        def _sin_tiempo(resultado):
            copia = dict(resultado)
            copia["metadata"] = {k: v for k, v in resultado["metadata"].items()
                                 if k not in ("fecha", "orden")}
            return copia

        for configuracion in (CONFIG_ESTANDAR, CONFIG_FRONTERA):
            with self.subTest(configuracion=configuracion):
                with patch("carrito_a.datetime", _reloj_fijo()):
                    esperado = _sin_tiempo(
                        carrito_a.procesar_orden_compra(carrito, CLIENTE, configuracion))
                with patch("carrito_b.datetime", _reloj_fijo()):
                    obtenido_b = _sin_tiempo(
                        carrito_b.procesar_orden_compra(carrito, CLIENTE, configuracion))
                with patch("carrito_c.datetime", _reloj_fijo()):
                    obtenido_c = _sin_tiempo(
                        carrito_c.procesar_orden_compra(carrito, CLIENTE, configuracion))
                self.assertEqual(obtenido_b, esperado)
                self.assertEqual(obtenido_c, esperado)


if __name__ == "__main__":
    unittest.main()
