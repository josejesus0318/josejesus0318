"""Pantalla de inicio de sesión.

- Autentica contra PostgreSQL (SCRAM-SHA-256) con la cuenta del usuario.
- Tras 3 intentos fallidos bloquea el formulario durante 30 segundos.
- Permite ajustar host, puerto y base de datos (se guardan en config.ini).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from control_acceso import NOMBRE_APP
from control_acceso.dao.sesion_dao import SesionDAO
from control_acceso.utils.config import config, guardar_conexion
from control_acceso.utils.conexion import sesion
from control_acceso.utils.errores import ErrorAplicacion

MAX_INTENTOS = 3
SEGUNDOS_BLOQUEO = 30


class LoginWindow(QDialog):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Iniciar sesión – {NOMBRE_APP}")
        self.setMinimumWidth(420)
        self._intentos = 0
        self._restante = 0
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(1000)
        self._temporizador.timeout.connect(self._cuenta_regresiva)
        self._construir()

    # -- interfaz ------------------------------------------------------------
    def _construir(self) -> None:
        layout = QVBoxLayout(self)

        titulo = QLabel("Grupo Solutions")
        titulo.setObjectName("loginTitulo")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitulo = QLabel("Sistema de Control de Acceso con Códigos QR")
        subtitulo.setObjectName("loginSubtitulo")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)

        formulario = QFormLayout()
        self.txt_usuario = QLineEdit()
        self.txt_usuario.setPlaceholderText("Cuenta de PostgreSQL (p. ej. gs_recepcion)")
        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_password.setPlaceholderText("Contraseña")
        self.txt_password.returnPressed.connect(self._ingresar)
        self.txt_usuario.returnPressed.connect(self.txt_password.setFocus)
        formulario.addRow("Usuario:", self.txt_usuario)
        formulario.addRow("Contraseña:", self.txt_password)
        layout.addLayout(formulario)

        # Opciones de conexión (plegables)
        self.grp_conexion = QGroupBox("Opciones de conexión")
        self.grp_conexion.setCheckable(True)
        self.grp_conexion.setChecked(False)
        self._panel_conexion = QWidget()
        QVBoxLayout(self.grp_conexion).addWidget(self._panel_conexion)
        form_con = QFormLayout(self._panel_conexion)
        self.txt_host = QLineEdit(config.host)
        self.spn_puerto = QSpinBox()
        self.spn_puerto.setRange(1, 65535)
        self.spn_puerto.setValue(config.puerto)
        self.txt_base = QLineEdit(config.base)
        form_con.addRow("Servidor:", self.txt_host)
        form_con.addRow("Puerto:", self.spn_puerto)
        form_con.addRow("Base de datos:", self.txt_base)
        self.grp_conexion.toggled.connect(self._mostrar_conexion)
        self._mostrar_conexion(False)
        layout.addWidget(self.grp_conexion)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setObjectName("loginEstado")
        self.lbl_estado.setWordWrap(True)
        self.lbl_estado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_estado)

        botones = QHBoxLayout()
        self.btn_ingresar = QPushButton("Ingresar")
        self.btn_ingresar.setObjectName("primario")
        self.btn_ingresar.setDefault(True)
        self.btn_ingresar.clicked.connect(self._ingresar)
        btn_salir = QPushButton("Salir")
        btn_salir.clicked.connect(self.reject)
        botones.addStretch()
        botones.addWidget(btn_salir)
        botones.addWidget(self.btn_ingresar)
        layout.addLayout(botones)

        self.txt_usuario.setFocus()

    def _mostrar_conexion(self, visible: bool) -> None:
        self._panel_conexion.setVisible(visible)
        self.adjustSize()

    # -- lógica --------------------------------------------------------------
    def _ingresar(self) -> None:
        if self._restante > 0:
            return
        usuario = self.txt_usuario.text().strip()
        password = self.txt_password.text()
        if not usuario or not password:
            self._estado("Escriba su usuario y contraseña.", error=True)
            return

        conexion_cambio = (self.txt_host.text().strip(), self.spn_puerto.value(),
                           self.txt_base.text().strip()) != (config.host, config.puerto, config.base)
        config.host = self.txt_host.text().strip() or config.host
        config.puerto = self.spn_puerto.value()
        config.base = self.txt_base.text().strip() or config.base

        self._estado("Conectando…")
        self.btn_ingresar.setEnabled(False)
        self.repaint()
        try:
            sesion.iniciar(usuario, password)
            SesionDAO().cargar_datos_sesion()
        except ErrorAplicacion as error:
            sesion.cerrar()
            self.btn_ingresar.setEnabled(True)
            self.txt_password.clear()
            if error.sqlstate in ("28P01", "28000"):
                self._intentos += 1
                if self._intentos >= MAX_INTENTOS:
                    self._bloquear()
                    return
                faltan = MAX_INTENTOS - self._intentos
                self._estado(f"{error.mensaje} Le quedan {faltan} intento(s).", error=True)
            else:
                self._estado(error.mensaje, error=True)
            return

        if not sesion.roles and not sesion.es_superusuario:
            sesion.cerrar()
            self.btn_ingresar.setEnabled(True)
            self._estado("La cuenta no tiene ningún rol de la aplicación asignado.", error=True)
            return

        if conexion_cambio:
            guardar_conexion(config)
        self.accept()

    def _bloquear(self) -> None:
        self._restante = SEGUNDOS_BLOQUEO
        for widget in (self.txt_usuario, self.txt_password, self.btn_ingresar):
            widget.setEnabled(False)
        self._cuenta_regresiva()
        self._temporizador.start()

    def _cuenta_regresiva(self) -> None:
        if self._restante <= 0:
            self._temporizador.stop()
            self._intentos = 0
            for widget in (self.txt_usuario, self.txt_password, self.btn_ingresar):
                widget.setEnabled(True)
            self._estado("Puede intentar de nuevo.")
            self.txt_password.setFocus()
            return
        self._estado(f"Demasiados intentos fallidos. Espere {self._restante} segundos.", error=True)
        self._restante -= 1

    def _estado(self, texto: str, error: bool = False) -> None:
        self.lbl_estado.setProperty("error", error)
        self.lbl_estado.style().unpolish(self.lbl_estado)
        self.lbl_estado.style().polish(self.lbl_estado)
        self.lbl_estado.setText(texto)
