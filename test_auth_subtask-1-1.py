"""Unit tests for subtask-1-1 (Consolidate authentication modules).

Covers the authentication flow in auth.py (validar_y_autenticar_usuario).
Run from the repository root with:
    python -m unittest discover -s . -p "test_auth_subtask-1-1.py"
"""

import hashlib
import re
import unittest
from unittest import mock

import auth
import auth_local
import auth_nube


PASSWORD = "clave-segura-123"
SALT = "sal123"
PASSWORD_HASH = hashlib.sha256(f"{PASSWORD}{SALT}".encode("utf-8")).hexdigest()


def _registro(intentos_fallidos=0, usuario_id=42):
    return {
        "id": usuario_id,
        "intentos_fallidos": intentos_fallidos,
        "salt": SALT,
        "password_hash": PASSWORD_HASH,
    }


def _base_datos(registro=None):
    db = mock.Mock()
    db.buscar_usuario = mock.Mock(return_value=registro)
    db.incrementar_intento_fallido = mock.Mock()
    db.resetear_intentos_fallidos = mock.Mock()
    return db


def _patch_now(module, timestamp=1700000000.5):
    """Replace the datetime module used by `module` with a fixed clock."""
    fake_dt = mock.MagicMock()
    fake_dt.datetime.now.return_value.timestamp.return_value = timestamp
    return mock.patch.object(module, "datetime", fake_dt)


class AuthValidationTests(unittest.TestCase):
    """AC-1: input validation (400 errors) and unknown user (401)."""

    def test_TC_01_missing_or_empty_credentials_return_400_without_lookup(self):
        casos = [
            {"password": PASSWORD},
            {"username": "alice"},
            {"username": "", "password": PASSWORD},
            {"username": "alice", "password": ""},
            {"username": "   ", "password": PASSWORD},
        ]
        for datos in casos:
            with self.subTest(datos=datos):
                db = _base_datos(_registro())
                resultado = auth.validar_y_autenticar_usuario(datos, db, {})
                self.assertFalse(resultado["exito"])
                self.assertEqual(resultado["codigo"], 400)
                db.buscar_usuario.assert_not_called()

    def test_TC_02_password_with_7_characters_returns_400_without_lookup(self):
        db = _base_datos(_registro())
        datos = {"username": "alice", "password": "1234567"}

        resultado = auth.validar_y_autenticar_usuario(datos, db, {})

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 400)
        self.assertEqual(resultado["error"], "La contraseña es muy corta")
        db.buscar_usuario.assert_not_called()

    def test_TC_03_password_with_exactly_8_characters_proceeds_to_lookup(self):
        db = _base_datos(None)
        datos = {"username": "alice", "password": "12345678"}

        auth.validar_y_autenticar_usuario(datos, db, {})

        db.buscar_usuario.assert_called_once_with("alice")

    def test_TC_04_invalid_email_format_returns_400_without_lookup(self):
        for usuario in ["user@", "a@b"]:
            with self.subTest(usuario=usuario):
                db = _base_datos(_registro())
                datos = {"username": usuario, "password": PASSWORD}

                resultado = auth.validar_y_autenticar_usuario(datos, db, {})

                self.assertFalse(resultado["exito"])
                self.assertEqual(resultado["codigo"], 400)
                self.assertEqual(resultado["error"], "Formato de correo inválido")
                db.buscar_usuario.assert_not_called()

    def test_TC_05_valid_email_with_valid_password_proceeds_to_lookup(self):
        db = _base_datos(None)
        datos = {"username": "user@example.com", "password": PASSWORD}

        auth.validar_y_autenticar_usuario(datos, db, {})

        db.buscar_usuario.assert_called_once_with("user@example.com")

    def test_TC_06_username_is_stripped_before_lookup(self):
        db = _base_datos(None)
        datos = {"username": "  alice  ", "password": PASSWORD}

        auth.validar_y_autenticar_usuario(datos, db, {})

        db.buscar_usuario.assert_called_once_with("alice")

    def test_TC_07_unknown_user_returns_401_invalid_credentials(self):
        db = _base_datos(None)
        datos = {"username": "ghost", "password": PASSWORD}

        resultado = auth.validar_y_autenticar_usuario(datos, db, {})

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 401)
        self.assertEqual(resultado["error"], "Credenciales inválidas")


