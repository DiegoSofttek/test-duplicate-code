"""Unit tests for the consolidated authentication module (subtask-1-1, User Story #1).

Run from the repository root:
    python -m unittest tests.test_auth -v
"""
import hashlib
import importlib
import unittest
from unittest import mock

import auth
from auth import validar_y_autenticar_usuario


SALT = "sal-de-prueba"
PASSWORD = "Password123"
USERNAME = "usuario_prueba"
EMAIL_USERNAME = "persona@dominio.com"


def hash_de(password, salt=SALT):
    """Mirrors the production hashing algorithm exactly."""
    return hashlib.sha256(f"{password}{salt}".encode("utf-8")).hexdigest()


def registro(intentos=0, password=PASSWORD, salt=SALT, id_=42):
    return {
        "id": id_,
        "salt": salt,
        "password_hash": hash_de(password, salt),
        "intentos_fallidos": intentos,
    }


class FakeBaseDatos:
    """In-memory data-access fake exposing only the three contract methods.

    Any other attribute access raises AttributeError, which enforces that the
    module depends only on buscar_usuario, incrementar_intento_fallido and
    resetear_intentos_fallidos.
    """

    def __init__(self, registros=None):
        self.registros = dict(registros or {})
        self.llamadas = []

    def buscar_usuario(self, usuario):
        self.llamadas.append(("buscar_usuario", usuario))
        return self.registros.get(usuario)

    def incrementar_intento_fallido(self, usuario):
        self.llamadas.append(("incrementar_intento_fallido", usuario))
        self.registros[usuario]["intentos_fallidos"] = (
            self.registros[usuario].get("intentos_fallidos", 0) + 1
        )

    def resetear_intentos_fallidos(self, usuario):
        self.llamadas.append(("resetear_intentos_fallidos", usuario))
        self.registros[usuario]["intentos_fallidos"] = 0

    def nombres_llamadas(self):
        return [nombre for nombre, _ in self.llamadas]


def login(username, password, bd, config=None):
    return validar_y_autenticar_usuario(
        {"username": username, "password": password},
        bd,
        config if config is not None else {"max_intentos_login": 3, "tiempo_sesion_minutos": 30},
    )


class TestValidacionCampos(unittest.TestCase):
    """UT-subtask-1-1-US-1-AC-1: 400 for invalid input."""

    def test_AUTH_1_1_01_usuario_o_password_vacios_devuelven_400(self):
        casos = [
            {"username": "", "password": PASSWORD},
            {"username": "   ", "password": PASSWORD},
            {"username": USERNAME, "password": ""},
            {"password": PASSWORD},
            {"username": USERNAME},
        ]
        for datos in casos:
            with self.subTest(datos=datos):
                bd = FakeBaseDatos({USERNAME: registro()})
                resultado = validar_y_autenticar_usuario(datos, bd, {})
                self.assertFalse(resultado["exito"])
                self.assertEqual(resultado["codigo"], 400)
                self.assertNotIn("buscar_usuario", bd.nombres_llamadas())

    def test_AUTH_1_1_02_password_de_7_caracteres_devuelve_400(self):
        password_corta = "abcdefg"
        self.assertEqual(len(password_corta), 7)
        bd = FakeBaseDatos({USERNAME: registro(password=password_corta)})

        resultado = login(USERNAME, password_corta, bd)

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 400)
        self.assertEqual(resultado["error"], "La contraseña es muy corta")
        self.assertNotIn("buscar_usuario", bd.nombres_llamadas())

    def test_AUTH_1_1_03_password_de_8_caracteres_pasa_la_validacion(self):
        password_minima = "abcdefgh"
        self.assertEqual(len(password_minima), 8)
        bd = FakeBaseDatos({USERNAME: registro(password=password_minima)})

        resultado = login(USERNAME, password_minima, bd)

        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)
        self.assertIn("buscar_usuario", bd.nombres_llamadas())

    def test_AUTH_1_1_04_email_con_formato_invalido_devuelve_400(self):
        for usuario_invalido in ["user@domain", "a@@b.com", "@dominio.com", "usuario@dominio.c om"]:
            with self.subTest(usuario=usuario_invalido):
                bd = FakeBaseDatos({usuario_invalido: registro()})
                resultado = login(usuario_invalido, PASSWORD, bd)
                self.assertFalse(resultado["exito"])
                self.assertEqual(resultado["codigo"], 400)
                self.assertEqual(resultado["error"], "Formato de correo inválido")
                self.assertNotIn("buscar_usuario", bd.nombres_llamadas())

    def test_AUTH_1_1_05_email_valido_con_password_correcta_autentica(self):
        bd = FakeBaseDatos({EMAIL_USERNAME: registro()})

        resultado = login(EMAIL_USERNAME, PASSWORD, bd)

        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)

    def test_AUTH_1_1_06_usuario_con_espacios_se_normaliza(self):
        bd = FakeBaseDatos({USERNAME: registro()})

        resultado = login(f"  {USERNAME}  ", PASSWORD, bd)

        self.assertTrue(resultado["exito"])
        self.assertEqual(bd.llamadas[0], ("buscar_usuario", USERNAME))


