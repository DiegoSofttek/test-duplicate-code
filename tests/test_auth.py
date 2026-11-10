"""Unit tests for the consolidated authentication module (subtask-1-1, US#1).

Covers UT-subtask-1-1-US-1-AC-1, AC-2 and AC-3 against auth.validar_y_autenticar_usuario.
The database collaborator is a fake; no real persistence is used.
"""
import hashlib
import importlib
import os
import re
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import auth  # noqa: E402

validar_y_autenticar_usuario = auth.validar_y_autenticar_usuario

SALT = "pepper123"
PASSWORD = "Secret-pass1"  # 11 chars, valid
USER = "alice"


def hash_de(password, salt=SALT):
    return hashlib.sha256(f"{password}{salt}".encode("utf-8")).hexdigest()


def registro(intentos=0, password=PASSWORD, salt=SALT, user_id=42):
    return {
        "id": user_id,
        "salt": salt,
        "password_hash": hash_de(password, salt),
        "intentos_fallidos": intentos,
    }


def fake_db(registro_usuario=None):
    db = mock.Mock()
    db.buscar_usuario.return_value = registro_usuario
    return db


class AuthBaseTestCase(unittest.TestCase):
    def assertError(self, resultado, codigo, mensaje=None):
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], codigo)
        self.assertIn("error", resultado)
        if mensaje is not None:
            self.assertEqual(resultado["error"], mensaje)


class TestInputValidationAC1(AuthBaseTestCase):
    """UT-subtask-1-1-US-1-AC-1: 400 for short password or invalid email."""

    def test_auth_01_missing_username_returns_400_without_db_calls(self):
        db = fake_db(registro())
        r = validar_y_autenticar_usuario({"username": "", "password": PASSWORD}, db, {})
        self.assertError(r, 400, "Usuario y contraseña son requeridos")
        db.buscar_usuario.assert_not_called()

    def test_auth_01_missing_password_returns_400_without_db_calls(self):
        db = fake_db(registro())
        r = validar_y_autenticar_usuario({"username": USER}, db, {})
        self.assertError(r, 400, "Usuario y contraseña son requeridos")
        db.buscar_usuario.assert_not_called()

    def test_auth_01_empty_password_returns_400(self):
        db = fake_db(registro())
        r = validar_y_autenticar_usuario({"username": USER, "password": ""}, db, {})
        self.assertError(r, 400, "Usuario y contraseña son requeridos")
        db.buscar_usuario.assert_not_called()

    def test_auth_02_password_of_7_chars_returns_400(self):
        db = fake_db(registro())
        r = validar_y_autenticar_usuario({"username": USER, "password": "1234567"}, db, {})
        self.assertError(r, 400, "La contraseña es muy corta")
        db.buscar_usuario.assert_not_called()

    def test_auth_03_password_of_exactly_8_chars_passes_length_check(self):
        pwd = "12345678"
        db = fake_db(registro(password=pwd))
        r = validar_y_autenticar_usuario({"username": USER, "password": pwd}, db, {})
        self.assertTrue(r["exito"])
        db.buscar_usuario.assert_called_once_with(USER)

    def test_auth_04_invalid_email_formats_return_400_without_db_calls(self):
        for bad in ["bad@", "a@b", "a b@x.com", "@example.com", "x@y..com@"]:
            with self.subTest(username=bad):
                db = fake_db(registro())
                r = validar_y_autenticar_usuario(
                    {"username": bad, "password": PASSWORD}, db, {}
                )
                self.assertError(r, 400, "Formato de correo inválido")
                db.buscar_usuario.assert_not_called()

    def test_auth_05_valid_email_passes_validation(self):
        email = "user.name+tag@mail.example.com"
        db = fake_db(registro(password=PASSWORD))
        r = validar_y_autenticar_usuario({"username": email, "password": PASSWORD}, db, {})
        self.assertTrue(r["exito"])
        db.buscar_usuario.assert_called_once_with(email)

    def test_auth_06_username_is_stripped_before_lookup(self):
        db = fake_db(registro())
        validar_y_autenticar_usuario({"username": "  alice  ", "password": PASSWORD}, db, {})
        db.buscar_usuario.assert_called_once_with(USER)


