"""Conexión a PostgreSQL.

Cada petición abre su conexión (Neon la reactiva si estaba dormida) y la cierra al
terminar. Toda la SQL de la aplicación usa parámetros (%s): nunca se concatena texto
del usuario, así que no hay inyección SQL.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from flask import Flask, current_app, g, session
from psycopg.rows import dict_row

# Mensajes en español para los errores más comunes de PostgreSQL (SQLSTATE)
MENSAJES = {
    "23505": "Ya existe un registro con ese dato (número de control, empleado, usuario o nombre repetido).",
    "23503": "El registro está relacionado con otro dato que no existe o que todavía se usa.",
    "23514": "Algún dato no cumple las reglas (fechas, horas, usos o formato).",
    "23502": "Falta un dato obligatorio.",
    "22P02": "Algún dato tiene un formato no válido.",
    "22007": "La fecha u hora no es válida.",
    "22008": "La fecha u hora no es válida.",
    "42501": "El usuario de la base de datos no tiene permiso para esta operación.",
    "40001": "Otro usuario modificó los mismos datos al mismo tiempo. Intente de nuevo.",
    "40P01": "Otro usuario modificó los mismos datos al mismo tiempo. Intente de nuevo.",
}


class ErrorBD(Exception):
    """Error de base de datos ya traducido a un mensaje para el usuario."""


def traducir(e: psycopg.Error) -> ErrorBD:
    estado = getattr(e, "sqlstate", None) or ""
    if estado.startswith("GS"):                         # errores propios (RAISE ... ERRCODE 'GSxxx')
        texto = e.diag.message_primary if e.diag else str(e)
        return ErrorBD(texto)
    if isinstance(e, psycopg.OperationalError):
        detalle = detalle_tecnico(e)
        try:
            current_app.logger.error("Error de conexión con PostgreSQL: %s", detalle)
        except RuntimeError:
            pass
        return ErrorBD("No fue posible conectar con la base de datos. Si es la primera visita del día, "
                       f"espere unos segundos y vuelva a intentar. Detalle técnico: {detalle}")
    if estado == "42883":
        return ErrorBD("Falta una función en la base de datos: ejecute en Neon los scripts que falten de la carpeta "
                       "database (por ejemplo 06_procedimientos.sql o 07_kiosco.sql).")
    if estado == "42P01":
        return ErrorBD("Faltan las tablas del sistema: ejecute los scripts de la carpeta database "
                       "(paso 2 de la guía de despliegue).")
    return ErrorBD(MENSAJES.get(estado, "Ocurrió un error en la base de datos."))


def detalle_tecnico(e: Exception) -> str:
    """Primera línea del error, sin contraseñas."""
    texto = " ".join(str(e).split())[:300]
    return re.sub(r"(://[^:/@\s]+:)[^@\s]+@", r"\1***@", texto) or e.__class__.__name__


def limpiar_url(url: str) -> str:
    """Corrige errores comunes al pegar la cadena de Neon en Render (comillas, 'psql', 'DATABASE_URL=')."""
    url = (url or "").strip()
    if url.lower().startswith("psql "):
        url = url[5:].strip()
    if url.upper().startswith("DATABASE_URL="):
        url = url.split("=", 1)[1].strip()
    return url.strip().strip('"').strip("'").strip()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(cerrar)


EJEMPLOS = ("ep-algo-123456", "ep-xxxx", "usuario:contraseña@")


def conexion() -> psycopg.Connection:
    if "conn" not in g:
        if any(x in current_app.config["DATABASE_URL"] for x in EJEMPLOS):
            raise ErrorBD("DATABASE_URL todavía tiene la cadena de EJEMPLO de la guía. En Render vaya a "
                          "Environment y pegue la cadena real que muestra Neon en el botón Connect.")
        try:
            # prepare_threshold=None: sin sentencias preparadas, compatible con el pooler de Neon
            conn = psycopg.connect(current_app.config["DATABASE_URL"], autocommit=True,
                                   row_factory=dict_row, connect_timeout=15, prepare_threshold=None)
        except psycopg.Error as e:
            raise traducir(e) from e
        zona = current_app.config["ZONA_HORARIA"]
        try:
            conn.execute("SELECT set_config('search_path', 'campus, public', false), "
                         "set_config('TimeZone', %s, false)", (zona,))
        except psycopg.Error as e:
            conn.close()
            raise traducir(e) from e
        g.conn = conn
    return g.conn


def cerrar(_exc: BaseException | None = None) -> None:
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def todos(sql: str, params: Any = None) -> list[dict]:
    try:
        return conexion().execute(sql, params).fetchall()
    except psycopg.Error as e:
        raise traducir(e) from e


def uno(sql: str, params: Any = None) -> dict | None:
    try:
        return conexion().execute(sql, params).fetchone()
    except psycopg.Error as e:
        raise traducir(e) from e


@contextmanager
def transaccion() -> Iterator[psycopg.Connection]:
    """Bloque atómico: todo o nada. Además indica a la auditoría quién hace el cambio."""
    conn = conexion()
    try:
        with conn.transaction():
            usuario = session.get("id_usuario")
            if usuario:
                conn.execute("SELECT set_config('app.id_usuario', %s, true)", (str(usuario),))
            yield conn
    except psycopg.Error as e:
        raise traducir(e) from e
