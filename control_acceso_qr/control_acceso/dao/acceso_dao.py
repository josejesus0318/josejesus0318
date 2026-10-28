"""Lector QR y bitácora de accesos."""

from __future__ import annotations

from datetime import date
from typing import Any

from control_acceso.dao.base_dao import BaseDAO
from control_acceso.models.entidades import PuntoAcceso, ResultadoLectura


class AccesoDAO(BaseDAO):

    # Solo columnas que rol_lector_qr tiene permitidas (GRANT por columna)
    SQL_PUNTOS = """
        SELECT id_punto_acceso, nombre, tipo_punto, activo
        FROM puntos_acceso WHERE activo ORDER BY id_punto_acceso
    """

    # Toda la validación y el registro ocurren dentro de la base de datos
    SQL_REGISTRAR = "SELECT estado_lectura, evento, persona, mensaje FROM sp_registrar_acceso(%s, %s)"

    SQL_BITACORA = """
        SELECT id_registro, fecha_hora, persona, tipo_persona, codigo_qr, punto_acceso,
               tipo_evento, resultado, motivo, registrado_por
        FROM vw_bitacora
        WHERE fecha_hora >= %(desde)s::date
          AND fecha_hora <  %(hasta)s::date + 1
          AND (%(resultado)s::text IS NULL OR resultado = %(resultado)s::text)
          AND (%(texto)s = ''
               OR persona      ILIKE '%%' || %(texto)s || '%%'
               OR codigo_qr    ILIKE '%%' || %(texto)s || '%%'
               OR punto_acceso ILIKE '%%' || %(texto)s || '%%')
        ORDER BY fecha_hora DESC, id_registro DESC
        LIMIT %(limite)s
    """

    SQL_DENTRO = """
        SELECT persona, tipo_persona, codigo_qr, punto_acceso, hora_entrada
        FROM vw_personas_dentro ORDER BY hora_entrada
    """

    def puntos_activos(self) -> list[PuntoAcceso]:
        return [PuntoAcceso(f["id_punto_acceso"], f["nombre"], f["tipo_punto"], f["activo"])
                for f in self._consultar(self.SQL_PUNTOS)]

    def registrar_lectura(self, codigo_qr: str, id_punto: int) -> ResultadoLectura:
        fila = self._consultar_uno(self.SQL_REGISTRAR, (codigo_qr, id_punto))
        assert fila is not None
        return ResultadoLectura(fila["estado_lectura"], fila["evento"], fila["persona"], fila["mensaje"])

    def bitacora(self, desde: date, hasta: date, texto: str = "",
                 resultado: str | None = None, limite: int = 2000) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_BITACORA, {"desde": desde, "hasta": hasta,
                                                   "texto": texto.strip(),
                                                   "resultado": resultado, "limite": limite})

    def personas_dentro(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_DENTRO)
