"""Módulo de administración de usuarios (solo administrador).

La creación de cuentas pide de nuevo credenciales de administrador, abre
una conexión temporal y ejecuta la función sp_crear_usuario
(SECURITY DEFINER). La aplicación nunca guarda contraseñas.
"""

from __future__ import annotations

import re
from typing import Any

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from control_acceso.dao.usuario_dao import ROLES_DISPONIBLES, UsuarioDAO
from control_acceso.models.entidades import UsuarioSistema
from control_acceso.utils.conexion import conexion_temporal, sesion
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.views.componentes import (
    Columna, TablaDatos, confirmar, llenar_combo, mostrar_error, mostrar_info,
)

PATRON_CUENTA = re.compile(r"^[a-z][a-z0-9_]{2,30}$")


def validar_password(password: str, confirmacion: str) -> None:
    if password != confirmacion:
        raise ErrorAplicacion("Las contraseñas no coinciden.")
    if (len(password) < 8 or not re.search(r"[A-Z]", password)
            or not re.search(r"[a-z]", password) or not re.search(r"[0-9]", password)):
        raise ErrorAplicacion("La contraseña debe tener al menos 8 caracteres, con mayúsculas, "
                              "minúsculas y números.")


class CrearUsuarioDialog(QDialog):
    """Diálogo modal: datos de la nueva cuenta + credenciales del administrador."""

    def __init__(self, colaboradores: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Crear usuario")
        self.setMinimumWidth(480)
        self.id_creado: int | None = None
        layout = QVBoxLayout(self)

        datos = QGroupBox("Nueva cuenta")
        form = QFormLayout(datos)
        self.txt_cuenta = QLineEdit()
        self.txt_cuenta.setPlaceholderText("minúsculas, números y _  (p. ej. recep_maria)")
        self.txt_cuenta.setMaxLength(31)
        self.txt_password = QLineEdit(); self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_confirmar = QLineEdit(); self.txt_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        self.cmb_rol = QComboBox()
        for clave, texto in ROLES_DISPONIBLES:
            self.cmb_rol.addItem(texto, clave)
        self.cmb_colaborador = QComboBox()
        llenar_combo(self.cmb_colaborador, colaboradores, "(ninguno – cuenta de servicio)")
        form.addRow("Cuenta *:", self.txt_cuenta)
        form.addRow("Contraseña *:", self.txt_password)
        form.addRow("Confirmar *:", self.txt_confirmar)
        form.addRow("Rol *:", self.cmb_rol)
        form.addRow("Colaborador:", self.cmb_colaborador)
        layout.addWidget(datos)

        admin = QGroupBox("Autorización del administrador")
        form_admin = QFormLayout(admin)
        self.txt_admin = QLineEdit(sesion.usuario)
        self.txt_admin_pwd = QLineEdit(); self.txt_admin_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        form_admin.addRow("Administrador:", self.txt_admin)
        form_admin.addRow("Contraseña:", self.txt_admin_pwd)
        nota = QLabel("Se abrirá una conexión temporal con estas credenciales solo para crear la cuenta.")
        nota.setWordWrap(True)
        nota.setObjectName("aviso")
        form_admin.addRow(nota)
        layout.addWidget(admin)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Crear usuario")
        botones.accepted.connect(self._crear)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def _crear(self) -> None:
        cuenta = self.txt_cuenta.text().strip().lower()
        try:
            if not PATRON_CUENTA.match(cuenta):
                raise ErrorAplicacion("La cuenta debe tener de 3 a 31 caracteres: letras minúsculas, "
                                      "números o guion bajo, y empezar con letra.")
            validar_password(self.txt_password.text(), self.txt_confirmar.text())
            if not self.txt_admin_pwd.text():
                raise ErrorAplicacion("Escriba la contraseña del administrador para autorizar.")
            usuario = UsuarioSistema(cuenta, self.cmb_rol.currentData(), self.cmb_colaborador.currentData())
            with conexion_temporal(self.txt_admin.text(), self.txt_admin_pwd.text()) as con:
                self.id_creado = UsuarioDAO.crear(con, usuario, self.txt_password.text())
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se creó el usuario")
            return
        finally:
            self.txt_admin_pwd.clear()
        self.accept()


class PasswordDialog(QDialog):
    def __init__(self, cuenta: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Restablecer contraseña – {cuenta}")
        form = QFormLayout(self)
        self.txt_password = QLineEdit(); self.txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_confirmar = QLineEdit(); self.txt_confirmar.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Nueva contraseña:", self.txt_password)
        form.addRow("Confirmar:", self.txt_confirmar)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)


class UsuariosView(QWidget):

    COLUMNAS = [
        Columna("cuenta", "Cuenta"),
        Columna("rol_aplicacion", "Rol"),
        Columna("colaborador", "Colaborador"),
        Columna("activo", "Activa", alinear_centro=True),
        Columna("puede_conectarse", "Puede conectarse", alinear_centro=True),
        Columna("fecha_alta", "Alta"),
        Columna("creado_por", "Creada por"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dao = UsuarioDAO()
        layout = QVBoxLayout(self)
        aviso = QLabel("Las contraseñas las guarda PostgreSQL cifradas con SCRAM-SHA-256; "
                       "esta aplicación no las almacena.")
        aviso.setObjectName("aviso")
        layout.addWidget(aviso)
        self.tabla = TablaDatos(self.COLUMNAS,
                                lambda f: None if f.get("activo") else QColor("#f6e3e3"))
        layout.addWidget(self.tabla)
        botones = QHBoxLayout()
        btn_crear = QPushButton("Crear usuario…"); btn_crear.setObjectName("primario")
        btn_activar = QPushButton("Habilitar")
        btn_desactivar = QPushButton("Deshabilitar"); btn_desactivar.setObjectName("peligro")
        btn_password = QPushButton("Restablecer contraseña…")
        btn_crear.clicked.connect(self._crear)
        btn_activar.clicked.connect(lambda: self._cambiar_estado(True))
        btn_desactivar.clicked.connect(lambda: self._cambiar_estado(False))
        btn_password.clicked.connect(self._restablecer)
        botones.addWidget(btn_crear)
        botones.addStretch()
        botones.addWidget(btn_activar)
        botones.addWidget(btn_desactivar)
        botones.addWidget(btn_password)
        layout.addLayout(botones)

    def cargar(self) -> None:
        try:
            self.tabla.cargar(self.dao.listar())
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudieron cargar los usuarios")

    refrescar = cargar

    def _seleccionada(self) -> dict[str, Any] | None:
        fila = self.tabla.seleccionada()
        if fila is None:
            mostrar_info(self, "Seleccione una cuenta de la lista.", "Usuarios")
        return fila

    def _crear(self) -> None:
        try:
            colaboradores = self.dao.colaboradores_sin_cuenta()
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        dialogo = CrearUsuarioDialog(colaboradores, self)
        if dialogo.exec():
            mostrar_info(self, f"Cuenta «{dialogo.txt_cuenta.text().strip().lower()}» creada correctamente.")
            self.cargar()

    def _cambiar_estado(self, activo: bool) -> None:
        fila = self._seleccionada()
        if fila is None:
            return
        accion = "habilitar" if activo else "deshabilitar"
        if not confirmar(self, f"¿{accion.capitalize()} la cuenta «{fila['cuenta']}»?"):
            return
        try:
            self.dao.cambiar_estado(fila["cuenta"], activo)
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()

    def _restablecer(self) -> None:
        fila = self._seleccionada()
        if fila is None:
            return
        dialogo = PasswordDialog(fila["cuenta"], self)
        if not dialogo.exec():
            return
        try:
            validar_password(dialogo.txt_password.text(), dialogo.txt_confirmar.text())
            self.dao.restablecer_password(fila["cuenta"], dialogo.txt_password.text())
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        mostrar_info(self, f"Contraseña de «{fila['cuenta']}» actualizada.")
