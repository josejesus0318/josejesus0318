"""Panel Genérico de Catálogos.

Una sola clase sirve para todos los catálogos simples: a partir del
DescriptorCatalogo construye el formulario, la tabla, la búsqueda y los
botones Nuevo / Guardar / Eliminar. Si el rol no puede editar el
catálogo, el panel queda en modo de solo lectura.
"""

from __future__ import annotations

from datetime import time
from typing import Any

from PyQt6.QtCore import QTime
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QStackedWidget, QTimeEdit, QVBoxLayout, QWidget,
)

from control_acceso.dao.catalogo_dao import CatalogoDAO
from control_acceso.models.catalogos import CATALOGOS, CampoCatalogo, DescriptorCatalogo
from control_acceso.utils.conexion import sesion
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.views.componentes import (
    Columna, TablaDatos, confirmar, formatear, llenar_combo, mostrar_error, seleccionar_combo,
)


def _a_time(valor: Any) -> time:
    if isinstance(valor, time):
        return valor
    horas, minutos, *_ = str(valor).split(":")
    return time(int(horas), int(minutos))


class PanelCatalogo(QWidget):

    def __init__(self, descriptor: DescriptorCatalogo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.d = descriptor
        self.dao = CatalogoDAO(descriptor)
        self.editable = sesion.tiene_rol(*descriptor.roles_editar)
        self._id_actual: Any = None
        self._editores: dict[str, QWidget] = {}
        self._textos_fk: dict[str, dict[Any, str]] = {}
        self._construir()

    # -- interfaz ------------------------------------------------------------
    def _construir(self) -> None:
        layout = QHBoxLayout(self)

        # Izquierda: búsqueda + tabla
        izquierda = QVBoxLayout()
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText(f"Buscar en {self.d.titulo.lower()}…")
        self.txt_buscar.setClearButtonEnabled(True)
        columnas = [Columna(c.columna, c.etiqueta, self._formateador(c)) for c in self.d.campos]
        self.tabla = TablaDatos(columnas)
        self.txt_buscar.textChanged.connect(self.tabla.filtrar)
        self.tabla.selectionModel().selectionChanged.connect(self._al_seleccionar)
        izquierda.addWidget(self.txt_buscar)
        izquierda.addWidget(self.tabla)
        layout.addLayout(izquierda, 3)

        # Derecha: formulario
        grupo = QGroupBox(self.d.titulo if self.editable else f"{self.d.titulo} (solo lectura)")
        form = QFormLayout(grupo)
        for campo in self.d.campos:
            editor = self._crear_editor(campo)
            editor.setEnabled(self.editable)
            self._editores[campo.columna] = editor
            form.addRow(campo.etiqueta + (" *" if campo.requerido and campo.tipo != "booleano" else "") + ":",
                        editor)

        botones = QHBoxLayout()
        self.btn_nuevo = QPushButton("Nuevo")
        self.btn_guardar = QPushButton("Guardar")
        self.btn_guardar.setObjectName("primario")
        self.btn_eliminar = QPushButton("Eliminar")
        self.btn_eliminar.setObjectName("peligro")
        self.btn_nuevo.clicked.connect(self.limpiar)
        self.btn_guardar.clicked.connect(self._guardar)
        self.btn_eliminar.clicked.connect(self._eliminar)
        for boton in (self.btn_nuevo, self.btn_guardar, self.btn_eliminar):
            boton.setVisible(self.editable)
            botones.addWidget(boton)
        form.addRow(botones)
        if not self.editable:
            aviso = QLabel("Su rol puede consultar este catálogo, pero no modificarlo.")
            aviso.setWordWrap(True)
            aviso.setObjectName("aviso")
            form.addRow(aviso)
        layout.addWidget(grupo, 2)

    def _crear_editor(self, campo: CampoCatalogo) -> QWidget:
        if campo.tipo == "entero":
            editor = QSpinBox()
            editor.setRange(campo.minimo, campo.maximo)
            return editor
        if campo.tipo == "hora":
            editor = QTimeEdit()
            editor.setDisplayFormat("HH:mm")
            return editor
        if campo.tipo == "booleano":
            return QCheckBox()
        if campo.tipo in ("fk", "opciones"):
            combo = QComboBox()
            if campo.tipo == "opciones":
                for opcion in campo.opciones:
                    combo.addItem(opcion, opcion)
            return combo
        editor = QLineEdit()
        editor.setMaxLength(campo.longitud)
        return editor

    def _formateador(self, campo: CampoCatalogo):
        if campo.tipo == "fk":
            return lambda valor, c=campo: self._textos_fk.get(c.columna, {}).get(valor, formatear(valor))
        return formatear

    # -- datos ---------------------------------------------------------------
    def cargar(self) -> None:
        try:
            for campo in self.d.campos:
                if campo.tipo == "fk":
                    opciones = self.dao.opciones(campo)
                    self._textos_fk[campo.columna] = {o["id"]: o["texto"] for o in opciones}
                    combo = self._editores[campo.columna]
                    assert isinstance(combo, QComboBox)
                    llenar_combo(combo, opciones, None if campo.requerido else "(ninguno)")
            self.tabla.cargar(self.dao.listar())
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudo cargar el catálogo")
        self.limpiar()

    def limpiar(self) -> None:
        self._id_actual = None
        self.tabla.clearSelection()
        for campo in self.d.campos:
            editor = self._editores[campo.columna]
            if isinstance(editor, QLineEdit):
                editor.clear()
            elif isinstance(editor, QSpinBox):
                editor.setValue(max(campo.minimo, 0))
            elif isinstance(editor, QTimeEdit):
                editor.setTime(QTime(9, 0))
            elif isinstance(editor, QCheckBox):
                editor.setChecked(True)
            elif isinstance(editor, QComboBox):
                editor.setCurrentIndex(0)
            # La clave capturada a mano solo se edita al crear
            if not self.d.pk_autogenerada and campo.columna == self.d.pk:
                editor.setEnabled(self.editable)
        self.btn_eliminar.setEnabled(False)

    def _al_seleccionar(self) -> None:
        fila = self.tabla.seleccionada()
        if fila is None:
            return
        self._id_actual = fila[self.d.pk]
        for campo in self.d.campos:
            editor = self._editores[campo.columna]
            valor = fila.get(campo.columna)
            if isinstance(editor, QLineEdit):
                editor.setText("" if valor is None else str(valor))
            elif isinstance(editor, QSpinBox):
                editor.setValue(int(valor or 0))
            elif isinstance(editor, QTimeEdit):
                hora = _a_time(valor)
                editor.setTime(QTime(hora.hour, hora.minute))
            elif isinstance(editor, QCheckBox):
                editor.setChecked(bool(valor))
            elif isinstance(editor, QComboBox):
                seleccionar_combo(editor, valor)
            if not self.d.pk_autogenerada and campo.columna == self.d.pk:
                editor.setEnabled(False)
        self.btn_eliminar.setEnabled(self.editable)

    def _valores(self) -> dict[str, Any]:
        valores: dict[str, Any] = {}
        for campo in self.d.campos:
            editor = self._editores[campo.columna]
            if isinstance(editor, QLineEdit):
                valor: Any = editor.text().strip() or None
            elif isinstance(editor, QSpinBox):
                valor = editor.value()
            elif isinstance(editor, QTimeEdit):
                t = editor.time()
                valor = time(t.hour(), t.minute())
            elif isinstance(editor, QCheckBox):
                valor = editor.isChecked()
            else:
                assert isinstance(editor, QComboBox)
                valor = editor.currentData()
            if campo.requerido and valor is None:
                raise ErrorAplicacion(f"El campo «{campo.etiqueta}» es obligatorio.")
            valores[campo.columna] = valor
        return valores

    def _guardar(self) -> None:
        try:
            valores = self._valores()
            if self._id_actual is None:
                self.dao.insertar(valores)
            else:
                self.dao.actualizar(self._id_actual, valores)
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()

    def _eliminar(self) -> None:
        if self._id_actual is None:
            return
        if not confirmar(self, "¿Eliminar el registro seleccionado?\n"
                               "Si está en uso por otros datos, la base de datos lo impedirá."):
            return
        try:
            self.dao.eliminar(self._id_actual)
        except ErrorAplicacion as error:
            mostrar_error(self, error)
            return
        self.cargar()


class CatalogosView(QWidget):
    """Selector de catálogos visibles para el rol + su panel genérico."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.descriptores = [d for d in CATALOGOS if sesion.tiene_rol(*d.roles_ver)]
        layout = QVBoxLayout(self)
        fila = QHBoxLayout()
        fila.addWidget(QLabel("Catálogo:"))
        self.cmb_catalogo = QComboBox()
        for d in self.descriptores:
            editable = sesion.tiene_rol(*d.roles_editar)
            self.cmb_catalogo.addItem(d.titulo + ("" if editable else "  (consulta)"), d.clave)
        fila.addWidget(self.cmb_catalogo, 1)
        fila.addStretch(2)
        layout.addLayout(fila)

        self.pila = QStackedWidget()
        self.paneles: list[PanelCatalogo] = []
        for d in self.descriptores:
            panel = PanelCatalogo(d)
            self.paneles.append(panel)
            self.pila.addWidget(panel)
        layout.addWidget(self.pila)
        self.cmb_catalogo.currentIndexChanged.connect(self._cambiar)

    def _cambiar(self, indice: int) -> None:
        if 0 <= indice < len(self.paneles):
            self.pila.setCurrentIndex(indice)
            self.paneles[indice].cargar()

    def refrescar(self) -> None:
        self._cambiar(self.cmb_catalogo.currentIndex())
