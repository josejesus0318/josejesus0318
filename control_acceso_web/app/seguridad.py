"""Inicio de sesión, roles y protección CSRF."""
from __future__ import annotations

import secrets
import time
from functools import wraps
from typing import Callable

from flask import Flask, abort, flash, g, redirect, request, session, url_for

# Qué puede hacer cada rol. Las plantillas usan puede('modulo') para mostrar el menú.
PERMISOS: dict[str, set[str]] = {
    "admin":      {"panel", "caseta", "personas", "personas_editar", "credenciales", "credenciales_editar",
                   "credenciales_estado", "pases", "horarios", "bitacora", "admin"},
    "vigilancia": {"panel", "caseta", "personas", "credenciales", "credenciales_estado", "bitacora"},
    "recepcion":  {"panel", "personas", "personas_editar", "credenciales", "credenciales_editar",
                   "credenciales_estado", "pases", "bitacora"},
    "consulta":   {"panel", "personas", "credenciales", "bitacora"},
}

NOMBRE_ROL = {"admin": "Administrador", "vigilancia": "Vigilancia", "recepcion": "Recepción", "consulta": "Consulta"}

# Bloqueo sencillo de fuerza bruta en el login (por dirección IP, en memoria)
_INTENTOS: dict[str, list[float]] = {}
MAX_INTENTOS, VENTANA = 5, 300


def puede(modulo: str) -> bool:
    return modulo in PERMISOS.get(session.get("rol", ""), set())


def requiere(modulo: str) -> Callable:
    def decorador(vista: Callable) -> Callable:
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if "id_usuario" not in session:
                if request.accept_mimetypes.best == "application/json" or request.is_json:
                    return {"error": "La sesión expiró. Vuelva a iniciar sesión."}, 401
                return redirect(url_for("panel.login", siguiente=request.path))
            if not puede(modulo):
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


def login_bloqueado(ip: str) -> bool:
    ahora = time.time()
    _INTENTOS[ip] = [t for t in _INTENTOS.get(ip, []) if ahora - t < VENTANA]
    return len(_INTENTOS[ip]) >= MAX_INTENTOS


def login_fallido(ip: str) -> None:
    _INTENTOS.setdefault(ip, []).append(time.time())


def login_correcto(ip: str) -> None:
    _INTENTOS.pop(ip, None)


def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def init_app(app: Flask) -> None:
    @app.before_request
    def verificar_csrf():
        if request.method in ("POST", "PUT", "DELETE"):
            enviado = request.form.get("csrf") or request.headers.get("X-CSRF-Token")
            esperado = session.get("csrf")
            if not esperado or not enviado or not secrets.compare_digest(enviado, esperado):
                if request.is_json:
                    return {"error": "La página caducó. Recárguela e intente de nuevo."}, 400
                flash("La página caducó. Intente de nuevo.", "error")
                return redirect(request.referrer or url_for("panel.inicio"))
        g.usuario = {"id": session.get("id_usuario"), "nombre": session.get("nombre"), "rol": session.get("rol")}

    @app.context_processor
    def contexto():
        return {"puede": puede, "csrf_token": token_csrf, "NOMBRE_ROL": NOMBRE_ROL,
                "INSTITUCION": app.config["INSTITUCION"]}
