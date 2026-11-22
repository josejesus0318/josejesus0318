"""Inicio de sesión y panel principal."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import db, seguridad
from ..seguridad import requiere

bp = Blueprint("panel", __name__)

PANTALLA_INICIAL = {"vigilancia": "caseta.inicio"}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr or "desconocida"
        if seguridad.login_bloqueado(ip):
            flash("Demasiados intentos fallidos. Espere 5 minutos.", "error")
            return render_template("login.html"), 429
        usuario = request.form.get("usuario", "")
        fila = db.uno("SELECT * FROM fn_login(%s, %s)", (usuario, request.form.get("password", "")))
        if not fila:
            seguridad.login_fallido(ip)
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template("login.html", usuario=usuario), 401
        seguridad.login_correcto(ip)
        session.clear()
        session.permanent = True
        session.update(id_usuario=fila["id_usuario"], usuario=fila["usuario"],
                       nombre=fila["nombre"], rol=fila["rol"])
        siguiente = request.args.get("siguiente", "")
        if siguiente.startswith("/") and not siguiente.startswith("//"):
            return redirect(siguiente)
        return redirect(url_for(PANTALLA_INICIAL.get(fila["rol"], "panel.inicio")))
    return render_template("login.html")


@bp.route("/salud")
def salud():
    """Diagnóstico sin iniciar sesión: ¿hay conexión con PostgreSQL y están instaladas las tablas?"""
    from urllib.parse import urlsplit

    from flask import current_app

    partes = urlsplit(current_app.config["DATABASE_URL"])
    info = {"servidor": partes.hostname, "base": partes.path.lstrip("/"), "usuario": partes.username}
    try:
        fila = db.uno("SELECT version() AS version, current_user AS usuario, "
                      "to_regclass('campus.personas') IS NOT NULL AS tablas")
    except db.ErrorBD as e:
        return {"base_de_datos": "error", "detalle": str(e), **info}, 503
    info.update(base_de_datos="ok", postgres=fila["version"].split(",")[0], tablas_instaladas=fila["tablas"])
    if fila["tablas"]:
        info["usuarios_app"] = db.uno("SELECT count(*) AS n FROM campus.usuarios")["n"]
    return info, (200 if fila["tablas"] else 503)


@bp.route("/salir", methods=["POST"])
def salir():
    session.clear()
    flash("Sesión cerrada.", "ok")
    return redirect(url_for("panel.login"))


@bp.route("/")
@requiere("panel")
def inicio():
    resumen = db.uno("SELECT * FROM vw_resumen_hoy")
    presentes = db.todos("SELECT * FROM vw_presentes ORDER BY desde DESC LIMIT 12")
    movimientos = db.todos("SELECT * FROM vw_bitacora ORDER BY fecha_hora DESC LIMIT 12")
    por_tipo = db.todos("SELECT tipo, count(*) AS total FROM vw_presentes GROUP BY tipo ORDER BY total DESC")
    alertas = db.todos(
        """SELECT * FROM vw_credenciales
            WHERE estado = 'vigente' AND vigencia_fin IS NOT NULL
              AND vigencia_fin < now() + interval '2 days'
            ORDER BY vigencia_fin LIMIT 6""")
    hoy = db.uno("SELECT fecha_local(now()) AS d")["d"]
    return render_template("panel.html", resumen=resumen, presentes=presentes, movimientos=movimientos,
                           por_tipo=por_tipo, alertas=alertas, hoy=hoy)
