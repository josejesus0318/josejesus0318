"""Ventana principal.

Menú lateral con los módulos permitidos para el rol de la sesión y un
QStackedWidget (equivalente al CardLayout de Swing) donde se muestran las
pantallas. Cada pantalla se crea la primera vez que se abre.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from control_acceso import NOMBRE_APP, __version__
from control_acceso.utils.config import config
from control_acceso.utils.conexion import sesion
from control_acceso.utils.permisos import MODULOS, Modulo, puede_editar, puede_ver
from control_acceso.views.bitacora_view import BitacoraView
from control_acceso.views.colaboradores_view import ColaboradoresView
from control_acceso.views.credenciales_view import CredencialesView
from control_acceso.views.inicio_view import InicioView
from control_acceso.views.lector_qr_dialog import LectorQRDlg
from control_acceso.views.panel_catalogo import CatalogosView
from control_acceso.views.usuarios_view import UsuariosView
from control_acceso.views.visitas_view import VisitasView


class PaginaLector(QWidget):
    """Página del módulo Lector: explica el uso y abre el diálogo de la cámara."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addStretch()
        titulo = QLabel("Lector de códigos QR")
        titulo.setObjectName("tituloSeccion")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        texto = QLabel(
            "Abre la cámara web, detecta el código QR de la credencial y registra automáticamente "
            "la <b>entrada</b> o <b>salida</b> en el punto de acceso seleccionado.<br><br>"
            "La base de datos valida que el código exista, que la credencial esté <b>activa</b>, "
            "que no esté vencida y que su rol tenga permiso en ese punto.")
        texto.setWordWrap(True)
        texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        texto.setMaximumWidth(620)
        boton = QPushButton("Abrir lector QR")
        boton.setObjectName("primarioGrande")
        boton.clicked.connect(self.abrir)
        layout.addWidget(titulo)
        layout.addWidget(texto, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(16)
        layout.addWidget(boton, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def abrir(self) -> None:
        LectorQRDlg(self).exec()


class MainWindow(QMainWindow):

    sesion_cerrada = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(NOMBRE_APP)
        self.resize(1280, 780)
        self.modulos: list[Modulo] = [m for m in MODULOS if puede_ver(m)]
        self.paginas: dict[str, QWidget] = {}
        self._cerrando_sesion = False
        self._fabricas: dict[str, Callable[[Modulo], QWidget]] = {
            "inicio": lambda m: InicioView(),
            "lector": lambda m: PaginaLector(),
            "bitacora": lambda m: BitacoraView(),
            "colaboradores": lambda m: ColaboradoresView(puede_editar(m)),
            "visitas": lambda m: VisitasView(puede_editar(m)),
            "credenciales": lambda m: CredencialesView(puede_editar(m)),
            "catalogos": lambda m: CatalogosView(),
            "usuarios": lambda m: UsuariosView(),
        }
        self._construir()
        self._crear_menu()
        self.menu_lateral.setCurrentRow(0)

        # Una cuenta exclusiva de lector abre directamente la cámara
        if sesion.roles == {"rol_lector_qr"} and not sesion.es_superusuario:
            QTimer.singleShot(400, self._abrir_lector)

    # -- interfaz ------------------------------------------------------------
    def _construir(self) -> None:
        central = QWidget()
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        cabecera = QWidget()
        cabecera.setObjectName("cabecera")
        fila = QHBoxLayout(cabecera)
        titulo = QLabel("Grupo Solutions · Control de Acceso QR")
        titulo.setObjectName("cabeceraTitulo")
        usuario = QLabel(f"{sesion.nombre_completo}  ·  {sesion.descripcion_roles}")
        usuario.setObjectName("cabeceraUsuario")
        btn_salir = QPushButton("Cerrar sesión")
        btn_salir.setObjectName("cabeceraBoton")
        btn_salir.clicked.connect(self.cerrar_sesion)
        fila.addWidget(titulo)
        fila.addStretch()
        fila.addWidget(usuario)
        fila.addWidget(btn_salir)
        raiz.addWidget(cabecera)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        self.menu_lateral = QListWidget()
        self.menu_lateral.setObjectName("menuLateral")
        self.menu_lateral.setFixedWidth(210)
        for modulo in self.modulos:
            item = QListWidgetItem(modulo.titulo)
            item.setData(Qt.ItemDataRole.UserRole, modulo.clave)
            self.menu_lateral.addItem(item)
        self.menu_lateral.currentRowChanged.connect(self._mostrar_modulo)
        self.pila = QStackedWidget()
        self.pila.setObjectName("contenido")
        cuerpo.addWidget(self.menu_lateral)
        cuerpo.addWidget(self.pila, 1)
        raiz.addLayout(cuerpo, 1)

        self.setCentralWidget(central)
        self.statusBar().showMessage(
            f"Conectado a {config.host}:{config.puerto}/{config.base} como {sesion.usuario}")

    def _crear_menu(self) -> None:
        menu_sesion = self.menuBar().addMenu("&Sesión")
        accion_cerrar = QAction("Cerrar sesión", self)
        accion_cerrar.triggered.connect(self.cerrar_sesion)
        accion_salir = QAction("Salir", self)
        accion_salir.setShortcut("Ctrl+Q")
        accion_salir.triggered.connect(self.close)
        menu_sesion.addAction(accion_cerrar)
        menu_sesion.addSeparator()
        menu_sesion.addAction(accion_salir)

        menu_ayuda = self.menuBar().addMenu("A&yuda")
        accion_acerca = QAction("Acerca de…", self)
        accion_acerca.triggered.connect(self._acerca_de)
        menu_ayuda.addAction(accion_acerca)

    # -- navegación ------------------------------------------------------------
    def _mostrar_modulo(self, fila: int) -> None:
        if not 0 <= fila < len(self.modulos):
            return
        modulo = self.modulos[fila]
        if modulo.clave not in self.paginas:
            pagina = self._fabricas[modulo.clave](modulo)
            self.paginas[modulo.clave] = pagina
            self.pila.addWidget(pagina)
        pagina = self.paginas[modulo.clave]
        self.pila.setCurrentWidget(pagina)
        refrescar = getattr(pagina, "refrescar", None)
        if callable(refrescar) and modulo.clave != "inicio":   # inicio se refresca al mostrarse
            refrescar()

    def _abrir_lector(self) -> None:
        LectorQRDlg(self).exec()

    # -- sesión ------------------------------------------------------------------
    def cerrar_sesion(self) -> None:
        self._cerrando_sesion = True
        self.close()
        self.deleteLater()
        self.sesion_cerrada.emit()          # el controlador vuelve a mostrar el login

    def closeEvent(self, event) -> None:  # noqa: N802
        sesion.cerrar()
        super().closeEvent(event)
        if not self._cerrando_sesion:       # cerrar la ventana = salir de la aplicación
            QApplication.quit()

    def _acerca_de(self) -> None:
        QMessageBox.about(
            self, "Acerca de",
            f"<b>{NOMBRE_APP}</b><br>Versión {__version__}<br><br>"
            "Taller de Bases de Datos – Instituto Tecnológico de Villahermosa<br>"
            "Equipo 6 – Color Magenta<br><br>"
            "Python · PyQt6 · psycopg · OpenCV · PostgreSQL")
