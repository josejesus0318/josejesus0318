"""Filtros de plantillas y conversión de datos de formularios."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from flask import Flask, request

from .db import ErrorBD

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

ESTADOS_CREDENCIAL = {
    "vigente": ("Vigente", "ok"), "inactiva": ("Desactivada", "gris"), "vencida": ("Vencida", "mal"),
    "agotada": ("Usada", "mal"), "pendiente": ("Aún no inicia", "aviso"),
}


def fecha(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, datetime):
        return f"{v.day:02d} {MESES[v.month - 1]} {v.year} {v.hour:02d}:{v.minute:02d}"
    if isinstance(v, date):
        return f"{v.day:02d} {MESES[v.month - 1]} {v.year}"
    return str(v)


def hora(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, (datetime, time)):
        return f"{v.hour:02d}:{v.minute:02d}"
    return str(v)


def duracion(v) -> str:
    if not isinstance(v, timedelta):
        return "—"
    minutos = int(v.total_seconds() // 60)
    return f"{minutos // 60} h {minutos % 60:02d} min"


def registrar_filtros(app: Flask) -> None:
    app.jinja_env.filters.update(fecha=fecha, hora=hora, duracion=duracion)
    app.jinja_env.globals.update(ESTADOS_CREDENCIAL=ESTADOS_CREDENCIAL, DIAS=DIAS)


# ----------------------------------------------------------- lectura de formularios
def texto(nombre: str, obligatorio: bool = False, maximo: int = 200) -> str | None:
    valor = (request.form.get(nombre) or "").strip()
    if not valor:
        if obligatorio:
            raise ErrorBD(f"Falta el dato: {nombre.replace('_', ' ')}.")
        return None
    return valor[:maximo]


def entero(nombre: str, obligatorio: bool = False) -> int | None:
    valor = texto(nombre, obligatorio)
    if valor is None:
        return None
    try:
        return int(valor)
    except ValueError:
        raise ErrorBD(f"El dato {nombre.replace('_', ' ')} debe ser un número.") from None


def fecha_hora_local(nombre: str, obligatorio: bool = False) -> str | None:
    """Valor de un <input type=datetime-local> (hora del campus) como texto ISO."""
    valor = texto(nombre, obligatorio)
    if valor is None:
        return None
    try:
        return datetime.fromisoformat(valor).isoformat(sep=" ")
    except ValueError:
        raise ErrorBD(f"La fecha de {nombre.replace('_', ' ')} no es válida.") from None


def para_input(v: datetime | None) -> str:
    return v.strftime("%Y-%m-%dT%H:%M") if v else ""
