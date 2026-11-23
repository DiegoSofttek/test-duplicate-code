"""Unit tests for subtask-2-1 cart processing."""

import importlib
import unittest

from carrito_a import procesar_orden_compra


class CartProcessingTests(unittest.TestCase):
    """Verify the canonical shopping-cart receipt and logistics calculations."""

    CLIENTE = {"id": "customer-7", "email": "customer@example.com"}

    def test_subtask_2_1_T01_standard_iva_calculation_with_item_discount(self):
        """subtask-2-1-T01: standard IVA is calculated from discounted lines."""
        resultado = procesar_orden_compra(
            [
                {
                    "sku": "DISC-1",
                    "nombre": "Discounted product",
                    "precio": 100.0,
                    "cantidad": 2,
                    "descuento": 10.0,
                    "peso_kg": 1.0,
                },
                {
                    "sku": "FULL-1",
                    "nombre": "Full-price product",
                    "precio": 50.0,
                    "cantidad": 1,
                    "peso_kg": 0.5,
                },
            ],
            self.CLIENTE,
            {"tarifa_envio_base": 40.0, "minimo_envio_gratis": 1_000.0},
        )

        resumen = resultado["resumen_financiero"]
        self.assertEqual(250.0, resumen["subtotal_bruto"])
        self.assertEqual(20.0, resumen["total_descuentos"])
        self.assertEqual(230.0, resumen["subtotal_neto"])
        self.assertEqual(36.8, resumen["total_iva"])
        self.assertEqual(40.0, resumen["costo_envio"])
        self.assertEqual(306.8, resumen["gran_total"])
        self.assertEqual(
            [
                {
                    "sku": "DISC-1", "nombre": "Discounted product",
                    "precio_unitario": 100.0, "cantidad": 2, "subtotal": 200.0,
                    "descuento_aplicado": 20.0, "iva": 28.8, "total_final": 208.8,
                },
                {
                    "sku": "FULL-1", "nombre": "Full-price product",
                    "precio_unitario": 50.0, "cantidad": 1, "subtotal": 50.0,
                    "descuento_aplicado": 0.0, "iva": 8.0, "total_final": 58.0,
                },
            ],
            resultado["detalle_articulos"],
        )

    def test_subtask_2_1_T02_border_zone_iva_calculation(self):
        """subtask-2-1-T02: border stores apply 8% IVA after discount."""
        resultado = procesar_orden_compra(
            [{"precio": 100.0, "descuento": 25.0}],
            self.CLIENTE,
            {"zona_fronteriza": True},
        )

        resumen = resultado["resumen_financiero"]
        self.assertEqual(100.0, resumen["subtotal_bruto"])
        self.assertEqual(25.0, resumen["total_descuentos"])
        self.assertEqual(75.0, resumen["subtotal_neto"])
        self.assertEqual(6.0, resumen["total_iva"])
        self.assertEqual(0, resumen["costo_envio"])
        self.assertEqual(81.0, resumen["gran_total"])
        self.assertEqual(6.0, resultado["detalle_articulos"][0]["iva"])

    def test_subtask_2_1_T03_excludes_inactive_items_and_uses_active_weight(self):
        """subtask-2-1-T03: inactive lines do not affect receipt or logistics."""
        resultado = procesar_orden_compra(
            [
                {
                    "sku": "ACTIVE", "precio": 100.0, "cantidad": 3,
                    "descuento": 10.0, "peso_kg": 2.0,
                },
                {
                    "sku": "INACTIVE", "activo": False, "precio": 1_000.0,
                    "cantidad": 4, "descuento": 50.0, "peso_kg": 10.0,
                },
            ],
            self.CLIENTE,
            {"tarifa_envio_base": 30.0, "minimo_envio_gratis": 1_000.0},
        )

        self.assertEqual(["ACTIVE"], [item["sku"] for item in resultado["detalle_articulos"]])
        self.assertEqual(300.0, resultado["resumen_financiero"]["subtotal_bruto"])
        self.assertEqual(30.0, resultado["resumen_financiero"]["total_descuentos"])
        self.assertEqual(270.0, resultado["resumen_financiero"]["subtotal_neto"])
        self.assertEqual(43.2, resultado["resumen_financiero"]["total_iva"])
        self.assertEqual(6.0, resultado["logistica"]["peso_total_kg"])
        self.assertTrue(resultado["logistica"]["requiere_envio"])

    def test_subtask_2_1_T04_charges_base_shipping_at_or_below_ten_kg(self):
        """subtask-2-1-T04: no excess-weight fee is added at ten kilograms."""
        resultado = procesar_orden_compra(
            [{"precio": 100.0, "cantidad": 2, "peso_kg": 5.0}],
            self.CLIENTE,
            {"tarifa_envio_base": 77.0, "minimo_envio_gratis": 500.0},
        )

        self.assertEqual(10.0, resultado["logistica"]["peso_total_kg"])
        self.assertEqual(77.0, resultado["resumen_financiero"]["costo_envio"])

    def test_subtask_2_1_T05_adds_surcharge_for_exact_excess_weight(self):
        """subtask-2-1-T05: shipping includes 15.50 per kilogram above ten."""
        resultado = procesar_orden_compra(
            [{"precio": 100.0, "peso_kg": 12.5}],
            self.CLIENTE,
            {"tarifa_envio_base": 40.0, "minimo_envio_gratis": 500.0},
        )

        self.assertEqual(78.75, resultado["resumen_financiero"]["costo_envio"])
        self.assertEqual(194.75, resultado["resumen_financiero"]["gran_total"])

    def test_subtask_2_1_T06_free_shipping_overrides_base_and_weight_charges(self):
        """subtask-2-1-T06: qualifying net subtotal makes even heavy shipping free."""
        resultado = procesar_orden_compra(
            [{"precio": 2_500.0, "descuento": 20.0, "peso_kg": 12.0}],
            self.CLIENTE,
            {"tarifa_envio_base": 40.0, "minimo_envio_gratis": 2_000.0},
        )

        self.assertEqual(2_000.0, resultado["resumen_financiero"]["subtotal_neto"])
        self.assertEqual(12.0, resultado["logistica"]["peso_total_kg"])
        self.assertEqual(0, resultado["resumen_financiero"]["costo_envio"])
        self.assertEqual(2_320.0, resultado["resumen_financiero"]["gran_total"])

    def test_subtask_2_1_T07_uses_canonical_cart_implementation(self):
        """subtask-2-1-T07: compatibility carts re-export the canonical processor."""
        carrito_b = importlib.import_module("carrito_b")
        carrito_c = importlib.import_module("carrito_c")
        self.assertIs(procesar_orden_compra, carrito_b.procesar_orden_compra)
        self.assertIs(procesar_orden_compra, carrito_c.procesar_orden_compra)

        estandar = procesar_orden_compra([{"precio": 100.0}], self.CLIENTE, {})
        frontera = procesar_orden_compra(
            [{"precio": 100.0}], self.CLIENTE, {"zona_fronteriza": True}
        )
        envio = procesar_orden_compra(
            [{"precio": 100.0, "peso_kg": 11.0}],
            self.CLIENTE,
            {"tarifa_envio_base": 10.0, "minimo_envio_gratis": 500.0},
        )
        self.assertEqual(16.0, estandar["resumen_financiero"]["total_iva"])
        self.assertEqual(8.0, frontera["resumen_financiero"]["total_iva"])
        self.assertEqual(25.5, envio["resumen_financiero"]["costo_envio"])


if __name__ == "__main__":
    unittest.main()
