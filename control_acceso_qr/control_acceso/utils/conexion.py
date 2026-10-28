"""Gestión de la conexión de la sesión.

La aplicación NO guarda contraseñas: el usuario escribe su cuenta y
contraseña de PostgreSQL, se abre una conexión con esas credenciales y
la base de datos aplica los permisos de su rol (rol_recepcion, etc.).
La contraseña solo se usa para abrir la conexión y no se conserva.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from control_acceso import NOMBRE_APP
from control_acceso.utils.config import config
from control_acceso.utils.errores import ErrorAplicacion, traducir_error


def abrir_conexion(usuario: str, password: str) -> psycopg.Connection:
    """Abre una conexión con las credenciales indicadas.

    autocommit=True: cada sentencia se confirma sola; las operaciones de
    varios pasos se escriben como una sola sentencia (CTE) o como función
    en la base de datos, así no quedan transacciones abiertas.
    """
    try:
        return psycopg.connect(
            host=config.host,
            port=config.puerto,
            dbname=config.base,
            user=usuario.strip(),
            password=password,
            connect_timeout=config.tiempo_espera,
            application_name=NOMBRE_APP[:60],
            autocommit=True,
            row_factory=dict_row,  # type: ignore[arg-type]  # filas como diccionarios
        )
    except psycopg.Error as exc:
        raise traducir_error(exc) from exc


class SesionBD:
    """Conexión persistente del usuario que inició sesión."""

    def __init__(self) -> None:
        self._conexion: psycopg.Connection | None = None
        self.usuario: str = ""
        self.nombre_completo: str = ""
        self.roles: set[str] = set()
        self.es_superusuario: bool = False

    # -- ciclo de vida -------------------------------------------------
    def iniciar(self, usuario: str, password: str) -> None:
        """Abre la conexión de la sesión (lanza ErrorAplicacion si falla)."""
        self.cerrar()
        self._conexion = abrir_conexion(usuario, password)
        self.usuario = usuario.strip()

    def cerrar(self) -> None:
        if self._conexion is not None and not self._conexion.closed:
            self._conexion.close()
        self._conexion = None
        self.usuario = ""
        self.nombre_completo = ""
        self.roles = set()
        self.es_superusuario = False

    @property
    def activa(self) -> bool:
        return self._conexion is not None and not self._conexion.closed

    @property
    def conexion(self) -> psycopg.Connection:
        if not self.activa:
            raise ErrorAplicacion("No hay una sesión activa. Inicie sesión de nuevo.", sqlstate="08003")
        assert self._conexion is not None
        return self._conexion

    # -- roles -----------------------------------------------------------
    @property
    def es_admin(self) -> bool:
        return self.es_superusuario or "rol_admin_bd" in self.roles

    def tiene_rol(self, *roles: str) -> bool:
        """True si la sesión es administradora o pertenece a alguno de los roles."""
        return self.es_admin or bool(self.roles.intersection(roles))

    @property
    def descripcion_roles(self) -> str:
        if self.es_superusuario:
            return "Superusuario"
        nombres = {
            "rol_admin_bd": "Administrador", "rol_seguridad": "Seguridad",
            "rol_recepcion": "Recepción", "rol_rrhh": "Recursos Humanos",
            "rol_consulta": "Consulta", "rol_lector_qr": "Lector QR",
        }
        return ", ".join(sorted(nombres.get(r, r) for r in self.roles)) or "Sin rol asignado"


@contextmanager
def conexion_temporal(usuario: str, password: str) -> Iterator[psycopg.Connection]:
    """Conexión de un solo uso (p. ej. credenciales de administrador para
    crear un usuario). Se cierra siempre al terminar."""
    con = abrir_conexion(usuario, password)
    try:
        yield con
    finally:
        con.close()


# Sesión única de la aplicación
sesion = SesionBD()
