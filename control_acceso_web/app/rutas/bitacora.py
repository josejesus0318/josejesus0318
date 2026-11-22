"""Bitácora de accesos, asistencia (llegadas y salidas) y personas dentro del campus."""
from __future__ import annotations

import csv
import io

from flask import Blueprint, Response, render_template, request

from .. import db
from ..seguridad import requiere
from ..utilidades import duracion

bp = Blueprint("bitacora", __name__, url_prefix="/bitacora")


def hoy() -> str:
    return db.uno("SELECT fecha_local(now())::text AS d")["d"]


def csv_respuesta(nombre: str, encabezados: list[str], filas: list[list]) -> Response:
    salida = io.StringIO()
    salida.write("﻿")                                   # BOM: Excel abre bien los acentos
    escritor = csv.writer(salida)
    escritor.writerow(encabezados)
    escritor.writerows(filas)
    return Response(salida.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


@bp.route("/")
@requiere("bitacora")
def lista():
    a = request.args
    desde, hasta = a.get("desde") or hoy(), a.get("hasta") or hoy()
    filtros, params = ["fecha BETWEEN %s AND %s"], [desde, hasta]
    for campo in ("resultado", "metodo", "evento"):
        if a.get(campo):
            filtros.append(f"{campo} = %s")
            params.append(a[campo])
    if a.get("punto"):
        filtros.append("id_punto = %s")
        params.append(a.get("punto", type=int))
    if a.get("q"):
        filtros.append("(lower(persona) LIKE %s OR lower(coalesce(motivo,'')) LIKE %s)")
        params += [f"%{a['q'].lower()}%"] * 2
    registros = db.todos(f"SELECT * FROM vw_bitacora WHERE {' AND '.join(filtros)} "
                         "ORDER BY fecha_hora DESC LIMIT 1000", params)
    if a.get("formato") == "csv":
        return csv_respuesta(f"bitacora_{desde}_{hasta}.csv",
                             ["Fecha", "Hora", "Punto", "Persona", "Tipo", "Método", "Evento", "Resultado", "Motivo",
                              "Operador"],
                             [[r["fecha"], r["hora"], r["punto"], r["persona"], r["tipo"], r["metodo"], r["evento"],
                               r["resultado"], r["motivo"], r["operador"]] for r in registros])
    puntos = db.todos("SELECT id_punto, nombre FROM puntos_acceso ORDER BY id_punto")
    return render_template("bitacora/lista.html", registros=registros, puntos=puntos, desde=desde, hasta=hasta,
                           f=a)


@bp.route("/asistencia")
@requiere("bitacora")
def asistencia():
    a = request.args
    desde, hasta = a.get("desde") or hoy(), a.get("hasta") or hoy()
    filtros, params = ["fecha BETWEEN %s AND %s"], [desde, hasta]
    if a.get("tipo"):
        filtros.append("tipo = %s")
        params.append(a["tipo"])
    if a.get("q"):
        filtros.append("(lower(persona) LIKE %s OR lower(coalesce(numero,'')) LIKE %s)")
        params += [f"%{a['q'].lower()}%"] * 2
    filas = db.todos(f"SELECT * FROM vw_asistencia WHERE {' AND '.join(filtros)} "
                     "ORDER BY fecha DESC, hora_llegada NULLS LAST LIMIT 1000", params)
    if a.get("formato") == "csv":
        return csv_respuesta(f"asistencia_{desde}_{hasta}.csv",
                             ["Fecha", "Persona", "Tipo", "Número", "Adscripción", "Llegada", "Salida",
                              "Tiempo en el campus", "Estado"],
                             [[f["fecha"], f["persona"], f["tipo"], f["numero"], f["adscripcion"], f["hora_llegada"],
                               f["hora_salida"], duracion(f["tiempo_en_campus"]), f["estado"]] for f in filas])
    tipos = db.todos("SELECT nombre FROM tipos_persona ORDER BY id_tipo")
    return render_template("bitacora/asistencia.html", filas=filas, tipos=tipos, desde=desde, hasta=hasta, f=a)


@bp.route("/presentes")
@requiere("bitacora")
def presentes():
    filas = db.todos("SELECT * FROM vw_presentes ORDER BY desde DESC")
    return render_template("bitacora/presentes.html", filas=filas)
