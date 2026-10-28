"""Generación y decodificación de códigos QR.

Decodificación: se intenta pyzbar (rápido y tolerante). Si su librería
nativa no carga (en Windows requiere el redistribuible de Visual C++
2013), se usa automáticamente el detector de OpenCV.
Generación: OpenCV (cv2.QRCodeEncoder), sin dependencias extra.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import cv2
import numpy as np

try:  # pragma: no cover - depende del sistema operativo
    from pyzbar import pyzbar as _pyzbar
    from pyzbar.pyzbar import ZBarSymbol as _ZBarSymbol
except Exception:  # ImportError, OSError (DLL faltante), etc.
    _pyzbar = None
    _ZBarSymbol = None


class DecodificadorQR:
    """Busca códigos QR en un fotograma BGR de OpenCV."""

    def __init__(self) -> None:
        self._opencv = cv2.QRCodeDetector()
        self.motor = "pyzbar" if _pyzbar is not None else "OpenCV"

    def decodificar(self, fotograma: np.ndarray) -> list[str]:
        """Devuelve los textos de los QR encontrados (lista vacía si no hay)."""
        gris = cv2.cvtColor(fotograma, cv2.COLOR_BGR2GRAY) if fotograma.ndim == 3 else fotograma
        if _pyzbar is not None and _ZBarSymbol is not None:
            simbolos = _pyzbar.decode(gris, symbols=[_ZBarSymbol.QRCODE])
            return [s.data.decode("utf-8", errors="replace").strip() for s in simbolos if s.data]
        texto, _puntos, _ = self._opencv.detectAndDecode(gris)
        return [texto.strip()] if texto else []


def generar_qr(texto: str, tamano: int = 360, margen: int = 4) -> np.ndarray:
    """Genera la imagen (escala de grises) de un código QR."""
    codificador = cv2.QRCodeEncoder.create()
    modulo = codificador.encode(texto)                  # 1 píxel por módulo
    if modulo.ndim == 3:
        modulo = cv2.cvtColor(modulo, cv2.COLOR_BGR2GRAY)
    modulo = cv2.copyMakeBorder(modulo, margen, margen, margen, margen,
                                cv2.BORDER_CONSTANT, value=255)
    escala = max(1, tamano // modulo.shape[0])
    return cv2.resize(modulo, None, fx=escala, fy=escala, interpolation=cv2.INTER_NEAREST)


def guardar_qr(texto: str, ruta: str | Path, leyenda: str = "") -> Path:
    """Guarda el QR como PNG, con una leyenda opcional debajo."""
    imagen = generar_qr(texto)
    if leyenda:
        alto_texto = 60
        lienzo = np.full((imagen.shape[0] + alto_texto, imagen.shape[1]), 255, dtype=np.uint8)
        lienzo[: imagen.shape[0]] = imagen
        # Las fuentes de OpenCV no tienen acentos: se quitan para la leyenda
        leyenda = unicodedata.normalize("NFKD", leyenda).encode("ascii", "ignore").decode()
        for i, linea in enumerate(leyenda.splitlines()[:2]):
            cv2.putText(lienzo, linea, (12, imagen.shape[0] + 22 + i * 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 1, cv2.LINE_AA)
        imagen = lienzo
    ruta = Path(ruta)
    ok, datos = cv2.imencode(".png", imagen)        # imencode admite rutas con acentos
    if not ok:
        raise OSError("No se pudo generar la imagen del código QR")
    ruta.write_bytes(datos.tobytes())
    return ruta
