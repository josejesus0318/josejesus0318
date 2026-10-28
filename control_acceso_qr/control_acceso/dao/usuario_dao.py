"""Administración de cuentas de usuario (solo rol_admin_bd).

Crear, habilitar o restablecer cuentas se hace con funciones
SECURITY DEFINER de la base de datos; la contraseña viaja como parámetro
y PostgreSQL la guarda cifrada con SCRAM-SHA-256.
"""

from __future__ import annotations

from typing import Any

import psycopg

from control_acceso.dao.base_dao import BaseDAO
from control_acceso.models.entidades import UsuarioSistema

ROLES_DISPONIBLES: list[tuple[str, str]] = [
    ("rol_admin_bd", "Administrador de la base de datos"),
    ("rol_seguridad", "Seguridad Patrimonial"),
    ("rol_recepcion", "Recepción"),
    ("rol_rrhh", "Recursos Humanos"),
    ("rol_consulta", "Consulta (Dirección)"),
    ("rol_lector_qr", "Lector QR (cuenta de servicio)"),
]


class UsuarioDAO(BaseDAO):

    SQL_LISTAR = """
        SELECT id_usuario_sistema, cuenta, rol_aplicacion, colaborador, activo,
               puede_conectarse, fecha_alta, creado_por
        FROM vw_usuarios_sistema ORDER BY cuenta
    """
    SQL_CREAR = "SELECT sp_crear_usuario(%s, %s, %s, %s) AS id"
    SQL_ESTADO = "SELECT sp_cambiar_estado_usuario(%s, %s)"
    SQL_PASSWORD = "SELECT sp_restablecer_password(%s, %s)"
    SQL_SIN_CUENTA = """
        SELECT d.id_colaborador AS id, d.nombre_completo || ' — ' || d.departamento AS texto
        FROM vw_directorio d
        WHERE NOT EXISTS (SELECT 1 FROM usuarios_sistema u WHERE u.id_colaborador = d.id_colaborador)
        ORDER BY d.nombre_completo
    """

    def listar(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_LISTAR)

    def colaboradores_sin_cuenta(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_SIN_CUENTA)

    def cambiar_estado(self, cuenta: str, activo: bool) -> None:
        self._consultar(self.SQL_ESTADO, (cuenta, activo))

    def restablecer_password(self, cuenta: str, password: str) -> None:
        self._consultar(self.SQL_PASSWORD, (cuenta, password))

    @staticmethod
    def crear(conexion_admin: psycopg.Connection, usuario: UsuarioSistema, password: str) -> int:
        """Crea la cuenta usando una conexión temporal con credenciales de administrador."""
        usuario.validar()
        dao = BaseDAO(conexion_admin)
        return dao._escalar(UsuarioDAO.SQL_CREAR, (usuario.cuenta, password,
                                                   usuario.rol_aplicacion, usuario.id_colaborador))
