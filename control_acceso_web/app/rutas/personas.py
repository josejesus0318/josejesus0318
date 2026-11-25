"""Alumnos, docentes, personal, proveedores y visitantes."""
from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from .. import db
from ..seguridad import requiere
from ..utilidades import entero, texto

bp = Blueprint("personas", __name__, url_prefix="/personas")

PERFIL_POR_TIPO = {"ALU": "Alumno", "DOC": "Docente", "ADM": "Administrativo", "PRV": "Proveedor", "VIS": "Visitante"}


def catalogos() -> dict:
    return {
        "tipos": db.todos("SELECT * FROM tipos_persona ORDER BY id_tipo"),
        "carreras": db.todos("SELECT * FROM carreras ORDER BY nombre"),
        "departamentos": db.todos("SELECT * FROM departamentos ORDER BY nombre"),
        "empresas": db.todos("SELECT * FROM empresas ORDER BY nombre"),
        "perfiles": db.todos("SELECT * FROM perfiles_acceso ORDER BY id_perfil"),
    }


@bp.route("/")
@requiere("personas")
def lista():
    q = (request.args.get("q") or "").strip()
    tipo = request.args.get("tipo") or ""
    estado = request.args.get("estado") or "activos"
    filtros, params = [], []
    if q:
        filtros.append("(lower(nombre_completo) LIKE %s OR lower(coalesce(numero,'')) LIKE %s "
                       "OR lower(coalesce(adscripcion,'')) LIKE %s)")
        params += [f"%{q.lower()}%"] * 3
    if tipo:
        filtros.append("tipo_clave = %s")
        params.append(tipo)
    if estado == "activos":
        filtros.append("activo")
    elif estado == "bajas":
        filtros.append("NOT activo")
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    personas = db.todos(
        f"""SELECT p.*,
                   (SELECT c.estado FROM vw_credenciales c WHERE c.id_persona = p.id_persona
                     ORDER BY (c.estado = 'vigente') DESC, c.id_credencial DESC LIMIT 1) AS credencial
              FROM vw_personas p {where}
             ORDER BY p.tipo, p.apellido_paterno, p.nombre LIMIT 300""", params)
    return render_template("personas/lista.html", personas=personas, q=q, tipo=tipo, estado=estado,
                           tipos=db.todos("SELECT * FROM tipos_persona ORDER BY id_tipo"))


def guardar_detalle(conn, id_persona: int, clave: str, nueva: bool) -> None:
    """Guarda los datos propios de cada tipo de persona."""
    if clave == "ALU":
        conn.execute(
            """INSERT INTO alumnos (id_persona, numero_control, id_carrera, semestre) VALUES (%s, %s, %s, %s)
               ON CONFLICT (id_persona) DO UPDATE SET numero_control = EXCLUDED.numero_control,
                   id_carrera = EXCLUDED.id_carrera, semestre = EXCLUDED.semestre""",
            (id_persona, texto("numero_control", True, 10).upper(), entero("id_carrera", True),
             entero("semestre", True)))
    elif clave in ("DOC", "ADM"):
        conn.execute(
            """INSERT INTO empleados (id_persona, numero_empleado, id_departamento, puesto) VALUES (%s, %s, %s, %s)
               ON CONFLICT (id_persona) DO UPDATE SET numero_empleado = EXCLUDED.numero_empleado,
                   id_departamento = EXCLUDED.id_departamento, puesto = EXCLUDED.puesto""",
            (id_persona, texto("numero_empleado", True, 10).upper(), entero("id_departamento", True),
             texto("puesto", True, 80)))
    elif clave == "PRV":
        id_empresa = entero("id_empresa")
        nueva_empresa = texto("empresa_nueva", maximo=120)
        if nueva_empresa:
            id_empresa = conn.execute(
                "INSERT INTO empresas (nombre) VALUES (%s) ON CONFLICT (nombre) DO UPDATE SET nombre = EXCLUDED.nombre "
                "RETURNING id_empresa", (nueva_empresa,)).fetchone()["id_empresa"]
        if not id_empresa:
            raise db.ErrorBD("Seleccione la empresa del proveedor o escriba una nueva.")
        conn.execute("INSERT INTO proveedores (id_persona, id_empresa) VALUES (%s, %s) "
                     "ON CONFLICT (id_persona) DO UPDATE SET id_empresa = EXCLUDED.id_empresa",
                     (id_persona, id_empresa))


