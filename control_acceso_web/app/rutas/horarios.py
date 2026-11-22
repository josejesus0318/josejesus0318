"""Horarios (nivel de acceso programado) y perfiles de acceso."""
from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import db
from ..seguridad import requiere
from ..utilidades import entero, texto

bp = Blueprint("horarios", __name__, url_prefix="/horarios")


def leer_franja() -> tuple[list[int], str, str]:
    dias = sorted({int(d) for d in request.form.getlist("dias") if d.isdigit() and 1 <= int(d) <= 7})
    if not dias:
        raise db.ErrorBD("Seleccione al menos un día.")
    inicio, fin = texto("hora_inicio", True, 5), texto("hora_fin", True, 5)
    if fin <= inicio:
        raise db.ErrorBD("La hora de fin debe ser posterior a la de inicio.")
    return dias, inicio, fin


@bp.route("/")
@requiere("horarios")
def lista():
    horarios = db.todos(
        """SELECT h.*, (SELECT count(*) FROM perfiles_acceso p WHERE p.id_horario = h.id_horario) AS perfiles,
                  (SELECT count(*) FROM credenciales c WHERE c.id_horario = h.id_horario) AS credenciales
             FROM vw_horarios h ORDER BY h.nombre""")
    perfiles = db.todos(
        """SELECT p.*, h.nombre AS horario,
                  (SELECT string_agg(pt.nombre, ', ' ORDER BY pt.id_punto) FROM perfil_puntos pp
                     JOIN puntos_acceso pt USING (id_punto) WHERE pp.id_perfil = p.id_perfil) AS puntos
             FROM perfiles_acceso p LEFT JOIN horarios h USING (id_horario) ORDER BY p.id_perfil""")
    return render_template("horarios/lista.html", horarios=horarios, perfiles=perfiles)


@bp.route("/nuevo", methods=["POST"])
@requiere("horarios")
def nuevo():
    dias, inicio, fin = leer_franja()
    with db.transaccion() as conn:
        id_horario = conn.execute("INSERT INTO horarios (nombre, descripcion) VALUES (%s, %s) RETURNING id_horario",
                                  (texto("nombre", True, 60), texto("descripcion", maximo=200))).fetchone()["id_horario"]
        for d in dias:
            conn.execute("INSERT INTO horario_franjas (id_horario, dia_semana, hora_inicio, hora_fin) "
                         "VALUES (%s, %s, %s, %s)", (id_horario, d, inicio, fin))
    flash("Horario creado. Puede agregarle más franjas.", "ok")
    return redirect(url_for("horarios.detalle", id_horario=id_horario))


@bp.route("/<int:id_horario>")
@requiere("horarios")
def detalle(id_horario: int):
    h = db.uno("SELECT * FROM vw_horarios WHERE id_horario = %s", (id_horario,))
    if not h:
        abort(404)
    franjas = db.todos("SELECT * FROM horario_franjas WHERE id_horario = %s ORDER BY dia_semana, hora_inicio",
                       (id_horario,))
    return render_template("horarios/detalle.html", h=h, franjas=franjas)


@bp.route("/<int:id_horario>/franja", methods=["POST"])
@requiere("horarios")
def agregar_franja(id_horario: int):
    dias, inicio, fin = leer_franja()
    with db.transaccion() as conn:
        for d in dias:
            conn.execute("INSERT INTO horario_franjas (id_horario, dia_semana, hora_inicio, hora_fin) "
                         "VALUES (%s, %s, %s, %s)", (id_horario, d, inicio, fin))
    flash("Franja agregada.", "ok")
    return redirect(url_for("horarios.detalle", id_horario=id_horario))


@bp.route("/<int:id_horario>/franja/<int:id_franja>/borrar", methods=["POST"])
@requiere("horarios")
def borrar_franja(id_horario: int, id_franja: int):
    with db.transaccion() as conn:
        conn.execute("DELETE FROM horario_franjas WHERE id_franja = %s AND id_horario = %s", (id_franja, id_horario))
    flash("Franja eliminada.", "ok")
    return redirect(url_for("horarios.detalle", id_horario=id_horario))


@bp.route("/perfil/<int:id_perfil>", methods=["GET", "POST"])
@requiere("horarios")
def perfil(id_perfil: int):
    p = db.uno("SELECT * FROM perfiles_acceso WHERE id_perfil = %s", (id_perfil,))
    if not p:
        abort(404)
    if request.method == "POST":
        puntos = [int(x) for x in request.form.getlist("puntos") if x.isdigit()]
        with db.transaccion() as conn:
            conn.execute("UPDATE perfiles_acceso SET descripcion = %s, id_horario = %s WHERE id_perfil = %s",
                         (texto("descripcion", maximo=200), entero("id_horario"), id_perfil))
            conn.execute("DELETE FROM perfil_puntos WHERE id_perfil = %s", (id_perfil,))
            for pt in puntos:
                conn.execute("INSERT INTO perfil_puntos (id_perfil, id_punto) VALUES (%s, %s)", (id_perfil, pt))
        flash("Perfil actualizado.", "ok")
        return redirect(url_for("horarios.lista"))
    return render_template(
        "horarios/perfil.html", p=p,
        horarios=db.todos("SELECT * FROM vw_horarios ORDER BY nombre"),
        puntos=db.todos("SELECT pt.*, EXISTS (SELECT 1 FROM perfil_puntos pp WHERE pp.id_perfil = %s "
                        "AND pp.id_punto = pt.id_punto) AS permitido FROM puntos_acceso pt ORDER BY id_punto",
                        (id_perfil,)))
