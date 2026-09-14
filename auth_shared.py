import datetime
import hashlib
import re


def validar_y_autenticar_usuario(datos_login, base_datos, configuracion_seguridad):
    # 1. Validación de campos básicos
    usuario = datos_login.get("username", "").strip()
    password = datos_login.get("password", "")

    if not usuario or not password:
        return {"exito": False, "error": "Usuario y contraseña son requeridos", "codigo": 400}

    if len(password) < 8:
        return {"exito": False, "error": "La contraseña es muy corta", "codigo": 400}

    # Validar formato de email si el username parece uno
    if "@" in usuario:
        patron_email = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        if not re.match(patron_email, usuario):
            return {"exito": False, "error": "Formato de correo inválido", "codigo": 400}

    # 2. Búsqueda en base de datos (simulada)
    registro_usuario = base_datos.buscar_usuario(usuario)
    if not registro_usuario:
        return {"exito": False, "error": "Credenciales inválidas", "codigo": 401}

    # Verificar si la cuenta está bloqueada
    intentos_fallidos = registro_usuario.get("intentos_fallidos", 0)
    max_intentos = configuracion_seguridad.get("max_intentos_login", 5)

    if intentos_fallidos >= max_intentos:
        return {"exito": False, "error": "Cuenta bloqueada temporalmente", "codigo": 403}

    # 3. Verificación criptográfica
    sal_guardada = registro_usuario.get("salt")
    hash_guardado = registro_usuario.get("password_hash")

    # Simulación de hasheo con salt
    string_a_hashear = f"{password}{sal_guardada}".encode("utf-8")
    hash_calculado = hashlib.sha256(string_a_hashear).hexdigest()

    if hash_calculado != hash_guardado:
        # Registrar intento fallido
        base_datos.incrementar_intento_fallido(usuario)
        return {"exito": False, "error": "Credenciales inválidas", "codigo": 401}

    # 4. Generación de sesión
    base_datos.resetear_intentos_fallidos(usuario)
    token_sesion = hashlib.md5(
        f"{usuario}{datetime.datetime.now().timestamp()}".encode()
    ).hexdigest()

    return {
        "exito": True,
        "mensaje": "Autenticación exitosa",
        "datos_sesion": {
            "token": token_sesion,
            "usuario_id": registro_usuario.get("id"),
            "expira_en": configuracion_seguridad.get("tiempo_sesion_minutos", 60) * 60,
        },
        "codigo": 200,
    }
