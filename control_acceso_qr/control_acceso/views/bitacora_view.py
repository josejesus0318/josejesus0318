"""Consulta de la bitácora de accesos (Seguridad y Dirección), con exportación a CSV."""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QWidget,
)

from control_acceso.dao.acceso_dao import AccesoDAO
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.views.componentes import (
    Columna, TablaDatos, a_date, a_qdate, formatear, mostrar_error, mostrar_info,
)


def _color(fila: dict[str, Any]) -> QColor | None:
    return QColor("#f6e3e3") if fila.get("resultado") == "denegado" else None


class BitacoraView(QWidget):

    COLUMNAS = [
        Columna("fecha_hora", "Fecha y hora"),
        Columna("persona", "Persona"),
        Columna("tipo_persona", "Tipo"),
        Columna("codigo_qr", "Código QR"),
        Columna("punto_acceso", "Punto de acceso"),
        Columna("tipo_evento", "Evento", alinear_centro=True),
        Columna("resultado", "Resultado", alinear_centro=True),
        Columna("motivo", "Motivo"),
        Columna("registrado_por", "Registró"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dao = AccesoDAO()
        layout = QVBoxLayout(self)

        filtros = QHBoxLayout()
        self.dte_desde = QDateEdit(a_qdate(date.today() - timedelta(days=30)))
        self.dte_hasta = QDateEdit(a_qdate(date.today()))
        for editor in (self.dte_desde, self.dte_hasta):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd/MM/yyyy")
        self.cmb_resultado = QComboBox()
        self.cmb_resultado.addItem("Todos", None)
        self.cmb_resultado.addItem("Permitidos", "permitido")
        self.cmb_resultado.addItem("Denegados", "denegado")
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Persona, código o punto de acceso…")
        self.txt_buscar.setClearButtonEnabled(True)
        self.txt_buscar.returnPressed.connect(self.cargar)
        btn_buscar = QPushButton("Consultar")
        btn_buscar.setObjectName("primario")
        btn_buscar.clicked.connect(self.cargar)
        btn_csv = QPushButton("Exportar CSV…")
        btn_csv.clicked.connect(self._exportar)
        filtros.addWidget(QLabel("Desde:"))
        filtros.addWidget(self.dte_desde)
        filtros.addWidget(QLabel("Hasta:"))
        filtros.addWidget(self.dte_hasta)
        filtros.addWidget(self.cmb_resultado)
        filtros.addWidget(self.txt_buscar, 1)
        filtros.addWidget(btn_buscar)
        filtros.addWidget(btn_csv)
        layout.addLayout(filtros)

        self.tabla = TablaDatos(self.COLUMNAS, _color)
        layout.addWidget(self.tabla)
        self.lbl_total = QLabel()
        layout.addWidget(self.lbl_total)

    def cargar(self) -> None:
        desde, hasta = a_date(self.dte_desde.date()), a_date(self.dte_hasta.date())
        if desde > hasta:
            mostrar_info(self, "La fecha inicial no puede ser posterior a la final.", "Bitácora")
            return
        try:
            filas = self.dao.bitacora(desde, hasta, self.txt_buscar.text(), self.cmb_resultado.currentData())
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudo consultar la bitácora")
            return
        self.tabla.cargar(filas)
        denegados = sum(1 for f in filas if f["resultado"] == "denegado")
        self.lbl_total.setText(f"{len(filas)} evento(s) · {denegados} denegado(s)"
                               + ("  (se muestran los 2000 más recientes)" if len(filas) >= 2000 else ""))

    refrescar = cargar

    def _exportar(self) -> None:
        filas = self.tabla.modelo.filas
        if not filas:
            mostrar_info(self, "No hay datos para exportar. Primero realice una consulta.", "Exportar")
            return
        sugerido = str(Path.home() / f"bitacora_{date.today():%Y%m%d}.csv")
        ruta, _ = QFileDialog.getSaveFileName(self, "Exportar bitácora", sugerido, "CSV (*.csv)")
        if not ruta:
            return
        try:
            # utf-8-sig: Excel abre correctamente los acentos
            with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
                escritor = csv.writer(archivo)
                escritor.writerow([c.titulo for c in self.COLUMNAS])
                for fila in filas:
                    escritor.writerow([formatear(fila.get(c.clave)) for c in self.COLUMNAS])
        except OSError as error:
            mostrar_error(self, error, "No se pudo exportar")
            return
        mostrar_info(self, f"Se exportaron {len(filas)} registros a:\n{ruta}")
