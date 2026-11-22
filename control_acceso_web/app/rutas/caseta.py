"""Caseta de vigilancia: lector QR con la cámara, NIP y registro manual."""
from __future__ import annotations

from flask import Blueprint, render_template, request, session

from .. import db
from ..seguridad import requiere

bp = Blueprint("caseta", __name__, url_prefix="/caseta")


@bp.route("/")
@requiere("caseta")
def inicio():
    puntos = db.todos("SELECT * FROM puntos_acceso WHERE activo ORDER BY id_punto")
    punto = session.get("punto") or (puntos[0]["id_punto"] if puntos else None)
    ultimos = db.todos("SELECT * FROM vw_bitacora WHERE fecha = fecha_local(now()) "
                       "ORDER BY fecha_hora DESC LIMIT 8")
    return render_template("caseta.html", puntos=puntos, punto=punto, ultimos=ultimos)


@bp.route("/registrar", methods=["POST"])
@requiere("caseta")
def registrar():
    datos = request.get_json(silent=True) or {}
    metodo = datos.get("metodo")
    if metodo not in ("qr", "nip", "manual"):
        return {"error": "Método no válido"}, 400
    try:
        punto = int(datos.get("punto"))
    except (TypeError, ValueError):
        return {"error": "Seleccione el punto de acceso"}, 400
    dato = str(datos.get("dato") or "").strip()[:60]
    if not dato:
        return {"error": "No se recibió ningún dato"}, 400
    session["punto"] = punto
    try:
        r = db.uno("SELECT * FROM fn_registrar_acceso(%s, %s, %s, %s, %s)",
                   (metodo, dato, punto, datos.get("nip"), session["id_usuario"]))
    except db.ErrorBD as e:
        return {"error": str(e)}, 400
    return dict(r)


@bp.route("/buscar")
@requiere("caseta")
def buscar():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return {"personas": []}
    patron = f"%{q.lower()}%"
    filas = db.todos(
        """SELECT p.id_persona, p.nombre_completo, p.tipo, p.numero, p.adscripcion, p.activo,
                  EXISTS (SELECT 1 FROM vw_presentes x WHERE x.id_persona = p.id_persona) AS dentro,
                  (SELECT c.estado FROM vw_credenciales c WHERE c.id_persona = p.id_persona
                    ORDER BY (c.estado = 'vigente') DESC, c.id_credencial DESC LIMIT 1) AS credencial
             FROM vw_personas p
            WHERE lower(p.nombre_completo) LIKE %s OR lower(coalesce(p.numero, '')) LIKE %s
               OR lower(coalesce(p.identificacion, '')) LIKE %s OR lower(coalesce(p.adscripcion, '')) LIKE %s
            ORDER BY p.activo DESC, p.nombre_completo
            LIMIT 10""", (patron, patron, patron, patron))
    return {"personas": [dict(f) for f in filas]}
