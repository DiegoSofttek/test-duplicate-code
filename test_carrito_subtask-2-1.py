"""Unit tests for subtask-2-1 (Implement robust cart processing).

Covers procesar_orden_compra in carrito_a.py (and its duplicates carrito_b.py
and carrito_c.py, used by TC-17): item filtering and defaults, discounts,
border/standard IVA, shipping rules, totals and receipt metadata.

Business rule note: shipping thresholds are evaluated against the pre-IVA net
amount (subtotal bruto - descuentos), as implemented in the code.

Run from the repository root with:
    python -m unittest discover -s . -p "test_carrito_subtask-2-1.py"
"""

import datetime
import unittest
from unittest import mock

import carrito_a
import carrito_b
import carrito_c


CLIENTE = {"id": 7, "email": "cliente@example.com"}
FIXED_NOW = (2024, 1, 2, 3, 4, 5)


class _FixedDateTime(datetime.datetime):
    """datetime subclass whose now() returns a fixed local moment."""

    @classmethod
    def now(cls, tz=None):
        return cls(*FIXED_NOW)


def _patch_now(module):
    """Replace the datetime module used by `module` with a fixed clock."""
    fake_dt = mock.Mock()
    fake_dt.datetime = _FixedDateTime
    return mock.patch.object(module, "datetime", fake_dt)


def _item(**overrides):
    item = {
        "sku": "SKU-1",
        "nombre": "Producto",
        "precio": 100,
        "cantidad": 1,
        "peso_kg": 1,
        "descuento": 0,
        "activo": True,
    }
    item.update(overrides)
    return item


class InactiveItemTests(unittest.TestCase):
    """TC-01: inactive items (activo=False) are skipped."""

    def test_TC_01_inactive_items_are_excluded_from_all_totals(self):
        carrito = [
            _item(precio=100, cantidad=1, descuento=10, peso_kg=2, activo=True),
            _item(sku="SKU-OFF", precio=500, cantidad=1, descuento=20,
                  peso_kg=5, activo=False),
        ]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertEqual(len(resultado["detalle_articulos"]), 1)
        self.assertEqual(resultado["detalle_articulos"][0]["sku"], "SKU-1")
        resumen = resultado["resumen_financiero"]
        self.assertAlmostEqual(resumen["subtotal_bruto"], 100.0)
        self.assertAlmostEqual(resumen["total_descuentos"], 10.0)
        self.assertAlmostEqual(resumen["subtotal_neto"], 90.0)
        self.assertAlmostEqual(resumen["total_iva"], 14.4)
        self.assertAlmostEqual(resultado["logistica"]["peso_total_kg"], 2.0)

    def test_TC_01_cart_with_only_inactive_items_yields_empty_result(self):
        carrito = [
            _item(precio=100, activo=False),
            _item(precio=50, cantidad=3, peso_kg=4, activo=False),
        ]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertEqual(resultado["detalle_articulos"], [])
        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["subtotal_bruto"], 0)
        self.assertEqual(resumen["total_descuentos"], 0)
        self.assertEqual(resumen["total_iva"], 0)
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 0)
        self.assertFalse(resultado["logistica"]["requiere_envio"])


class ItemDefaultsTests(unittest.TestCase):
    """TC-02: item defaults when keys are missing."""

    def test_TC_02_missing_item_keys_use_documented_defaults(self):
        resultado = carrito_a.procesar_orden_compra([{}], CLIENTE, {})

        detalle = resultado["detalle_articulos"]
        self.assertEqual(len(detalle), 1)
        articulo = detalle[0]
        self.assertEqual(articulo["cantidad"], 1)
        self.assertEqual(articulo["descuento_aplicado"], 0)
        self.assertEqual(articulo["sku"], "UNKNOWN")
        self.assertEqual(articulo["nombre"], "Producto Sin Nombre")
        self.assertEqual(articulo["precio_unitario"], 0)


