"""Pruebas de las reglas de acceso dentro de PostgreSQL.

Necesitan una base de datos de PRUEBA (se borra y se reinstala en cada prueba):
    set TEST_DATABASE_URL=postgresql://usuario:clave@servidor/base_de_pruebas
    python -m pytest pruebas -v
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import threading
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from herramientas.instalar_bd import instalar  # noqa: E402

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="Defina TEST_DATABASE_URL para probar la base de datos")
ZONA = ZoneInfo("America/Mexico_City")


@pytest.fixture
def db():
    instalar(URL, silencioso=True)
    with psycopg.connect(URL, autocommit=True, row_factory=dict_row) as conn:
        conn.execute("SET search_path TO campus, public")
        conn.execute("UPDATE configuracion SET valor = '0' WHERE clave = 'segundos_repeticion'")
        yield conn


# ------------------------------------------------------------------ utilidades
def registrar(conn, metodo, dato, punto, nip=None, usuario=2):
    return conn.execute(
        "SELECT * FROM fn_registrar_acceso(%s, %s, %s, %s, %s)", (metodo, str(dato), punto, nip, usuario)
    ).fetchone()


def token(conn, id_credencial):
    return conn.execute("SELECT token FROM credenciales WHERE id_credencial = %s", (id_credencial,)).fetchone()["token"]


def cred_de(conn, id_persona):
    return conn.execute(
        "SELECT * FROM credenciales WHERE id_persona = %s ORDER BY id_credencial DESC LIMIT 1", (id_persona,)
    ).fetchone()


def sin_horario(conn, id_credencial):
    """Asigna un horario de 24 h todos los días para que la prueba no dependa de la hora."""
    conn.execute(
        """INSERT INTO horarios (nombre) VALUES ('Prueba 24 h') ON CONFLICT (nombre) DO NOTHING;
           INSERT INTO horario_franjas (id_horario, dia_semana, hora_inicio, hora_fin)
           SELECT h.id_horario, d, '00:00', '23:59:59.999'
             FROM horarios h, generate_series(1, 7) d
            WHERE h.nombre = 'Prueba 24 h'
           ON CONFLICT DO NOTHING"""
    )
    conn.execute(
        "UPDATE credenciales SET id_horario = (SELECT id_horario FROM horarios WHERE nombre = 'Prueba 24 h') "
        "WHERE id_credencial = %s",
        (id_credencial,),
    )


# ------------------------------------------------------------------ pruebas
def test_entrada_salida_y_asistencia(db):
    c = cred_de(db, 7)                                    # docente Patricia Morales
    sin_horario(db, c["id_credencial"])
    r = registrar(db, "qr", token(db, c["id_credencial"]), 1)
    assert (r["resultado"], r["evento"]) == ("permitido", "entrada")
    assert r["persona"] == "Patricia Elena Morales Vázquez"
    assert db.execute("SELECT count(*) AS n FROM vw_presentes WHERE id_persona = 7").fetchone()["n"] == 1

    r = registrar(db, "qr", token(db, c["id_credencial"]), 2)
    assert (r["resultado"], r["evento"]) == ("permitido", "salida")
    a = db.execute("SELECT * FROM vw_asistencia WHERE id_persona = 7 AND fecha = fecha_local(now())").fetchone()
    assert a["hora_llegada"] is not None and a["hora_salida"] is not None and a["estado"] == "fuera"
    assert db.execute("SELECT count(*) AS n FROM vw_presentes WHERE id_persona = 7").fetchone()["n"] == 0


def test_lectura_repetida_no_se_registra(db):
    db.execute("UPDATE configuracion SET valor = '10' WHERE clave = 'segundos_repeticion'")
    c = cred_de(db, 7)
    sin_horario(db, c["id_credencial"])
    registrar(db, "qr", c["token"], 1)
    r = registrar(db, "qr", c["token"], 1)
    assert r["resultado"] == "repetido"
    assert db.execute("SELECT count(*) AS n FROM registro_accesos WHERE id_persona = 7 "
                      "AND fecha_local(fecha_hora) = fecha_local(now())").fetchone()["n"] == 1


def test_qr_inexistente(db):
    r = registrar(db, "qr", "ITVH-NOEXISTE", 1)
    assert r["resultado"] == "denegado" and r["mensaje"] == "Código QR no registrado"
    fila = db.execute("SELECT dato_leido FROM registro_accesos ORDER BY id_registro DESC LIMIT 1").fetchone()
    assert fila["dato_leido"] == "ITVH-NOEXISTE"


def test_activar_y_desactivar(db):
    c = cred_de(db, 4)                                    # Carlos: credencial desactivada por extravío
    sin_horario(db, c["id_credencial"])
    assert registrar(db, "qr", c["token"], 1)["mensaje"] == "Credencial desactivada"
    db.execute("UPDATE credenciales SET activa = TRUE WHERE id_credencial = %s", (c["id_credencial"],))
    assert registrar(db, "qr", c["token"], 1)["resultado"] == "permitido"


def test_baja_de_persona(db):
    with db.transaction():
        db.execute("SET LOCAL app.id_usuario = '1'")
        db.execute("UPDATE personas SET activo = FALSE WHERE id_persona = 1")
    c = cred_de(db, 1)
    assert c["activa"] is False                           # el trigger desactivó su credencial
    acciones = db.execute("SELECT tabla, accion, id_usuario FROM auditoria ORDER BY id_auditoria").fetchall()
    assert {"tabla": "personas", "accion": "desactivar", "id_usuario": 1} in acciones
    assert {"tabla": "credenciales", "accion": "desactivar", "id_usuario": 1} in acciones
    # Aunque se reactive la credencial, la persona sigue de baja
    db.execute("UPDATE credenciales SET activa = TRUE WHERE id_credencial = %s", (c["id_credencial"],))
    sin_horario(db, c["id_credencial"])
    assert registrar(db, "qr", c["token"], 1)["mensaje"] == "Persona dada de baja"


def test_pase_de_un_solo_uso(db):
    c = cred_de(db, 15)                                   # visitante Ana Karen, pase de 1 uso
    sin_horario(db, c["id_credencial"])
    r = registrar(db, "qr", c["token"], 1)
    assert (r["resultado"], r["evento"], r["usos_restantes"]) == ("permitido", "entrada", 0)
    assert db.execute("SELECT estado FROM visitas WHERE id_visita = 1").fetchone()["estado"] == "realizada"
    assert registrar(db, "qr", c["token"], 1)["evento"] == "salida"      # la salida siempre se permite
    r = registrar(db, "qr", c["token"], 1)
    assert r["resultado"] == "denegado" and r["mensaje"] == "Pase de un solo uso ya utilizado"


def test_pase_vencido_y_pendiente(db):
    c = cred_de(db, 14)                                   # proveedora con pase vencido
    sin_horario(db, c["id_credencial"])
    assert registrar(db, "qr", c["token"], 1)["mensaje"].startswith("Pase vencido el")
    db.execute(
        "UPDATE credenciales SET vigencia_inicio = now() + interval '1 day', vigencia_fin = now() + interval '3 days' "
        "WHERE id_credencial = %s", (c["id_credencial"],))
    assert registrar(db, "qr", c["token"], 1)["mensaje"].startswith("El pase es válido a partir del")


def test_horario_programado(db):
    def permite(h, local):
        return db.execute("SELECT horario_permite(%s, %s) AS ok", (h, local.replace(tzinfo=ZONA))).fetchone()["ok"]

    lunes = dt.datetime(2026, 11, 23)                     # lunes
    assert permite(1, lunes.replace(hour=10)) is True     # alumnos, lunes 10:00
    assert permite(1, lunes.replace(hour=22)) is False    # lunes 22:00
    assert permite(1, lunes.replace(hour=14) - dt.timedelta(days=2)) is True    # sábado 14:00
    assert permite(1, lunes.replace(hour=16) - dt.timedelta(days=2)) is False   # sábado 16:00
    assert permite(1, lunes.replace(hour=10) - dt.timedelta(days=1)) is False   # domingo
    assert permite(None, lunes) is True                   # sin horario = sin restricción

    # Un horario sin franjas nunca permite la entrada
    db.execute("INSERT INTO horarios (nombre) VALUES ('Cerrado')")
    c = cred_de(db, 8)
    db.execute("UPDATE credenciales SET id_horario = (SELECT id_horario FROM horarios WHERE nombre = 'Cerrado') "
               "WHERE id_credencial = %s", (c["id_credencial"],))
    assert registrar(db, "qr", c["token"], 1)["mensaje"] == "Fuera del horario permitido"


def test_punto_sin_permiso(db):
    c = cred_de(db, 13)                                   # proveedor: solo accesos principal y vehicular
    sin_horario(db, c["id_credencial"])
    assert registrar(db, "qr", c["token"], 4)["mensaje"] == "Sin permiso en este punto de acceso"


def test_ingreso_con_nip_y_bloqueo(db):
    c = cred_de(db, 1)                                    # alumna Andrea, número de control 22301001
    sin_horario(db, c["id_credencial"])
    r = registrar(db, "nip", "22301001", 1, nip="1234")
    assert (r["resultado"], r["evento"]) == ("permitido", "entrada")
    for _ in range(5):
        assert registrar(db, "nip", "22301001", 2, nip="0000")["mensaje"] == "NIP incorrecto"
    r = registrar(db, "nip", "22301001", 2, nip="1234")
    assert r["resultado"] == "denegado" and r["mensaje"].startswith("NIP bloqueado")
    assert registrar(db, "nip", "99999999", 1, nip="1234")["mensaje"].startswith("Número de control")


def test_registro_manual(db):
    c = cred_de(db, 13)
    sin_horario(db, c["id_credencial"])
    r = registrar(db, "manual", 13, 2)
    assert (r["resultado"], r["evento"]) == ("permitido", "entrada")
    assert db.execute("SELECT metodo FROM registro_accesos WHERE id_registro = %s",
                      (r["id_registro"],)).fetchone()["metodo"] == "manual"
    nueva = db.execute("INSERT INTO personas (id_tipo, nombre, apellido_paterno) VALUES (5, 'Sin', 'Pase') "
                       "RETURNING id_persona").fetchone()["id_persona"]
    assert registrar(db, "manual", nueva, 1)["mensaje"].startswith("La persona no tiene credencial")


def test_pases_genericos_de_evento(db):
    pases = db.execute("SELECT * FROM credenciales WHERE id_evento = 1 ORDER BY id_credencial").fetchall()
    individual, otro, grupal = pases[0], pases[1], pases[3]
    # Pase de un solo uso: entra por el acceso principal y luego al auditorio sin gastar otro uso
    assert registrar(db, "qr", individual["token"], 1)["evento"] == "entrada"
    r = registrar(db, "qr", individual["token"], 5)
    assert r["resultado"] == "permitido" and r["mensaje"] == "Acceso permitido a Auditorio"
    assert db.execute("SELECT usos_realizados AS u FROM credenciales WHERE id_credencial = %s",
                      (individual["id_credencial"],)).fetchone()["u"] == 1
    # Otro pase que no ha cruzado la entrada principal no puede ir directo al auditorio
    assert registrar(db, "qr", otro["token"], 5)["mensaje"] == "Registre primero su entrada al campus"
    # Pase grupal: cada lectura es una entrada y descuenta un uso
    for esperado in (39, 38, 37):
        r = registrar(db, "qr", grupal["token"], 1)
        assert (r["evento"], r["usos_restantes"]) == ("entrada", esperado)


def test_un_solo_uso_con_dos_lectores_al_mismo_tiempo(db):
    """FOR UPDATE: si dos casetas leen el mismo pase a la vez, solo una lo acepta."""
    c = cred_de(db, 15)
    sin_horario(db, c["id_credencial"])
    db.execute("UPDATE puntos_acceso SET sentido = 'entrada' WHERE id_punto = 2")   # B solo registra entradas
    resultados = {}
    with psycopg.connect(URL, row_factory=dict_row) as a, psycopg.connect(URL, row_factory=dict_row) as b:
        a.execute("SET search_path TO campus, public")
        b.execute("SET search_path TO campus, public")
        resultados["a"] = registrar(a, "qr", c["token"], 1)           # A no confirma todavía

        def lector_b():
            resultados["b"] = registrar(b, "qr", c["token"], 2)
            b.commit()

        hilo = threading.Thread(target=lector_b)
        hilo.start()
        time.sleep(0.5)
        assert hilo.is_alive(), "B debería estar esperando el bloqueo de A"
        a.commit()
        hilo.join(5)
    assert resultados["a"]["resultado"] == "permitido"
    assert resultados["b"]["resultado"] == "denegado"
    assert resultados["b"]["mensaje"] == "Pase de un solo uso ya utilizado"


def test_bitacora_inmutable(db):
    for sql in ("UPDATE registro_accesos SET resultado = 'permitido'", "DELETE FROM registro_accesos"):
        with pytest.raises(psycopg.DatabaseError, match="no se puede modificar") as error:
            db.execute(sql)
        assert error.value.sqlstate == "GS001"


def test_login(db):
    ok = db.execute("SELECT * FROM fn_login('Admin ', 'Campus#2026')").fetchone()
    assert ok["rol"] == "admin"
    assert db.execute("SELECT * FROM fn_login('admin', 'otra')").fetchone() is None
    db.execute("UPDATE usuarios SET activo = FALSE WHERE usuario = 'consulta'")
    assert db.execute("SELECT * FROM fn_login('consulta', 'Campus#2026')").fetchone() is None


def test_rol_de_minimo_privilegio(db):
    db.execute("ALTER ROLE app_campus LOGIN PASSWORD 'clave_de_prueba_larga'")
    info = psycopg.conninfo.conninfo_to_dict(URL)
    info.update(user="app_campus", password="clave_de_prueba_larga")
    with psycopg.connect(**info, autocommit=True, row_factory=dict_row) as app:
        app.execute("SET search_path TO campus, public")
        assert app.execute("SELECT count(*) AS n FROM vw_credenciales").fetchone()["n"] > 0
        assert app.execute("SELECT * FROM fn_login('admin', 'Campus#2026')").fetchone()["rol"] == "admin"
        c = app.execute("SELECT token FROM credenciales WHERE id_persona = 13").fetchone()
        assert registrar(app, "qr", c["token"], 1)["resultado"] in ("permitido", "denegado")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("INSERT INTO registro_accesos (id_punto, metodo, resultado, motivo) "
                        "VALUES (1, 'qr', 'denegado', 'falso')")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("SELECT password_hash FROM usuarios")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute("DELETE FROM personas WHERE id_persona = 16")


def test_asistencia_historica(db):
    filas = db.execute("SELECT * FROM vw_asistencia WHERE fecha < fecha_local(now()) ORDER BY fecha").fetchall()
    assert filas, "Los datos de demostración deben traer llegadas y salidas de días anteriores"
    assert all(f["hora_llegada"] < f["hora_salida"] for f in filas)
    assert all(f["estado"] == "fuera" for f in filas)
