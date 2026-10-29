"""Unit tests for shopping cart processing (subtask-2-1, User Story #2).

Run from the repository root:
    python -m unittest tests.test_carrito_a -v

Scope: procesar_orden_compra in carrito_a.py. carrito_b.py and carrito_c.py are
duplicates and are not covered here.
"""
import datetime as dt
import unittest
from unittest import mock

import carrito_a
from carrito_a import procesar_orden_compra


CLIENTE = {"id": 15, "email": "cliente@dominio.com"}
TIENDA = {"zona_fronteriza": False}
FECHA_FIJA = dt.datetime(2024, 3, 10, 14, 30, 5)


def item(precio=100, cantidad=1, peso=0, descuento=0, **extra):
    base = {
        "sku": "SKU-1",
        "nombre": "Producto",
        "precio": precio,
        "cantidad": cantidad,
        "peso_kg": peso,
        "descuento": descuento,
    }
    base.update(extra)
    return base


def procesar(carrito, cliente=None, tienda=None):
    """Calls the function with a fixed clock so the output is deterministic."""
    with mock.patch.object(carrito_a, "datetime") as datetime_mock:
        datetime_mock.datetime.now.return_value = FECHA_FIJA
        return procesar_orden_compra(
            carrito,
            cliente if cliente is not None else CLIENTE,
            tienda if tienda is not None else TIENDA,
        )


class TestSubtotalDescuentosIva(unittest.TestCase):
    """UT-subtask-2-1-US-2-AC-1: subtotal, item discounts and IVA."""

    def test_UT_2_1_01_item_con_descuento_10_y_iva_16(self):
        resultado = procesar([item(precio=100, cantidad=2, descuento=10)])

        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["subtotal_bruto"], 200.00)
        self.assertEqual(resumen["total_descuentos"], 20.00)
        self.assertEqual(resumen["subtotal_neto"], 180.00)
        self.assertEqual(resumen["total_iva"], 28.80)

    def test_UT_2_1_02_zona_fronteriza_aplica_iva_8(self):
        resultado = procesar(
            [item(precio=100, cantidad=2, descuento=10)],
            tienda={"zona_fronteriza": True},
        )

        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["total_iva"], 14.40)
        self.assertNotEqual(resumen["total_iva"], 28.80)

    def test_UT_2_1_03_bandera_ausente_o_falsa_aplica_iva_16(self):
        configuraciones = [{}, {"zona_fronteriza": False}, {"zona_fronteriza": None}]
        for tienda in configuraciones:
            with self.subTest(tienda=tienda):
                resultado = procesar(
                    [item(precio=100, cantidad=2, descuento=10)], tienda=tienda
                )
                self.assertAlmostEqual(
                    resultado["resumen_financiero"]["total_iva"], 28.80, places=2
                )

    def test_UT_2_1_04_varios_items_acumulan_totales(self):
        carrito = [
            item(precio=100, cantidad=2, descuento=10, sku="A"),
            item(precio=50, cantidad=3, descuento=0, sku="B"),
            item(precio=20, cantidad=1, descuento=25, sku="C"),
        ]

        resultado = procesar(carrito)

        detalle = resultado["detalle_articulos"]
        resumen = resultado["resumen_financiero"]
        self.assertEqual(len(detalle), 3)
        self.assertAlmostEqual(
            resumen["subtotal_bruto"], sum(d["subtotal"] for d in detalle), places=2
        )
        self.assertAlmostEqual(
            resumen["total_descuentos"], sum(d["descuento_aplicado"] for d in detalle), places=2
        )
        self.assertAlmostEqual(
            resumen["total_iva"], sum(d["iva"] for d in detalle), places=2
        )
        self.assertEqual(resumen["subtotal_bruto"], 370.00)
        self.assertEqual(resumen["total_descuentos"], 25.00)

    def test_UT_2_1_05_items_inactivos_se_excluyen(self):
        carrito = [
            item(precio=100, sku="ACTIVO"),
            item(precio=999, peso=20, sku="INACTIVO", activo=False),
        ]

        resultado = procesar(carrito)

        self.assertEqual(resultado["resumen_financiero"]["subtotal_bruto"], 100.00)
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 0)
        self.assertEqual(len(resultado["detalle_articulos"]), 1)
        self.assertEqual(resultado["detalle_articulos"][0]["sku"], "ACTIVO")

    def test_UT_2_1_06_campos_opcionales_usan_valores_por_defecto(self):
        resultado = procesar([{"precio": 100}])

        detalle = resultado["detalle_articulos"][0]
        self.assertEqual(detalle["cantidad"], 1)
        self.assertEqual(detalle["descuento_aplicado"], 0)
        self.assertEqual(detalle["sku"], "UNKNOWN")
        self.assertEqual(detalle["nombre"], "Producto Sin Nombre")
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 0)
        self.assertEqual(resultado["resumen_financiero"]["subtotal_bruto"], 100.00)

    def test_UT_2_1_07_descuento_100_por_ciento_da_neto_y_iva_cero(self):
        resultado = procesar([item(precio=100, cantidad=2, descuento=100)])

        resumen = resultado["resumen_financiero"]
        self.assertEqual(resumen["subtotal_neto"], 0.00)
        self.assertEqual(resumen["total_iva"], 0.00)

    def test_UT_2_1_08_gran_total_es_neto_mas_iva_mas_envio(self):
        resultado = procesar([item(precio=100, cantidad=2, descuento=10, peso=1)])

        resumen = resultado["resumen_financiero"]
        self.assertAlmostEqual(
            resumen["gran_total"],
            resumen["subtotal_neto"] + resumen["total_iva"] + resumen["costo_envio"],
            places=2,
        )
        self.assertAlmostEqual(resumen["gran_total"], 180.00 + 28.80 + 150.00, places=2)

    def test_UT_2_1_09_carrito_vacio_devuelve_totales_en_cero(self):
        resultado = procesar([])

        resumen = resultado["resumen_financiero"]
        for campo in ["subtotal_bruto", "total_descuentos", "subtotal_neto",
                      "total_iva", "costo_envio", "gran_total"]:
            with self.subTest(campo=campo):
                self.assertEqual(resumen[campo], 0)
        self.assertFalse(resultado["logistica"]["requiere_envio"])
        self.assertEqual(resultado["detalle_articulos"], [])


