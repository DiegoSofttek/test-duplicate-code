"""Unit tests for subtask-1-1: consolidation of authentication modules.

Covers User Story #1 (AC-1, AC-2, AC-3) for validar_y_autenticar_usuario.
Run from the repository root with: python -m unittest test_auth_subtask-1-1
(the hyphenated filename requires discovery: python -m unittest discover -p "test_auth_subtask-1-1.py")
"""
import contextlib
import hashlib
import importlib
import re
import unittest
from unittest import mock

import auth


def _hash_password(password, salt):
    return hashlib.sha256(f"{password}{salt}".encode("utf-8")).hexdigest()


def _make_record(password="contraseña-válida", salt="sal123", intentos=0, user_id=42):
    return {
        "id": user_id,
        "salt": salt,
        "password_hash": _hash_password(password, salt),
        "intentos_fallidos": intentos,
    }


class FakeDB:
    """Plain fake of the injected base_datos object; records every call."""

    def __init__(self, record=None):
        self.record = record
        self.buscar_calls = []
        self.incrementar_calls = []
        self.resetear_calls = []

    def buscar_usuario(self, username):
        self.buscar_calls.append(username)
        return self.record

    def incrementar_intento_fallido(self, username):
        self.incrementar_calls.append(username)

    def resetear_intentos_fallidos(self, username):
        self.resetear_calls.append(username)


def _fake_datetime_module(timestamp):
    fake = mock.MagicMock()
    fake.datetime.now.return_value.timestamp.return_value = timestamp
    return fake


PASSWORD = "contraseña-válida"
VALID_LOGIN = {"username": "ana", "password": PASSWORD}


class TestAuthValidationAC1(unittest.TestCase):
    """AC-1: short password or invalid email format returns 400."""

    def test_TC_1_01_missing_or_empty_credentials(self):
        """TC-1-01: Username or password is missing or empty."""
        cases = [
            {"username": "", "password": PASSWORD},
            {"username": "ana", "password": ""},
            {"password": PASSWORD},
            {"username": "ana"},
        ]
        for datos in cases:
            with self.subTest(datos=datos):
                db = FakeDB(_make_record())
                resultado = auth.validar_y_autenticar_usuario(datos, db, {})
                self.assertFalse(resultado["exito"])
                self.assertEqual(resultado["codigo"], 400)
                self.assertEqual(resultado["error"], "Usuario y contraseña son requeridos")
                self.assertEqual(db.buscar_calls, [])

    def test_TC_1_02_password_seven_characters(self):
        """TC-1-02: Password has 7 characters -> 400 'muy corta', no DB query."""
        db = FakeDB(_make_record(password="abcdefg"))
        resultado = auth.validar_y_autenticar_usuario(
            {"username": "ana", "password": "abcdefg"}, db, {}
        )
        self.assertEqual(resultado["codigo"], 400)
        self.assertIn("muy corta", resultado["error"])
        self.assertEqual(db.buscar_calls, [])

    def test_TC_1_03_password_exactly_eight_characters_passes(self):
        """TC-1-03: Password with exactly 8 characters and valid credentials -> 200."""
        password = "12345678"
        db = FakeDB(_make_record(password=password))
        resultado = auth.validar_y_autenticar_usuario(
            {"username": "ana", "password": password}, db, {}
        )
        self.assertEqual(resultado["codigo"], 200)
        self.assertTrue(resultado["exito"])

    def test_TC_1_04_malformed_email_rejected(self):
        """TC-1-04: Username contains '@' but fails the regex -> 400 invalid email."""
        for username in ["user@domain", "user@@x.com"]:
            with self.subTest(username=username):
                db = FakeDB(_make_record())
                resultado = auth.validar_y_autenticar_usuario(
                    {"username": username, "password": PASSWORD}, db, {}
                )
                self.assertEqual(resultado["codigo"], 400)
                self.assertEqual(resultado["error"], "Formato de correo inválido")
                self.assertEqual(db.buscar_calls, [])

    def test_TC_1_05_valid_email_proceeds_to_lookup(self):
        """TC-1-05: Valid email passes format check and reaches the DB lookup."""
        username = "ana.lopez+x@mail.example.com"
        db = FakeDB(_make_record())
        resultado = auth.validar_y_autenticar_usuario(
            {"username": username, "password": PASSWORD}, db, {}
        )
        self.assertEqual(db.buscar_calls, [username])
        self.assertNotEqual(resultado.get("error"), "Formato de correo inválido")

    def test_TC_1_06_non_email_username_skips_email_validation(self):
        """TC-1-06: Username without '@' skips email validation and proceeds to lookup."""
        db = FakeDB(_make_record())
        resultado = auth.validar_y_autenticar_usuario(
            {"username": "ana_lopez", "password": PASSWORD}, db, {}
        )
        self.assertEqual(db.buscar_calls, ["ana_lopez"])
        self.assertNotEqual(resultado.get("error"), "Formato de correo inválido")


