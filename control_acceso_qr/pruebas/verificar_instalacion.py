"""Verifica que la computadora esté lista para ejecutar la aplicación.

Uso (desde la carpeta control_acceso_qr):
    python pruebas/verificar_instalacion.py
    python pruebas/verificar_instalacion.py --usuario gs_admin --sin-camara

Revisa: versión de Python, librerías, conexión a PostgreSQL con una
cuenta, roles detectados, consulta de prueba, cámara web y lectura de un
código QR generado en memoria.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

OK, FALLA, AVISO = "  [OK]   ", "  [FALLA]", "  [AVISO]"


def revisar_librerias() -> bool:
    print("\n1. Librerías")
    todo_bien = True
    if sys.version_info < (3, 10):
        print(f"{FALLA} Python {sys.version.split()[0]}: se requiere 3.10 o superior")
        todo_bien = False
    else:
        print(f"{OK} Python {sys.version.split()[0]}")
    for modulo, nombre in (("PyQt6.QtWidgets", "PyQt6"), ("psycopg", "psycopg"),
                           ("cv2", "opencv-python"), ("numpy", "numpy")):
        try:
            mod = __import__(modulo, fromlist=["_"])
            version = getattr(mod, "__version__", "") or getattr(mod, "PYQT_VERSION_STR", "")
            print(f"{OK} {nombre} {version}")
        except Exception as exc:  # noqa: BLE001
            print(f"{FALLA} {nombre}: {exc}  →  pip install -r requirements.txt")
            todo_bien = False
    try:
        from pyzbar import pyzbar  # noqa: F401
        print(f"{OK} pyzbar (decodificador principal)")
    except Exception as exc:  # noqa: BLE001
        print(f"{AVISO} pyzbar no disponible ({exc.__class__.__name__}); se usará OpenCV.")
        print("          En Windows suele faltar el «Visual C++ Redistributable 2013».")
    return todo_bien


def revisar_base_datos(usuario: str) -> bool:
    print("\n2. Base de datos")
    from control_acceso.dao.sesion_dao import SesionDAO
    from control_acceso.utils.config import config
    from control_acceso.utils.conexion import sesion
    from control_acceso.utils.errores import ErrorAplicacion

    print(f"         Servidor {config.host}:{config.puerto}  base «{config.base}»  usuario «{usuario}»")
    password = getpass.getpass("         Contraseña: ")
    try:
        sesion.iniciar(usuario, password)
        SesionDAO().cargar_datos_sesion()
        print(f"{OK} Conexión correcta como {sesion.nombre_completo}")
        print(f"{OK} Roles detectados: {sesion.descripcion_roles}")
        resumen = SesionDAO().resumen_hoy()
        print(f"{OK} Consulta de prueba: {resumen.get('colaboradores_activos')} colaboradores activos, "
              f"{resumen.get('visitas_hoy')} visita(s) hoy")
        return True
    except ErrorAplicacion as error:
        print(f"{FALLA} {error.mensaje}")
        if error.detalle:
            print("          " + error.detalle.replace("\n", "\n          "))
        return False
    finally:
        sesion.cerrar()


def revisar_camara(indice: int) -> bool:
    print("\n3. Cámara y lectura QR")
    import cv2

    from control_acceso.utils.qr import DecodificadorQR, generar_qr

    decodificador = DecodificadorQR()
    imagen = cv2.cvtColor(generar_qr("QR-PRUEBA-0001"), cv2.COLOR_GRAY2BGR)
    if decodificador.decodificar(imagen) == ["QR-PRUEBA-0001"]:
        print(f"{OK} Generación y lectura de QR ({decodificador.motor})")
    else:
        print(f"{FALLA} No se pudo leer un QR generado en memoria")
        return False

    backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
    camara = cv2.VideoCapture(indice, backend)
    try:
        if not camara.isOpened():
            print(f"{FALLA} No se pudo abrir la cámara {indice}. Pruebe otro índice con --camara 1")
            return False
        ok, cuadro = camara.read()
        if not ok:
            print(f"{FALLA} La cámara {indice} abrió pero no entregó imagen")
            return False
        alto, ancho = cuadro.shape[:2]
        print(f"{OK} Cámara {indice} funcionando ({ancho}×{alto})")
        return True
    finally:
        camara.release()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--usuario", default="gs_admin", help="cuenta de PostgreSQL para la prueba")
    parser.add_argument("--camara", type=int, default=0, help="índice de la cámara (0 = predeterminada)")
    parser.add_argument("--sin-camara", action="store_true", help="omitir la prueba de cámara")
    args = parser.parse_args()

    print("Verificación de instalación – Control de Acceso QR")
    resultados = [revisar_librerias()]
    if resultados[0]:
        resultados.append(revisar_base_datos(args.usuario))
        if not args.sin_camara:
            resultados.append(revisar_camara(args.camara))
    print("\nResultado:", "TODO LISTO, ejecute: python main.py" if all(resultados)
          else "hay elementos por corregir (vea arriba)")
    return 0 if all(resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