class TestLogisticaEnvio(unittest.TestCase):
    """UT-subtask-2-1-US-2-AC-2: base rate, excess-weight surcharge and free shipping."""

    def test_UT_2_1_10_peso_5kg_cobra_solo_tarifa_base(self):
        resultado = procesar([item(precio=100, peso=5)])

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_UT_2_1_11_peso_exacto_10kg_no_tiene_recargo(self):
        resultado = procesar([item(precio=100, peso=10)])

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_UT_2_1_12_peso_10_5kg_agrega_recargo_por_kilo_extra(self):
        resultado = procesar([item(precio=100, peso=10.5)])

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 157.75)

    def test_UT_2_1_13_recargo_usa_peso_por_cantidad(self):
        resultado = procesar([item(precio=100, cantidad=2, peso=6)])

        self.assertEqual(resultado["logistica"]["peso_total_kg"], 12.00)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 181.00)

    def test_UT_2_1_14_peso_cero_no_tiene_envio(self):
        resultado = procesar([item(precio=100, peso=0)])

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)
        self.assertFalse(resultado["logistica"]["requiere_envio"])
        self.assertEqual(resultado["logistica"]["peso_total_kg"], 0)

    def test_UT_2_1_15_neto_exacto_en_umbral_envia_gratis(self):
        resultado = procesar([item(precio=1000, cantidad=2, peso=1)])

        self.assertEqual(resultado["resumen_financiero"]["subtotal_neto"], 2000.00)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)
        self.assertTrue(resultado["logistica"]["requiere_envio"])

    def test_UT_2_1_16_neto_justo_debajo_del_umbral_se_cobra(self):
        resultado = procesar([item(precio=1999.99, peso=1)])

        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_UT_2_1_17_envio_gratis_anula_recargo_por_peso(self):
        resultado = procesar([item(precio=2000, cantidad=1, peso=12)])

        self.assertEqual(resultado["logistica"]["peso_total_kg"], 12.00)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 0)

    def test_UT_2_1_18_umbral_se_evalua_despues_de_descuentos(self):
        resultado = procesar([item(precio=2100, peso=1, descuento=10)])

        self.assertEqual(resultado["resumen_financiero"]["subtotal_neto"], 1890.00)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)

    def test_UT_2_1_19_tarifa_y_minimo_personalizados_se_respetan(self):
        tienda = {"tarifa_envio_base": 80.0, "minimo_envio_gratis": 500.0}

        cobrado = procesar([item(precio=499.99, peso=1)], tienda=tienda)
        gratis = procesar([item(precio=500, peso=1)], tienda=tienda)

        self.assertEqual(cobrado["resumen_financiero"]["costo_envio"], 80.00)
        self.assertEqual(gratis["resumen_financiero"]["costo_envio"], 0)

    def test_UT_2_1_23_descuento_100_con_peso_positivo_cobra_tarifa_base(self):
        # Characterization: behavior to confirm with the owner. The shipping
        # decision uses the weight, so a fully discounted order with weight
        # still pays the base rate. This test pins that current behavior.
        resultado = procesar([item(precio=100, peso=2, descuento=100)])

        self.assertEqual(resultado["resumen_financiero"]["subtotal_neto"], 0.00)
        self.assertEqual(resultado["resumen_financiero"]["costo_envio"], 150.00)


class TestMetadataYRedondeo(unittest.TestCase):
    """UT-subtask-2-1-US-2-AC-1: receipt metadata and rounding."""

    def test_UT_2_1_20_metadata_del_recibo(self):
        resultado = procesar([item(precio=100)])

        metadata = resultado["metadata"]
        self.assertEqual(metadata["fecha"], "2024-03-10 14:30:05")
        self.assertEqual(
            metadata["orden"], f"ORD-15-{int(FECHA_FIJA.timestamp())}"
        )
        self.assertEqual(metadata["cliente_id"], 15)
        self.assertEqual(metadata["cliente_email"], "cliente@dominio.com")

    def test_UT_2_1_21_cliente_sin_id_usa_000_en_la_orden(self):
        resultado = procesar([item(precio=100)], cliente={"email": "x@dominio.com"})

        self.assertTrue(resultado["metadata"]["orden"].startswith("ORD-000-"))
        self.assertIsNone(resultado["metadata"]["cliente_id"])
        self.assertEqual(resultado["metadata"]["cliente_email"], "x@dominio.com")

    def test_UT_2_1_22_valores_monetarios_con_dos_decimales(self):
        carrito = [
            item(precio=33.33, cantidad=3, descuento=7, peso=3.333, sku="A"),
            item(precio=19.99, cantidad=1, descuento=5, peso=0.7, sku="B"),
        ]

        resultado = procesar(carrito, tienda={"zona_fronteriza": True})

        for campo, valor in resultado["resumen_financiero"].items():
            with self.subTest(campo=campo):
                self.assertEqual(round(valor, 2), valor)
        self.assertEqual(round(resultado["logistica"]["peso_total_kg"], 2),
                         resultado["logistica"]["peso_total_kg"])


if __name__ == "__main__":
    unittest.main()
