"""Local authentication compatibility entry point.

Authentication policy is implemented centrally in :mod:`auth`.
"""

from auth import validar_y_autenticar_usuario

__all__ = ["validar_y_autenticar_usuario"]
