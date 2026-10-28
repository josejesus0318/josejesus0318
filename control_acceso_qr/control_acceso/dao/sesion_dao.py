"""Datos de la sesión: roles del usuario e indicadores del día."""

from __future__ import annotations

from typing import Any

from control_acceso.dao.base_dao import BaseDAO
from control_acceso.utils.conexion import sesion

ROLES_APLICACION = ("rol_admin_bd", "rol_seguridad", "rol_recepcion",
                    "rol_rrhh", "rol_consulta", "rol_lector_qr")


class SesionDAO(BaseDAO):

    SQL_ROLES = """
        SELECT r.rolname
        FROM pg_roles r
        WHERE r.rolname = ANY(%s)
          AND pg_has_role(current_user, r.oid, 'MEMBER')
    """
    SQL_SUPERUSUARIO = "SELECT rolsuper FROM pg_roles WHERE rolname = current_user"
    SQL_MI_USUARIO = "SELECT cuenta, rol_aplicacion, nombre_completo, puesto FROM vw_mi_usuario"
    SQL_RESUMEN = "SELECT * FROM vw_resumen_hoy"

    def cargar_datos_sesion(self) -> None:
        """Detecta los roles con pg_has_role() y el nombre del usuario."""
        sesion.roles = {f["rolname"] for f in self._consultar(self.SQL_ROLES, (list(ROLES_APLICACION),))}
        sesion.es_superusuario = bool(self._escalar(self.SQL_SUPERUSUARIO))
        fila = None
        if sesion.roles or sesion.es_superusuario:
            fila = self._consultar_uno(self.SQL_MI_USUARIO)
        sesion.nombre_completo = (fila or {}).get("nombre_completo") or sesion.usuario

    def resumen_hoy(self) -> dict[str, Any]:
        return self._consultar_uno(self.SQL_RESUMEN) or {}
