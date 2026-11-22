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
        with db.transaccion() as conn:
            if not id_persona:
                id_persona = conn.execute(
                    """INSERT INTO personas (id_tipo, nombre, apellido_paterno, apellido_materno, telefono,
                                             correo, identificacion)
                       VALUES ((SELECT id_tipo FROM tipos_persona WHERE clave = %s), %s, %s, %s, %s, %s, %s)
                       RETURNING id_persona""",
                    (clase, texto("nombre", True, 60), texto("apellido_paterno", True, 40),
                     texto("apellido_materno", maximo=40), texto("telefono", maximo=15), texto("correo", maximo=120),
                     texto("identificacion", maximo=40))).fetchone()["id_persona"]
                if clase == "PRV":
                    from .personas import guardar_detalle
                    guardar_detalle(conn, id_persona, "PRV", True)
            id_visita = conn.execute(
                """INSERT INTO visitas (id_persona, id_anfitrion, motivo, fecha)
                   VALUES (%s, %s, %s, (%s::timestamptz AT TIME ZONE zona_horaria())::date) RETURNING id_visita""",
                (id_persona, entero("id_anfitrion"), texto("motivo", True, 200),
                 fecha_hora_local("vigencia_inicio", True))).fetchone()["id_visita"]
            perfil = "Proveedor" if clase == "PRV" else "Visitante"
            usos = 1 if request.form.get("un_solo_uso") == "1" else None
            id_cred = conn.execute(
                """INSERT INTO credenciales (tipo, id_persona, id_perfil, id_visita, vigencia_inicio, vigencia_fin,
                                            usos_maximos, id_horario, creada_por)
                   VALUES ('personal', %s, (SELECT id_perfil FROM perfiles_acceso WHERE nombre = %s), %s,
                           %s::timestamptz, %s::timestamptz, %s, %s, %s)
                   RETURNING id_credencial""",
                (id_persona, perfil, id_visita, fecha_hora_local("vigencia_inicio", True),
                 fecha_hora_local("vigencia_fin", True), usos, entero("id_horario"),
                 session["id_usuario"])).fetchone()["id_credencial"]
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
    if not 1 <= cantidad <= 500:
        raise db.ErrorBD("La cantidad debe estar entre 1 y 500.")
    etiqueta = texto("etiqueta", maximo=80) or "Pase de evento"
    with db.transaccion() as conn:
        ev = conn.execute("SELECT * FROM eventos WHERE id_evento = %s FOR UPDATE", (id_evento,)).fetchone()
        if not ev:
            abort(404)
        emitidos = conn.execute(
            "SELECT coalesce(sum(coalesce(usos_maximos, 1)), 0) AS n FROM credenciales WHERE id_evento = %s",
            (id_evento,)).fetchone()["n"]
        if ev["cupo"] and emitidos + cantidad > ev["cupo"]:
            raise db.ErrorBD(f"Se rebasaría el cupo del evento ({ev['cupo']}). Ya hay {emitidos} lugares emitidos.")
        perfil = "(SELECT id_perfil FROM perfiles_acceso WHERE nombre = 'Invitado a evento')"
        if modo == "grupal":
            conn.execute(
                f"""INSERT INTO credenciales (tipo, descripcion, id_perfil, id_evento, vigencia_inicio, vigencia_fin,
                                             usos_maximos, creada_por)
                    VALUES ('generica', %s, {perfil}, %s, %s, %s, %s, %s)""",
                (f"{etiqueta} ({cantidad} personas)", id_evento, ev["inicio"], ev["fin"], cantidad,
                 session["id_usuario"]))
        else:
            conn.execute(
                f"""INSERT INTO credenciales (tipo, descripcion, id_perfil, id_evento, vigencia_inicio, vigencia_fin,
                                             usos_maximos, creada_por)
                    SELECT 'generica', %s || ' #' || (%s + n), {perfil}, %s, %s, %s, 1, %s
                      FROM generate_series(1, %s) n""",
                (etiqueta, conn.execute("SELECT count(*) AS n FROM credenciales WHERE id_evento = %s",
                                        (id_evento,)).fetchone()["n"],
                 id_evento, ev["inicio"], ev["fin"], session["id_usuario"], cantidad))
    flash(f"Se generaron los pases ({cantidad} {'lugares en un pase grupal' if modo == 'grupal' else 'pases'}).", "ok")
    return redirect(url_for("pases.evento", id_evento=id_evento))


@bp.route("/eventos/<int:id_evento>/imprimir")
@requiere("pases")
def imprimir_evento(id_evento: int):
    creds = db.todos("SELECT * FROM vw_credenciales WHERE id_evento = %s AND estado IN ('vigente', 'pendiente') "
                     "ORDER BY id_credencial", (id_evento,))
    return render_template("credenciales/imprimir.html", creds=creds)
