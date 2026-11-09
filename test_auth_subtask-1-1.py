"""Unit tests for subtask-1-1 (consolidation of authentication modules).

Target: validar_y_autenticar_usuario in auth.py (identical to auth_local.py and
auth_nube.py before consolidation). Test IDs are preserved from the Explorer
test plan and appear in each test's docstring.
"""
import hashlib
import re
import unittest
from unittest.mock import Mock

from auth import validar_y_autenticar_usuario

SALT = "sal123"
PASSWORD_VALIDA = "password123"


def _hash_de(password, salt=SALT):
    return hashlib.sha256(f"{password}{salt}".encode("utf-8")).hexdigest()


def _registro(intentos=0, password=PASSWORD_VALIDA, usuario_id=42):
    return {
        "id": usuario_id,
        "salt": SALT,
        "password_hash": _hash_de(password),
        "intentos_fallidos": intentos,
    }


def _base_datos(registro=None):
    bd = Mock()
    bd.buscar_usuario.return_value = registro
    return bd


class AuthSubtask11Tests(unittest.TestCase):

    # AC-1 -------------------------------------------------------------

    def test_auth_t01_blank_credentials_return_400_without_db_calls(self):
        """AUTH-T01: Blank username or password (or whitespace-only username)
        returns exito False, codigo 400, and makes no DB calls. (AC-1)"""
        casos = [
            {"username": "", "password": PASSWORD_VALIDA},
            {"username": "user", "password": ""},
            {"username": "   ", "password": PASSWORD_VALIDA},
        ]
        for datos in casos:
            with self.subTest(datos=datos):
                bd = _base_datos(_registro())
                resultado = validar_y_autenticar_usuario(datos, bd, {})
                self.assertFalse(resultado["exito"])
                self.assertEqual(resultado["codigo"], 400)
                self.assertEqual(bd.method_calls, [])

    def test_auth_t02_password_of_7_chars_returns_400_without_lookup(self):
        """AUTH-T02: Password of 7 characters returns exito False, codigo 400,
        and buscar_usuario is not called. (AC-1)"""
        bd = _base_datos(_registro())
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": "1234567"}, bd, {}
        )
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 400)
        bd.buscar_usuario.assert_not_called()

    def test_auth_t03_password_of_exactly_8_chars_proceeds_to_authentication(self):
        """AUTH-T03: Password of exactly 8 characters with valid credentials
        passes the length check and proceeds to authentication. (AC-1)"""
        password = "12345678"
        bd = _base_datos(_registro(password=password))
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": password}, bd, {}
        )
        bd.buscar_usuario.assert_called_once_with("user")
        self.assertNotEqual(resultado["codigo"], 400)
        self.assertEqual(resultado["codigo"], 200)

    def test_auth_t04_invalid_email_format_returns_400_without_db_lookup(self):
        """AUTH-T04: Username containing '@' that fails the regex returns
        exito False, codigo 400, and no DB lookup. (AC-1)"""
        for usuario in ["user@", "a@b"]:
            with self.subTest(usuario=usuario):
                bd = _base_datos(_registro())
                resultado = validar_y_autenticar_usuario(
                    {"username": usuario, "password": PASSWORD_VALIDA}, bd, {}
                )
                self.assertFalse(resultado["exito"])
                self.assertEqual(resultado["codigo"], 400)
                bd.buscar_usuario.assert_not_called()

    def test_auth_t05_valid_email_username_passes_validation(self):
        """AUTH-T05: Valid email username with a valid password passes
        validation and proceeds (no 400). (AC-1)"""
        email = "user@example.com"
        bd = _base_datos(_registro())
        resultado = validar_y_autenticar_usuario(
            {"username": email, "password": PASSWORD_VALIDA}, bd, {}
        )
        bd.buscar_usuario.assert_called_once_with(email)
        self.assertNotEqual(resultado["codigo"], 400)
        self.assertEqual(resultado["codigo"], 200)

    def test_auth_t06_unknown_user_returns_401_without_counter_changes(self):
        """AUTH-T06: Unknown user returns codigo 401, and no increment or reset
        is called. (AC-1 negative path)"""
        bd = _base_datos(None)
        resultado = validar_y_autenticar_usuario(
            {"username": "nadie", "password": PASSWORD_VALIDA}, bd, {}
        )
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 401)
        bd.incrementar_intento_fallido.assert_not_called()
        bd.resetear_intentos_fallidos.assert_not_called()

    # AC-2 -------------------------------------------------------------

    def test_auth_t07_attempts_equal_to_custom_limit_returns_403_without_hash_check(self):
        """AUTH-T07: intentos_fallidos equal to max_intentos_login returns
        exito False, codigo 403, error 'Cuenta bloqueada temporalmente', and
        the hash is not verified. (AC-2)"""
        # Registro con hash correcto: si el hash se verificara, el login
        # resultaría exitoso; el bloqueo debe impedirlo.
        bd = _base_datos(_registro(intentos=3))
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": PASSWORD_VALIDA},
            bd,
            {"max_intentos_login": 3},
        )
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 403)
        self.assertEqual(resultado["error"], "Cuenta bloqueada temporalmente")
        bd.incrementar_intento_fallido.assert_not_called()
        bd.resetear_intentos_fallidos.assert_not_called()

    def test_auth_t08_one_below_limit_with_wrong_password_returns_401_and_increments(self):
        """AUTH-T08: intentos_fallidos one below the limit with a wrong password
        returns codigo 401 and calls incrementar_intento_fallido once. (AC-2 boundary)"""
        bd = _base_datos(_registro(intentos=2))
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": "incorrecta123"},
            bd,
            {"max_intentos_login": 3},
        )
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 401)
        bd.incrementar_intento_fallido.assert_called_once_with("user")

    def test_auth_t09_default_limit_of_5_attempts_returns_403(self):
        """AUTH-T09: Without max_intentos_login in the config, 5 failed attempts
        returns codigo 403 (default limit). (AC-2)"""
        bd = _base_datos(_registro(intentos=5))
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": PASSWORD_VALIDA}, bd, {}
        )
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 403)

    # AC-3 -------------------------------------------------------------

    def test_auth_t10_correct_password_resets_counter_and_does_not_increment(self):
        """AUTH-T10: Correct password (SHA-256 of password+salt matches stored
        hash) returns exito True, codigo 200, calls resetear_intentos_fallidos
        once, and does not call incrementar_intento_fallido. (AC-3)"""
        bd = _base_datos(_registro(intentos=1))
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": PASSWORD_VALIDA}, bd, {}
        )
        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)
        bd.resetear_intentos_fallidos.assert_called_once_with("user")
        bd.incrementar_intento_fallido.assert_not_called()

    def test_auth_t11_success_session_payload_contains_token_user_id_and_default_expiry(self):
        """AUTH-T11: Successful login session payload contains a non-empty hex
        token, usuario_id from the record, and expira_en equal to 3600 by
        default. (AC-3)"""
        bd = _base_datos(_registro(usuario_id=77))
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": PASSWORD_VALIDA}, bd, {}
        )
        sesion = resultado["datos_sesion"]
        self.assertTrue(sesion["token"])
        self.assertIsNotNone(re.fullmatch(r"[0-9a-f]+", sesion["token"]))
        self.assertEqual(sesion["usuario_id"], 77)
        self.assertEqual(sesion["expira_en"], 3600)

    def test_auth_t12_success_session_expiry_uses_configured_minutes(self):
        """AUTH-T12: Successful login with a custom tiempo_sesion_minutos makes
        expira_en reflect the configured value. (AC-3)"""
        bd = _base_datos(_registro())
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": PASSWORD_VALIDA},
            bd,
            {"tiempo_sesion_minutos": 15},
        )
        self.assertEqual(resultado["datos_sesion"]["expira_en"], 900)

    def test_auth_t13_wrong_password_on_unblocked_account_increments_counter_only(self):
        """AUTH-T13: Wrong password with a non-blocked account returns codigo
        401, calls incrementar_intento_fallido once with the username, and makes
        no reset call. (AC-2/AC-3 counter behavior)"""
        bd = _base_datos(_registro(intentos=0))
        resultado = validar_y_autenticar_usuario(
            {"username": "user", "password": "otra-clave-mala"}, bd, {}
        )
        self.assertFalse(resultado["exito"])
        self.assertEqual(resultado["codigo"], 401)
        bd.incrementar_intento_fallido.assert_called_once_with("user")
        bd.resetear_intentos_fallidos.assert_not_called()


if __name__ == "__main__":
    unittest.main()
