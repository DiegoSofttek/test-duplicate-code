"""Unit tests for subtask-1-1 authentication consolidation."""

import hashlib
import importlib
import unittest
from unittest.mock import Mock

from auth import validar_y_autenticar_usuario


class AuthenticationConsolidationTests(unittest.TestCase):
    """Tests for the canonical authentication entry point."""

    def _database(self, user=None):
        database = Mock()
        database.buscar_usuario.return_value = user
        return database

    @staticmethod
    def _user(password, salt="salt", **overrides):
        user = {
            "id": 17,
            "intentos_fallidos": 0,
            "salt": salt,
            "password_hash": hashlib.sha256(
                f"{password}{salt}".encode("utf-8")
            ).hexdigest(),
        }
        user.update(overrides)
        return user

    def test_subtask_1_1_T01_rejects_short_password_before_lookup(self):
        """subtask-1-1-T01: passwords shorter than eight characters are rejected."""
        database = self._database()

        result = validar_y_autenticar_usuario(
            {"username": "person", "password": "short7!"}, database, {}
        )

        self.assertFalse(result["exito"])
        self.assertEqual(400, result["codigo"])
        self.assertEqual("La contraseña es muy corta", result["error"])
        database.buscar_usuario.assert_not_called()

    def test_subtask_1_1_T02_rejects_invalid_email_before_lookup(self):
        """subtask-1-1-T02: malformed email-shaped usernames are rejected."""
        database = self._database()

        result = validar_y_autenticar_usuario(
            {"username": "invalid@email", "password": "password8"}, database, {}
        )

        self.assertFalse(result["exito"])
        self.assertEqual(400, result["codigo"])
        self.assertEqual("Formato de correo inválido", result["error"])
        database.buscar_usuario.assert_not_called()

    def test_subtask_1_1_T03_blocks_user_at_failed_attempt_threshold(self):
        """subtask-1-1-T03: a user at the configured threshold is blocked."""
        database = self._database(
            self._user("password8", intentos_fallidos=3)
        )

        result = validar_y_autenticar_usuario(
            {"username": "person", "password": "password8"},
            database,
            {"max_intentos_login": 3},
        )

        self.assertFalse(result["exito"])
        self.assertEqual(403, result["codigo"])
        self.assertEqual("Cuenta bloqueada temporalmente", result["error"])
        database.incrementar_intento_fallido.assert_not_called()
        database.resetear_intentos_fallidos.assert_not_called()

    def test_subtask_1_1_T04_authenticates_and_creates_session(self):
        """subtask-1-1-T04: valid credentials reset failures and create a session."""
        username = "person"
        database = self._database(self._user("password8"))

        result = validar_y_autenticar_usuario(
            {"username": username, "password": "password8"},
            database,
            {"tiempo_sesion_minutos": 15},
        )

        self.assertTrue(result["exito"])
        self.assertEqual(200, result["codigo"])
        self.assertEqual(17, result["datos_sesion"]["usuario_id"])
        self.assertIsInstance(result["datos_sesion"]["token"], str)
        self.assertTrue(result["datos_sesion"]["token"])
        self.assertEqual(15 * 60, result["datos_sesion"]["expira_en"])
        database.resetear_intentos_fallidos.assert_called_once_with(username)
        database.incrementar_intento_fallido.assert_not_called()

    def test_subtask_1_1_T05_increments_failed_attempt_for_invalid_credentials(self):
        """subtask-1-1-T05: invalid credentials register exactly one failure."""
        username = "person"
        database = self._database(
            self._user("different-password", salt="known-salt")
        )

        result = validar_y_autenticar_usuario(
            {"username": username, "password": "password8"}, database, {}
        )

        self.assertFalse(result["exito"])
        self.assertEqual(401, result["codigo"])
        self.assertEqual("Credenciales inválidas", result["error"])
        database.incrementar_intento_fallido.assert_called_once_with(username)
        database.resetear_intentos_fallidos.assert_not_called()

    def test_subtask_1_1_T06_uses_auth_as_the_canonical_implementation(self):
        """subtask-1-1-T06: compatibility modules delegate to canonical auth."""
        auth_local = importlib.import_module("auth_local")
        auth_nube = importlib.import_module("auth_nube")
        self.assertIs(
            validar_y_autenticar_usuario, auth_local.validar_y_autenticar_usuario
        )
        self.assertIs(
            validar_y_autenticar_usuario, auth_nube.validar_y_autenticar_usuario
        )

        validation_database = self._database()
        validation_result = validar_y_autenticar_usuario(
            {"username": "person", "password": "short"}, validation_database, {}
        )
        self.assertEqual(400, validation_result["codigo"])

        blocked_database = self._database(
            self._user("password8", intentos_fallidos=1)
        )
        blocked_result = validar_y_autenticar_usuario(
            {"username": "person", "password": "password8"},
            blocked_database,
            {"max_intentos_login": 1},
        )
        self.assertEqual(403, blocked_result["codigo"])

        success_database = self._database(self._user("password8"))
        success_result = validar_y_autenticar_usuario(
            {"username": "person", "password": "password8"}, success_database, {}
        )
        self.assertTrue(success_result["exito"])
        self.assertEqual(200, success_result["codigo"])


if __name__ == "__main__":
    unittest.main()
