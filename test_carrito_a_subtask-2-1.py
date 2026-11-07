"""Unit tests for subtask-2-1: robust cart processing in carrito_a.procesar_orden_compra.

Covers User Story #2 (AC-1: subtotal, discounts, 8%/16% IVA; AC-2: shipping rules).
Run from the repository root with:
    python -m unittest discover -p "test_carrito_a_subtask-2-1.py"
"""
import copy
import unittest
from unittest import mock

import carrito_a
import carrito_b
import carrito_c


CLIENTE = {"id": 42, "email": "cliente@example.com"}


def _config(**overrides):
    config = {"zona_fronteriza": False}
    config.update(overrides)
    return config


def _fake_datetime_module(fecha_texto="2024-01-02 03:04:05", timestamp=1700000000.0):
    fake = mock.MagicMock()
    fake.datetime.now.return_value.strftime.return_value = fecha_texto
    fake.datetime.now.return_value.timestamp.return_value = timestamp
    return fake


def _procesar(carrito, cliente=None, configuracion=None, module=carrito_a):
    """Runs the function with a deterministic clock (procesar_orden_compra is synchronous)."""
    with mock.patch.object(module, "datetime", _fake_datetime_module()):
        return module.procesar_orden_compra(
            carrito,
            CLIENTE if cliente is None else cliente,
            _config() if configuracion is None else configuracion,
        )


class TestCartAmountsAC1(unittest.TestCase):
    """AC-1: subtotal, item discounts, and 8%/16% IVA."""

    def test_TC_2_1_01_inactive_items_excluded(self):
        """TC-2-1-01: Inactive items are excluded from totals and detalle_articulos."""
        carrito = [
            {"sku": "A", "nombre": "Activo", "precio": 100, "peso_kg": 2, "activo": True},
            {"sku": "B", "nombre": "Inactivo", "precio": 500, "peso_kg": 5, "activo": False},
        ]
        resultado = _procesar(carrito)
        self.assertEqual(resultado["resumen_financiero"]["subtotal_bruto"], 100.0)
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 2.0)
        self.assertEqual(len(resultado["detalle_articulos"]), 1)
        self.assertEqual(resultado["detalle_articulos"][0]["sku"], "A")

    def test_TC_2_1_02_single_item_quantity_and_discount_standard_iva(self):
        """TC-2-1-02: 100 x 2 with 10% discount and 16% IVA, including the item detail."""
        carrito = [{"sku": "A", "precio": 100, "cantidad": 2, "descuento": 10}]
        resultado = _procesar(carrito)
        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["subtotal_bruto"], 200.00)
        self.assertEqual(resumen["total_descuentos"], 20.00)
        self.assertEqual(resumen["subtotal_neto"], 180.00)
        self.assertEqual(resumen["total_iva"], 28.80)
        self.assertEqual(resumen["gran_total"], 208.80)
        detalle = resultado["detalle_articulos"][0]
        self.assertAlmostEqual(detalle["iva"], 28.80, places=2)
        self.assertAlmostEqual(detalle["total_final"], 208.80, places=2)

    def test_TC_2_1_03_border_zone_uses_8_percent_iva(self):
        """TC-2-1-03: zona_fronteriza True applies 8% IVA (14.40) to the same cart."""
        carrito = [{"sku": "A", "precio": 100, "cantidad": 2, "descuento": 10}]
        resumen = _procesar(carrito, configuracion=_config(zona_fronteriza=True))["resumen_financiero"]
        self.assertEqual(resumen["total_iva"], 14.40)
        self.assertEqual(resumen["gran_total"], 194.40)

    def test_TC_2_1_04_multiple_items_different_discounts_border_iva(self):
        """TC-2-1-04: Totals are sums of per-item values; IVA is per item on discounted amounts."""
        carrito = [
            {"sku": "A", "precio": 100, "cantidad": 1, "descuento": 0},
            {"sku": "B", "precio": 50, "cantidad": 2, "descuento": 20},
        ]
        resultado = _procesar(carrito, configuracion=_config(zona_fronteriza=True))
        resumen = resultado["resumen_financiero"]
        detalle = resultado["detalle_articulos"]
        self.assertEqual(resumen["subtotal_bruto"], 200.00)
        self.assertEqual(resumen["total_descuentos"], 20.00)
        self.assertEqual(resumen["subtotal_neto"], 180.00)
        self.assertEqual(detalle[0]["iva"], 8.00)
        self.assertEqual(detalle[1]["iva"], 6.40)
        self.assertEqual(resumen["total_iva"], 14.40)

    def test_TC_2_1_05_missing_optional_fields_use_defaults(self):
        """TC-2-1-05: Missing cantidad, descuento, sku, nombre, activo use defaults; item included."""
        resultado = _procesar([{"precio": 100}])
        detalle = resultado["detalle_articulos"]
        self.assertEqual(len(detalle), 1)
        self.assertEqual(detalle[0]["cantidad"], 1)
        self.assertEqual(detalle[0]["descuento_aplicado"], 0)
        self.assertEqual(detalle[0]["sku"], "UNKNOWN")
        self.assertEqual(detalle[0]["nombre"], "Producto Sin Nombre")
        self.assertEqual(resultado["resumen_financiero"]["subtotal_bruto"], 100.00)

    def test_TC_2_1_06_empty_cart(self):
        """TC-2-1-06: Empty cart yields zero totals, zero shipping, no shipping required, no items."""
        resultado = _procesar([])
        resumen = resultado["resumen_financiero"]
        for clave in ("subtotal_bruto", "total_descuentos", "subtotal_neto", "total_iva", "gran_total"):
            with self.subTest(campo=clave):
                self.assertEqual(resumen[clave], 0)
        self.assertEqual(resumen["costo_envio"], 0)
        self.assertFalse(resultado["logistica"]["requiere_envio"])
        self.assertEqual(resultado["detalle_articulos"], [])


