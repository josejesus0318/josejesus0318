"""Conexión a PostgreSQL.

Cada petición abre su conexión (Neon la reactiva si estaba dormida) y la cierra al
terminar. Toda la SQL de la aplicación usa parámetros (%s): nunca se concatena texto
del usuario, así que no hay inyección SQL.
"""
from __future__ import annotations

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
        return ErrorBD("No fue posible conectar con la base de datos. Si es la primera visita del día, "
                       "espere unos segundos y vuelva a intentar.")
    return ErrorBD(MENSAJES.get(estado, "Ocurrió un error en la base de datos."))


def init_app(app: Flask) -> None:
    app.teardown_appcontext(cerrar)


def conexion() -> psycopg.Connection:
    if "conn" not in g:
        try:
            # prepare_threshold=None: sin sentencias preparadas, compatible con el pooler de Neon
            conn = psycopg.connect(current_app.config["DATABASE_URL"], autocommit=True,
                                   row_factory=dict_row, connect_timeout=15, prepare_threshold=None)
        except psycopg.Error as e:
            raise traducir(e) from e
        zona = current_app.config["ZONA_HORARIA"]
        conn.execute("SELECT set_config('search_path', 'campus, public', false), "
                     "set_config('TimeZone', %s, false)", (zona,))
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
