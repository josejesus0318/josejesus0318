"""Credenciales y pases: QR personales o genéricos, vigencia, horario, usos y NIP."""
from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from .. import db
from ..seguridad import requiere
from ..utilidades import entero, fecha_hora_local, para_input, texto

bp = Blueprint("credenciales", __name__, url_prefix="/credenciales")


def leer_usos() -> int | None:
    """Ilimitado, un solo uso o un número de usos."""
    opcion = request.form.get("usos", "ilimitado")
    if opcion == "uno":
        return 1
    if opcion == "varios":
        n = entero("usos_numero", True)
        if not n or n < 1:
            raise db.ErrorBD("El número de usos debe ser mayor que cero.")
        return n
    return None


def leer_nip() -> str | None:
    nip = texto("nip", maximo=6)
    if nip and not (nip.isdigit() and 4 <= len(nip) <= 6):
        raise db.ErrorBD("El NIP debe tener de 4 a 6 dígitos.")
    return nip


def obtener(id_credencial: int) -> dict:
    c = db.uno("SELECT * FROM vw_credenciales WHERE id_credencial = %s", (id_credencial,))
    if not c:
        abort(404)
    return c


@bp.route("/")
@requiere("credenciales")
def lista():
    q = (request.args.get("q") or "").strip()
    estado = request.args.get("estado") or ""
    tipo = request.args.get("tipo") or ""
    filtros, params = [], []
    if q:
        filtros.append("(lower(titular) LIKE %s OR lower(coalesce(numero,'')) LIKE %s OR lower(token) LIKE %s)")
        params += [f"%{q.lower()}%"] * 3
    if estado:
        filtros.append("estado = %s")
        params.append(estado)
    if tipo:
        filtros.append("tipo = %s")
        params.append(tipo)
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    creds = db.todos(f"SELECT * FROM vw_credenciales {where} ORDER BY id_credencial DESC LIMIT 300", params)
    return render_template("credenciales/lista.html", creds=creds, q=q, estado=estado, tipo=tipo)


def catalogos() -> dict:
    return {
        "perfiles": db.todos("SELECT p.*, h.nombre AS horario FROM perfiles_acceso p "
                             "LEFT JOIN horarios h USING (id_horario) ORDER BY id_perfil"),
        "horarios": db.todos("SELECT * FROM vw_horarios ORDER BY nombre"),
        "eventos": db.todos("SELECT * FROM eventos WHERE fin > now() ORDER BY inicio"),
    }


@bp.route("/nueva", methods=["GET", "POST"])
@requiere("credenciales_editar")
def nueva():
    if request.method == "POST":
        tipo = request.form.get("tipo")
        if tipo not in ("personal", "generica"):
            raise db.ErrorBD("Indique si el pase es personal o genérico.")
        id_persona = entero("id_persona", tipo == "personal") if tipo == "personal" else None
        descripcion = texto("descripcion", tipo == "generica", 120) if tipo == "generica" else None
        nip = leer_nip() if tipo == "personal" else None
        with db.transaccion() as conn:
            fila = conn.execute(
                """INSERT INTO credenciales (tipo, id_persona, descripcion, id_perfil, id_horario, id_evento,
                                            nip_hash, vigencia_inicio, vigencia_fin, usos_maximos, creada_por)
                   VALUES (%s, %s, %s, %s, %s, %s,
                           CASE WHEN %s::text IS NULL THEN NULL ELSE cifrar(%s) END,
                           coalesce(%s::timestamptz, now()), %s::timestamptz, %s, %s)
                   RETURNING id_credencial""",
                (tipo, id_persona, descripcion, entero("id_perfil", True), entero("id_horario"), entero("id_evento"),
                 nip, nip, fecha_hora_local("vigencia_inicio"), fecha_hora_local("vigencia_fin"), leer_usos(),
                 session["id_usuario"])).fetchone()
        flash("Credencial emitida. Puede imprimir o compartir el código QR.", "ok")
        return redirect(url_for("credenciales.detalle", id_credencial=fila["id_credencial"]))

    id_persona = request.args.get("persona", type=int)
    persona = db.uno("SELECT * FROM vw_personas WHERE id_persona = %s", (id_persona,)) if id_persona else None
    personas = [] if persona else db.todos(
        "SELECT id_persona, nombre_completo, tipo, numero FROM vw_personas WHERE activo ORDER BY nombre_completo")
    perfil_sugerido = None
    if persona:
        from .personas import PERFIL_POR_TIPO
        perfil_sugerido = PERFIL_POR_TIPO.get(persona["tipo_clave"])
    return render_template("credenciales/form.html", persona=persona, personas=personas,
                           perfil_sugerido=perfil_sugerido, tipo=request.args.get("tipo", "personal"),
                           **catalogos())


