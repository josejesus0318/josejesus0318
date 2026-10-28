"""Acceso a datos de colaboradores (Recursos Humanos)."""

from __future__ import annotations

from datetime import date
from typing import Any

from control_acceso.dao.base_dao import BaseDAO
from control_acceso.models.entidades import Colaborador


class ColaboradorDAO(BaseDAO):

    SQL_LISTAR = """
        SELECT id_colaborador, numero_empleado, nombre, apellido_paterno, apellido_materno,
               nombre_completo, tipo_colaborador, id_puesto, puesto, departamento,
               id_horario, nombre_turno, telefono, correo, fecha_ingreso, activo, fecha_baja
        FROM vw_colaboradores_detalle
        WHERE (%(todos)s OR activo)
          AND (%(texto)s = ''
               OR nombre_completo ILIKE '%%' || %(texto)s || '%%'
               OR numero_empleado ILIKE '%%' || %(texto)s || '%%'
               OR departamento    ILIKE '%%' || %(texto)s || '%%')
        ORDER BY activo DESC, apellido_paterno, nombre
    """

    SQL_INSERTAR = """
        INSERT INTO colaboradores (numero_empleado, nombre, apellido_paterno, apellido_materno,
                                   tipo_colaborador, id_puesto, id_horario, telefono, correo,
                                   fecha_ingreso)
        VALUES (%(numero_empleado)s, %(nombre)s, %(apellido_paterno)s, %(apellido_materno)s,
                %(tipo_colaborador)s, %(id_puesto)s, %(id_horario)s, %(telefono)s, %(correo)s,
                %(fecha_ingreso)s)
        RETURNING id_colaborador
    """

    SQL_ACTUALIZAR = """
        UPDATE colaboradores
           SET numero_empleado = %(numero_empleado)s, nombre = %(nombre)s,
               apellido_paterno = %(apellido_paterno)s, apellido_materno = %(apellido_materno)s,
               tipo_colaborador = %(tipo_colaborador)s, id_puesto = %(id_puesto)s,
               id_horario = %(id_horario)s, telefono = %(telefono)s, correo = %(correo)s,
               fecha_ingreso = %(fecha_ingreso)s
         WHERE id_colaborador = %(id_colaborador)s
    """

    # Baja lógica: nunca se borra; el trigger revoca sus credenciales
    SQL_BAJA = """
        UPDATE colaboradores SET activo = FALSE, fecha_baja = %s
         WHERE id_colaborador = %s AND activo
    """
    SQL_REACTIVAR = """
        UPDATE colaboradores SET activo = TRUE, fecha_baja = NULL
         WHERE id_colaborador = %s AND NOT activo
    """

    SQL_PUESTOS = """
        SELECT p.id_puesto AS id, p.nombre || ' — ' || d.nombre AS texto
        FROM puestos p JOIN departamentos d ON d.id_departamento = p.id_departamento
        ORDER BY d.nombre, p.nombre
    """
    SQL_HORARIOS = """
        SELECT id_horario AS id,
               nombre_turno || ' (' || to_char(hora_entrada, 'HH24:MI') || ' – '
                            || to_char(hora_salida, 'HH24:MI') || ')' AS texto
        FROM horarios_laborales ORDER BY hora_entrada
    """

    def listar(self, texto: str = "", incluir_bajas: bool = False) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_LISTAR, {"todos": incluir_bajas, "texto": texto.strip()})

    def insertar(self, c: Colaborador) -> int:
        c.validar()
        return self._escalar(self.SQL_INSERTAR, self._parametros(c))

    def actualizar(self, c: Colaborador) -> None:
        c.validar()
        self._ejecutar(self.SQL_ACTUALIZAR, self._parametros(c))

    def dar_de_baja(self, id_colaborador: int, fecha_baja: date) -> bool:
        return self._ejecutar(self.SQL_BAJA, (fecha_baja, id_colaborador)) > 0

    def reactivar(self, id_colaborador: int) -> bool:
        return self._ejecutar(self.SQL_REACTIVAR, (id_colaborador,)) > 0

    def puestos(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_PUESTOS)

    def horarios(self) -> list[dict[str, Any]]:
        return self._consultar(self.SQL_HORARIOS)

    @staticmethod
    def _parametros(c: Colaborador) -> dict[str, Any]:
        return {
            "id_colaborador": c.id_colaborador,
            "numero_empleado": c.numero_empleado.strip().upper(),
            "nombre": c.nombre.strip(),
            "apellido_paterno": c.apellido_paterno.strip(),
            "apellido_materno": (c.apellido_materno or "").strip() or None,
            "tipo_colaborador": c.tipo_colaborador,
            "id_puesto": c.id_puesto,
            "id_horario": c.id_horario,
            "telefono": c.telefono.strip(),
            "correo": c.correo.strip().lower(),
            "fecha_ingreso": c.fecha_ingreso,
        }
