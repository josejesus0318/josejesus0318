"""Traducción de errores de PostgreSQL a mensajes comprensibles.

Ninguna pantalla muestra el texto técnico del servidor como mensaje
principal: se traduce el código SQLSTATE (y, cuando aplica, el nombre de
la restricción) a una frase en español. El detalle técnico se conserva
para mostrarlo en "Detalles".
"""

from __future__ import annotations

import re


class ErrorAplicacion(Exception):
    """Error listo para mostrarse al usuario."""

    def __init__(self, mensaje: str, detalle: str = "", sqlstate: str | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle
        self.sqlstate = sqlstate

    @property
    def es_permiso_denegado(self) -> bool:
        return self.sqlstate == "42501"


# Mensajes por código SQLSTATE
MENSAJES_SQLSTATE: dict[str, str] = {
    "23505": "Ya existe un registro con ese valor; los datos deben ser únicos.",
    "23503": "La operación no es posible porque el registro está relacionado con otros datos.",
    "23502": "Falta llenar un campo obligatorio.",
    "23514": "Los datos no cumplen las reglas de validación.",
    "22001": "Uno de los textos es demasiado largo.",
    "22003": "Uno de los números está fuera del rango permitido.",
    "22007": "La fecha u hora no tiene un formato válido.",
    "22008": "La fecha u hora no es válida.",
    "22P02": "Uno de los valores no tiene el formato correcto.",
    "42501": "No tiene permiso para realizar esta operación con su rol actual.",
    "42710": "Ese elemento ya existe.",
    "28P01": "Usuario o contraseña incorrectos.",
    "28000": "La cuenta no tiene autorización para conectarse.",
    "3D000": "La base de datos indicada no existe.",
    "53300": "El servidor alcanzó el máximo de conexiones; intente más tarde.",
    "57014": "La operación tardó demasiado y fue cancelada.",
    "40001": "Otro usuario modificó los mismos datos; intente de nuevo.",
    "40P01": "Otro usuario modificó los mismos datos; intente de nuevo.",
}

# Mensajes específicos por restricción del modelo v2
MENSAJES_RESTRICCION: dict[str, str] = {
    "ck_colab_baja_con_fecha": "Para dar de baja a un colaborador se requiere la fecha de baja.",
    "ck_colab_fecha_baja": "La fecha de baja no puede ser anterior a la fecha de ingreso.",
    "ck_colab_correo": "El correo electrónico no tiene un formato válido.",
    "ck_colab_tipo": "El tipo de colaborador debe ser empleado o contratista.",
    "colaboradores_correo_key": "Ese correo ya está registrado para otro colaborador.",
    "colaboradores_numero_empleado_key": "Ese número de empleado ya existe.",
    "ck_horario_horas": "La hora de salida debe ser posterior a la hora de entrada.",
    "ck_cred_fechas": "La fecha de vigencia no puede ser anterior a la de emisión.",
    "ck_cred_titular": "La credencial debe pertenecer a un colaborador o a una visita, no a ambos.",
    "ux_credencial_activa_colaborador": "El colaborador ya tiene una credencial activa. "
                                        "Suspenda o revoque la anterior antes de emitir otra.",
    "credenciales_codigo_qr_key": "Ese código QR ya está asignado a otra credencial.",
    "uq_visitante_identificacion": "Ya existe un visitante con ese tipo y número de identificación.",
    "uq_puesto_departamento": "Ese puesto ya existe en el departamento.",
    "ck_ubicacion_piso": "El piso debe estar entre -5 y 50.",
    "ck_dia_rango": "El día debe estar entre 1 (lunes) y 7 (domingo).",
    "usuarios_sistema_id_colaborador_key": "Ese colaborador ya tiene una cuenta de usuario.",
}

_PATRON_RESTRICCION = re.compile(r'constraint "([^"]+)"')


def _es_error_autenticacion(texto: str) -> bool:
    texto = texto.lower()
    return ("password authentication failed" in texto
            or "autentificación password falló" in texto
            or "autenticación password falló" in texto
            or "no password supplied" in texto)


def traducir_error(exc: BaseException) -> ErrorAplicacion:
    """Convierte cualquier excepción de psycopg en un ErrorAplicacion."""
    if isinstance(exc, ErrorAplicacion):
        return exc

    sqlstate = getattr(exc, "sqlstate", None)
    diag = getattr(exc, "diag", None)
    primario = (getattr(diag, "message_primary", None) or str(exc) or "").strip()
    detalle_srv = getattr(diag, "message_detail", None) or ""
    restriccion = getattr(diag, "constraint_name", None)
    if not restriccion:
        coincidencia = _PATRON_RESTRICCION.search(str(exc))
        restriccion = coincidencia.group(1) if coincidencia else None
    detalle = "\n".join(p for p in (f"SQLSTATE {sqlstate}" if sqlstate else "",
                                    primario, detalle_srv) if p)

    # Errores de conexión: psycopg no siempre trae SQLSTATE
    texto = str(exc)
    if _es_error_autenticacion(texto):
        return ErrorAplicacion(MENSAJES_SQLSTATE["28P01"], texto, "28P01")
    if "is not permitted to log in" in texto or "no tiene permitido iniciar sesión" in texto:
        return ErrorAplicacion("La cuenta está deshabilitada. Consulte al administrador.", texto, "28000")
    if sqlstate is None and ("connection" in texto.lower() or "conexión" in texto.lower()
                             or "could not" in texto.lower()):
        return ErrorAplicacion("No fue posible conectar con el servidor de base de datos. "
                               "Verifique que PostgreSQL esté encendido y los datos de conexión.",
                               texto, "08001")

    if sqlstate:
        # Errores propios del sistema (RAISE EXCEPTION en las funciones):
        # su mensaje ya está redactado para el usuario
        if sqlstate.startswith("GS") or sqlstate == "P0001":
            return ErrorAplicacion(primario, detalle, sqlstate)
        if restriccion and restriccion in MENSAJES_RESTRICCION:
            return ErrorAplicacion(MENSAJES_RESTRICCION[restriccion], detalle, sqlstate)
        if sqlstate in ("42710",) and primario:
            return ErrorAplicacion(primario, detalle, sqlstate)
        if sqlstate.startswith("08"):
            return ErrorAplicacion("Se perdió la conexión con el servidor. Inicie sesión de nuevo.",
                                   detalle, sqlstate)
        if sqlstate in MENSAJES_SQLSTATE:
            return ErrorAplicacion(MENSAJES_SQLSTATE[sqlstate], detalle, sqlstate)

    return ErrorAplicacion("Ocurrió un error inesperado en la base de datos.", detalle or texto, sqlstate)