@bp.route("/<int:id_credencial>")
@requiere("credenciales")
def detalle(id_credencial: int):
    c = obtener(id_credencial)
    accesos = db.todos("SELECT * FROM vw_bitacora WHERE id_credencial = %s ORDER BY fecha_hora DESC LIMIT 20",
                       (id_credencial,))
    puntos = db.todos("""SELECT pt.nombre FROM perfil_puntos pp JOIN puntos_acceso pt USING (id_punto)
                          WHERE pp.id_perfil = %s ORDER BY pt.id_punto""", (c["id_perfil"],))
    horario = db.uno("SELECT * FROM vw_horarios WHERE id_horario = %s", (c["id_horario_efectivo"],)) \
        if c["id_horario_efectivo"] else None
    return render_template("credenciales/detalle.html", c=c, accesos=accesos, puntos=puntos, horario=horario,
                           para_input=para_input, **catalogos())


@bp.route("/<int:id_credencial>/imprimir")
@requiere("credenciales")
def imprimir(id_credencial: int):
    return render_template("credenciales/imprimir.html", creds=[obtener(id_credencial)])


@bp.route("/<int:id_credencial>/estado", methods=["POST"])
@requiere("credenciales_estado")
def estado(id_credencial: int):
    activa = request.form.get("activa") == "1"
    with db.transaccion() as conn:
        conn.execute("UPDATE credenciales SET activa = %s WHERE id_credencial = %s", (activa, id_credencial))
    flash("Credencial activada." if activa else "Credencial desactivada: ya no permite entrar.", "ok")
    return redirect(request.referrer or url_for("credenciales.detalle", id_credencial=id_credencial))


@bp.route("/<int:id_credencial>/editar", methods=["POST"])
@requiere("credenciales_editar")
def editar(id_credencial: int):
    c = obtener(id_credencial)
    usos = leer_usos()
    if usos is not None and usos < c["usos_realizados"]:
        raise db.ErrorBD(f"El pase ya se usó {c['usos_realizados']} veces; no puede tener menos usos.")
    with db.transaccion() as conn:
        conn.execute(
            """UPDATE credenciales SET id_perfil = %s, id_horario = %s,
                      vigencia_inicio = %s::timestamptz, vigencia_fin = %s::timestamptz, usos_maximos = %s
                WHERE id_credencial = %s""",
            (entero("id_perfil", True), entero("id_horario"), fecha_hora_local("vigencia_inicio", True),
             fecha_hora_local("vigencia_fin"), usos, id_credencial))
    flash("Credencial actualizada.", "ok")
    return redirect(url_for("credenciales.detalle", id_credencial=id_credencial))


@bp.route("/<int:id_credencial>/nip", methods=["POST"])
@requiere("credenciales_editar")
def nip(id_credencial: int):
    c = obtener(id_credencial)
    if c["tipo"] != "personal":
        raise db.ErrorBD("Solo las credenciales personales pueden tener NIP.")
    nuevo = leer_nip()
    with db.transaccion() as conn:
        conn.execute("UPDATE credenciales SET nip_hash = CASE WHEN %s::text IS NULL THEN NULL ELSE cifrar(%s) END "
                     "WHERE id_credencial = %s", (nuevo, nuevo, id_credencial))
    flash("NIP asignado." if nuevo else "NIP eliminado: esta persona ya no podrá entrar con NIP.", "ok")
    return redirect(url_for("credenciales.detalle", id_credencial=id_credencial))


@bp.route("/<int:id_credencial>/regenerar", methods=["POST"])
@requiere("credenciales_editar")
def regenerar(id_credencial: int):
    with db.transaccion() as conn:
        conn.execute("UPDATE credenciales SET token = 'ITVH-' || upper(encode(gen_random_bytes(12), 'hex')) "
                     "WHERE id_credencial = %s", (id_credencial,))
    flash("Se generó un código QR nuevo. El anterior ya no funciona.", "ok")
    return redirect(url_for("credenciales.detalle", id_credencial=id_credencial))
