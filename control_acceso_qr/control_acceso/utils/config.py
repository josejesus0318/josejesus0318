"""Lectura de config.ini (datos de conexión y del lector QR).

El archivo vive junto a main.py. Si no existe, se usan valores por omisión.
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
RUTA_CONFIG = RAIZ_PROYECTO / "config.ini"
RUTA_RECURSOS = RAIZ_PROYECTO / "recursos"


@dataclass
class Configuracion:
    """Parámetros de la aplicación."""

    host: str = "127.0.0.1"
    puerto: int = 5432
    base: str = "grupo_solutions_v2"
    tiempo_espera: int = 5
    punto_acceso: int = 1
    indice_camara: int = 0
    pausa_resultado: float = 2.5


def cargar_configuracion(ruta: Path = RUTA_CONFIG) -> Configuracion:
    """Lee config.ini; cualquier valor ausente conserva su valor por omisión."""
    cfg = Configuracion()
    lector = configparser.ConfigParser()
    if not lector.read(ruta, encoding="utf-8"):
        return cfg

    bd = lector["base_datos"] if lector.has_section("base_datos") else {}
    lq = lector["lector"] if lector.has_section("lector") else {}

    cfg.host = bd.get("host", cfg.host)
    cfg.puerto = int(bd.get("puerto", cfg.puerto))
    cfg.base = bd.get("base", cfg.base)
    cfg.tiempo_espera = int(bd.get("tiempo_espera", cfg.tiempo_espera))
    cfg.punto_acceso = int(lq.get("punto_acceso", cfg.punto_acceso))
    cfg.indice_camara = int(lq.get("indice_camara", cfg.indice_camara))
    cfg.pausa_resultado = float(lq.get("pausa_resultado", cfg.pausa_resultado))
    return cfg


def guardar_conexion(cfg: Configuracion, ruta: Path = RUTA_CONFIG) -> None:
    """Guarda host, puerto y base en config.ini (se usa desde el login)."""
    lector = configparser.ConfigParser()
    lector.read(ruta, encoding="utf-8")
    if not lector.has_section("base_datos"):
        lector.add_section("base_datos")
    lector["base_datos"]["host"] = cfg.host
    lector["base_datos"]["puerto"] = str(cfg.puerto)
    lector["base_datos"]["base"] = cfg.base
    with open(ruta, "w", encoding="utf-8") as archivo:
        lector.write(archivo)


# Instancia compartida por toda la aplicación
config = cargar_configuracion()
