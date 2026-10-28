"""DAO genérico para los catálogos simples.

El SQL se arma con psycopg.sql: los nombres de tabla y columna vienen del
descriptor (código del programa) y se escapan con sql.Identifier; los
valores siempre viajan como parámetros.
"""

from __future__ import annotations

from typing import Any

from psycopg import sql

from control_acceso.dao.base_dao import BaseDAO
from control_acceso.models.catalogos import CampoCatalogo, DescriptorCatalogo


class CatalogoDAO(BaseDAO):

    def __init__(self, descriptor: DescriptorCatalogo) -> None:
        super().__init__()
        self.d = descriptor

    def listar(self) -> list[dict[str, Any]]:
        consulta = sql.SQL("SELECT * FROM {tabla} ORDER BY {orden}").format(
            tabla=sql.Identifier(self.d.tabla),
            orden=sql.Identifier(self.d.orden or self.d.pk),
        )
        return self._consultar(consulta)

    def opciones(self, campo: CampoCatalogo) -> list[dict[str, Any]]:
        """Pares (id, texto) para un campo de llave foránea."""
        assert campo.fk_tabla and campo.fk_id and campo.fk_texto
        consulta = sql.SQL("SELECT {id} AS id, {texto} AS texto FROM {tabla} ORDER BY 2").format(
            id=sql.Identifier(campo.fk_id),
            texto=sql.Identifier(campo.fk_texto),
            tabla=sql.Identifier(campo.fk_tabla),
        )
        return self._consultar(consulta)

    def insertar(self, valores: dict[str, Any]) -> Any:
        columnas = [c.columna for c in self.d.campos if c.columna in valores]
        consulta = sql.SQL("INSERT INTO {tabla} ({cols}) VALUES ({vals}) RETURNING {pk}").format(
            tabla=sql.Identifier(self.d.tabla),
            cols=sql.SQL(", ").join(map(sql.Identifier, columnas)),
            vals=sql.SQL(", ").join([sql.Placeholder()] * len(columnas)),
            pk=sql.Identifier(self.d.pk),
        )
        return self._escalar(consulta, [valores[c] for c in columnas])

    def actualizar(self, id_registro: Any, valores: dict[str, Any]) -> int:
        columnas = [c.columna for c in self.d.campos
                    if c.columna in valores and c.columna != self.d.pk]
        consulta = sql.SQL("UPDATE {tabla} SET {asignaciones} WHERE {pk} = %s").format(
            tabla=sql.Identifier(self.d.tabla),
            asignaciones=sql.SQL(", ").join(
                sql.SQL("{} = %s").format(sql.Identifier(c)) for c in columnas),
            pk=sql.Identifier(self.d.pk),
        )
        return self._ejecutar(consulta, [valores[c] for c in columnas] + [id_registro])

    def eliminar(self, id_registro: Any) -> int:
        consulta = sql.SQL("DELETE FROM {tabla} WHERE {pk} = %s").format(
            tabla=sql.Identifier(self.d.tabla),
            pk=sql.Identifier(self.d.pk),
        )
        return self._ejecutar(consulta, [id_registro])
