"""Acceso a datos de credenciales QR (Seguridad y Recepción)."""

from __future__ import annotations

from datetime import date
from typing import Any

from control_acceso.dao.base_dao import BaseDAO
from control_acceso.models.entidades import Credencial
from control_acceso.utils.errores import ErrorAplicacion


class CredencialDAO(BaseDAO):

    SQL_LISTAR = """
        SELECT id_credencial, codigo_qr, tipo_titular, titular, id_colaborador, id_visita,
               rol_acceso, id_estado, estado, fecha_emision, fecha_vigencia, dias_restantes
        FROM vw_credenciales_detalle
        WHERE (%(estado)s::int IS NULL OR id_estado = %(estado)s::int)
          AND (%(tipo)s::text IS NULL OR tipo_titular = %(tipo)s::text)
          AND (%(texto)s = ''
               OR titular   ILIKE '%%' || %(texto)s || '%%'
               OR codigo_qr ILIKE '%%' || %(texto)s || '%%')
        ORDER BY id_estado, fecha_vigencia
    """

    SQL_EMITIR = """
        INSERT INTO credenciales (id_rol_acceso, id_colaborador, id_visita, fecha_emision,
                                  fecha_vigencia, id_estado)
        VALUES (%(id_rol_acceso)s, %(id_colaborador)s, %(id_visita)s, %(fecha_emision)s,
                %(fecha_vigencia)s, %(id_estado)s)
        RETURNING id_credencial, codigo_qr
    """

    SQL_ACTIVA_DE_VISITA = """
        SELECT id_credencial, codigo_qr FROM credenciales
         WHERE id_visita = %s AND id_estado = 1
    """

    # Credencial de visita: rol de visitante y vigencia = día de la visita
    SQL_EMITIR_VISITA = """
        INSERT INTO credenciales (id_rol_acceso, id_visita, fecha_emision, fecha_vigencia)
        SELECT (SELECT id_rol_acceso FROM roles_acceso WHERE nombre = 'Acceso Temporal de Visitante'),
               v.id_visita, CURRENT_DATE, v.fecha_visita
          FROM visitas v
         WHERE v.id_visita = %s
        RETURNING id_credencial, codigo_qr
    """

    SQL_CAMBIAR_ESTADO = "UPDATE credenciales SET id_estado = %s WHERE id_credencial = %s"
    SQL_CAMBIAR_VIGENCIA = "UPDATE credenciales SET fecha_vigencia = %s WHERE id_credencial = %s"

    SQL_ESTADOS = "SELECT id_estado AS id, clave AS texto FROM estados_credencial ORDER BY id_estado"
    SQL_ROLES = "SELECT id_rol_acceso AS id, nombre AS texto FROM roles_acceso ORDER BY id_rol_acceso"
    SQL_COLABORADORES = """
        SELECT id_colaborador AS id, nombre_completo || ' (' || numero_empleado || ')' AS texto
        FROM vw_directorio ORDER BY nombre_completo
    """

    def listar(self, texto: str = "", id_estado: int | None = None,
               tipo_titular: str | None = None) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_LISTAR, {"texto": texto.strip(), "estado": id_estado,
                                                 "tipo": tipo_titular})

    def emitir(self, c: Credencial) -> dict[str, Any]:
        """Emite una credencial; el código QR lo genera la base de datos."""
        c.validar()
        fila = self._consultar_uno(self.SQL_EMITIR, {
            "id_rol_acceso": c.id_rol_acceso, "id_colaborador": c.id_colaborador,
            "id_visita": c.id_visita, "fecha_emision": c.fecha_emision,
            "fecha_vigencia": c.fecha_vigencia, "id_estado": c.id_estado,
        })
        assert fila is not None
        return fila

    def emitir_para_visita(self, id_visita: int) -> dict[str, Any]:
        """Emite la credencial temporal de una visita (o avisa si ya tiene una)."""
        existente = self._consultar_uno(self.SQL_ACTIVA_DE_VISITA, (id_visita,))
        if existente:
            raise ErrorAplicacion(f"La visita ya tiene la credencial activa {existente['codigo_qr']}.")
        fila = self._consultar_uno(self.SQL_EMITIR_VISITA, (id_visita,))
        if not fila:
            raise ErrorAplicacion("La visita seleccionada no existe.")
        return fila

    def cambiar_estado(self, id_credencial: int, id_estado: int) -> None:
        self._ejecutar(self.SQL_CAMBIAR_ESTADO, (id_estado, id_credencial))

    def cambiar_vigencia(self, id_credencial: int, fecha_vigencia: date) -> None:
        self._ejecutar(self.SQL_CAMBIAR_VIGENCIA, (fecha_vigencia, id_credencial))

    def estados(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_ESTADOS)

    def roles_acceso(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_ROLES)

    def colaboradores(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_COLABORADORES)