class TestShippingAC2(unittest.TestCase):
    """AC-2: base rate, excess weight surcharge, and free-shipping threshold."""

    def test_TC_2_1_07_weight_under_threshold_default_base_rate(self):
        """TC-2-1-07: 5 kg under the threshold costs the default base rate 150.00."""
        carrito = [{"precio": 100, "peso_kg": 5}]
        resultado = _procesar(carrito)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)
        self.assertTrue(resultado["logistica"]["requiere_envio"])

    def test_TC_2_1_08_custom_base_rate(self):
        """TC-2-1-08: Custom tarifa_envio_base is used as the shipping cost."""
        carrito = [{"precio": 100, "peso_kg": 5}]
        resultado = _procesar(carrito, configuracion=_config(tarifa_envio_base=200))
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 200.00)

    def test_TC_2_1_09_weight_exactly_10kg_no_surcharge(self):
        """TC-2-1-09: Exactly 10 kg has no excess-weight surcharge."""
        carrito = [{"precio": 100, "peso_kg": 10}]
        resultado = _procesar(carrito)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_TC_2_1_10_weight_12kg_applies_surcharge(self):
        """TC-2-1-10: 12 kg adds 2 x 15.50 over the base rate (181.00)."""
        carrito = [{"precio": 100, "peso_kg": 12}]
        resultado = _procesar(carrito)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 181.00)

    def test_TC_2_1_11_zero_weight_no_shipping(self):
        """TC-2-1-11: Zero weight (explicit 0 or missing peso_kg) gives no shipping even with a price."""
        carritos = [
            [{"precio": 500, "peso_kg": 0}],
            [{"precio": 500}],
        ]
        for carrito in carritos:
            with self.subTest(carrito=carrito):
                resultado = _procesar(carrito)
                self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)
                self.assertFalse(resultado["logistica"]["requiere_envio"])

    def test_TC_2_1_12_net_exactly_at_free_shipping_threshold(self):
        """TC-2-1-12: Net subtotal equal to minimo_envio_gratis (2000) gets free shipping."""
        carrito = [{"precio": 2000, "peso_kg": 5}]
        resultado = _procesar(carrito)
        self.assertEqual(resultado["resumen_financiero"]["subtotal_neto"], 2000.00)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_TC_2_1_13_net_just_below_free_shipping_threshold(self):
        """TC-2-1-13: Net subtotal 1999.99 is below the threshold, so the base rate applies."""
        carrito = [{"precio": 1999.99, "peso_kg": 5}]
        resultado = _procesar(carrito)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_TC_2_1_14_free_shipping_overrides_excess_weight_surcharge(self):
        """TC-2-1-14: Free shipping (net 2500) overrides the surcharge for 12 kg."""
        carrito = [{"precio": 2500, "peso_kg": 12}]
        resultado = _procesar(carrito)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_TC_2_1_15_gran_total_composition(self):
        """TC-2-1-15: gran_total equals subtotal_neto + total_iva + costo_envio, rounded to 2 decimals."""
        carrito = [{"precio": 100, "cantidad": 2, "descuento": 10, "peso_kg": 5}]
        resumen = _procesar(carrito)["resumen_financiero"]
        self.assertEqual(resumen["subtotal_neto"], 180.00)
        self.assertEqual(resumen["total_iva"], 28.80)
        self.assertEqual(resumen["costo_envio"], 150.00)
        self.assertEqual(resumen["gran_total"], 358.80)
        esperado = round(resumen["subtotal_neto"] + resumen["total_iva"] + resumen["costo_envio"], 2)
        self.assertEqual(resumen["gran_total"], esperado)


