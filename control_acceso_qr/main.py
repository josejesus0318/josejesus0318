"""Punto de entrada de la aplicación.

Uso:
    python main.py
"""

from __future__ import annotations

import sys
import traceback

from PyQt6.QtWidgets import QApplication, QMessageBox

from control_acceso import NOMBRE_APP
from control_acceso.utils.config import RUTA_RECURSOS
from control_acceso.views.login_window import LoginWindow
from control_acceso.views.main_window import MainWindow


def _manejar_excepcion(tipo, valor, rastreo) -> None:
    """Muestra cualquier error no previsto en lugar de cerrar la aplicación."""
    texto = "".join(traceback.format_exception(tipo, valor, rastreo))
    print(texto, file=sys.stderr)
    caja = QMessageBox(QMessageBox.Icon.Critical, "Error inesperado",
                       "Ocurrió un error inesperado. La operación no se completó.")
    caja.setDetailedText(texto)
    caja.exec()


class Aplicacion:
    """Controla el ciclo login → ventana principal → cerrar sesión → login."""

    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.ventana: MainWindow | None = None

    def mostrar_login(self) -> bool:
        """Muestra el login; devuelve False si el usuario decidió salir."""
        login = LoginWindow()
        if not login.exec():
            self.app.quit()
            return False
        self.ventana = MainWindow()
        self.ventana.sesion_cerrada.connect(self._volver_al_login)
        self.ventana.show()
        return True

    def _volver_al_login(self) -> None:
        self.mostrar_login()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(NOMBRE_APP)
    # La salida es explícita: al cerrar sesión hay un instante sin ventanas abiertas
    app.setQuitOnLastWindowClosed(False)
    sys.excepthook = _manejar_excepcion

    estilo = RUTA_RECURSOS / "estilo.qss"
    if estilo.exists():
        app.setStyleSheet(estilo.read_text(encoding="utf-8"))

    controlador = Aplicacion(app)
    if not controlador.mostrar_login():
        return 0
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
