"""Diálogo que muestra el código QR de una credencial y permite guardarlo en PNG."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from control_acceso.utils.qr import generar_qr, guardar_qr
from control_acceso.views.componentes import mostrar_error, mostrar_info


class QRDialog(QDialog):

    def __init__(self, codigo_qr: str, titular: str, detalle: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.codigo = codigo_qr
        self.titular = titular
        self.setWindowTitle(f"Credencial {codigo_qr}")
        layout = QVBoxLayout(self)

        imagen = generar_qr(codigo_qr, tamano=300)
        alto, ancho = imagen.shape
        datos = imagen.tobytes()
        qimagen = QImage(datos, ancho, alto, ancho, QImage.Format.Format_Grayscale8).copy()
        lbl_qr = QLabel()
        lbl_qr.setPixmap(QPixmap.fromImage(qimagen))
        lbl_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_qr)

        for texto, nombre in ((titular, "qrTitular"), (codigo_qr, "qrCodigo"), (detalle, "qrDetalle")):
            if texto:
                etiqueta = QLabel(texto)
                etiqueta.setObjectName(nombre)
                etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(etiqueta)

        botones = QHBoxLayout()
        btn_guardar = QPushButton("Guardar imagen PNG…")
        btn_guardar.setObjectName("primario")
        btn_guardar.clicked.connect(self._guardar)
        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(self.accept)
        botones.addStretch()
        botones.addWidget(btn_guardar)
        botones.addWidget(btn_cerrar)
        layout.addLayout(botones)

    def _guardar(self) -> None:
        sugerido = str(Path.home() / f"{self.codigo}.png")
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar código QR", sugerido, "Imagen PNG (*.png)")
        if not ruta:
            return
        if not ruta.lower().endswith(".png"):
            ruta += ".png"
        try:
            guardar_qr(self.codigo, ruta, f"{self.titular}\n{self.codigo}")
        except OSError as error:
            mostrar_error(self, error, "No se pudo guardar")
            return
        mostrar_info(self, f"Imagen guardada en:\n{ruta}")