class TestReceiptAndRoundingAC1(unittest.TestCase):
    """AC-1: receipt metadata and rounding of monetary outputs."""

    def test_TC_2_1_16_receipt_metadata(self):
        """TC-2-1-16: fecha from strftime, orden uses id and timestamp, client fields copied."""
        cliente = {"id": 42, "email": "cliente@example.com"}
        carrito = [{"precio": 100}]
        with mock.patch.object(carrito_a, "datetime", _fake_datetime_module(
            fecha_texto="2024-05-06 07:08:09", timestamp=1700000123.7
        )):
            resultado = carrito_a.procesar_orden_compra(carrito, cliente, _config())
        metadata = resultado["metadata"]
        self.assertEqual(metadata["fecha"], "2024-05-06 07:08:09")
        self.assertEqual(metadata["orden"], "ORD-42-1700000123")
        self.assertEqual(metadata["cliente_id"], 42)
        self.assertEqual(metadata["cliente_email"], "cliente@example.com")

    def test_TC_2_1_17_monetary_outputs_are_rounded_to_two_decimals(self):
        """TC-2-1-17: Fractional inputs produce outputs equal to round(x, 2)."""
        carrito = [{"sku": "F", "precio": 33.335, "cantidad": 3, "descuento": 7, "peso_kg": 0}]
        resumen = _procesar(carrito)["resumen_financiero"]
        bruto = 33.335 * 3
        descuento = bruto * 0.07
        neto = bruto - descuento
        iva = neto * 0.16
        self.assertEqual(resumen["subtotal_bruto"], round(bruto, 2))
        self.assertEqual(resumen["total_descuentos"], round(descuento, 2))
        self.assertEqual(resumen["subtotal_neto"], round(neto, 2))
        self.assertEqual(resumen["total_iva"], round(iva, 2))
        self.assertEqual(resumen["gran_total"], round(neto + iva, 2))


class TestInputIsolation(unittest.TestCase):
    """AC-1/AC-2: the function does not mutate its inputs."""

    def test_TC_2_1_18_cart_and_config_not_mutated(self):
        """TC-2-1-18: Cart and configuration dicts are equal before and after the call."""
        carrito = [
            {"sku": "A", "nombre": "Uno", "precio": 100, "cantidad": 2, "peso_kg": 12,
             "descuento": 10, "activo": True},
            {"sku": "B", "precio": 50, "peso_kg": 1, "activo": False},
        ]
        configuracion = _config(zona_fronteriza=True, tarifa_envio_base=160, minimo_envio_gratis=3000)
        carrito_original = copy.deepcopy(carrito)
        configuracion_original = copy.deepcopy(configuracion)
        _procesar(carrito, configuracion=configuracion)
        self.assertEqual(carrito, carrito_original)
        self.assertEqual(configuracion, configuracion_original)


class TestConsolidationEquivalence(unittest.TestCase):
    """Consolidation regression: carrito_b and carrito_c match carrito_a."""

    def test_TC_2_1_19_copies_match_carrito_a(self):
        """TC-2-1-19: carrito_b and carrito_c return the same result dict as carrito_a."""
        carrito = [
            {"sku": "A", "nombre": "Uno", "precio": 100, "cantidad": 2, "peso_kg": 12, "descuento": 10},
            {"sku": "B", "nombre": "Dos", "precio": 50, "peso_kg": 1, "activo": False},
        ]
        configuracion = _config(zona_fronteriza=True)
        resultado_a = _procesar(copy.deepcopy(carrito), configuracion=configuracion, module=carrito_a)
        resultado_b = _procesar(copy.deepcopy(carrito), configuracion=configuracion, module=carrito_b)
        resultado_c = _procesar(copy.deepcopy(carrito), configuracion=configuracion, module=carrito_c)
        self.assertEqual(resultado_a, resultado_b)
        self.assertEqual(resultado_a, resultado_c)


if __name__ == "__main__":
    unittest.main()
