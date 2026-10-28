"""Descriptores de los catálogos simples.

Un descriptor indica qué tabla administra el Panel Genérico de Catálogos,
qué campos muestra, de qué tipo son y quién puede editarlo. Con esto, una
sola clase de pantalla (views/panel_catalogo.py) y una sola clase DAO
(dao/catalogo_dao.py) sirven para todos los catálogos.

Los nombres de tabla y columna salen de este archivo (código del
programa), nunca de lo que escribe el usuario.
"""

from __future__ import annotations

from dataclasses import dataclass, field

TIPOS_CAMPO = ("texto", "entero", "hora", "booleano", "fk", "opciones")


@dataclass(frozen=True)
class CampoCatalogo:
    columna: str
    etiqueta: str
    tipo: str = "texto"
    requerido: bool = True
    longitud: int = 100
    # Para tipo "fk": tabla, columna id y columna de texto a mostrar
    fk_tabla: str | None = None
    fk_id: str | None = None
    fk_texto: str | None = None
    # Para tipo "opciones": valores permitidos
    opciones: tuple[str, ...] = ()
    minimo: int = -1_000_000
    maximo: int = 1_000_000


@dataclass(frozen=True)
class DescriptorCatalogo:
    clave: str
    titulo: str
    tabla: str
    pk: str
    campos: tuple[CampoCatalogo, ...]
    roles_ver: frozenset[str]
    roles_editar: frozenset[str] = field(default_factory=frozenset)
    pk_autogenerada: bool = True       # False: el usuario captura la clave (p. ej. id_dia)
    orden: str | None = None           # columna para ordenar el listado


CATALOGOS: tuple[DescriptorCatalogo, ...] = (
    DescriptorCatalogo(
        "ubicaciones", "Ubicaciones", "ubicaciones", "id_ubicacion",
        (CampoCatalogo("nombre", "Nombre", longitud=80),
         CampoCatalogo("piso", "Piso", "entero", minimo=-5, maximo=50),
         CampoCatalogo("descripcion", "Descripción", requerido=False, longitud=200)),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset({"rol_rrhh"}),
        orden="nombre"),
    DescriptorCatalogo(
        "departamentos", "Departamentos", "departamentos", "id_departamento",
        (CampoCatalogo("nombre", "Nombre", longitud=60),
         CampoCatalogo("id_ubicacion", "Ubicación", "fk", fk_tabla="ubicaciones",
                       fk_id="id_ubicacion", fk_texto="nombre")),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset({"rol_rrhh"}),
        orden="nombre"),
    DescriptorCatalogo(
        "puestos", "Puestos", "puestos", "id_puesto",
        (CampoCatalogo("nombre", "Nombre", longitud=80),
         CampoCatalogo("id_departamento", "Departamento", "fk", fk_tabla="departamentos",
                       fk_id="id_departamento", fk_texto="nombre")),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset({"rol_rrhh"}),
        orden="nombre"),
    DescriptorCatalogo(
        "horarios", "Horarios laborales", "horarios_laborales", "id_horario",
        (CampoCatalogo("nombre_turno", "Turno", longitud=40),
         CampoCatalogo("hora_entrada", "Hora de entrada", "hora"),
         CampoCatalogo("hora_salida", "Hora de salida", "hora")),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset({"rol_rrhh"}),
        orden="hora_entrada"),
    DescriptorCatalogo(
        "dias", "Días de la semana", "dias_semana", "id_dia",
        (CampoCatalogo("id_dia", "Número (1 = lunes)", "entero", minimo=1, maximo=7),
         CampoCatalogo("nombre", "Nombre", longitud=10),
         CampoCatalogo("abreviatura", "Abreviatura", longitud=3)),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset(),
        pk_autogenerada=False, orden="id_dia"),
    DescriptorCatalogo(
        "empresas", "Empresas", "empresas", "id_empresa",
        (CampoCatalogo("nombre", "Nombre", longitud=100),
         CampoCatalogo("rfc", "RFC", requerido=False, longitud=13),
         CampoCatalogo("telefono", "Teléfono", requerido=False, longitud=15)),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset({"rol_recepcion"}),
        orden="nombre"),
    DescriptorCatalogo(
        "tipos_identificacion", "Tipos de identificación", "tipos_identificacion",
        "id_tipo_identificacion",
        (CampoCatalogo("clave", "Clave", longitud=5),
         CampoCatalogo("nombre", "Nombre", longitud=60)),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset(),
        orden="clave"),
    DescriptorCatalogo(
        "roles_acceso", "Roles de acceso", "roles_acceso", "id_rol_acceso",
        (CampoCatalogo("nombre", "Nombre", longitud=60),
         CampoCatalogo("descripcion", "Descripción", longitud=200)),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset({"rol_seguridad"}),
        orden="nombre"),
    DescriptorCatalogo(
        "puntos_acceso", "Puntos de acceso", "puntos_acceso", "id_punto_acceso",
        (CampoCatalogo("nombre", "Nombre", longitud=70),
         CampoCatalogo("id_ubicacion", "Ubicación", "fk", fk_tabla="ubicaciones",
                       fk_id="id_ubicacion", fk_texto="nombre"),
         CampoCatalogo("tipo_punto", "Tipo", "opciones", opciones=("mixto", "entrada", "salida")),
         CampoCatalogo("activo", "Activo", "booleano")),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset({"rol_seguridad"}),
        orden="nombre"),
    DescriptorCatalogo(
        "estados_credencial", "Estados de credencial", "estados_credencial", "id_estado",
        (CampoCatalogo("id_estado", "Número", "entero", minimo=1, maximo=99),
         CampoCatalogo("clave", "Clave", longitud=12),
         CampoCatalogo("descripcion", "Descripción", longitud=100),
         CampoCatalogo("permite_acceso", "Permite acceso", "booleano")),
        frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"}), frozenset(),
        pk_autogenerada=False, orden="id_estado"),
)


def catalogo(clave: str) -> DescriptorCatalogo:
    return next(d for d in CATALOGOS if d.clave == clave)
