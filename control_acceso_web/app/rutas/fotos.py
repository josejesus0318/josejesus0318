"""Fotografías de las personas (las muestra el kiosco para que el guardia compare).

Si una persona no tiene foto, se dibuja una IMAGEN DE EJEMPLO (una ilustración
genérica tipo fotografía de credencial). Así el sistema funciona desde el primer día
y las fotos reales se pueden ir subiendo desde la ficha de cada persona.
"""
from __future__ import annotations

import hashlib

from flask import Blueprint, Response, abort, flash, redirect, request, url_for

from .. import db
from ..seguridad import requiere

bp = Blueprint("fotos", __name__, url_prefix="/fotos")

TAMANO_MAXIMO = 900 * 1024

FONDOS = ["#dbe7f5", "#e3efe6", "#f3e6ee", "#efe9dc", "#e2e6f3", "#e9f1f4"]
PIELES = ["#f1c9a5", "#e0ac83", "#c98e65", "#a8714c", "#8d5a3b"]
CABELLOS = ["#1f1a17", "#2e2520", "#4a3426", "#6b4a32", "#2a2a2a"]
CAMISAS = ["#1b396a", "#5b6475", "#a23b72", "#2f6f5e", "#7a4b2a", "#34495e"]


def tipo_imagen(datos: bytes) -> str | None:
    """Reconoce el formato por su contenido, no por el nombre del archivo."""
    if datos.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if datos.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


def avatar_ejemplo(id_persona: int, nombre: str) -> str:
    """Ilustración genérica (SVG) con proporción de fotografía de credencial."""
    h = hashlib.sha256(f"{id_persona}-{nombre}".encode()).digest()
    fondo, piel = FONDOS[h[0] % len(FONDOS)], PIELES[h[1] % len(PIELES)]
    cabello, camisa = CABELLOS[h[2] % len(CABELLOS)], CAMISAS[h[3] % len(CAMISAS)]
    primero = (nombre.split() or ["x"])[0].lower()
    largo = primero.endswith("a") or primero in {"isabel", "carmen", "raquel", "beatriz"}
    pelo_atras = (f'<path d="M66 118 Q60 60 120 52 Q180 60 174 118 L182 236 Q120 252 58 236 Z" fill="{cabello}"/>'
                  if largo else "")
    pelo_arriba = ('<path d="M74 122 Q70 58 120 54 Q170 58 166 122 Q160 92 132 86 Q104 96 80 100 Z" '
                   f'fill="{cabello}"/>') if largo else (
                  '<path d="M76 116 Q72 62 120 58 Q168 62 164 116 Q158 90 120 86 Q90 88 80 104 Z" '
                  f'fill="{cabello}"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 300" width="240" height="300">
<rect width="240" height="300" fill="{fondo}"/>
{pelo_atras}
<path d="M28 300 Q30 232 92 214 L148 214 Q210 232 212 300 Z" fill="{camisa}"/>
<path d="M104 196 L136 196 L138 222 Q120 236 102 222 Z" fill="{piel}"/>
<path d="M104 216 L120 240 L136 216 L148 214 L120 262 L92 214 Z" fill="#ffffff" opacity=".85"/>
<ellipse cx="120" cy="134" rx="46" ry="58" fill="{piel}"/>
<ellipse cx="73" cy="138" rx="7" ry="11" fill="{piel}"/>
<ellipse cx="167" cy="138" rx="7" ry="11" fill="{piel}"/>
{pelo_arriba}
<ellipse cx="102" cy="136" rx="4.5" ry="5" fill="#2b211c"/>
<ellipse cx="138" cy="136" rx="4.5" ry="5" fill="#2b211c"/>
<path d="M94 124 Q102 119 110 123 M130 123 Q138 119 146 124" stroke="#3b2b22" stroke-width="3" fill="none" stroke-linecap="round"/>
<path d="M118 142 Q115 156 121 158" stroke="#00000033" stroke-width="2.5" fill="none" stroke-linecap="round"/>
<path d="M106 170 Q120 180 134 170" stroke="#8a4b3c" stroke-width="3.5" fill="none" stroke-linecap="round"/>
</svg>"""


@bp.route("/<int:id_persona>")
@requiere("fotos")
def ver(id_persona: int):
    foto = db.uno("SELECT tipo_mime, datos FROM fotos_personas WHERE id_persona = %s", (id_persona,))
    if foto:
        resp = Response(bytes(foto["datos"]), mimetype=foto["tipo_mime"])
        resp.headers["X-Foto-Ejemplo"] = "0"
    else:
        persona = db.uno("SELECT nombre FROM personas WHERE id_persona = %s", (id_persona,))
        if not persona:
            abort(404)
        resp = Response(avatar_ejemplo(id_persona, persona["nombre"]), mimetype="image/svg+xml")
        resp.headers["X-Foto-Ejemplo"] = "1"
    resp.headers["Cache-Control"] = "private, max-age=60"
    return resp


@bp.route("/<int:id_persona>", methods=["POST"])
@requiere("personas_editar")
def subir(id_persona: int):
    archivo = request.files.get("foto")
    datos = archivo.read(TAMANO_MAXIMO + 1) if archivo else b""
    if not datos:
        flash("Seleccione una fotografía.", "error")
    elif len(datos) > TAMANO_MAXIMO:
        flash("La fotografía pesa más de 900 KB. Redúzcala e intente de nuevo.", "error")
    elif not (mime := tipo_imagen(datos)):
        flash("La fotografía debe ser JPG, PNG o WEBP.", "error")
    else:
        with db.transaccion() as conn:
            if not conn.execute("SELECT 1 FROM personas WHERE id_persona = %s", (id_persona,)).fetchone():
                abort(404)
            conn.execute(
                """INSERT INTO fotos_personas (id_persona, tipo_mime, datos) VALUES (%s, %s, %s)
                   ON CONFLICT (id_persona) DO UPDATE
                      SET tipo_mime = EXCLUDED.tipo_mime, datos = EXCLUDED.datos, actualizada = now()""",
                (id_persona, mime, datos))
        flash("Fotografía actualizada.", "ok")
    return redirect(url_for("personas.detalle", id_persona=id_persona))


@bp.route("/<int:id_persona>/quitar", methods=["POST"])
@requiere("personas_editar")
def quitar(id_persona: int):
    with db.transaccion() as conn:
        conn.execute("DELETE FROM fotos_personas WHERE id_persona = %s", (id_persona,))
    flash("Fotografía eliminada: se mostrará la imagen de ejemplo.", "ok")
    return redirect(url_for("personas.detalle", id_persona=id_persona))