class TestBloqueoPorIntentos(unittest.TestCase):
    """UT-subtask-1-1-US-1-AC-2: 401 for unknown users, 403 when blocked."""

    def test_AUTH_1_1_07_usuario_desconocido_devuelve_401_sin_modificar_contador(self):
        bd = FakeBaseDatos({})

        resultado = login(USERNAME, PASSWORD, bd)

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 401)
        self.assertNotIn("incrementar_intento_fallido", bd.nombres_llamadas())
        self.assertNotIn("resetear_intentos_fallidos", bd.nombres_llamadas())

    def test_AUTH_1_1_08_intentos_iguales_al_maximo_devuelven_403_aunque_la_clave_sea_correcta(self):
        bd = FakeBaseDatos({USERNAME: registro(intentos=3)})

        resultado = login(USERNAME, PASSWORD, bd, {"max_intentos_login": 3})

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 403)
        self.assertEqual(resultado["error"], "Cuenta bloqueada temporalmente")
        self.assertNotIn("resetear_intentos_fallidos", bd.nombres_llamadas())
        self.assertEqual(bd.registros[USERNAME]["intentos_fallidos"], 3)

    def test_AUTH_1_1_09_intentos_por_encima_del_maximo_devuelven_403(self):
        bd = FakeBaseDatos({USERNAME: registro(intentos=10)})

        resultado = login(USERNAME, PASSWORD, bd, {"max_intentos_login": 3})

        self.assertEqual(resultado["codigo"], 403)

    def test_AUTH_1_1_10_valores_por_defecto_max_5_intentos(self):
        bd_bloqueado = FakeBaseDatos({USERNAME: registro(intentos=5)})
        bd_permitido = FakeBaseDatos({USERNAME: registro(intentos=4)})

        bloqueado = validar_y_autenticar_usuario(
            {"username": USERNAME, "password": PASSWORD}, bd_bloqueado, {}
        )
        permitido = validar_y_autenticar_usuario(
            {"username": USERNAME, "password": PASSWORD}, bd_permitido, {}
        )

        self.assertEqual(bloqueado["codigo"], 403)
        self.assertEqual(permitido["codigo"], 200)

    def test_AUTH_1_1_10b_registro_sin_intentos_usa_cero_por_defecto(self):
        registro_sin_contador = registro()
        del registro_sin_contador["intentos_fallidos"]
        bd = FakeBaseDatos({USERNAME: registro_sin_contador})

        resultado = validar_y_autenticar_usuario(
            {"username": USERNAME, "password": PASSWORD}, bd, {}
        )

        self.assertEqual(resultado["codigo"], 200)

    def test_AUTH_1_1_11_un_intento_debajo_del_maximo_sigue_permitido(self):
        bd = FakeBaseDatos({USERNAME: registro(intentos=2)})

        resultado = login(USERNAME, PASSWORD, bd, {"max_intentos_login": 3})

        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)

    def test_AUTH_1_1_12_password_incorrecta_incrementa_contador_una_vez(self):
        bd = FakeBaseDatos({USERNAME: registro(intentos=0)})

        resultado = login(USERNAME, "ContraseñaErronea", bd)

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 401)
        self.assertEqual(
            [c for c in bd.llamadas if c[0] == "incrementar_intento_fallido"],
            [("incrementar_intento_fallido", USERNAME)],
        )
        self.assertNotIn("resetear_intentos_fallidos", bd.nombres_llamadas())
        self.assertEqual(bd.registros[USERNAME]["intentos_fallidos"], 1)


