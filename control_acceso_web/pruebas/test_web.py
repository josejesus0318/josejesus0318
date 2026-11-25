"""Pruebas de la aplicación web: inicio de sesión, permisos, caseta y formularios.

Usan la misma base de PRUEBA que test_base_datos.py (TEST_DATABASE_URL).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import create_app  # noqa: E402
from herramientas.instalar_bd import instalar  # noqa: E402

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Defina TEST_DATABASE_URL para probar la aplicación")


@pytest.fixture
def app():
    instalar(URL, silencioso=True)
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("UPDATE campus.configuracion SET valor = '0' WHERE clave = 'segundos_repeticion'")
        # Horario de 24 h para que las pruebas no dependan de la hora en que se ejecutan
        conn.execute("""INSERT INTO campus.horarios (nombre) VALUES ('Prueba 24 h');
                        INSERT INTO campus.horario_franjas (id_horario, dia_semana, hora_inicio, hora_fin)
                        SELECT currval('campus.horarios_id_horario_seq'), d, '00:00', '23:59:59.999'
                          FROM generate_series(1, 7) d;
                        UPDATE campus.perfiles_acceso SET id_horario = currval('campus.horarios_id_horario_seq')
                         WHERE id_horario IS NOT NULL""")
    return create_app({"DATABASE_URL": URL, "SESSION_COOKIE_SECURE": False, "TESTING": True})


def sql(consulta, params=None):
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute("SET search_path TO campus, public")
        return conn.execute(consulta, params).fetchall()


class Cliente:
    def __init__(self, app, usuario=None):
        self.c = app.test_client()
        self.csrf = None
        if usuario:
            r = self.post("/login", usuario=usuario, password="Campus#2026")
            assert r.status_code == 302, f"No se pudo iniciar sesión como {usuario}"
            self.csrf = None            # al iniciar sesión se genera un token nuevo

    def get(self, ruta):
        r = self.c.get(ruta)
        m = re.search(r'name="csrf(?:-token)?" (?:value|content)="([^"]+)"', r.text)
        if m:
            self.csrf = m.group(1)
        return r

    def post(self, ruta, **datos):
        if ruta == "/login":
            self.csrf = None
        if self.csrf is None:
            self.get("/login" if ruta == "/login" else "/")
        datos.setdefault("csrf", self.csrf)
        return self.c.post(ruta, data=datos)

    def caseta(self, **datos):
        if self.csrf is None:
            self.get("/")
        return self.c.post("/caseta/registrar", json=datos, headers={"X-CSRF-Token": self.csrf})


# ---------------------------------------------------------------- sesión y permisos
def test_login_incorrecto_y_redireccion(app):
    c = Cliente(app)
    assert c.post("/login", usuario="admin", password="mala").status_code == 401
    r = c.c.get("/personas/")
    assert r.status_code == 302 and "/login" in r.headers["Location"]


def test_vigilancia_entra_directo_a_la_caseta(app):
    c = Cliente(app)
    r = c.post("/login", usuario="vigilancia", password="Campus#2026")
    assert r.headers["Location"].endswith("/caseta/")


@pytest.mark.parametrize("usuario,ruta,codigo", [
    ("vigilancia", "/admin/", 403), ("vigilancia", "/pases/visita", 403), ("vigilancia", "/caseta/", 200),
    ("recepcion", "/caseta/", 403), ("recepcion", "/pases/visita", 200), ("recepcion", "/horarios/", 403),
    ("consulta", "/caseta/", 403), ("consulta", "/personas/nueva", 403), ("consulta", "/bitacora/", 200),
    ("admin", "/admin/", 200),
])
def test_permisos_por_rol(app, usuario, ruta, codigo):
    assert Cliente(app, usuario).get(ruta).status_code == codigo


def test_post_sin_token_csrf_se_rechaza(app):
    c = Cliente(app, "admin")
    r = c.c.post("/admin/usuarios/nuevo", data={"usuario": "intruso", "nombre": "X", "rol": "admin",
                                                "password": "12345678"})
    assert r.status_code == 302
    assert not sql("SELECT 1 FROM usuarios WHERE usuario = 'intruso'")
    r = c.c.post("/caseta/registrar", json={"metodo": "qr", "dato": "x", "punto": 1})
    assert r.status_code == 400


# ---------------------------------------------------------------- caseta
def test_caseta_qr_nip_y_manual(app):
    c = Cliente(app, "vigilancia")
    token = sql("SELECT token FROM credenciales WHERE id_persona = 7")[0][0]
    r = c.caseta(metodo="qr", dato=token.lower(), punto=1).get_json()      # el lector puede enviar minúsculas
    assert (r["resultado"], r["evento"]) == ("permitido", "entrada")
    r = c.caseta(metodo="nip", dato="22301002", nip="1234", punto=1).get_json()
    assert r["resultado"] == "permitido" and r["persona"] == "Luis Fernando Pérez Ramos"
    r = c.caseta(metodo="manual", dato="13", punto=2).get_json()
    assert r["resultado"] == "permitido"
    r = c.caseta(metodo="qr", dato="ITVH-FALSO", punto=1).get_json()
    assert r["resultado"] == "denegado"
    operadores = sql("SELECT DISTINCT u.usuario FROM registro_accesos r JOIN usuarios u USING (id_usuario) "
                     "WHERE fecha_local(r.fecha_hora) = fecha_local(now())")
    assert operadores == [("vigilancia",)]
    busqueda = c.get("/caseta/buscar?q=ramos").get_json()
    assert busqueda["personas"][0]["dentro"] is True


def test_caseta_valida_entrada(app):
    c = Cliente(app, "vigilancia")
    assert c.caseta(metodo="otro", dato="x", punto=1).status_code == 400
    assert c.caseta(metodo="qr", dato="", punto=1).status_code == 400
    assert c.caseta(metodo="qr", dato="x", punto="abc").status_code == 400
    assert c.caseta(metodo="qr", dato="x", punto=999).status_code == 400


# ---------------------------------------------------------------- altas y pases
def test_alta_de_alumno_con_credencial_y_nip(app):
    c = Cliente(app, "recepcion")
    r = c.post("/personas/nueva", id_tipo="1", nombre="Sofía", apellido_paterno="Ruiz", numero_control="25301999",
               id_carrera="1", semestre="1", emitir="1", nip="4321")
    assert r.status_code == 302
    fila = sql("SELECT c.id_perfil, c.nip_hash IS NOT NULL FROM credenciales c JOIN alumnos a USING (id_persona) "
               "WHERE a.numero_control = '25301999'")
    assert fila == [(1, True)]
    r = Cliente(app, "vigilancia").caseta(metodo="nip", dato="25301999", nip="4321", punto=1).get_json()
    assert r["resultado"] == "permitido"
    # Número de control repetido: mensaje claro, sin error del servidor
    r = c.post("/personas/nueva", id_tipo="1", nombre="Otra", apellido_paterno="Persona", numero_control="25301999",
               id_carrera="1", semestre="1")
    assert r.status_code == 400 and "Ya existe" in r.text


def test_pase_de_proveedor_con_caducidad_y_un_solo_uso(app):
    c = Cliente(app, "recepcion")
    hoy = sql("SELECT to_char(now() AT TIME ZONE zona_horaria(), 'YYYY-MM-DD')")[0][0]
    r = c.post("/pases/visita", clase="PRV", nombre="Mario", apellido_paterno="López", empresa_nueva="Fumigaciones Usumacinta",
               motivo="Fumigación de laboratorios", vigencia_inicio=f"{hoy}T00:00", vigencia_fin=f"{hoy}T23:59",
               un_solo_uso="1")
    assert r.status_code == 302
    id_cred = int(r.headers["Location"].rstrip("/").split("/")[-1])
    cred = sql("SELECT token, usos_maximos, vigencia_fin > now(), id_visita IS NOT NULL FROM credenciales "
               "WHERE id_credencial = %s", (id_cred,))[0]
    assert cred[1:] == (1, True, True)
    assert sql("SELECT e.nombre FROM proveedores p JOIN empresas e USING (id_empresa) "
               "JOIN personas x USING (id_persona) WHERE x.nombre = 'Mario'") == [("Fumigaciones Usumacinta",)]
    v = Cliente(app, "vigilancia")
    assert v.caseta(metodo="qr", dato=cred[0], punto=1).get_json()["evento"] == "entrada"
    assert v.caseta(metodo="qr", dato=cred[0], punto=1).get_json()["evento"] == "salida"
    assert v.caseta(metodo="qr", dato=cred[0], punto=1).get_json()["mensaje"] == "Pase de un solo uso ya utilizado"
    pagina = c.get(f"/credenciales/{id_cred}")
    assert cred[0] in pagina.text and "Un solo uso" in pagina.text


def test_pases_de_evento_y_cupo(app):
    c = Cliente(app, "recepcion")
    assert c.post("/pases/eventos/1/generar", modo="individuales", cantidad="5", etiqueta="Conferencia").status_code == 302
    assert c.post("/pases/eventos/1/generar", modo="grupal", cantidad="30", etiqueta="Prepa 5").status_code == 302
    assert sql("SELECT count(*) FROM credenciales WHERE id_evento = 1 AND descripcion LIKE 'Conferencia #%%'")[0][0] == 5
    assert sql("SELECT usos_maximos FROM credenciales WHERE descripcion = 'Prepa 5 (30 personas)'") == [(30,)]
    # Cupo de 200: ya hay 3 + 40 + 5 + 30 = 78 lugares; 150 más lo rebasan
    r = c.post("/pases/eventos/1/generar", modo="grupal", cantidad="150")
    assert r.status_code == 400 and "cupo" in r.text
    assert c.get("/pases/eventos/1/imprimir").text.count('class="gafete"') == 3 + 1 + 5 + 1


def test_desactivar_y_activar_credencial_con_auditoria(app):
    c = Cliente(app, "vigilancia")
    id_cred = sql("SELECT id_credencial FROM credenciales WHERE id_persona = 13")[0][0]
    c.get(f"/credenciales/{id_cred}")
    assert c.post(f"/credenciales/{id_cred}/estado", activa="0").status_code == 302
    token = sql("SELECT token FROM credenciales WHERE id_credencial = %s", (id_cred,))[0][0]
    assert c.caseta(metodo="qr", dato=token, punto=1).get_json()["mensaje"] == "Credencial desactivada"
    c.post(f"/credenciales/{id_cred}/estado", activa="1")
    assert c.caseta(metodo="qr", dato=token, punto=1).get_json()["resultado"] == "permitido"
    assert sql("SELECT a.accion, u.usuario FROM auditoria a JOIN usuarios u USING (id_usuario) "
               "WHERE a.tabla = 'credenciales' ORDER BY a.id_auditoria") == [("desactivar", "vigilancia"),
                                                                              ("activar", "vigilancia")]


def test_editar_credencial_y_regenerar_qr(app):
    c = Cliente(app, "admin")
    id_cred = sql("SELECT id_credencial FROM credenciales WHERE id_persona = 2")[0][0]
    anterior = sql("SELECT token FROM credenciales WHERE id_credencial = %s", (id_cred,))[0][0]
    c.get(f"/credenciales/{id_cred}")
    r = c.post(f"/credenciales/{id_cred}/editar", id_perfil="1", id_horario="", vigencia_inicio="2026-08-01T00:00",
               vigencia_fin="2026-08-02T00:00", usos="varios", usos_numero="3")
    assert r.status_code == 302
    assert sql("SELECT usos_maximos, estado FROM vw_credenciales WHERE id_credencial = %s", (id_cred,)) == [(3, "vencida")]
    c.post(f"/credenciales/{id_cred}/regenerar")
    nuevo = sql("SELECT token FROM credenciales WHERE id_credencial = %s", (id_cred,))[0][0]
    assert nuevo != anterior and nuevo.startswith("ITVH-")
    r = Cliente(app, "vigilancia").caseta(metodo="qr", dato=anterior, punto=1).get_json()
    assert r["mensaje"] == "Código QR no registrado"


def test_horarios_y_perfiles(app):
    c = Cliente(app, "admin")
    r = c.post("/horarios/nuevo", nombre="Sabatino", dias=["6"], hora_inicio="08:00", hora_fin="14:00")
    assert r.status_code == 302
    id_h = sql("SELECT id_horario FROM horarios WHERE nombre = 'Sabatino'")[0][0]
    c.post(f"/horarios/{id_h}/franja", dias=["7"], hora_inicio="09:00", hora_fin="12:00")
    assert sql("SELECT franjas FROM vw_horarios WHERE id_horario = %s", (id_h,)) == [("Sáb 08:00–14:00, Dom 09:00–12:00",)]
    r = c.post(f"/horarios/{id_h}/franja", dias=["1"], hora_inicio="14:00", hora_fin="08:00")
    assert r.status_code == 400
    c.post("/horarios/perfil/5", descripcion="Proveedores", id_horario=str(id_h), puntos=["2"])
    assert sql("SELECT id_horario FROM perfiles_acceso WHERE id_perfil = 5") == [(id_h,)]
    assert sql("SELECT id_punto FROM perfil_puntos WHERE id_perfil = 5") == [(2,)]


def test_administracion_de_usuarios(app):
    c = Cliente(app, "admin")
    c.get("/admin/")
    assert c.post("/admin/usuarios/nuevo", usuario="guardia2", nombre="Guardia turno noche", rol="vigilancia",
                  password="NocheSegura1").status_code == 302
    c2 = Cliente(app)
    assert c2.post("/login", usuario="guardia2", password="NocheSegura1").status_code == 302
    assert c2.get("/admin/").status_code == 403
    assert c.post("/admin/usuarios/nuevo", usuario="corta", nombre="X", rol="admin", password="123").status_code == 400
    id_admin = sql("SELECT id_usuario FROM usuarios WHERE usuario = 'admin'")[0][0]
    assert c.post(f"/admin/usuarios/{id_admin}/estado", activo="0").status_code == 400


def test_reportes_csv(app):
    c = Cliente(app, "consulta")
    r = c.get("/bitacora/asistencia?desde=2026-01-01&formato=csv")
    assert r.mimetype == "text/csv"
    texto = r.data.decode("utf-8-sig")
    assert texto.splitlines()[0].startswith("Fecha,Persona,Tipo")
    assert len(texto.splitlines()) > 10


# ---------------------------------------------------------------- kiosco de alumnos
PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d494441"
    "54789c63f8ffffff7f0009fb03fd2a86e38a0000000049454e44ae426082")


def test_kiosco_pantalla_y_permisos(app):
    c = Cliente(app)
    r = c.post("/login", usuario="kiosco", password="Campus#2026")
    assert r.status_code == 302 and r.headers["Location"].endswith("/kiosco/")
    assert "¿En qué acceso está esta computadora?" in c.get("/kiosco/").text       # dos accesos de entrada
    assert "Escribe tu número de control" in c.get("/kiosco/?punto=1").text
    assert "Escribe tu número de control" in c.get("/kiosco/").text                # recuerda el acceso
    assert c.get("/personas/").status_code == 403
    assert c.get("/").status_code == 403
    assert Cliente(app, "vigilancia").get("/kiosco/").status_code == 403
    assert "Kiosco de alumnos" in Cliente(app, "admin").get("/").text


def test_kiosco_registra_y_muestra_foto_de_ejemplo(app):
    c = Cliente(app, "kiosco")
    c.get("/kiosco/?punto=1")
    r = c.c.post("/kiosco/registrar", json={"dato": "22301001", "punto": 1}, headers={"X-CSRF-Token": c.csrf})
    d = r.get_json()
    assert d["resultado"] == "permitido" and d["foto"] == "/fotos/1" and d["foto_ejemplo"] is True
    foto = c.get("/fotos/1")
    assert foto.mimetype == "image/svg+xml" and foto.headers["X-Foto-Ejemplo"] == "1"
    assert sql("SELECT metodo, evento, operador FROM vw_bitacora ORDER BY id_registro DESC LIMIT 1") == \
        [("kiosco", "entrada", "kiosco")]
    r = c.c.post("/kiosco/registrar", json={"dato": "", "punto": 1}, headers={"X-CSRF-Token": c.csrf})
    assert r.status_code == 400


def test_subir_y_quitar_foto(app):
    import io
    c = Cliente(app, "recepcion")
    c.get("/personas/1")
    r = c.post("/fotos/1", foto=(io.BytesIO(b"no soy una imagen"), "x.png"))
    assert r.status_code == 302 and sql("SELECT count(*) FROM fotos_personas") == [(0,)]
    c.post("/fotos/1", foto=(io.BytesIO(PNG_1x1), "foto.png"))
    foto = c.c.get("/fotos/1")
    assert foto.mimetype == "image/png" and foto.data == PNG_1x1 and foto.headers["X-Foto-Ejemplo"] == "0"
    assert "Cambiar foto" in c.get("/personas/1").text
    assert Cliente(app, "consulta").post("/fotos/1", foto=(io.BytesIO(PNG_1x1), "f.png")).status_code == 403
    c.post("/fotos/1/quitar")
    assert sql("SELECT count(*) FROM fotos_personas") == [(0,)]