@bp.route("/nueva", methods=["GET", "POST"])
@requiere("personas_editar")
def nueva():
    cat = catalogos()
    if request.method == "POST":
        id_tipo = entero("id_tipo", True)
        clave = next((t["clave"] for t in cat["tipos"] if t["id_tipo"] == id_tipo), None)
        if not clave:
            raise db.ErrorBD("Tipo de persona no válido.")
        with db.transaccion() as conn:
            id_persona = conn.execute(
                """INSERT INTO personas (id_tipo, nombre, apellido_paterno, apellido_materno, correo, telefono,
                                         identificacion)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id_persona""",
                (id_tipo, texto("nombre", True, 60), texto("apellido_paterno", True, 40),
                 texto("apellido_materno", maximo=40), texto("correo", maximo=120), texto("telefono", maximo=15),
                 texto("identificacion", maximo=40))).fetchone()["id_persona"]
            guardar_detalle(conn, id_persona, clave, True)
            if request.form.get("emitir") == "1":
                nip = texto("nip", maximo=6)
                if nip and not (nip.isdigit() and 4 <= len(nip) <= 6):
                    raise db.ErrorBD("El NIP debe tener de 4 a 6 dígitos.")
                conn.execute(
                    """INSERT INTO credenciales (tipo, id_persona, id_perfil, nip_hash, creada_por)
                       VALUES ('personal', %s, (SELECT id_perfil FROM perfiles_acceso WHERE nombre = %s),
                               CASE WHEN %s::text IS NULL THEN NULL ELSE cifrar(%s) END, %s)""",
                    (id_persona, PERFIL_POR_TIPO[clave], nip, nip, session.get("id_usuario")))
        flash("Persona registrada.", "ok")
        return redirect(url_for("personas.detalle", id_persona=id_persona))
    return render_template("personas/form.html", persona=None, **cat)


@bp.route("/<int:id_persona>")
@requiere("personas")
def detalle(id_persona: int):
    persona = db.uno("SELECT * FROM vw_personas WHERE id_persona = %s", (id_persona,))
    if not persona:
        abort(404)
    credenciales = db.todos("SELECT * FROM vw_credenciales WHERE id_persona = %s ORDER BY id_credencial DESC",
                            (id_persona,))
    asistencia = db.todos("SELECT * FROM vw_asistencia WHERE id_persona = %s ORDER BY fecha DESC LIMIT 10",
                          (id_persona,))
    accesos = db.todos("SELECT * FROM vw_bitacora WHERE id_persona = %s ORDER BY fecha_hora DESC LIMIT 15",
                       (id_persona,))
    visitas = db.todos(
        """SELECT v.*, a.nombre_completo AS anfitrion FROM visitas v
             LEFT JOIN vw_personas a ON a.id_persona = v.id_anfitrion
            WHERE v.id_persona = %s ORDER BY v.fecha DESC""", (id_persona,))
    try:
        tiene_foto = db.uno("SELECT EXISTS (SELECT 1 FROM fotos_personas WHERE id_persona = %s) AS x",
                            (id_persona,))["x"]
    except db.ErrorBD:                          # base sin el módulo del kiosco (07_kiosco.sql)
        tiene_foto = False
    return render_template("personas/detalle.html", p=persona, credenciales=credenciales,
                           asistencia=asistencia, accesos=accesos, visitas=visitas, tiene_foto=tiene_foto)


@bp.route("/<int:id_persona>/editar", methods=["GET", "POST"])
@requiere("personas_editar")
def editar(id_persona: int):
    persona = db.uno("SELECT * FROM vw_personas WHERE id_persona = %s", (id_persona,))
    if not persona:
        abort(404)
    if request.method == "POST":
        with db.transaccion() as conn:
            conn.execute(
                """UPDATE personas SET nombre = %s, apellido_paterno = %s, apellido_materno = %s, correo = %s,
                          telefono = %s, identificacion = %s WHERE id_persona = %s""",
                (texto("nombre", True, 60), texto("apellido_paterno", True, 40), texto("apellido_materno", maximo=40),
                 texto("correo", maximo=120), texto("telefono", maximo=15), texto("identificacion", maximo=40),
                 id_persona))
            guardar_detalle(conn, id_persona, persona["tipo_clave"], False)
        flash("Datos actualizados.", "ok")
        return redirect(url_for("personas.detalle", id_persona=id_persona))
    return render_template("personas/form.html", persona=persona, **catalogos())


@bp.route("/<int:id_persona>/estado", methods=["POST"])
@requiere("personas_editar")
def estado(id_persona: int):
    activo = request.form.get("activo") == "1"
    if not db.uno("SELECT 1 AS x FROM personas WHERE id_persona = %s", (id_persona,)):
        abort(404)
    with db.transaccion() as conn:
        if activo:
            conn.execute("UPDATE personas SET activo = TRUE WHERE id_persona = %s", (id_persona,))
        else:                                   # baja lógica con procedimiento almacenado + trigger
            conn.execute("CALL sp_baja_persona(%s, %s)", (id_persona, session["id_usuario"]))
    flash("Persona reactivada. Active también la credencial que corresponda." if activo
          else "Persona dada de baja: sus credenciales se desactivaron.", "ok")
    return redirect(url_for("personas.detalle", id_persona=id_persona))
