"""Pantalla dedicada de Credenciales QR (Seguridad y Recepción).

- Seguridad emite credenciales a colaboradores, cambia su estado y vigencia.
- Recepción consulta credenciales y puede suspender o revocar las de visita
  (las emite desde la pantalla de visitas).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from control_acceso.dao.credencial_dao import CredencialDAO
from control_acceso.models.entidades import Credencial
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.utils.permisos import tiene_capacidad
from control_acceso.views.componentes import (
    Columna, TablaDatos, a_date, a_qdate, llenar_combo, mostrar_error, mostrar_info,
    seleccionar_combo,
)
from control_acceso.views.qr_dialog import QRDialog

COLOR_ESTADO = {"suspendida": "#fff4d6", "revocada": "#f6e3e3", "vencida": "#ececec"}


def _color_credencial(fila: dict[str, Any]) -> QColor | None:
    if fila.get("estado") == "activa" and (fila.get("dias_restantes") or 0) <= 30:
        return QColor("#fff4d6")                     # por vencer
    color = COLOR_ESTADO.get(fila.get("estado", ""))
    return QColor(color) if color else None


def _formato_dias(valor: Any) -> str:
    if valor is None:
        return ""
    return "vencida" if valor < 0 else f"{valor} días"


class EmitirCredencialDialog(QDialog):
    """Emisión de credencial para un colaborador."""

    def __init__(self, colaboradores: list[dict[str, Any]], roles: list[dict[str, Any]],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Emitir credencial a colaborador")
        self.setMinimumWidth(460)
        form = QFormLayout(self)
        self.cmb_colaborador = QComboBox()
        self.cmb_colaborador.setEditable(True)
        self.cmb_colaborador.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        llenar_combo(self.cmb_colaborador, colaboradores, "(seleccione)")
        self.cmb_rol = QComboBox()
        llenar_combo(self.cmb_rol, roles)
        seleccionar_combo(self.cmb_rol, 2)              # Acceso Horario de Oficina
        self.dte_vigencia = QDateEdit(a_qdate(date.today() + timedelta(days=365)))
        self.dte_vigencia.setCalendarPopup(True)
        self.dte_vigencia.setDisplayFormat("dd/MM/yyyy")
        self.dte_vigencia.setMinimumDate(a_qdate(date.today()))
        nota = QLabel("El código QR lo genera la base de datos. Si el colaborador ya tiene una "
                      "credencial activa, primero suspéndala o revóquela.")
        nota.setWordWrap(True)
        nota.setObjectName("aviso")
        form.addRow("Colaborador *:", self.cmb_colaborador)
        form.addRow("Rol de acceso *:", self.cmb_rol)
        form.addRow("Vigente hasta *:", self.dte_vigencia)
        form.addRow(nota)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

    def credencial(self) -> Credencial:
        return Credencial(id_rol_acceso=self.cmb_rol.currentData(),
                          fecha_vigencia=a_date(self.dte_vigencia.date()),
                          id_colaborador=self.cmb_colaborador.currentData())


class CredencialesView(QWidget):

    COLUMNAS = [
        Columna("codigo_qr", "Código QR"),
        Columna("tipo_titular", "Tipo"),
        Columna("titular", "Titular"),
        Columna("rol_acceso", "Rol de acceso"),
        Columna("estado", "Estado", alinear_centro=True),
        Columna("fecha_emision", "Emisión", alinear_centro=True),
        Columna("fecha_vigencia", "Vigencia", alinear_centro=True),
        Columna("dias_restantes", "Restan", _formato_dias, alinear_centro=True),
    ]

    def __init__(self, editable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dao = CredencialDAO()
        self.editable = editable
        self._construir()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        filtros = QHBoxLayout()
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar por titular o código…")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.returnPressed.connect(self.cargar)
        self.cmb_estado = QComboBox()
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItem("Todos los titulares", None)
        self.cmb_tipo.addItem("Colaboradores", "Colaborador")
        self.cmb_tipo.addItem("Visitantes", "Visitante")
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self.cargar)
        self.cmb_estado.currentIndexChanged.connect(self.cargar)
        self.cmb_tipo.currentIndexChanged.connect(self.cargar)
        filtros.addWidget(self.txt_buscar, 1)
        filtros.addWidget(QLabel("Estado:"))
        filtros.addWidget(self.cmb_estado)
        filtros.addWidget(self.cmb_tipo)
        filtros.addWidget(btn_buscar)
        layout.addLayout(filtros)

        self.tabla = TablaDatos(self.COLUMNAS, _color_credencial)
        self.tabla.doubleClicked.connect(self._ver_qr)
        layout.addWidget(self.tabla)
        leyenda = QLabel("Amarillo: suspendida o por vencer (30 días) · Rojo: revocada · Gris: vencida")
        leyenda.setObjectName("aviso")
        layout.addWidget(leyenda)

        acciones = QHBoxLayout()
        self.btn_emitir = QPushButton("Emitir a colaborador…")
        self.btn_emitir.setObjectName("primario")
        self.btn_qr = QPushButton("Ver código QR")
        self.cmb_nuevo_estado = QComboBox()
        self.btn_estado = QPushButton("Aplicar estado")
        self.dte_vigencia = QDateEdit()
        self.dte_vigencia.setCalendarPopup(True)
        self.dte_vigencia.setDisplayFormat("dd/MM/yyyy")
        self.dte_vigencia.setDate(a_qdate(date.today() + timedelta(days=365)))
        self.btn_vigencia = QPushButton("Cambiar vigencia")
        self.btn_emitir.clicked.connect(self._emitir)
        self.btn_qr.clicked.connect(self._ver_qr)
        self.btn_estado.clicked.connect(self._cambiar_estado)
        self.btn_vigencia.clicked.connect(self._cambiar_vigencia)

        self.btn_emitir.setVisible(self.editable and tiene_capacidad("emitir_credencial_colaborador"))
        puede_vigencia = self.editable and tiene_capacidad("cambiar_vigencia_credencial")
        self.dte_vigencia.setVisible(puede_vigencia)
        self.btn_vigencia.setVisible(puede_vigencia)
        self.cmb_nuevo_estado.setVisible(self.editable)
        self.btn_estado.setVisible(self.editable)

        acciones.addWidget(self.btn_emitir)
        acciones.addWidget(self.btn_qr)
        acciones.addStretch()
        acciones.addWidget(self.cmb_nuevo_estado)
        acciones.addWidget(self.btn_estado)
        acciones.addWidget(self.dte_vigencia)
        acciones.addWidget(self.btn_vigencia)
        layout.addLayout(acciones)

    def cargar(self) -> None:
        try:
            if self.cmb_estado.count() == 0:
                estados = self.dao.estados()
                llenar_combo(self.cmb_estado, estados, "Todos los estados")
                llenar_combo(self.cmb_nuevo_estado, [e for e in estados if e["texto"] != "vencida"])
            filas = self.dao.listar(self.txt_buscar.text(), self.cmb_estado.currentData(),
                                    self.cmb_tipo.currentData())
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudieron cargar las credenciales")
            return
        self.tabla.cargar(filas)

    refrescar = cargar

    def _seleccionada(self) -> dict[str, Any] | None:
        fila = self.tabla.seleccionada()
        if fila is None:
            mostrar_info(self, "Seleccione una credencial de la lista.", "Credenciales")
        return fila

    def _emitir(self) -> None:
        try:
            dialogo = EmitirCredencialDialog(self.dao.colaboradores(), self.dao.roles_acceso(), self)
            if not dialogo.exec():
                return
            nueva = self.dao.emitir(dialogo.credencial())
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()
        QRDialog(nueva["codigo_qr"], dialogo.cmb_colaborador.currentText(),
                 f"Vigente hasta el {dialogo.credencial().fecha_vigencia:%d/%m/%Y}", self).exec()

    def _ver_qr(self) -> None:
        fila = self._seleccionada()
        if fila is None:
            return
        QRDialog(fila["codigo_qr"], fila["titular"],
                 f"{fila['rol_acceso']} · vigente hasta el {fila['fecha_vigencia']:%d/%m/%Y}", self).exec()

    def _cambiar_estado(self) -> None:
        fila = self._seleccionada()
        if fila is None:
            return
        try:
            self.dao.cambiar_estado(fila["id_credencial"], self.cmb_nuevo_estado.currentData())
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()

    def _cambiar_vigencia(self) -> None:
        fila = self._seleccionada()
        if fila is None:
            return
        try:
            self.dao.cambiar_vigencia(fila["id_credencial"], a_date(self.dte_vigencia.date()))
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()
