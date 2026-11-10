"""Unit tests for shopping cart processing (subtask-2-1, US#2 AC-1 and AC-2).

Covers UT-subtask-2-1-US-2-AC-1-* and UT-subtask-2-1-US-2-AC-2-* against
carrito_a.procesar_orden_compra. The clock is patched for determinism; no real
I/O, database, or network is used.

US#3 (sales/expenses report refactor) is outside this subtask and is not tested here.
"""
import copy
import datetime as real_datetime
import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import carrito_a  # noqa: E402

procesar_orden_compra = carrito_a.procesar_orden_compra

FIXED_NOW = real_datetime.datetime(2024, 1, 15, 10, 30, 0)
CLIENTE = {"id": "C42", "email": "cliente@example.com"}
CONFIG_NORMAL = {}
CONFIG_FRONTERA = {"zona_fronteriza": True}


def item(**campos):
    base = {"sku": "SKU-1", "nombre": "Producto"}
    base.update(campos)
    return base


class CarritoBase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(carrito_a, "datetime")
        self.mock_datetime = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_datetime.datetime.now.return_value = FIXED_NOW

    def procesar(self, carrito, cliente=None, config=None):
        return procesar_orden_compra(
            carrito,
            CLIENTE if cliente is None else cliente,
            CONFIG_NORMAL if config is None else config,
        )


