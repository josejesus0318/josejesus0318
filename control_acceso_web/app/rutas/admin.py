"""Administración: usuarios de la aplicación, puntos de acceso, configuración y auditoría."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .. import db
from ..seguridad import NOMBRE_ROL, requiere
from ..utilidades import entero, texto

bp = Blueprint("admin", __name__, url_prefix="/admin")


def validar_password(pw: str | None) -> str:
    if not pw or len(pw) < 8:
        raise db.ErrorBD("La contraseña debe tener al menos 8 caracteres.")
    return pw


@bp.route("/")
@requiere("admin")
def inicio():
    usuarios = db.todos("SELECT id_usuario, usuario, nombre, rol, activo, ultimo_acceso FROM usuarios "
                        "ORDER BY activo DESC, usuario")
    puntos = db.todos("SELECT * FROM puntos_acceso ORDER BY id_punto")
    config = db.todos("SELECT * FROM configuracion ORDER BY clave")
    auditoria = db.todos(
        """SELECT a.*, u.usuario FROM auditoria a LEFT JOIN usuarios u USING (id_usuario)
            ORDER BY a.fecha_hora DESC LIMIT 40""")
    return render_template("admin/inicio.html", usuarios=usuarios, puntos=puntos, config=config,
                           auditoria=auditoria, roles=NOMBRE_ROL)


@bp.route("/usuarios/nuevo", methods=["POST"])
@requiere("admin")
def usuario_nuevo():
    rol = request.form.get("rol")
    if rol not in NOMBRE_ROL:
        raise db.ErrorBD("Rol no válido.")
    with db.transaccion() as conn:
        conn.execute("INSERT INTO usuarios (usuario, password_hash, nombre, rol) VALUES (lower(%s), cifrar(%s), %s, %s)",
                     (texto("usuario", True, 30), validar_password(request.form.get("password")),
                      texto("nombre", True, 100), rol))
    flash("Usuario creado.", "ok")
    return redirect(url_for("admin.inicio"))


@bp.route("/usuarios/<int:id_usuario>/estado", methods=["POST"])
@requiere("admin")
def usuario_estado(id_usuario: int):
    if id_usuario == session.get("id_usuario"):
        raise db.ErrorBD("No puede desactivar su propio usuario.")
    activo = request.form.get("activo") == "1"
    with db.transaccion() as conn:
        conn.execute("UPDATE usuarios SET activo = %s WHERE id_usuario = %s", (activo, id_usuario))
    flash("Usuario activado." if activo else "Usuario desactivado.", "ok")
    return redirect(url_for("admin.inicio"))


@bp.route("/usuarios/<int:id_usuario>/password", methods=["POST"])
@requiere("admin")
def usuario_password(id_usuario: int):
    with db.transaccion() as conn:
        conn.execute("UPDATE usuarios SET password_hash = cifrar(%s) WHERE id_usuario = %s",
                     (validar_password(request.form.get("password")), id_usuario))
    flash("Contraseña cambiada.", "ok")
    return redirect(url_for("admin.inicio"))


@bp.route("/puntos/nuevo", methods=["POST"])
@requiere("admin")
def punto_nuevo():
    sentido = request.form.get("sentido", "ambos")
    if sentido not in ("entrada", "salida", "ambos"):
        raise db.ErrorBD("Sentido no válido.")
    with db.transaccion() as conn:
        conn.execute("INSERT INTO puntos_acceso (nombre, ubicacion, sentido, perimetral) VALUES (%s, %s, %s, %s)",
                     (texto("nombre", True, 80), texto("ubicacion", maximo=120), sentido,
                      request.form.get("perimetral") == "1"))
    flash("Punto de acceso creado. Asígnelo a los perfiles en Horarios y perfiles.", "ok")
    return redirect(url_for("admin.inicio"))


@bp.route("/puntos/<int:id_punto>/estado", methods=["POST"])
@requiere("admin")
def punto_estado(id_punto: int):
    activo = request.form.get("activo") == "1"
    with db.transaccion() as conn:
        conn.execute("UPDATE puntos_acceso SET activo = %s WHERE id_punto = %s", (activo, id_punto))
    flash("Punto de acceso activado." if activo else "Punto de acceso desactivado.", "ok")
    return redirect(url_for("admin.inicio"))


@bp.route("/configuracion", methods=["POST"])
@requiere("admin")
def configuracion():
    with db.transaccion() as conn:
        for clave in ("intentos_nip", "segundos_repeticion"):
            valor = entero(clave)
            if valor is not None:
                if valor < 0 or valor > 3600:
                    raise db.ErrorBD("Valor fuera de rango.")
                conn.execute("UPDATE configuracion SET valor = %s WHERE clave = %s", (str(valor), clave))
    flash("Configuración guardada.", "ok")
    return redirect(url_for("admin.inicio"))
