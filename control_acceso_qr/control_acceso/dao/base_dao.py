"""Clase base de los DAO.

Usa la conexión de la sesión (credenciales del usuario autenticado), de
modo que PostgreSQL aplica los permisos de su rol. Todas las consultas
son parametrizadas (%s): los valores nunca se concatenan al SQL.
Cualquier error de psycopg se convierte en ErrorAplicacion.
"""

from __future__ import annotations

from typing import Any, Sequence, cast

import psycopg

from control_acceso.utils.conexion import sesion
from control_acceso.utils.errores import traducir_error

Parametros = Sequence[Any] | dict[str, Any] | None


class BaseDAO:
    """Métodos comunes de consulta y ejecución."""

    def __init__(self, conexion: psycopg.Connection | None = None) -> None:
        # Si se pasa una conexión (p. ej. temporal de administrador) se usa esa;
        # si no, la de la sesión.
        self._conexion_propia = conexion

    @property
    def _con(self) -> psycopg.Connection:
        return self._conexion_propia if self._conexion_propia is not None else sesion.conexion

    def _consultar(self, sql: Any, params: Parametros = None) -> list[dict[str, Any]]:
        try:
            return cast(list[dict[str, Any]], self._con.execute(sql, params).fetchall())
        except psycopg.Error as exc:
            raise traducir_error(exc) from exc

    def _consultar_uno(self, sql: Any, params: Parametros = None) -> dict[str, Any] | None:
        try:
            return cast("dict[str, Any] | None", self._con.execute(sql, params).fetchone())
        except psycopg.Error as exc:
            raise traducir_error(exc) from exc

    def _escalar(self, sql: Any, params: Parametros = None) -> Any:
        fila = self._consultar_uno(sql, params)
        return next(iter(fila.values())) if fila else None

    def _ejecutar(self, sql: Any, params: Parametros = None) -> int:
        """Ejecuta INSERT/UPDATE/DELETE y devuelve las filas afectadas."""
        try:
            return self._con.execute(sql, params).rowcount
        except psycopg.Error as exc:
            raise traducir_error(exc) from exc