class ItemDiscountTests(unittest.TestCase):
    """TC-03: item discount calculation."""

    def test_TC_03_discount_is_percentage_of_line_subtotal(self):
        carrito = [_item(precio=100, cantidad=2, descuento=10)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        articulo = resultado["detalle_articulos"][0]
        self.assertAlmostEqual(articulo["subtotal"], 200.0)
        self.assertAlmostEqual(articulo["descuento_aplicado"], 20.0)
        self.assertAlmostEqual(
            resultado["resumen_financiero"]["subtotal_neto"], 180.0
        )


class IvaTests(unittest.TestCase):
    """TC-04 and TC-05: standard 16% and border 8% IVA."""

    def test_TC_04_standard_iva_is_16_percent_of_discounted_amount(self):
        carrito = [
            _item(precio=100, cantidad=1, descuento=10),
            _item(sku="SKU-2", precio=50, cantidad=2, descuento=0),
        ]

        for configuracion in ({}, {"zona_fronteriza": False}):
            with self.subTest(configuracion=configuracion):
                resultado = carrito_a.procesar_orden_compra(
                    carrito, CLIENTE, configuracion
                )

                detalle = resultado["detalle_articulos"]
                self.assertAlmostEqual(detalle[0]["iva"], 14.4)
                self.assertAlmostEqual(detalle[1]["iva"], 16.0)
                self.assertAlmostEqual(
                    resultado["resumen_financiero"]["total_iva"], 30.4
                )

    def test_TC_05_border_iva_is_8_percent_of_discounted_amount(self):
        carrito = [_item(precio=100, cantidad=1, descuento=10)]

        resultado = carrito_a.procesar_orden_compra(
            carrito, CLIENTE, {"zona_fronteriza": True}
        )

        self.assertAlmostEqual(resultado["detalle_articulos"][0]["iva"], 7.2)
        self.assertAlmostEqual(
            resultado["resumen_financiero"]["total_iva"], 7.2
        )


class TotalCompositionTests(unittest.TestCase):
    """TC-06: final total composition and rounding."""

    def test_TC_06_gran_total_is_net_plus_iva_plus_shipping_rounded(self):
        carrito = [_item(precio=33.33, cantidad=1, peso_kg=1)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        resumen = resultado["resumen_financiero"]
        self.assertAlmostEqual(resumen["subtotal_neto"], 33.33)
        self.assertAlmostEqual(resumen["total_iva"], 5.33)
        self.assertAlmostEqual(resumen["costo_envio"], 150.0)
        self.assertAlmostEqual(resumen["gran_total"], 188.66)
        self.assertAlmostEqual(
            resumen["gran_total"],
            round(
                resumen["subtotal_neto"]
                + resumen["total_iva"]
                + resumen["costo_envio"],
                2,
            ),
        )


class ShippingTests(unittest.TestCase):
    """TC-07 to TC-14: shipping rates, surcharge, free shipping and weight."""

    def test_TC_07_base_rate_is_150_by_default_or_configured_tarifa(self):
        carrito = [_item(precio=100, peso_kg=1)]

        with self.subTest("default tarifa"):
            resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})
            self.assertAlmostEqual(
                resultado["resumen_financiero"]["costo_envio"], 150.0
            )

        with self.subTest("configured tarifa"):
            resultado = carrito_a.procesar_orden_compra(
                carrito, CLIENTE, {"tarifa_envio_base": 99.0}
            )
            self.assertAlmostEqual(
                resultado["resumen_financiero"]["costo_envio"], 99.0
            )

    def test_TC_08_weight_above_10kg_adds_15_50_per_extra_kilo(self):
        carrito = [_item(precio=100, cantidad=1, peso_kg=12)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertAlmostEqual(
            resultado["resumen_financiero"]["costo_envio"], 181.00
        )

    def test_TC_09_weight_of_exactly_10kg_has_no_surcharge(self):
        carrito = [_item(precio=100, cantidad=1, peso_kg=10)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertAlmostEqual(
            resultado["resumen_financiero"]["costo_envio"], 150.0
        )

    def test_TC_10_free_shipping_applies_at_threshold_and_honors_custom(self):
        with self.subTest("default threshold of 2000 reached exactly"):
            carrito = [_item(precio=2000, cantidad=1, peso_kg=1)]
            resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})
            self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

        with self.subTest("custom threshold of 500 reached exactly"):
            carrito = [_item(precio=500, cantidad=1, peso_kg=1)]
            resultado = carrito_a.procesar_orden_compra(
                carrito, CLIENTE, {"minimo_envio_gratis": 500}
            )
            self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_TC_11_just_below_free_shipping_threshold_keeps_base_rate(self):
        carrito = [_item(precio=1999.99, cantidad=1, peso_kg=1)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertAlmostEqual(
            resultado["resumen_financiero"]["costo_envio"], 150.0
        )

    def test_TC_12_free_shipping_overrides_weight_surcharge(self):
        carrito = [_item(precio=2000, cantidad=1, peso_kg=12)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)
        self.assertAlmostEqual(
            resultado["logistica"]["peso_total_kg"], 12.0
        )

    def test_TC_13_zero_weight_cart_requires_no_shipping_and_no_cost(self):
        carrito = [_item(precio=500, cantidad=1, peso_kg=0)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertFalse(resultado["logistica"]["requiere_envio"])
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_TC_14_weight_is_multiplied_by_quantity(self):
        carrito = [_item(precio=100, cantidad=6, peso_kg=2)]

        resultado = carrito_a.procesar_orden_compra(carrito, CLIENTE, {})

        self.assertAlmostEqual(
            resultado["logistica"]["peso_total_kg"], 12.0
        )
        self.assertAlmostEqual(
            resultado["resumen_financiero"]["costo_envio"], 181.00
        )


class EmptyCartTests(unittest.TestCase):
    """TC-15: empty cart."""

    def test_TC_15_empty_cart_returns_zero_totals_and_no_shipping(self):
        resultado = carrito_a.procesar_orden_compra([], CLIENTE, {})

        resumen = resultado["resumen_financiero"]
        for clave in ("subtotal_bruto", "total_descuentos", "subtotal_neto",
                      "total_iva", "costo_envio", "gran_total"):
            with self.subTest(campo=clave):
                self.assertEqual(resumen[clave], 0)
        self.assertFalse(resultado["logistica"]["requiere_envio"])
        self.assertEqual(resultado["detalle_articulos"], [])


class ReceiptMetadataTests(unittest.TestCase):
    """TC-16: receipt metadata (customer data, order number, date)."""

    def test_TC_16_receipt_metadata_is_built_from_customer_and_clock(self):
        timestamp = int(_FixedDateTime(*FIXED_NOW).timestamp())
        carrito = [_item(precio=10)]

        with self.subTest("customer id and email are copied"):
            with _patch_now(carrito_a):
                resultado = carrito_a.procesar_orden_compra(
                    carrito, CLIENTE, {}
                )
            metadata = resultado["metadata"]
            self.assertEqual(metadata["cliente_id"], 7)
            self.assertEqual(metadata["cliente_email"], "cliente@example.com")
            self.assertEqual(metadata["orden"], f"ORD-7-{timestamp}")
            self.assertEqual(metadata["fecha"], "2024-01-02 03:04:05")

        with self.subTest("missing customer id falls back to 000"):
            with _patch_now(carrito_a):
                resultado = carrito_a.procesar_orden_compra(
                    carrito, {"email": "cliente@example.com"}, {}
                )
            metadata = resultado["metadata"]
            self.assertIsNone(metadata["cliente_id"])
            self.assertEqual(metadata["orden"], f"ORD-000-{timestamp}")


class DuplicateModuleConsistencyTests(unittest.TestCase):
    """TC-17: carrito_a, carrito_b and carrito_c return identical results."""

    def test_TC_17_duplicate_modules_return_identical_results(self):
        escenarios = [
            ([], {}),
            ([_item(precio=100, cantidad=2, descuento=10, peso_kg=3)], {}),
            (
                [_item(precio=33.33, peso_kg=12),
                 _item(sku="OFF", activo=False, precio=10)],
                {"zona_fronteriza": True},
            ),
            ([_item(precio=2000, peso_kg=12)], {"minimo_envio_gratis": 2000}),
        ]
        modulos = [carrito_a, carrito_b, carrito_c]

        for carrito, configuracion in escenarios:
            with self.subTest(carrito=carrito, configuracion=configuracion):
                resultados = []
                for modulo in modulos:
                    with _patch_now(modulo):
                        res = modulo.procesar_orden_compra(
                            [dict(i) for i in carrito],
                            dict(CLIENTE),
                            dict(configuracion),
                        )
                    res["metadata"].pop("orden")
                    resultados.append(res)
                self.assertEqual(resultados[0], resultados[1])
                self.assertEqual(resultados[0], resultados[2])


if __name__ == "__main__":
    unittest.main()