class TestAccountBlockingAC2(AuthBaseTestCase):
    """UT-subtask-1-1-US-1-AC-2: 403 when max failed attempts reached."""

    def test_auth_07_unknown_user_returns_401_without_counter_changes(self):
        db = fake_db(None)
        r = validar_y_autenticar_usuario({"username": USER, "password": PASSWORD}, db, {})
        self.assertError(r, 401, "Credenciales inválidas")
        db.incrementar_intento_fallido.assert_not_called()
        db.resetear_intentos_fallidos.assert_not_called()

    def test_auth_08_default_max_attempts_blocks_with_403(self):
        db = fake_db(registro(intentos=5))
        r = validar_y_autenticar_usuario({"username": USER, "password": PASSWORD}, db, {})
        self.assertError(r, 403, "Cuenta bloqueada temporalmente")
        db.resetear_intentos_fallidos.assert_not_called()
        db.incrementar_intento_fallido.assert_not_called()

    def test_auth_08_blocked_account_does_not_check_password(self):
        db = fake_db(registro(intentos=5))
        with mock.patch.object(auth.hashlib, "sha256") as sha:
            r = validar_y_autenticar_usuario(
                {"username": USER, "password": "wrong-password"}, db, {}
            )
        self.assertError(r, 403)
        sha.assert_not_called()

    def test_auth_09_custom_max_attempts_is_honored(self):
        db = fake_db(registro(intentos=3))
        r = validar_y_autenticar_usuario(
            {"username": USER, "password": PASSWORD}, db, {"max_intentos_login": 3}
        )
        self.assertError(r, 403, "Cuenta bloqueada temporalmente")

    def test_auth_09_custom_higher_max_overrides_default_block(self):
        db = fake_db(registro(intentos=5))
        r = validar_y_autenticar_usuario(
            {"username": USER, "password": PASSWORD}, db, {"max_intentos_login": 10}
        )
        self.assertTrue(r["exito"])

    def test_auth_10_one_below_max_is_not_blocked(self):
        db = fake_db(registro(intentos=4))
        r = validar_y_autenticar_usuario({"username": USER, "password": PASSWORD}, db, {})
        self.assertTrue(r["exito"])
        self.assertEqual(r["codigo"], 200)


class TestCredentialsAndSessionAC3(AuthBaseTestCase):
    """UT-subtask-1-1-US-1-AC-3: session on success, counter reset; failure increments."""

    def test_auth_11_wrong_password_returns_401_and_increments_counter(self):
        db = fake_db(registro())
        r = validar_y_autenticar_usuario(
            {"username": USER, "password": "WrongPassword9"}, db, {}
        )
        self.assertError(r, 401, "Credenciales inválidas")
        db.incrementar_intento_fallido.assert_called_once_with(USER)
        db.resetear_intentos_fallidos.assert_not_called()

    def test_auth_12_correct_password_resets_counter_and_succeeds(self):
        db = fake_db(registro(intentos=2))
        r = validar_y_autenticar_usuario({"username": USER, "password": PASSWORD}, db, {})
        self.assertTrue(r["exito"])
        self.assertEqual(r["codigo"], 200)
        self.assertEqual(r["mensaje"], "Autenticación exitosa")
        db.resetear_intentos_fallidos.assert_called_once_with(USER)
        db.incrementar_intento_fallido.assert_not_called()

    def test_auth_13_session_payload_defaults(self):
        db = fake_db(registro(user_id=42))
        r = validar_y_autenticar_usuario({"username": USER, "password": PASSWORD}, db, {})
        sesion = r["datos_sesion"]
        self.assertRegex(sesion["token"], re.compile(r"^[0-9a-f]{32}$"))
        self.assertEqual(sesion["usuario_id"], 42)
        self.assertEqual(sesion["expira_en"], 3600)

    def test_auth_13_session_expiry_uses_configured_minutes(self):
        db = fake_db(registro(user_id=7))
        r = validar_y_autenticar_usuario(
            {"username": USER, "password": PASSWORD},
            db,
            {"tiempo_sesion_minutos": 15},
        )
        self.assertEqual(r["datos_sesion"]["expira_en"], 900)
        self.assertEqual(r["datos_sesion"]["usuario_id"], 7)


class TestConsolidationRegressionAUTH14(unittest.TestCase):
    """UT-subtask-1-1 consolidation: duplicates removed or re-exported from auth.py."""

    def _module_or_none(self, name):
        try:
            return importlib.import_module(name)
        except ImportError:
            return None

    def test_auth_14_duplicate_modules_removed_or_reexport_canonical_callable(self):
        for name in ("auth_local", "auth_nube"):
            with self.subTest(module=name):
                mod = self._module_or_none(name)
                if mod is None:
                    continue
                self.assertIs(
                    getattr(mod, "validar_y_autenticar_usuario", None),
                    auth.validar_y_autenticar_usuario,
                    f"{name} must re-export auth.validar_y_autenticar_usuario",
                )

    def test_auth_14_behavior_identical_across_entry_points(self):
        entry_points = [auth.validar_y_autenticar_usuario]
        for name in ("auth_local", "auth_nube"):
            mod = self._module_or_none(name)
            if mod is not None:
                entry_points.append(mod.validar_y_autenticar_usuario)
        for fn in entry_points:
            db = fake_db(registro(intentos=5))
            r = fn({"username": USER, "password": PASSWORD}, db, {})
            self.assertEqual(r["codigo"], 403)


if __name__ == "__main__":
    unittest.main()