class TestAC1ItemsDescuentosIva(CarritoBase):
    """UT-subtask-2-1-US-2-AC-1: subtotal, item discounts, and IVA (8% border / 16% standard)."""

    def test_01_inactive_item_is_excluded_from_all_totals(self):
        carrito = [
            item(precio=100, cantidad=1, peso_kg=2, sku="ACT"),
            item(precio=50, cantidad=3, peso_kg=5, descuento=10, activo=False, sku="INACT"),
        ]
        resultado = self.procesar(carrito)

        self.assertEqual(len(resultado["detalle_articulos"]), 1)
        self.assertEqual(resultado["detalle_articulos"][0]["sku"], "ACT")
        self.assertEqual(resultado["resumen_financiero"]["subtotal_bruto"], 100.0)
        self.assertEqual(resultado["resumen_financiero"]["total_descuentos"], 0.0)
        self.assertEqual(resultado["resumen_financiero"]["total_iva"], 16.0)
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 2.0)

    def test_02_item_without_activo_key_is_treated_as_active(self):
        resultado = self.procesar([item(precio=40, cantidad=2, sku="SIN-ACTIVO")])

        self.assertEqual(len(resultado["detalle_articulos"]), 1)
        self.assertEqual(resultado["detalle_articulos"][0]["sku"], "SIN-ACTIVO")
        self.assertEqual(resultado["resumen_financiero"]["subtotal_bruto"], 80.0)

    def test_03_subtotal_and_item_discount(self):
        resultado = self.procesar([item(precio=100, cantidad=2, descuento=10)])

        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["subtotal_bruto"], 200.00)
        self.assertEqual(resumen["total_descuentos"], 20.00)
        self.assertEqual(resumen["subtotal_neto"], 180.00)

        linea = resultado["detalle_articulos"][0]
        self.assertEqual(linea["subtotal"], 200.0)
        self.assertAlmostEqual(linea["descuento_aplicado"], 20.0)
        self.assertEqual(linea["cantidad"], 2)
        self.assertEqual(linea["precio_unitario"], 100)

    def test_04_standard_16_percent_iva_when_no_border_zone(self):
        resultado = self.procesar([item(precio=100, cantidad=2, descuento=10)], config={})

        self.assertEqual(resultado["resumen_financiero"]["subtotal_neto"], 180.00)
        self.assertEqual(resultado["resumen_financiero"]["total_iva"], 28.80)
        self.assertEqual(resultado["detalle_articulos"][0]["iva"], 28.8)

    def test_04b_standard_16_percent_iva_when_zona_fronteriza_falsy(self):
        for valor in (False, 0, None):
            with self.subTest(zona_fronteriza=valor):
                resultado = self.procesar(
                    [item(precio=100, cantidad=2, descuento=10)],
                    config={"zona_fronteriza": valor},
                )
                self.assertEqual(resultado["resumen_financiero"]["total_iva"], 28.80)

    def test_05_border_8_percent_iva_when_zona_fronteriza_truthy(self):
        resultado = self.procesar(
            [item(precio=100, cantidad=2, descuento=10)], config=CONFIG_FRONTERA
        )

        self.assertEqual(resultado["resumen_financiero"]["subtotal_neto"], 180.00)
        self.assertEqual(resultado["resumen_financiero"]["total_iva"], 14.40)
        self.assertAlmostEqual(resultado["detalle_articulos"][0]["iva"], 14.4)

    def test_06_final_total_is_net_plus_iva_plus_shipping(self):
        # 2 kg total -> base shipping 150; net 180; IVA 16% = 28.80
        resultado = self.procesar([item(precio=100, cantidad=2, descuento=10, peso_kg=1)])

        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["costo_envio"], 150.00)
        self.assertEqual(resumen["gran_total"], 358.80)
        self.assertEqual(
            resumen["gran_total"],
            round(resumen["subtotal_neto"] + resumen["total_iva"] + resumen["costo_envio"], 2),
        )

    def test_07_missing_item_fields_use_defaults(self):
        resultado = self.procesar([{}])

        self.assertEqual(len(resultado["detalle_articulos"]), 1)
        linea = resultado["detalle_articulos"][0]
        self.assertEqual(linea["sku"], "UNKNOWN")
        self.assertEqual(linea["nombre"], "Producto Sin Nombre")
        self.assertEqual(linea["precio_unitario"], 0)
        self.assertEqual(linea["cantidad"], 1)
        self.assertEqual(linea["subtotal"], 0)
        self.assertEqual(linea["descuento_aplicado"], 0)
        self.assertEqual(linea["iva"], 0)
        self.assertEqual(linea["total_final"], 0)

        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["subtotal_neto"], 0)
        self.assertEqual(resumen["total_iva"], 0)
        self.assertEqual(resumen["costo_envio"], 0)
        self.assertEqual(resultado["logistica"]["requiere_envio"], False)

    def test_08_empty_cart(self):
        resultado = self.procesar([])

        resumen = resultado["resumen_financiero"]
        for campo in ("subtotal_bruto", "total_descuentos", "subtotal_neto",
                      "total_iva", "costo_envio", "gran_total"):
            with self.subTest(campo=campo):
                self.assertEqual(resumen[campo], 0)
        self.assertEqual(resultado["detalle_articulos"], [])
        self.assertFalse(resultado["logistica"]["requiere_envio"])
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 0)

    def test_11_monetary_outputs_rounded_to_two_decimals(self):
        # 33.33 * 16% = 5.3328 -> 5.33 ; gran total 38.6628 -> 38.66
        resultado = self.procesar([item(precio=33.33, cantidad=1)])

        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["subtotal_neto"], 33.33)
        self.assertEqual(resumen["total_iva"], 5.33)
        self.assertEqual(resumen["gran_total"], 38.66)

    def test_10_metadata_and_order_number(self):
        ts = int(FIXED_NOW.timestamp())
        resultado = self.procesar([item(precio=10)], cliente={"id": "C42", "email": "a@b.com"})

        meta = resultado["metadata"]
        self.assertEqual(meta["cliente_id"], "C42")
        self.assertEqual(meta["cliente_email"], "a@b.com")
        self.assertEqual(meta["orden"], f"ORD-C42-{ts}")
        self.assertEqual(meta["fecha"], "2024-01-15 10:30:00")

    def test_10b_missing_client_id_defaults_order_number_to_000(self):
        ts = int(FIXED_NOW.timestamp())
        resultado = self.procesar([item(precio=10)], cliente={"email": "a@b.com"})

        self.assertEqual(resultado["metadata"]["orden"], f"ORD-000-{ts}")
        self.assertEqual(resultado["metadata"]["cliente_email"], "a@b.com")

    def test_12_input_data_is_not_mutated(self):
        carrito = [
            item(precio=100, cantidad=2, descuento=10, peso_kg=3),
            item(precio=5, activo=False),
        ]
        configuracion = {"zona_fronteriza": True, "tarifa_envio_base": 175.0}
        cliente = {"id": "C7", "email": "x@y.z"}
        carrito_original = copy.deepcopy(carrito)
        config_original = copy.deepcopy(configuracion)
        cliente_original = copy.deepcopy(cliente)

        procesar_orden_compra(carrito, cliente, configuracion)

        self.assertEqual(carrito, carrito_original)
        self.assertEqual(configuracion, config_original)
        self.assertEqual(cliente, cliente_original)


