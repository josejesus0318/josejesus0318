"""Kiosco de alumnos: computadora fija con cámara en un acceso del campus.

El alumno teclea su número de control (o muestra el código de su credencial a la
cámara). La pantalla muestra su foto para que el guardia la compare y la entrada
queda registrada en la bitácora. Las reglas están en fn_kiosco_registrar (PostgreSQL).
"""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session, url_for

from .. import db
from ..seguridad import requiere

bp = Blueprint("kiosco", __name__, url_prefix="/kiosco")

# Solo los accesos de entrada al campus pueden tener kiosco
PUNTOS_KIOSCO = ("SELECT id_punto, nombre, ubicacion FROM puntos_acceso "
                 "WHERE activo AND perimetral AND sentido IN ('entrada', 'ambos') ORDER BY id_punto")


@bp.route("/")
@requiere("kiosco")
def inicio():
    puntos = db.todos(PUNTOS_KIOSCO)
    elegido = request.args.get("punto", type=int) or session.get("punto_kiosco")
    if request.args.get("cambiar"):
        elegido = None
    if elegido is None and len(puntos) == 1:
        elegido = puntos[0]["id_punto"]
    punto = next((p for p in puntos if p["id_punto"] == elegido), None)
    if not punto:
        return render_template("kiosco.html", puntos=puntos, punto=None)
    session["punto_kiosco"] = punto["id_punto"]
    segundos = db.uno("SELECT config_int('kiosco_segundos_pantalla', 6) AS s")["s"]
    return render_template("kiosco.html", puntos=puntos, punto=punto, segundos=segundos)


@bp.route("/registrar", methods=["POST"])
@requiere("kiosco")
def registrar():
    datos = request.get_json(silent=True) or {}
    dato = str(datos.get("dato") or "").strip()[:60]
    if not dato:
        return {"error": "Escribe tu número de control"}, 400
    try:
        punto = int(datos.get("punto") or session.get("punto_kiosco"))
    except (TypeError, ValueError):
        return {"error": "El kiosco no tiene un acceso asignado"}, 400
    try:
        r = db.uno("SELECT * FROM fn_kiosco_registrar(%s, %s, %s)", (dato, punto, session["id_usuario"]))
    except db.ErrorBD as e:
        return {"error": str(e)}, 400
    r = dict(r)
    if r["id_persona"]:
        tiene_foto = db.uno("SELECT EXISTS (SELECT 1 FROM fotos_personas WHERE id_persona = %s) AS x",
                            (r["id_persona"],))["x"]
        r["foto"] = url_for("fotos.ver", id_persona=r["id_persona"])
        r["foto_ejemplo"] = not tiene_foto
    return r


@bp.route("/cambiar")
@requiere("kiosco")
def cambiar():
    session.pop("punto_kiosco", None)
    return redirect(url_for("kiosco.inicio", cambiar=1))
