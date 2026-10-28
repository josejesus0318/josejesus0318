"""Pantalla dedicada de Visitantes y Visitas (Recepción).

Arriba: el registro de visitantes (cada persona se captura una sola vez).
Abajo: las visitas del visitante seleccionado, o todas las de hoy.
Desde aquí se programa una visita, se emite su credencial temporal y se
muestra su código QR.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QRadioButton, QSplitter, QVBoxLayout, QWidget,
)

from control_acceso.dao.credencial_dao import CredencialDAO
from control_acceso.dao.visita_dao import VisitaDAO
from control_acceso.models.entidades import Visita, Visitante
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.views.componentes import (
    Columna, TablaDatos, a_date, a_qdate, confirmar, llenar_combo, mostrar_error, mostrar_info,
    seleccionar_combo, titulo_seccion,
)
from control_acceso.views.qr_dialog import QRDialog

COLORES_ESTADO = {"cancelada": "#f6e3e3", "realizada": "#e6f2e8"}


def _color_visita(fila: dict[str, Any]) -> QColor | None:
    color = COLORES_ESTADO.get(fila.get("estado", ""))
    return QColor(color) if color else None


class NuevaVisitaDialog(QDialog):

    def __init__(self, visitante: str, anfitriones: list[dict[str, Any]],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Programar visita")
        self.setMinimumWidth(460)
        form = QFormLayout(self)
        form.addRow("Visitante:", QLabel(f"<b>{visitante}</b>"))
        self.cmb_anfitrion = QComboBox()
        self.cmb_anfitrion.setEditable(True)            # permite escribir para buscar
        self.cmb_anfitrion.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        llenar_combo(self.cmb_anfitrion, anfitriones, "(seleccione)")
        self.dte_fecha = QDateEdit(a_qdate(date.today()))
        self.dte_fecha.setCalendarPopup(True)
        self.dte_fecha.setDisplayFormat("dd/MM/yyyy")
        self.dte_fecha.setMinimumDate(a_qdate(date.today()))
        self.txt_motivo = QLineEdit()
        self.txt_motivo.setMaxLength(150)
        form.addRow("Anfitrión *:", self.cmb_anfitrion)
        form.addRow("Fecha *:", self.dte_fecha)
        form.addRow("Motivo *:", self.txt_motivo)
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        form.addRow(botones)

    def visita(self, id_visitante: int) -> Visita:
        return Visita(id_visitante, self.cmb_anfitrion.currentData(),
                      a_date(self.dte_fecha.date()), self.txt_motivo.text())


class VisitasView(QWidget):

    COL_VISITANTES = [
        Columna("nombre_completo", "Visitante"),
        Columna("tipo_identificacion", "Identificación"),
        Columna("numero_identificacion", "Número"),
        Columna("empresa", "Empresa"),
        Columna("telefono", "Teléfono"),
        Columna("total_visitas", "Visitas", alinear_centro=True),
    ]
    COL_VISITAS = [
        Columna("fecha_visita", "Fecha", alinear_centro=True),
        Columna("visitante", "Visitante"),
        Columna("anfitrion", "Anfitrión"),
        Columna("area_visitada", "Área"),
        Columna("ubicacion", "Ubicación"),
        Columna("motivo", "Motivo"),
        Columna("estado", "Estado", alinear_centro=True),
        Columna("codigo_qr", "Credencial"),
    ]

    def __init__(self, editable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dao = VisitaDAO()
        self.dao_cred = CredencialDAO()
        self.editable = editable
        self._id_visitante: int | None = None
        self._construir()

    def _construir(self) -> None:
        layout = QVBoxLayout(self)
        divisor = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(divisor)

        # --- Visitantes -------------------------------------------------------
        superior = QWidget()
        sup = QHBoxLayout(superior)
        izq = QVBoxLayout()
        izq.addWidget(titulo_seccion("Visitantes"))
        busqueda = QHBoxLayout()
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar por nombre, identificación o empresa…")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.returnPressed.connect(self.cargar)
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self.cargar)
        busqueda.addWidget(self.txt_buscar, 1)
        busqueda.addWidget(btn_buscar)
        self.tbl_visitantes = TablaDatos(self.COL_VISITANTES)
        self.tbl_visitantes.selectionModel().selectionChanged.connect(self._al_seleccionar_visitante)
        izq.addLayout(busqueda)
        izq.addWidget(self.tbl_visitantes)
        sup.addLayout(izq, 3)

        grupo = QGroupBox("Datos del visitante")
        form = QFormLayout(grupo)
        self.txt_nombre = QLineEdit(); self.txt_nombre.setMaxLength(60)
        self.txt_paterno = QLineEdit(); self.txt_paterno.setMaxLength(60)
        self.txt_materno = QLineEdit(); self.txt_materno.setMaxLength(60)
        self.cmb_tipo_id = QComboBox()
        self.txt_num_id = QLineEdit(); self.txt_num_id.setMaxLength(25)
        self.cmb_empresa = QComboBox()
        self.txt_telefono = QLineEdit(); self.txt_telefono.setMaxLength(15)
        form.addRow("Nombre(s) *:", self.txt_nombre)
        form.addRow("Apellido paterno *:", self.txt_paterno)
        form.addRow("Apellido materno:", self.txt_materno)
        form.addRow("Identificación *:", self.cmb_tipo_id)
        form.addRow("Número *:", self.txt_num_id)
        form.addRow("Empresa:", self.cmb_empresa)
        form.addRow("Teléfono:", self.txt_telefono)
        botones = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo")
        self.btn_guardar = QPushButton("Guardar"); self.btn_guardar.setObjectName("primario")
        self.btn_nuevo.clicked.connect(self.limpiar)
        self.btn_guardar.clicked.connect(self._guardar_visitante)
        botones.addWidget(self.btn_nuevo)
        botones.addWidget(self.btn_guardar)
        form.addRow(botones)
        grupo.setEnabled(self.editable)
        sup.addWidget(grupo, 2)
        divisor.addWidget(superior)

        # --- Visitas ----------------------------------------------------------
        inferior = QWidget()
        inf = QVBoxLayout(inferior)
        cabecera = QHBoxLayout()
        cabecera.addWidget(titulo_seccion("Visitas"))
        self.rad_visitante = QRadioButton("Del visitante seleccionado")
        self.rad_hoy = QRadioButton("Todas las de hoy")
        self.rad_hoy.setChecked(True)
        self.rad_visitante.toggled.connect(self._cargar_visitas)
        cabecera.addStretch()
        cabecera.addWidget(self.rad_visitante)
        cabecera.addWidget(self.rad_hoy)
        inf.addLayout(cabecera)
        self.tbl_visitas = TablaDatos(self.COL_VISITAS, _color_visita)
        inf.addWidget(self.tbl_visitas)

        acciones = QHBoxLayout()
        self.btn_programar = QPushButton("Programar visita…")
        self.btn_programar.setObjectName("primario")
        self.btn_credencial = QPushButton("Emitir credencial")
        self.btn_ver_qr = QPushButton("Ver código QR")
        self.btn_cancelar = QPushButton("Cancelar visita")
        self.btn_cancelar.setObjectName("peligro")
        self.btn_programar.clicked.connect(self._programar)
        self.btn_credencial.clicked.connect(self._emitir_credencial)
        self.btn_ver_qr.clicked.connect(self._ver_qr)
        self.btn_cancelar.clicked.connect(self._cancelar)
        for boton in (self.btn_programar, self.btn_credencial, self.btn_cancelar):
            boton.setVisible(self.editable)
        acciones.addWidget(self.btn_programar)
        acciones.addWidget(self.btn_credencial)
        acciones.addWidget(self.btn_ver_qr)
        acciones.addStretch()
        acciones.addWidget(self.btn_cancelar)
        inf.addLayout(acciones)
        divisor.addWidget(inferior)
        divisor.setSizes([380, 320])

    # -- carga -----------------------------------------------------------------
    def cargar(self) -> None:
        try:
            if self.cmb_tipo_id.count() == 0:
                llenar_combo(self.cmb_tipo_id, self.dao.tipos_identificacion(), "(seleccione)")
            llenar_combo(self.cmb_empresa, self.dao.empresas(), "Particular (sin empresa)")
            self.tbl_visitantes.cargar(self.dao.listar_visitantes(self.txt_buscar.text()))
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudieron cargar los visitantes")
            return
        self.limpiar()
        self._cargar_visitas()

    refrescar = cargar

    def _cargar_visitas(self) -> None:
        try:
            if self.rad_visitante.isChecked():
                filas = self.dao.listar_visitas(id_visitante=self._id_visitante) if self._id_visitante else []
            else:
                filas = self.dao.listar_visitas(fecha=date.today())
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudieron cargar las visitas")
            return
        self.tbl_visitas.cargar(filas)

    def limpiar(self) -> None:
        self._id_visitante = None
        self.tbl_visitantes.clearSelection()
        for editor in (self.txt_nombre, self.txt_paterno, self.txt_materno, self.txt_num_id,
                       self.txt_telefono):
            editor.clear()
        self.cmb_tipo_id.setCurrentIndex(0)
        self.cmb_empresa.setCurrentIndex(0)
        self.btn_programar.setEnabled(False)

    def _al_seleccionar_visitante(self) -> None:
        fila = self.tbl_visitantes.seleccionada()
        if fila is None:
            return
        self._id_visitante = fila["id_visitante"]
        self.txt_nombre.setText(fila["nombre"])
        self.txt_paterno.setText(fila["apellido_paterno"])
        self.txt_materno.setText(fila.get("apellido_materno") or "")
        seleccionar_combo(self.cmb_tipo_id, fila["id_tipo_identificacion"])
        self.txt_num_id.setText(str(fila["numero_identificacion"]))
        seleccionar_combo(self.cmb_empresa, fila.get("id_empresa"))
        self.txt_telefono.setText(str(fila.get("telefono") or ""))
        self.btn_programar.setEnabled(True)
        self.rad_visitante.setChecked(True)
        self._cargar_visitas()

    # -- acciones ----------------------------------------------------------------
    def _guardar_visitante(self) -> None:
        visitante = Visitante(
            nombre=self.txt_nombre.text(), apellido_paterno=self.txt_paterno.text(),
            apellido_materno=self.txt_materno.text(),
            id_tipo_identificacion=self.cmb_tipo_id.currentData(),
            numero_identificacion=self.txt_num_id.text(),
            id_empresa=self.cmb_empresa.currentData(), telefono=self.txt_telefono.text(),
            id_visitante=self._id_visitante,
        )
        try:
            if self._id_visitante is None:
                self.dao.insertar_visitante(visitante)
            else:
                self.dao.actualizar_visitante(visitante)
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        # Deja seleccionado al visitante recién guardado
        self.txt_buscar.setText(visitante.numero_identificacion.strip())
        self.cargar()
        self.tbl_visitantes.selectRow(0)
        mostrar_info(self, "Visitante guardado. Ahora puede programar su visita.")

    def _programar(self) -> None:
        fila = self.tbl_visitantes.seleccionada()
        if fila is None:
            mostrar_info(self, "Seleccione primero un visitante.", "Programar visita")
            return
        try:
            dialogo = NuevaVisitaDialog(fila["nombre_completo"], self.dao.anfitriones(), self)
            if not dialogo.exec():
                return
            self.dao.programar_visita(dialogo.visita(fila["id_visitante"]))
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self._cargar_visitas()

    def _visita_seleccionada(self) -> dict[str, Any] | None:
        fila = self.tbl_visitas.seleccionada()
        if fila is None:
            mostrar_info(self, "Seleccione una visita de la lista.", "Visitas")
        return fila

    def _emitir_credencial(self) -> None:
        visita = self._visita_seleccionada()
        if visita is None:
            return
        try:
            credencial = self.dao_cred.emitir_para_visita(visita["id_visita"])
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self._cargar_visitas()
        QRDialog(credencial["codigo_qr"], visita["visitante"],
                 f"Visita del {visita['fecha_visita']:%d/%m/%Y} – {visita['area_visitada']}", self).exec()

    def _ver_qr(self) -> None:
        visita = self._visita_seleccionada()
        if visita is None:
            return
        if not visita.get("codigo_qr"):
            mostrar_info(self, "Esta visita aún no tiene credencial. Use «Emitir credencial».", "Código QR")
            return
        QRDialog(visita["codigo_qr"], visita["visitante"],
                 f"Visita del {visita['fecha_visita']:%d/%m/%Y} – {visita['area_visitada']}", self).exec()

    def _cancelar(self) -> None:
        visita = self._visita_seleccionada()
        if visita is None:
            return
        if visita["estado"] != "programada":
            mostrar_info(self, "Solo se pueden cancelar visitas programadas.", "Cancelar visita")
            return
        if not confirmar(self, f"¿Cancelar la visita de {visita['visitante']}?\n"
                               "Su credencial activa quedará revocada."):
            return
        try:
            self.dao.cancelar_visita(visita["id_visita"])
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self._cargar_visitas()
