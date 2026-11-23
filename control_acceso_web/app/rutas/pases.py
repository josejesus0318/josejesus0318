"""Pases rápidos: visitas y proveedores con caducidad, y eventos con pases genéricos."""
from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from .. import db
from ..seguridad import requiere
from ..utilidades import entero, fecha_hora_local, texto

bp = Blueprint("pases", __name__, url_prefix="/pases")


@bp.route("/visita", methods=["GET", "POST"])
@requiere("pases")
def visita():
    """Registra a un visitante o proveedor, su visita y un QR con caducidad en un solo paso."""
    if request.method == "POST":
        clase = request.form.get("clase")                      # VIS | PRV
        if clase not in ("VIS", "PRV"):
            raise db.ErrorBD("Indique si es visitante o proveedor.")
        id_persona = entero("id_persona")
        nuevo = id_persona is None
        # Todo el alta se hace en PostgreSQL con un procedimiento almacenado (CALL)
        with db.transaccion() as conn:
            id_cred = conn.execute(
                """CALL sp_crear_pase_visita(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                             %s::timestamptz, %s::timestamptz, %s, %s, %s, NULL)""",
                (clase, id_persona,
                 texto("nombre", nuevo, 60) if nuevo else None,
                 texto("apellido_paterno", nuevo, 40) if nuevo else None,
                 texto("apellido_materno", maximo=40), texto("telefono", maximo=15), texto("correo", maximo=120),
                 texto("identificacion", maximo=40), entero("id_empresa"), texto("empresa_nueva", maximo=120),
                 entero("id_anfitrion"), texto("motivo", True, 200),
                 fecha_hora_local("vigencia_inicio", True), fecha_hora_local("vigencia_fin", True),
                 request.form.get("un_solo_uso") == "1", entero("id_horario"), session["id_usuario"])
            ).fetchone()["p_id_credencial"]
        flash("Pase creado. Muestre o envíe el código QR a la persona.", "ok")
        return redirect(url_for("credenciales.detalle", id_credencial=id_cred))

    return render_template(
        "pases/visita.html",
        anfitriones=db.todos("SELECT id_persona, nombre_completo, adscripcion FROM vw_personas "
                             "WHERE tipo_clave IN ('DOC','ADM') AND activo ORDER BY nombre_completo"),
        empresas=db.todos("SELECT * FROM empresas ORDER BY nombre"),
        externos=db.todos("SELECT id_persona, nombre_completo, tipo, tipo_clave, adscripcion FROM vw_personas "
                          "WHERE tipo_clave IN ('VIS','PRV') AND activo ORDER BY nombre_completo"),
        horarios=db.todos("SELECT * FROM vw_horarios ORDER BY nombre"),
        hoy=db.uno("SELECT to_char(now(), 'YYYY-MM-DD') AS d")["d"],
    )


@bp.route("/eventos")
@requiere("pases")
def eventos():
    lista = db.todos(
        """SELECT e.*, count(c.*) AS pases,
                  count(c.*) FILTER (WHERE c.usos_realizados > 0) AS usados,
                  coalesce(sum(c.usos_realizados), 0) AS entradas
             FROM eventos e LEFT JOIN credenciales c USING (id_evento)
            GROUP BY e.id_evento ORDER BY e.inicio DESC""")
    return render_template("pases/eventos.html", eventos=lista)


@bp.route("/eventos/nuevo", methods=["POST"])
@requiere("pases")
def evento_nuevo():
    with db.transaccion() as conn:
        fila = conn.execute(
            """INSERT INTO eventos (nombre, lugar, inicio, fin, cupo)
               VALUES (%s, %s, %s::timestamptz, %s::timestamptz, %s) RETURNING id_evento""",
            (texto("nombre", True, 120), texto("lugar", maximo=120), fecha_hora_local("inicio", True),
             fecha_hora_local("fin", True), entero("cupo"))).fetchone()
    flash("Evento creado. Ahora genere sus pases.", "ok")
    return redirect(url_for("pases.evento", id_evento=fila["id_evento"]))


@bp.route("/eventos/<int:id_evento>")
@requiere("pases")
def evento(id_evento: int):
    ev = db.uno("SELECT * FROM eventos WHERE id_evento = %s", (id_evento,))
    if not ev:
        abort(404)
    pases = db.todos("SELECT * FROM vw_credenciales WHERE id_evento = %s ORDER BY id_credencial", (id_evento,))
    return render_template("pases/evento.html", ev=ev, pases=pases)


@bp.route("/eventos/<int:id_evento>/generar", methods=["POST"])
@requiere("pases")
def generar(id_evento: int):
    """Genera N pases genéricos de un solo uso, o un pase grupal con N usos."""
    cantidad = entero("cantidad", True) or 0
    modo = request.form.get("modo", "individuales")
    with db.transaccion() as conn:
        conn.execute("CALL sp_generar_pases_evento(%s, %s, %s, %s, %s, NULL)",
                     (id_evento, cantidad, modo, texto("etiqueta", maximo=80), session["id_usuario"]))
    flash(f"Se generaron los pases ({cantidad} {'lugares en un pase grupal' if modo == 'grupal' else 'pases'}).", "ok")
    return redirect(url_for("pases.evento", id_evento=id_evento))


@bp.route("/eventos/<int:id_evento>/imprimir")
@requiere("pases")
def imprimir_evento(id_evento: int):
    creds = db.todos("SELECT * FROM vw_credenciales WHERE id_evento = %s AND estado IN ('vigente', 'pendiente') "
                     "ORDER BY id_credencial", (id_evento,))
    return render_template("credenciales/imprimir.html", creds=creds)
