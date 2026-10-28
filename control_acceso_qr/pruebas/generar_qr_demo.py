"""Genera imágenes PNG de las credenciales de demostración para probar el lector.

Uso (desde la carpeta control_acceso_qr):
    python pruebas/generar_qr_demo.py

Crea la carpeta qr_demo/ con un PNG por credencial. Ábranlas en el celular
y acérquenlas a la cámara. Resultado esperado en la Entrada Principal:
    QR-COL-0001  Mariana Torres      → permitido (entrada / salida)
    QR-COL-0005  Karla Hernández     → denegado: credencial revocada (baja)
    QR-VIS-0002  Gabriela Nava       → denegado: credencial vencida
    QR-VIS-0006  Óscar Ramírez       → permitido (visita programada para hoy*)
    QR-COL-0002  Roberto Jiménez     → denegado en «Sala de Servidores» (sin permiso)

* La visita de Óscar se crea con la fecha del día en que se instaló la base
  de datos; si la prueban otro día, programen una visita nueva en Recepción.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from control_acceso.utils.qr import guardar_qr  # noqa: E402

DEMO = {
    "QR-COL-0001": "Mariana Torres Gutierrez",
    "QR-COL-0002": "Roberto Jimenez Pech",
    "QR-COL-0005": "Karla Hernandez Cruz (baja)",
    "QR-COL-0007": "Sergio Dominguez Vera",
    "QR-VIS-0002": "Gabriela Nava Cetina (vencida)",
    "QR-VIS-0006": "Oscar Ramirez Cordero (visita)",
}


def main() -> None:
    carpeta = RAIZ / "qr_demo"
    carpeta.mkdir(exist_ok=True)
    for codigo, titular in DEMO.items():
        ruta = guardar_qr(codigo, carpeta / f"{codigo}.png", f"{titular}\n{codigo}")
        print("Generado:", ruta)


if __name__ == "__main__":
    main()
