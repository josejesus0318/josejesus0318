"""Acceso a datos de visitantes y visitas (Recepción)."""

from __future__ import annotations

from datetime import date
from typing import Any

from control_acceso.dao.base_dao import BaseDAO
from control_acceso.models.entidades import Visita, Visitante


class VisitaDAO(BaseDAO):

    SQL_VISITANTES = """
        SELECT id_visitante, nombre, apellido_paterno, apellido_materno, nombre_completo,
               id_tipo_identificacion, tipo_identificacion, numero_identificacion,
               id_empresa, empresa, telefono, total_visitas
        FROM vw_visitantes_detalle
        WHERE %(texto)s = ''
           OR nombre_completo       ILIKE '%%' || %(texto)s || '%%'
           OR numero_identificacion ILIKE '%%' || %(texto)s || '%%'
           OR empresa               ILIKE '%%' || %(texto)s || '%%'
        ORDER BY apellido_paterno, nombre
    """

    SQL_INSERTAR_VISITANTE = """
        INSERT INTO visitantes (nombre, apellido_paterno, apellido_materno, id_tipo_identificacion,
                                numero_identificacion, id_empresa, telefono)
        VALUES (%(nombre)s, %(apellido_paterno)s, %(apellido_materno)s, %(id_tipo_identificacion)s,
                %(numero_identificacion)s, %(id_empresa)s, %(telefono)s)
        RETURNING id_visitante
    """

    SQL_ACTUALIZAR_VISITANTE = """
        UPDATE visitantes
           SET nombre = %(nombre)s, apellido_paterno = %(apellido_paterno)s,
               apellido_materno = %(apellido_materno)s,
               id_tipo_identificacion = %(id_tipo_identificacion)s,
               numero_identificacion = %(numero_identificacion)s,
               id_empresa = %(id_empresa)s, telefono = %(telefono)s
         WHERE id_visitante = %(id_visitante)s
    """

    SQL_VISITAS = """
        SELECT id_visita, id_visitante, visitante, empresa, fecha_visita, motivo, estado,
               id_colaborador_anfitrion, anfitrion, area_visitada, ubicacion, codigo_qr
        FROM vw_visitas_detalle
        WHERE (%(id_visitante)s::int IS NULL OR id_visitante = %(id_visitante)s::int)
          AND (%(fecha)s::date IS NULL OR fecha_visita = %(fecha)s::date)
        ORDER BY fecha_visita DESC, id_visita DESC
    """

    SQL_PROGRAMAR = """
        INSERT INTO visitas (id_visitante, id_colaborador_anfitrion, fecha_visita, motivo)
        VALUES (%(id_visitante)s, %(id_colaborador_anfitrion)s, %(fecha_visita)s, %(motivo)s)
        RETURNING id_visita
    """

    # Cancela la visita y revoca su credencial activa en una sola sentencia
    SQL_CANCELAR = """
        WITH v AS (
            UPDATE visitas SET estado = 'cancelada'
             WHERE id_visita = %s AND estado = 'programada'
            RETURNING id_visita
        ), c AS (
            UPDATE credenciales SET id_estado = 3
             WHERE id_visita IN (SELECT id_visita FROM v) AND id_estado = 1
            RETURNING id_credencial
        )
        SELECT (SELECT COUNT(*) FROM v) AS visitas, (SELECT COUNT(*) FROM c) AS credenciales
    """

    SQL_ANFITRIONES = """
        SELECT id_colaborador AS id, nombre_completo || ' — ' || departamento AS texto
        FROM vw_directorio ORDER BY nombre_completo
    """
    SQL_TIPOS_ID = """
        SELECT id_tipo_identificacion AS id, clave || ' – ' || nombre AS texto
        FROM tipos_identificacion ORDER BY clave
    """
    SQL_EMPRESAS = "SELECT id_empresa AS id, nombre AS texto FROM empresas ORDER BY nombre"

    # -- visitantes ------------------------------------------------------
    def listar_visitantes(self, texto: str = "") -> list[dict[str, Any]]:
        return self._consultar(self.SQL_VISITANTES, {"texto": texto.strip()})

    def insertar_visitante(self, v: Visitante) -> int:
        v.validar()
        return self._escalar(self.SQL_INSERTAR_VISITANTE, self._param_visitante(v))

    def actualizar_visitante(self, v: Visitante) -> None:
        v.validar()
        self._ejecutar(self.SQL_ACTUALIZAR_VISITANTE, self._param_visitante(v))

    # -- visitas -----------------------------------------------------------
    def listar_visitas(self, id_visitante: int | None = None,
                       fecha: date | None = None) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_VISITAS, {"id_visitante": id_visitante, "fecha": fecha})

    def programar_visita(self, v: Visita) -> int:
        v.validar()
        return self._escalar(self.SQL_PROGRAMAR, {
            "id_visitante": v.id_visitante,
            "id_colaborador_anfitrion": v.id_colaborador_anfitrion,
            "fecha_visita": v.fecha_visita,
            "motivo": v.motivo.strip(),
        })

    def cancelar_visita(self, id_visita: int) -> dict[str, int]:
        return self._consultar_uno(self.SQL_CANCELAR, (id_visita,)) or {"visitas": 0, "credenciales": 0}

    # -- listas para los formularios ---------------------------------------
    def anfitriones(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_ANFITRIONES)

    def tipos_identificacion(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_TIPOS_ID)

    def empresas(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_EMPRESAS)

    @staticmethod
    def _param_visitante(v: Visitante) -> dict[str, Any]:
        return {
            "id_visitante": v.id_visitante,
            "nombre": v.nombre.strip(),
            "apellido_paterno": v.apellido_paterno.strip(),
            "apellido_materno": (v.apellido_materno or "").strip() or None,
            "id_tipo_identificacion": v.id_tipo_identificacion,
            "numero_identificacion": v.numero_identificacion.strip().upper(),
            "id_empresa": v.id_empresa,
            "telefono": (v.telefono or "").strip() or None,
        }
