"""Entidades del modelo v2 (dataclasses).

Cada clase refleja una tabla. Los DAO las usan para recibir datos de las
pantallas y validarlos antes de enviarlos a la base de datos; las
consultas de listado devuelven diccionarios porque provienen de vistas
con columnas calculadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from control_acceso.utils.errores import ErrorAplicacion


def _requerido(valor: object, nombre: str) -> None:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ErrorAplicacion(f"El campo «{nombre}» es obligatorio.")


@dataclass
class Colaborador:
    numero_empleado: str
    nombre: str
    apellido_paterno: str
    apellido_materno: str | None
    tipo_colaborador: str
    id_puesto: int | None
    id_horario: int | None
    telefono: str
    correo: str
    fecha_ingreso: date
    activo: bool = True
    fecha_baja: date | None = None
    id_colaborador: int | None = None

    def validar(self) -> None:
        _requerido(self.numero_empleado, "Número de empleado")
        _requerido(self.nombre, "Nombre")
        _requerido(self.apellido_paterno, "Apellido paterno")
        _requerido(self.id_puesto, "Puesto")
        _requerido(self.id_horario, "Turno")
        _requerido(self.telefono, "Teléfono")
        _requerido(self.correo, "Correo")
        if self.tipo_colaborador not in ("empleado", "contratista"):
            raise ErrorAplicacion("El tipo debe ser empleado o contratista.")
        if "@" not in self.correo:
            raise ErrorAplicacion("El correo electrónico no es válido.")
        if not self.telefono.strip().isdigit():
            raise ErrorAplicacion("El teléfono solo debe contener números.")


@dataclass
class Visitante:
    nombre: str
    apellido_paterno: str
    apellido_materno: str | None
    id_tipo_identificacion: int | None
    numero_identificacion: str
    id_empresa: int | None = None
    telefono: str | None = None
    id_visitante: int | None = None

    def validar(self) -> None:
        _requerido(self.nombre, "Nombre")
        _requerido(self.apellido_paterno, "Apellido paterno")
        _requerido(self.id_tipo_identificacion, "Tipo de identificación")
        _requerido(self.numero_identificacion, "Número de identificación")


@dataclass
class Visita:
    id_visitante: int | None
    id_colaborador_anfitrion: int | None
    fecha_visita: date
    motivo: str
    estado: str = "programada"
    id_visita: int | None = None

    def validar(self) -> None:
        _requerido(self.id_visitante, "Visitante")
        _requerido(self.id_colaborador_anfitrion, "Anfitrión")
        _requerido(self.motivo, "Motivo")
        if self.fecha_visita < date.today() and self.id_visita is None:
            raise ErrorAplicacion("No se pueden programar visitas en fechas pasadas.")


@dataclass
class Credencial:
    id_rol_acceso: int | None
    fecha_vigencia: date
    id_colaborador: int | None = None
    id_visita: int | None = None
    fecha_emision: date = field(default_factory=date.today)
    id_estado: int = 1
    codigo_qr: str | None = None          # None = lo genera la base de datos
    id_credencial: int | None = None

    def validar(self) -> None:
        _requerido(self.id_rol_acceso, "Rol de acceso")
        if (self.id_colaborador is None) == (self.id_visita is None):
            raise ErrorAplicacion("La credencial debe ser de un colaborador o de una visita.")
        if self.fecha_vigencia < self.fecha_emision:
            raise ErrorAplicacion("La vigencia no puede ser anterior a la fecha de emisión.")


@dataclass
class PuntoAcceso:
    id_punto_acceso: int
    nombre: str
    tipo_punto: str = "mixto"
    activo: bool = True


@dataclass
class ResultadoLectura:
    """Respuesta de sp_registrar_acceso."""

    estado_lectura: str            # permitido | denegado | repetido | no_encontrado
    evento: str | None
    persona: str | None
    mensaje: str

    @property
    def permitido(self) -> bool:
        return self.estado_lectura == "permitido"


@dataclass
class UsuarioSistema:
    cuenta: str
    rol_aplicacion: str
    id_colaborador: int | None = None
    activo: bool = True

    def validar(self) -> None:
        _requerido(self.cuenta, "Cuenta")
        _requerido(self.rol_aplicacion, "Rol")