class AccountBlockingTests(unittest.TestCase):
    """AC-2: account blocked after max failed attempts (403)."""

    def test_TC_08_attempts_at_default_max_return_403_without_hash_check_or_writes(self):
        db = _base_datos(_registro(intentos_fallidos=5))
        datos = {"username": "alice", "password": PASSWORD}

        resultado = auth.validar_y_autenticar_usuario(datos, db, {})

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 403)
        self.assertEqual(resultado["error"], "Cuenta bloqueada temporalmente")
        db.incrementar_intento_fallido.assert_not_called()
        db.resetear_intentos_fallidos.assert_not_called()

    def test_TC_09_attempts_one_below_max_with_correct_credentials_succeeds(self):
        db = _base_datos(_registro(intentos_fallidos=4))
        datos = {"username": "alice", "password": PASSWORD}

        with _patch_now(auth):
            resultado = auth.validar_y_autenticar_usuario(datos, db, {})

        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)

    def test_TC_10_custom_max_intentos_login_is_honored(self):
        db = _base_datos(_registro(intentos_fallidos=3))
        datos = {"username": "alice", "password": PASSWORD}
        configuracion = {"max_intentos_login": 3}

        resultado = auth.validar_y_autenticar_usuario(datos, db, configuracion)

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 403)
        self.assertEqual(resultado["error"], "Cuenta bloqueada temporalmente")


class SuccessfulAuthenticationTests(unittest.TestCase):
    """AC-3: successful cryptographic verification, token and counter reset."""

    def test_TC_11_correct_password_succeeds_resets_counter_and_skips_increment(self):
        db = _base_datos(_registro(intentos_fallidos=0))
        datos = {"username": "alice", "password": PASSWORD}

        with _patch_now(auth):
            resultado = auth.validar_y_autenticar_usuario(datos, db, {})

        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)
        self.assertEqual(resultado["mensaje"], "Autenticación exitosa")
        db.resetear_intentos_fallidos.assert_called_once_with("alice")
        db.incrementar_intento_fallido.assert_not_called()

    def test_TC_12_session_token_is_md5_of_username_and_timestamp(self):
        timestamp = 1700000000.5
        db = _base_datos(_registro())
        datos = {"username": "alice", "password": PASSWORD}

        with _patch_now(auth, timestamp):
            resultado = auth.validar_y_autenticar_usuario(datos, db, {})

        token = resultado["datos_sesion"]["token"]
        self.assertTrue(token)
        self.assertRegex(token, re.compile(r"^[0-9a-f]{32}$"))
        esperado = hashlib.md5(f"alice{timestamp}".encode()).hexdigest()
        self.assertEqual(token, esperado)

    def test_TC_13_session_data_contains_user_id_and_expiry(self):
        datos = {"username": "alice", "password": PASSWORD}

        with self.subTest("default expiry"):
            db = _base_datos(_registro(usuario_id=42))
            with _patch_now(auth):
                resultado = auth.validar_y_autenticar_usuario(datos, db, {})
            self.assertEqual(resultado["datos_sesion"]["usuario_id"], 42)
            self.assertEqual(resultado["datos_sesion"]["expira_en"], 3600)

        with self.subTest("configured expiry"):
            db = _base_datos(_registro(usuario_id=42))
            with _patch_now(auth):
                resultado = auth.validar_y_autenticar_usuario(
                    datos, db, {"tiempo_sesion_minutos": 30}
                )
            self.assertEqual(resultado["datos_sesion"]["expira_en"], 30 * 60)

    def test_TC_14_wrong_password_returns_401_and_records_failed_attempt(self):
        db = _base_datos(_registro(intentos_fallidos=0))
        datos = {"username": "alice", "password": "contraseña-incorrecta"}

        resultado = auth.validar_y_autenticar_usuario(datos, db, {})

        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 401)
        db.incrementar_intento_fallido.assert_called_once_with("alice")
        db.resetear_intentos_fallidos.assert_not_called()


class ConsolidationTests(unittest.TestCase):
    """User Story #1: duplicated modules must behave identically."""

    def test_TC_15_auth_modules_return_identical_results_for_same_inputs(self):
        escenarios = [
            ({"username": "", "password": PASSWORD}, None, {}),
            ({"username": "alice", "password": "short"}, None, {}),
            ({"username": "user@", "password": PASSWORD}, None, {}),
            ({"username": "ghost", "password": PASSWORD}, None, {}),
            ({"username": "alice", "password": PASSWORD}, _registro(5), {}),
            ({"username": "alice", "password": PASSWORD}, _registro(0), {}),
            ({"username": "alice", "password": "incorrecta-1"}, _registro(0), {}),
        ]
        modulos = [auth, auth_local, auth_nube]

        for datos, registro, config in escenarios:
            with self.subTest(datos=datos, registro=registro):
                resultados = []
                for modulo in modulos:
                    db = _base_datos(registro)
                    # auth_local/auth_nube re-export auth.py, so the clock to patch is auth's.
                    with _patch_now(auth):
                        res = modulo.validar_y_autenticar_usuario(
                            dict(datos), db, dict(config)
                        )
                    if "datos_sesion" in res:
                        res["datos_sesion"].pop("token")
                    resultados.append(res)
                self.assertEqual(resultados[0], resultados[1])
                self.assertEqual(resultados[0], resultados[2])


if __name__ == "__main__":
    unittest.main()
