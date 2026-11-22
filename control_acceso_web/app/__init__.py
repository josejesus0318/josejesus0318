"""Control de Acceso Campus ITVH – aplicación web (Flask + PostgreSQL)."""
from __future__ import annotations

import os
import secrets
from datetime import timedelta

from flask import Flask, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from . import db, seguridad
from .utilidades import registrar_filtros


def cargar_env(ruta: str) -> None:
    """Lee un archivo .env sencillo (CLAVE=valor) si existe. En la nube se usan variables de entorno."""
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def create_app(config: dict | None = None) -> Flask:
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cargar_env(os.path.join(raiz, ".env"))

    app = Flask(__name__)
    app.config.update(
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        ZONA_HORARIA=os.environ.get("ZONA_HORARIA", "America/Mexico_City"),
        INSTITUCION=os.environ.get("INSTITUCION", "Instituto Tecnológico de Villahermosa"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SEGURA", "1") == "1",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=10),
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    if config:
        app.config.update(config)
    app.config["DATABASE_URL"] = db.limpiar_url(app.config["DATABASE_URL"])
    if not os.environ.get("SECRET_KEY") and not (config or {}).get("SECRET_KEY"):
        app.logger.warning("SECRET_KEY no está definida: las sesiones se cerrarán al reiniciar el servidor.")
    if not app.config["DATABASE_URL"]:
        raise RuntimeError("Falta DATABASE_URL. Cópiela de Neon en el archivo .env o en las variables del servidor.")

    # En Render la aplicación está detrás de un proxy: así se obtiene la IP real y https
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    seguridad.init_app(app)
    registrar_filtros(app)

    from .rutas import admin, bitacora, caseta, credenciales, horarios, panel, pases, personas

    for modulo in (panel, caseta, personas, credenciales, pases, horarios, bitacora, admin):
        app.register_blueprint(modulo.bp)

    @app.errorhandler(403)
    def prohibido(_e):
        return render_template("error.html", titulo="Sin permiso",
                               mensaje="Su usuario no tiene acceso a esta sección."), 403

    @app.errorhandler(404)
    def no_encontrado(_e):
        return render_template("error.html", titulo="No encontrado",
                               mensaje="La página o el registro que busca no existe."), 404

    @app.errorhandler(db.ErrorBD)
    def error_bd(e):
        return render_template("error.html", titulo="No se pudo completar la operación", mensaje=str(e)), 400

    @app.after_request
    def cabeceras(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("Permissions-Policy", "camera=(self)")
        return resp

    return app