class TestAC2Logistica(CarritoBase):
    """UT-subtask-2-1-US-2-AC-2: base rate, 15.50/kg surcharge over 10 kg, free shipping threshold."""

    def test_01_base_rate_at_exact_10kg_no_surcharge(self):
        resultado = self.procesar([item(precio=100, cantidad=1, peso_kg=10)])

        self.assertEqual(resultado["logistica"]["peso_total_kg"], 10.0)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_02_custom_base_rate_is_honored(self):
        resultado = self.procesar(
            [item(precio=100, cantidad=1, peso_kg=5)],
            config={"tarifa_envio_base": 200},
        )

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 200.00)

    def test_03_excess_weight_surcharge_above_10kg(self):
        resultado = self.procesar([item(precio=100, cantidad=1, peso_kg=12)])

        # 150 + 2 kilos extra * 15.50 = 181.00
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 181.00)

    def test_04_free_shipping_at_exact_default_threshold(self):
        resultado = self.procesar([item(precio=2000, cantidad=1, peso_kg=1)])

        self.assertEqual(resultado["resumen_financiero"]["subtotal_neto"], 2000.00)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_05_just_below_default_threshold_pays_base_rate(self):
        resultado = self.procesar([item(precio=1999.99, cantidad=1, peso_kg=1)])

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_06_custom_free_shipping_threshold_is_honored(self):
        resultado = self.procesar(
            [item(precio=600, cantidad=1, peso_kg=1)],
            config={"minimo_envio_gratis": 500},
        )

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_07_free_shipping_overrides_excess_weight_surcharge(self):
        resultado = self.procesar([item(precio=2000, cantidad=1, peso_kg=12)])

        self.assertEqual(resultado["logistica"]["peso_total_kg"], 12.0)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_08_threshold_uses_net_after_discount_and_before_iva(self):
        # Gross 2100, 5% discount -> net 1995 (< 2000) -> base rate
        bajo = self.procesar([item(precio=2100, cantidad=1, descuento=5, peso_kg=1)])
        self.assertEqual(bajo["resumen_financiero"]["subtotal_neto"], 1995.00)
        self.assertEqual(bajo["resumen_financiero"]["costo_envio"], 150.00)

        # Gross 2200, 5% discount -> net 2090 (>= 2000) -> free shipping
        alto = self.procesar([item(precio=2200, cantidad=1, descuento=5, peso_kg=1)])
        self.assertEqual(alto["resumen_financiero"]["subtotal_neto"], 2090.00)
        self.assertEqual(alto["resumen_financiero"]["costo_envio"], 0)

    def test_09_zero_weight_cart_has_no_shipping_even_above_threshold(self):
        resultado = self.procesar([item(precio=2500, cantidad=1, peso_kg=0)])

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)
        self.assertFalse(resultado["logistica"]["requiere_envio"])

    def test_09b_weight_is_multiplied_by_quantity(self):
        resultado = self.procesar([item(precio=100, cantidad=4, peso_kg=3)])

        self.assertEqual(resultado["logistica"]["peso_total_kg"], 12.00)
        self.assertTrue(resultado["logistica"]["requiere_envio"])


if __name__ == "__main__":
    unittest.main()
