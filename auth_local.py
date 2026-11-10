"""Compatibility shim: re-exports the consolidated authentication module.

The authentication logic lives in ``auth.py`` (single source of truth).
"""
from auth import validar_y_autenticar_usuario

__all__ = ["validar_y_autenticar_usuario"]
