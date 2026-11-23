"""Instala (o reinstala) la base de datos del Control de Acceso Campus ITVH.

No necesita psql: usa la misma librería (psycopg) que la aplicación.

Uso:
    python herramientas/instalar_bd.py                 # usa DATABASE_URL del archivo .env
    python herramientas/instalar_bd.py "postgresql://usuario:clave@servidor/neondb?sslmode=require"

ATENCIÓN: borra el esquema "campus" y lo vuelve a crear con los datos de demostración.
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS = ["01_esquema.sql", "02_funciones.sql", "03_vistas.sql", "04_datos.sql", "05_seguridad.sql",
            "06_procedimientos.sql"]


def leer_env(nombre: str) -> str | None:
    """Busca una variable en el entorno o en el archivo .env de la carpeta del proyecto."""
    import os

    if os.environ.get(nombre):
        return os.environ[nombre]
    env = RAIZ / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea.startswith(nombre + "="):
                return linea.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def instalar(url: str, silencioso: bool = False) -> dict[str, int]:
    """Ejecuta los scripts en una sola transacción: si algo falla, no queda nada a medias."""
    with psycopg.connect(url) as conn:
        for nombre in ARCHIVOS:
            if not silencioso:
                print(f">> {nombre}")
            sql = (RAIZ / "database" / nombre).read_text(encoding="utf-8")
            conn.execute(sql)
        filas = conn.execute(
            """SELECT 'personas', count(*) FROM campus.personas
               UNION ALL SELECT 'credenciales', count(*) FROM campus.credenciales
               UNION ALL SELECT 'registro_accesos', count(*) FROM campus.registro_accesos
               UNION ALL SELECT 'usuarios', count(*) FROM campus.usuarios"""
        ).fetchall()
    return {tabla: total for tabla, total in filas}


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else leer_env("DATABASE_URL")
    if not url:
        print("Falta la cadena de conexión. Póngala en el archivo .env como DATABASE_URL=... "
              "o pásela como argumento entre comillas.")
        return 1
    try:
        totales = instalar(url)
    except psycopg.Error as e:
        print(f"\nERROR de PostgreSQL: {e}")
        return 1
    print("\n>> Instalación terminada")
    for tabla, total in totales.items():
        print(f"   {tabla:<18} {total}")
    print("\nUsuarios de demostración: admin, vigilancia, recepcion, consulta  (contraseña: Campus#2026)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
