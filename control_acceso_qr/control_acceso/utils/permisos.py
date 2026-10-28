"""Gestor de permisos de la interfaz.

La seguridad real la aplica PostgreSQL (GRANT por rol). Este módulo solo
decide qué opciones del menú se muestran y si una pantalla permite editar,
para que el usuario no vea botones que la base de datos le negaría.
Los roles de la sesión se obtienen con pg_has_role() al iniciar sesión.
"""

from __future__ import annotations

from dataclasses import dataclass

from control_acceso.utils.conexion import sesion

TODOS = frozenset({"rol_admin_bd", "rol_seguridad", "rol_recepcion",
                   "rol_rrhh", "rol_consulta", "rol_lector_qr"})


@dataclass(frozen=True)
class Modulo:
    clave: str
    titulo: str
    roles_ver: frozenset[str]
    roles_editar: frozenset[str] = frozenset()


# Módulos de la ventana principal. El administrador ve y edita todo.
MODULOS: list[Modulo] = [
    Modulo("inicio", "Inicio", TODOS),
    Modulo("lector", "Lector QR", frozenset({"rol_lector_qr", "rol_seguridad"}),
           frozenset({"rol_lector_qr", "rol_seguridad"})),
    Modulo("bitacora", "Bitácora", frozenset({"rol_seguridad", "rol_consulta"})),
    Modulo("colaboradores", "Colaboradores", frozenset({"rol_rrhh"}), frozenset({"rol_rrhh"})),
    Modulo("visitas", "Visitantes y visitas", frozenset({"rol_recepcion"}),
           frozenset({"rol_recepcion"})),
    Modulo("credenciales", "Credenciales", frozenset({"rol_seguridad", "rol_recepcion"}),
           frozenset({"rol_seguridad", "rol_recepcion"})),
    Modulo("catalogos", "Catálogos", frozenset({"rol_rrhh", "rol_seguridad", "rol_recepcion"})),
    Modulo("usuarios", "Usuarios", frozenset()),          # solo administrador
]

# Capacidades puntuales dentro de una pantalla
CAPACIDADES: dict[str, frozenset[str]] = {
    "ver_personas_dentro": frozenset({"rol_seguridad", "rol_recepcion", "rol_consulta"}),
    "emitir_credencial_colaborador": frozenset({"rol_seguridad"}),
    "emitir_credencial_visita": frozenset({"rol_seguridad", "rol_recepcion"}),
    "cambiar_vigencia_credencial": frozenset({"rol_seguridad"}),
}


def puede_ver(modulo: Modulo) -> bool:
    return sesion.tiene_rol(*modulo.roles_ver)


def puede_editar(modulo: Modulo) -> bool:
    return sesion.tiene_rol(*modulo.roles_editar)


def tiene_capacidad(clave: str) -> bool:
    return sesion.tiene_rol(*CAPACIDADES.get(clave, frozenset()))


def modulo(clave: str) -> Modulo:
    return next(m for m in MODULOS if m.clave == clave)