class TestAccountBlockAC2(unittest.TestCase):
    """AC-2: reaching the maximum failed attempts returns 403."""

    def test_TC_2_01_attempts_equal_limit_blocks_account(self):
        """TC-2-01: intentos_fallidos == max_intentos_login -> 403, no hash check, no reset."""
        db = FakeDB(_make_record(intentos=5))
        with mock.patch.object(auth.hashlib, "sha256", wraps=hashlib.sha256) as sha:
            resultado = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {"max_intentos_login": 5})
        self.assertEqual(resultado["codigo"], 403)
        self.assertEqual(resultado["error"], "Cuenta bloqueada temporalmente")
        sha.assert_not_called()
        self.assertEqual(db.resetear_calls, [])

    def test_TC_2_02_one_below_limit_not_blocked(self):
        """TC-2-02: intentos_fallidos one below limit with correct password -> 200."""
        db = FakeDB(_make_record(intentos=4))
        resultado = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {"max_intentos_login": 5})
        self.assertEqual(resultado["codigo"], 200)

    def test_TC_2_03_locked_account_with_correct_password_still_403(self):
        """TC-2-03: Locked account with correct password still returns 403 (block check first)."""
        db = FakeDB(_make_record(intentos=7))
        resultado = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {})
        self.assertEqual(resultado["codigo"], 403)
        self.assertFalse(resultado["exito"])
        self.assertEqual(db.resetear_calls, [])

    def test_TC_2_04_custom_max_attempts_honored(self):
        """TC-2-04: Custom max_intentos_login changes the block threshold."""
        db = FakeDB(_make_record(intentos=3))
        bloqueado = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {"max_intentos_login": 3})
        self.assertEqual(bloqueado["codigo"], 403)

        db = FakeDB(_make_record(intentos=3))
        permitido = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {"max_intentos_login": 4})
        self.assertEqual(permitido["codigo"], 200)


