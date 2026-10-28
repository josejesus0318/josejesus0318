"""Componentes reutilizables de la interfaz: modelo de tabla, mensajes,
listas desplegables y tarjetas de indicadores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Callable, Sequence

from PyQt6.QtCore import QAbstractTableModel, QDate, QModelIndex, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHeaderView, QLabel, QMessageBox, QTableView,
    QVBoxLayout, QWidget,
)

from control_acceso.utils.errores import ErrorAplicacion, traducir_error

# ---------------------------------------------------------------------------
# Formato de valores
# ---------------------------------------------------------------------------


def formatear(valor: Any) -> str:
    """Convierte un valor de la base de datos en texto para mostrar."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, time):
        return valor.strftime("%H:%M")
    return str(valor)


def a_qdate(valor: date | None) -> QDate:
    valor = valor or date.today()
    return QDate(valor.year, valor.month, valor.day)


def a_date(qfecha: QDate) -> date:
    return date(qfecha.year(), qfecha.month(), qfecha.day())


# ---------------------------------------------------------------------------
# Modelo de tabla genérico
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Columna:
    clave: str
    titulo: str
    formato: Callable[[Any], str] = formatear
    alinear_centro: bool = False


class TablaModelo(QAbstractTableModel):
    """Modelo de solo lectura que muestra una lista de diccionarios."""

    def __init__(self, columnas: Sequence[Columna],
                 colorear: Callable[[dict[str, Any]], QColor | None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.columnas = list(columnas)
        self.filas: list[dict[str, Any]] = []
        self._colorear = colorear

    # -- datos -------------------------------------------------------------
    def cargar(self, filas: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self.filas = filas
        self.endResetModel()

    def fila(self, indice: int) -> dict[str, Any]:
        return self.filas[indice]

    # -- interfaz de Qt ------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.filas)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.columnas)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        fila = self.filas[index.row()]
        columna = self.columnas[index.column()]
        valor = fila.get(columna.clave)
        if role == Qt.ItemDataRole.DisplayRole:
            return columna.formato(valor)
        if role == Qt.ItemDataRole.UserRole:          # valor para ordenar
            if valor is None:
                return ""
            if isinstance(valor, (date, datetime, time)):
                return valor.isoformat()
            return valor
        if role == Qt.ItemDataRole.TextAlignmentRole and columna.alinear_centro:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.BackgroundRole and self._colorear:
            return self._colorear(fila)
        return None

    def headerData(self, section: int, orientation: Qt.Orientation,  # noqa: N802
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self.columnas[section].titulo
        return None


class TablaDatos(QTableView):
    """QTableView con ordenamiento, filtro de texto y selección por fila."""

    def __init__(self, columnas: Sequence[Columna],
                 colorear: Callable[[dict[str, Any]], QColor | None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.modelo = TablaModelo(columnas, colorear, self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.modelo)
        self.proxy.setSortRole(Qt.ItemDataRole.UserRole)
        self.proxy.setFilterKeyColumn(-1)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setModel(self.proxy)
        self.setSortingEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        cabecera = self.horizontalHeader()
        cabecera.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecera.setStretchLastSection(True)

    def cargar(self, filas: list[dict[str, Any]]) -> None:
        self.modelo.cargar(filas)
        self.resizeColumnsToContents()

    def filtrar(self, texto: str) -> None:
        self.proxy.setFilterFixedString(texto)

    def seleccionada(self) -> dict[str, Any] | None:
        indices = self.selectionModel().selectedRows()
        if not indices:
            return None
        return self.modelo.fila(self.proxy.mapToSource(indices[0]).row())


# ---------------------------------------------------------------------------
# Listas desplegables
# ---------------------------------------------------------------------------


def llenar_combo(combo: QComboBox, opciones: list[dict[str, Any]], vacio: str | None = None) -> None:
    """Llena un QComboBox con filas {'id', 'texto'}; el id queda como dato."""
    actual = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    if vacio is not None:
        combo.addItem(vacio, None)
    for opcion in opciones:
        combo.addItem(str(opcion["texto"]), opcion["id"])
    combo.blockSignals(False)
    if actual is not None:
        seleccionar_combo(combo, actual)


def seleccionar_combo(combo: QComboBox, valor: Any) -> None:
    indice = combo.findData(valor)
    combo.setCurrentIndex(indice if indice >= 0 else 0)


# ---------------------------------------------------------------------------
# Mensajes
# ---------------------------------------------------------------------------


def mostrar_error(parent: QWidget | None, exc: BaseException, titulo: str = "No se pudo completar") -> None:
    """Muestra un error comprensible; el detalle técnico va en «Mostrar detalles»."""
    error = exc if isinstance(exc, ErrorAplicacion) else traducir_error(exc)
    caja = QMessageBox(parent)
    caja.setIcon(QMessageBox.Icon.Warning)
    caja.setWindowTitle(titulo)
    caja.setText(error.mensaje)
    if error.detalle:
        caja.setDetailedText(error.detalle)
    caja.exec()


def mostrar_info(parent: QWidget, texto: str, titulo: str = "Listo") -> None:
    QMessageBox.information(parent, titulo, texto)


def confirmar(parent: QWidget, texto: str, titulo: str = "Confirmar") -> bool:
    respuesta = QMessageBox.question(parent, titulo, texto,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
    return respuesta == QMessageBox.StandardButton.Yes


# ---------------------------------------------------------------------------
# Tarjeta de indicador (pantalla de inicio)
# ---------------------------------------------------------------------------


class Tarjeta(QFrame):
    def __init__(self, titulo: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("tarjeta")
        layout = QVBoxLayout(self)
        self.valor = QLabel("–")
        self.valor.setObjectName("tarjetaValor")
        self.valor.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etiqueta = QLabel(titulo)
        etiqueta.setObjectName("tarjetaTitulo")
        etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        etiqueta.setWordWrap(True)
        layout.addWidget(self.valor)
        layout.addWidget(etiqueta)

    def establecer(self, valor: Any) -> None:
        self.valor.setText(formatear(valor) if valor is not None else "–")


def titulo_seccion(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setObjectName("tituloSeccion")
    return etiqueta