class TestAutenticacionExitosa(unittest.TestCase):
    """UT-subtask-1-1-US-1-AC-3: session token generated and counter reset."""

    def test_AUTH_1_1_13_password_correcta_autentica_y_resetea_contador(self):
        bd = FakeBaseDatos({USERNAME: registro(intentos=1)})

        resultado = login(USERNAME, PASSWORD, bd)

        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)
        self.assertEqual(resultado["mensaje"], "Autenticación exitosa")
        self.assertEqual(bd.nombres_llamadas().count("resetear_intentos_fallidos"), 1)
        self.assertNotIn("incrementar_intento_fallido", bd.nombres_llamadas())
        self.assertEqual(bd.registros[USERNAME]["intentos_fallidos"], 0)

    def test_AUTH_1_1_14_payload_de_sesion_con_duracion_personalizada(self):
        bd = FakeBaseDatos({USERNAME: registro(id_=77)})

        resultado = login(USERNAME, PASSWORD, bd, {"max_intentos_login": 3, "tiempo_sesion_minutos": 30})

        sesion = resultado["datos_sesion"]
        self.assertEqual(sesion["usuario_id"], 77)
        self.assertEqual(sesion["expira_en"], 30 * 60)
        self.assertRegex(sesion["token"], r"^[0-9a-f]{32}$")

    def test_AUTH_1_1_15_duracion_de_sesion_por_defecto_es_3600(self):
        bd = FakeBaseDatos({USERNAME: registro()})

        resultado = validar_y_autenticar_usuario(
            {"username": USERNAME, "password": PASSWORD}, bd, {}
        )

        self.assertEqual(resultado["datos_sesion"]["expira_en"], 3600)

    def test_AUTH_1_1_16_token_determinista_con_datetime_fijo(self):
        timestamp_fijo = 1700000000.5
        bd = FakeBaseDatos({USERNAME: registro()})

        with mock.patch.object(auth, "datetime") as datetime_mock:
            datetime_mock.datetime.now.return_value.timestamp.return_value = timestamp_fijo
            resultado = login(USERNAME, PASSWORD, bd)

        esperado = hashlib.md5(f"{USERNAME}{timestamp_fijo}".encode()).hexdigest()
        self.assertEqual(resultado["datos_sesion"]["token"], esperado)


class TestConsolidacionModulo(unittest.TestCase):
    """Consolidation goal: a single source of truth for the authentication logic."""

    def test_AUTH_1_1_17_auth_expone_la_funcion(self):
        self.assertTrue(callable(auth.validar_y_autenticar_usuario))

    def test_AUTH_1_1_17b_modulos_duplicados_no_redefinen_la_logica(self):
        for nombre in ["auth_local", "auth_nube"]:
            with self.subTest(modulo=nombre):
                try:
                    modulo = importlib.import_module(nombre)
                except ImportError:
                    continue  # Removed during consolidation: acceptable.
                funcion = getattr(modulo, "validar_y_autenticar_usuario", None)
                self.assertIsNotNone(funcion, f"{nombre} must re-export the function or be removed")
                self.assertIs(funcion, auth.validar_y_autenticar_usuario)


class TestContratoBaseDatos(unittest.TestCase):
    """UT-subtask-1-1-US-1: duck-typed data-access contract, no ORM or SQL."""

    def test_AUTH_1_1_18_solo_usa_los_tres_metodos_del_contrato(self):
        bd = FakeBaseDatos({USERNAME: registro(intentos=0)})

        login(USERNAME, PASSWORD, bd)
        login(USERNAME, "ContraseñaErronea", bd)

        self.assertTrue(set(bd.nombres_llamadas()) <= {
            "buscar_usuario",
            "incrementar_intento_fallido",
            "resetear_intentos_fallidos",
        })
        for nombre, argumento in bd.llamadas:
            self.assertEqual(argumento, USERNAME)


if __name__ == "__main__":
    unittest.main()
