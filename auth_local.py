"""Compatibility shim: the authentication logic lives in auth.py (single source of truth)."""
from auth import validar_y_autenticar_usuario

__all__ = ["validar_y_autenticar_usuario"]