class TestAuthenticationAC3(unittest.TestCase):
    """AC-3: valid credentials create a session token and reset failed attempts."""

    def test_TC_3_01_correct_password_returns_session(self):
        """TC-3-01: Correct password -> exito=True, 200, usuario_id from record, expira_en=3600."""
        db = FakeDB(_make_record(user_id=99))
        resultado = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {})
        self.assertTrue(resultado["exito"])
        self.assertEqual(resultado["codigo"], 200)
        self.assertEqual(resultado["datos_sesion"]["usuario_id"], 99)
        self.assertEqual(resultado["datos_sesion"]["expira_en"], 3600)

    def test_TC_3_02_success_resets_attempts_once(self):
        """TC-3-02: Success calls resetear_intentos_fallidos once; no increment."""
        db = FakeDB(_make_record())
        auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {})
        self.assertEqual(db.resetear_calls, ["ana"])
        self.assertEqual(db.incrementar_calls, [])

    def test_TC_3_03_token_is_md5_hex_and_varies_with_time(self):
        """TC-3-03: Token is 32 hex chars and differs for different timestamps."""
        tokens = []
        for timestamp in (1700000000.0, 1700000001.5):
            db = FakeDB(_make_record())
            with mock.patch.object(auth, "datetime", _fake_datetime_module(timestamp)):
                resultado = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {})
            tokens.append(resultado["datos_sesion"]["token"])
        for token in tokens:
            self.assertIsNotNone(re.fullmatch(r"[0-9a-f]{32}", token))
        self.assertNotEqual(tokens[0], tokens[1])

    def test_TC_3_04_custom_session_time_in_minutes(self):
        """TC-3-04: Custom tiempo_sesion_minutos=10 -> expira_en=600."""
        db = FakeDB(_make_record())
        resultado = auth.validar_y_autenticar_usuario(
            VALID_LOGIN, db, {"tiempo_sesion_minutos": 10}
        )
        self.assertEqual(resultado["datos_sesion"]["expira_en"], 600)

    def test_TC_3_05_wrong_password_returns_401_and_increments(self):
        """TC-3-05: Wrong password -> 401 'Credenciales inválidas', one increment, no reset."""
        db = FakeDB(_make_record())
        resultado = auth.validar_y_autenticar_usuario(
            {"username": "ana", "password": "otra-clave-larga"}, db, {}
        )
        self.assertEqual(resultado["codigo"], 401)
        self.assertEqual(resultado["error"], "Credenciales inválidas")
        self.assertEqual(db.incrementar_calls, ["ana"])
        self.assertEqual(db.resetear_calls, [])

    def test_TC_3_06_unknown_username_returns_401_without_side_effects(self):
        """TC-3-06: Unknown username -> 401, no increment or reset calls."""
        db = FakeDB(None)
        resultado = auth.validar_y_autenticar_usuario(VALID_LOGIN, db, {})
        self.assertEqual(resultado["codigo"], 401)
        self.assertEqual(db.incrementar_calls, [])
        self.assertEqual(db.resetear_calls, [])

    def test_TC_3_07_username_is_stripped_before_lookup(self):
        """TC-3-07: Leading/trailing spaces are trimmed before buscar_usuario."""
        db = FakeDB(_make_record())
        auth.validar_y_autenticar_usuario(
            {"username": "  ana  ", "password": PASSWORD}, db, {}
        )
        self.assertEqual(db.buscar_calls, ["ana"])


class TestConsolidationRegression(unittest.TestCase):
    """Regression: the merged auth module matches the original local/cloud copies."""

    ORIGINAL_MODULES = ("auth", "auth_local", "auth_nube")

    def _input_matrix(self):
        record_ok = _make_record(intentos=0)
        record_bloqueado = _make_record(intentos=5)
        record_casi = _make_record(intentos=4)
        return [
            ({"username": "", "password": PASSWORD}, record_ok, {}),
            ({"username": "ana", "password": "corta"}, record_ok, {}),
            ({"username": "ana", "password": "12345678"}, _make_record(password="12345678"), {}),
            ({"username": "user@domain", "password": PASSWORD}, record_ok, {}),
            ({"username": "ana.lopez+x@mail.example.com", "password": PASSWORD}, record_ok, {}),
            ({"username": "ana", "password": PASSWORD}, record_bloqueado, {}),
            ({"username": "ana", "password": PASSWORD}, record_casi, {"max_intentos_login": 5}),
            ({"username": "ana", "password": PASSWORD}, record_ok, {"tiempo_sesion_minutos": 10}),
            ({"username": "ana", "password": "otra-clave-larga"}, record_ok, {}),
            ({"username": "ana", "password": PASSWORD}, None, {}),
            ({"username": "  ana  ", "password": PASSWORD}, record_ok, {}),
        ]

    def _run(self, module, datos, record, config, timestamp):
        db = FakeDB(dict(record) if record is not None else None)
        with mock.patch.object(module, "datetime", _fake_datetime_module(timestamp)):
            resultado = module.validar_y_autenticar_usuario(dict(datos), db, dict(config))
        return resultado, db

    def test_TC_R_01_merged_module_matches_original_copies(self):
        """TC-R-01: Outputs and DB side effects match originals for the shared matrix."""
        modules = [importlib.import_module(name) for name in self.ORIGINAL_MODULES]
        for index, (datos, record, config) in enumerate(self._input_matrix()):
            with self.subTest(case=index):
                outputs = []
                for module in modules:
                    resultado, db = self._run(module, datos, record, config, 1700000000.0)
                    outputs.append((resultado, db.buscar_calls, db.incrementar_calls, db.resetear_calls))
                for other in outputs[1:]:
                    self.assertEqual(outputs[0], other)


if __name__ == "__main__":
    unittest.main()
