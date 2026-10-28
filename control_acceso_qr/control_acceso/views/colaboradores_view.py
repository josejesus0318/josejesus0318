"""Pantalla dedicada de Colaboradores (Recursos Humanos).

Alta, edición, baja lógica (activo = FALSE con fecha) y reactivación.
Al dar de baja, un trigger de la base de datos revoca sus credenciales.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from control_acceso.dao.colaborador_dao import ColaboradorDAO
from control_acceso.models.entidades import Colaborador
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.views.componentes import (
    Columna, TablaDatos, a_date, a_qdate, confirmar, llenar_combo, mostrar_error, mostrar_info,
    seleccionar_combo,
)


def _color_baja(fila: dict[str, Any]) -> QColor | None:
    return QColor("#f3e5ea") if not fila.get("activo") else None


class ColaboradoresView(QWidget):

    COLUMNAS = [
        Columna("numero_empleado", "No. empleado"),
        Columna("nombre_completo", "Nombre"),
        Columna("tipo_colaborador", "Tipo"),
        Columna("puesto", "Puesto"),
        Columna("departamento", "Departamento"),
        Columna("nombre_turno", "Turno"),
        Columna("telefono", "Teléfono"),
        Columna("correo", "Correo"),
        Columna("fecha_ingreso", "Ingreso", alinear_centro=True),
        Columna("activo", "Activo", alinear_centro=True),
        Columna("fecha_baja", "Baja", alinear_centro=True),
    ]

    def __init__(self, editable: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dao = ColaboradorDAO()
        self.editable = editable
        self._id_actual: int | None = None
        self._construir()

    def _construir(self) -> None:
        layout = QHBoxLayout(self)

        izquierda = QVBoxLayout()
        filtros = QHBoxLayout()
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Buscar por nombre, número o departamento…")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.returnPressed.connect(self.cargar)
        self.chk_bajas = QCheckBox("Incluir dados de baja")
        self.chk_bajas.toggled.connect(self.cargar)
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self.cargar)
        filtros.addWidget(self.txt_buscar, 1)
        filtros.addWidget(self.chk_bajas)
        filtros.addWidget(btn_buscar)
        self.tabla = TablaDatos(self.COLUMNAS, _color_baja)
        self.tabla.selectionModel().selectionChanged.connect(self._al_seleccionar)
        self.lbl_total = QLabel()
        izquierda.addLayout(filtros)
        izquierda.addWidget(self.tabla)
        izquierda.addWidget(self.lbl_total)
        layout.addLayout(izquierda, 3)

        grupo = QGroupBox("Datos del colaborador")
        form = QFormLayout(grupo)
        self.txt_numero = QLineEdit(); self.txt_numero.setMaxLength(15)
        self.txt_nombre = QLineEdit(); self.txt_nombre.setMaxLength(60)
        self.txt_paterno = QLineEdit(); self.txt_paterno.setMaxLength(60)
        self.txt_materno = QLineEdit(); self.txt_materno.setMaxLength(60)
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItem("Empleado", "empleado")
        self.cmb_tipo.addItem("Contratista", "contratista")
        self.cmb_puesto = QComboBox()
        self.cmb_horario = QComboBox()
        self.txt_telefono = QLineEdit(); self.txt_telefono.setMaxLength(15)
        self.txt_telefono.setInputMask("9999999999")
        self.txt_correo = QLineEdit(); self.txt_correo.setMaxLength(100)
        self.dte_ingreso = QDateEdit(); self.dte_ingreso.setCalendarPopup(True)
        self.dte_ingreso.setDisplayFormat("dd/MM/yyyy")
        self.lbl_estado = QLabel()

        form.addRow("No. empleado *:", self.txt_numero)
        form.addRow("Nombre(s) *:", self.txt_nombre)
        form.addRow("Apellido paterno *:", self.txt_paterno)
        form.addRow("Apellido materno:", self.txt_materno)
        form.addRow("Tipo *:", self.cmb_tipo)
        form.addRow("Puesto *:", self.cmb_puesto)
        form.addRow("Turno *:", self.cmb_horario)
        form.addRow("Teléfono *:", self.txt_telefono)
        form.addRow("Correo *:", self.txt_correo)
        form.addRow("Fecha de ingreso *:", self.dte_ingreso)
        form.addRow("Estado:", self.lbl_estado)

        botones = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo")
        self.btn_guardar = QPushButton("Guardar"); self.btn_guardar.setObjectName("primario")
        self.btn_baja = QPushButton("Dar de baja"); self.btn_baja.setObjectName("peligro")
        self.btn_reactivar = QPushButton("Reactivar")
        self.btn_nuevo.clicked.connect(self.limpiar)
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_baja.clicked.connect(self._dar_de_baja)
        self.btn_reactivar.clicked.connect(self._reactivar)
        for boton in (self.btn_nuevo, self.btn_guardar, self.btn_baja, self.btn_reactivar):
            botones.addWidget(boton)
            boton.setVisible(self.editable)
        form.addRow(botones)
        grupo.setEnabled(True)
        for editor in (self.txt_numero, self.txt_nombre, self.txt_paterno, self.txt_materno,
                       self.cmb_tipo, self.cmb_puesto, self.cmb_horario, self.txt_telefono,
                       self.txt_correo, self.dte_ingreso):
            editor.setEnabled(self.editable)
        layout.addWidget(grupo, 2)

    # -- datos ---------------------------------------------------------------
    def cargar(self) -> None:
        try:
            if self.cmb_puesto.count() == 0:
                llenar_combo(self.cmb_puesto, self.dao.puestos(), "(seleccione)")
                llenar_combo(self.cmb_horario, self.dao.horarios(), "(seleccione)")
            filas = self.dao.listar(self.txt_buscar.text(), self.chk_bajas.isChecked())
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudo cargar la lista")
            return
        self.tabla.cargar(filas)
        self.lbl_total.setText(f"{len(filas)} colaborador(es)")
        self.limpiar()

    refrescar = cargar

    def limpiar(self) -> None:
        self._id_actual = None
        self.tabla.clearSelection()
        for editor in (self.txt_numero, self.txt_nombre, self.txt_paterno, self.txt_materno,
                       self.txt_telefono, self.txt_correo):
            editor.clear()
        self.cmb_tipo.setCurrentIndex(0)
        self.cmb_puesto.setCurrentIndex(0)
        self.cmb_horario.setCurrentIndex(0)
        self.dte_ingreso.setDate(a_qdate(date.today()))
        self.lbl_estado.setText("Nuevo registro")
        self.btn_baja.setEnabled(False)
        self.btn_reactivar.setEnabled(False)

    def _al_seleccionar(self) -> None:
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        self._id_actual = fila["id_colaborador"]
        self.txt_numero.setText(fila["numero_empleado"])
        self.txt_nombre.setText(fila["nombre"])
        self.txt_paterno.setText(fila["apellido_paterno"])
        self.txt_materno.setText(fila.get("apellido_materno") or "")
        seleccionar_combo(self.cmb_tipo, fila["tipo_colaborador"])
        seleccionar_combo(self.cmb_puesto, fila["id_puesto"])
        seleccionar_combo(self.cmb_horario, fila["id_horario"])
        self.txt_telefono.setText(str(fila["telefono"]))
        self.txt_correo.setText(fila["correo"])
        self.dte_ingreso.setDate(a_qdate(fila["fecha_ingreso"]))
        activo = bool(fila["activo"])
        self.lbl_estado.setText("Activo" if activo else f"Dado de baja el {fila['fecha_baja']:%d/%m/%Y}")
        self.btn_baja.setEnabled(activo)
        self.btn_reactivar.setEnabled(not activo)

    def _leer_formulario(self) -> Colaborador:
        return Colaborador(
            numero_empleado=self.txt_numero.text(),
            nombre=self.txt_nombre.text(),
            apellido_paterno=self.txt_paterno.text(),
            apellido_materno=self.txt_materno.text(),
            tipo_colaborador=self.cmb_tipo.currentData(),
            id_puesto=self.cmb_puesto.currentData(),
            id_horario=self.cmb_horario.currentData(),
            telefono=self.txt_telefono.text(),
            correo=self.txt_correo.text(),
            fecha_ingreso=a_date(self.dte_ingreso.date()),
            id_colaborador=self._id_actual,
        )

    def _guardar(self) -> None:
        try:
            colaborador = self._leer_formulario()
            if self._id_actual is None:
                self.dao.insertar(colaborador)
                mensaje = "Colaborador registrado."
            else:
                self.dao.actualizar(colaborador)
                mensaje = "Cambios guardados."
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        mostrar_info(self, mensaje)
        self.cargar()

    def _dar_de_baja(self) -> None:
        if self._id_actual is None:
            return
        dialogo = QDialog(self)
        dialogo.setWindowTitle("Baja de colaborador")
        form = QFormLayout(dialogo)
        texto = QLabel(f"Se dará de baja a <b>{self.txt_nombre.text()} {self.txt_paterno.text()}</b>.<br>"
                       "Sus credenciales activas se revocarán automáticamente.")
        texto.setWordWrap(True)
        fecha = QDateEdit(a_qdate(date.today()))
        fecha.setCalendarPopup(True)
        fecha.setDisplayFormat("dd/MM/yyyy")
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(dialogo.accept)
        botones.rejected.connect(dialogo.reject)
        form.addRow(texto)
        form.addRow("Fecha de baja:", fecha)
        form.addRow(botones)
        if not dialogo.exec():
            return
        try:
            self.dao.dar_de_baja(self._id_actual, a_date(fecha.date()))
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()

    def _reactivar(self) -> None:
        if self._id_actual is None or not confirmar(
                self, "¿Reactivar al colaborador?\nDeberá emitírsele una credencial nueva."):
            return
        try:
            self.dao.reactivar(self._id_actual)
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()
