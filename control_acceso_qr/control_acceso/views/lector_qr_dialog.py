"""Lector QR con cámara web (OpenCV + pyzbar).

- Un hilo QThread captura fotogramas con OpenCV y busca códigos QR, sin
  congelar la interfaz.
- Al detectar un código: pausa la lectura, la base de datos valida y
  registra el acceso (sp_registrar_acceso), se muestra el resultado con
  color y sonido, y tras unos segundos se reanuda la lectura.
- También permite capturar el código a mano (por si no hay cámara).
"""

from __future__ import annotations

import sys
import time
from datetime import datetime

import cv2
import numpy as np
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from control_acceso.dao.acceso_dao import AccesoDAO
from control_acceso.models.entidades import ResultadoLectura
from control_acceso.utils.config import config
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.utils.qr import DecodificadorQR
from control_acceso.views.componentes import mostrar_error

try:  # sonidos del sistema en Windows
    import winsound
except ImportError:  # pragma: no cover - Linux / macOS
    winsound = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Hilo de captura
# ---------------------------------------------------------------------------


class CamaraWorker(QThread):
    """Captura fotogramas y detecta códigos QR en segundo plano."""

    fotograma = pyqtSignal(QImage)
    codigo_detectado = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, indice_camara: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.indice = indice_camara
        self._activo = True
        self._pausado = False
        self.decodificador = DecodificadorQR()

    def run(self) -> None:
        # En Windows, DirectShow abre la cámara mucho más rápido que el backend por omisión
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        camara = cv2.VideoCapture(self.indice, backend)
        if not camara.isOpened():
            self.error.emit(f"No se pudo abrir la cámara {self.indice}. Verifique que esté conectada "
                            "y que ninguna otra aplicación la esté usando.")
            return
        camara.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camara.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        contador = 0
        try:
            while self._activo:
                ok, cuadro = camara.read()
                if not ok:
                    time.sleep(0.05)
                    continue
                contador += 1
                # Decodificar 1 de cada 3 fotogramas reduce el uso de CPU
                if not self._pausado and contador % 3 == 0:
                    codigos = self.decodificador.decodificar(cuadro)
                    if codigos:
                        self._pausado = True
                        self._marcar(cuadro)
                        self.codigo_detectado.emit(codigos[0])
                self.fotograma.emit(self._a_qimage(cuadro))
                self.msleep(15)
        finally:
            camara.release()

    def reanudar(self) -> None:
        self._pausado = False

    def detener(self) -> None:
        self._activo = False

    @staticmethod
    def _marcar(cuadro: np.ndarray) -> None:
        """Marco verde alrededor de la imagen para indicar que se leyó un código."""
        alto, ancho = cuadro.shape[:2]
        cv2.rectangle(cuadro, (4, 4), (ancho - 5, alto - 5), (60, 200, 60), 8)

    @staticmethod
    def _a_qimage(cuadro: np.ndarray) -> QImage:
        rgb = cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB)
        alto, ancho, canales = rgb.shape
        datos = rgb.tobytes()           # se mantiene vivo hasta que QImage hace su copia
        return QImage(datos, ancho, alto, canales * ancho, QImage.Format.Format_RGB888).copy()


# ---------------------------------------------------------------------------
# Diálogo del lector
# ---------------------------------------------------------------------------


class LectorQRDlg(QDialog):

    ESTILOS = {
        "permitido": ("resultadoPermitido", "ACCESO PERMITIDO"),
        "denegado": ("resultadoDenegado", "ACCESO DENEGADO"),
        "no_encontrado": ("resultadoDenegado", "CÓDIGO NO REGISTRADO"),
        "repetido": ("resultadoAviso", "LECTURA REPETIDA"),
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lector de códigos QR")
        self.setMinimumSize(980, 620)
        self.dao = AccesoDAO()
        self.worker: CamaraWorker | None = None
        self._reanudar = QTimer(self)
        self._reanudar.setSingleShot(True)
        self._reanudar.timeout.connect(self._listo_para_leer)
        self._construir()
        self._cargar_puntos()

    def _construir(self) -> None:
        layout = QHBoxLayout(self)

        # Izquierda: video
        izquierda = QVBoxLayout()
        self.lbl_video = QLabel("Cámara detenida")
        self.lbl_video.setObjectName("video")
        self.lbl_video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_video.setMinimumSize(640, 480)
        izquierda.addWidget(self.lbl_video, 1)
        controles = QHBoxLayout()
        controles.addWidget(QLabel("Cámara:"))
        self.spn_camara = QSpinBox()
        self.spn_camara.setRange(0, 5)
        self.spn_camara.setValue(config.indice_camara)
        self.btn_camara = QPushButton("Iniciar cámara")
        self.btn_camara.setObjectName("primario")
        self.btn_camara.clicked.connect(self._alternar_camara)
        self.lbl_motor = QLabel(f"Decodificador: {DecodificadorQR().motor}")
        self.lbl_motor.setObjectName("aviso")
        controles.addWidget(self.spn_camara)
        controles.addWidget(self.btn_camara)
        controles.addStretch()
        controles.addWidget(self.lbl_motor)
        izquierda.addLayout(controles)
        layout.addLayout(izquierda, 3)

        # Derecha: punto de acceso, resultado e historial
        derecha = QVBoxLayout()
        derecha.addWidget(QLabel("Punto de acceso:"))
        self.cmb_punto = QComboBox()
        derecha.addWidget(self.cmb_punto)

        self.lbl_resultado = QLabel("Acerque el código QR a la cámara")
        self.lbl_resultado.setObjectName("resultadoEspera")
        self.lbl_resultado.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_resultado.setWordWrap(True)
        self.lbl_resultado.setMinimumHeight(170)
        derecha.addWidget(self.lbl_resultado)

        derecha.addWidget(QLabel("Captura manual del código:"))
        manual = QHBoxLayout()
        self.txt_manual = QLineEdit()
        self.txt_manual.setPlaceholderText("QR-COL-0001")
        self.txt_manual.returnPressed.connect(self._registrar_manual)
        btn_manual = QPushButton("Registrar")
        btn_manual.clicked.connect(self._registrar_manual)
        manual.addWidget(self.txt_manual)
        manual.addWidget(btn_manual)
        derecha.addLayout(manual)

        derecha.addWidget(QLabel("Últimas lecturas:"))
        self.lst_historial = QListWidget()
        derecha.addWidget(self.lst_historial, 1)
        btn_cerrar = QPushButton("Cerrar lector")
        btn_cerrar.clicked.connect(self.accept)
        derecha.addWidget(btn_cerrar)
        layout.addLayout(derecha, 2)

    def _cargar_puntos(self) -> None:
        try:
            puntos = self.dao.puntos_activos()
        except ErrorAplicacion as error:
            mostrar_error(self, error, "No se pudieron cargar los puntos de acceso")
            return
        for punto in puntos:
            self.cmb_punto.addItem(f"{punto.nombre}  ({punto.tipo_punto})", punto.id_punto_acceso)
        indice = self.cmb_punto.findData(config.punto_acceso)
        if indice >= 0:
            self.cmb_punto.setCurrentIndex(indice)

    # -- cámara ------------------------------------------------------------------
    def _alternar_camara(self) -> None:
        if self.worker is not None:
            self._detener_camara()
            return
        self.worker = CamaraWorker(self.spn_camara.value(), self)
        self.worker.fotograma.connect(self._mostrar_fotograma)
        self.worker.codigo_detectado.connect(self._procesar_codigo)
        self.worker.error.connect(self._error_camara)
        self.worker.finished.connect(self._camara_terminada)
        self.worker.start()
        self.btn_camara.setText("Detener cámara")
        self.spn_camara.setEnabled(False)
        self.lbl_video.setText("Abriendo cámara…")

    def _detener_camara(self) -> None:
        if self.worker is not None:
            self.worker.detener()
            self.worker.wait(3000)

    def _camara_terminada(self) -> None:
        self.worker = None
        self.btn_camara.setText("Iniciar cámara")
        self.spn_camara.setEnabled(True)
        self.lbl_video.clear()
        self.lbl_video.setText("Cámara detenida")

    def _mostrar_fotograma(self, imagen: QImage) -> None:
        self.lbl_video.setPixmap(QPixmap.fromImage(imagen).scaled(
            self.lbl_video.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def _error_camara(self, mensaje: str) -> None:
        self.lbl_video.setText(mensaje)
        self.lbl_video.setWordWrap(True)

    # -- lectura -------------------------------------------------------------------
    def _registrar_manual(self) -> None:
        codigo = self.txt_manual.text().strip()
        if codigo:
            self.txt_manual.clear()
            self._procesar_codigo(codigo)

    def _procesar_codigo(self, codigo: str) -> None:
        id_punto = self.cmb_punto.currentData()
        if id_punto is None:
            self._mostrar_resultado(ResultadoLectura("denegado", None, None,
                                                     "Seleccione un punto de acceso"), codigo)
            return
        try:
            resultado = self.dao.registrar_lectura(codigo, id_punto)
        except ErrorAplicacion as error:
            resultado = ResultadoLectura("denegado", None, None, error.mensaje)
        self._mostrar_resultado(resultado, codigo)
        self._reanudar.start(int(config.pausa_resultado * 1000))

    def _mostrar_resultado(self, r: ResultadoLectura, codigo: str) -> None:
        nombre_estilo, encabezado = self.ESTILOS.get(r.estado_lectura, ("resultadoDenegado", "ERROR"))
        lineas = [f"<span style='font-size:22pt; font-weight:700'>{encabezado}</span>"]
        if r.persona:
            lineas.append(f"<span style='font-size:15pt'>{r.persona}</span>")
        if r.evento and r.estado_lectura == "permitido":
            lineas.append(f"<span style='font-size:13pt'>Registro de <b>{r.evento.upper()}</b></span>")
        lineas.append(f"<span style='font-size:11pt'>{r.mensaje}</span>")
        self.lbl_resultado.setObjectName(nombre_estilo)
        self.lbl_resultado.style().unpolish(self.lbl_resultado)
        self.lbl_resultado.style().polish(self.lbl_resultado)
        self.lbl_resultado.setText("<br>".join(lineas))
        self._sonido(r.permitido)

        icono = "✔" if r.permitido else ("•" if r.estado_lectura == "repetido" else "✖")
        detalle = f"{r.persona or codigo} – {r.evento or r.mensaje}"
        self.lst_historial.insertItem(0, f"{datetime.now():%H:%M:%S}  {icono}  {detalle}")
        while self.lst_historial.count() > 15:
            self.lst_historial.takeItem(self.lst_historial.count() - 1)

    def _listo_para_leer(self) -> None:
        self.lbl_resultado.setObjectName("resultadoEspera")
        self.lbl_resultado.style().unpolish(self.lbl_resultado)
        self.lbl_resultado.style().polish(self.lbl_resultado)
        self.lbl_resultado.setText("Acerque el código QR a la cámara")
        if self.worker is not None:
            self.worker.reanudar()

    @staticmethod
    def _sonido(exito: bool) -> None:
        if winsound is not None:
            winsound.MessageBeep(winsound.MB_OK if exito else winsound.MB_ICONHAND)
        else:
            QApplication.beep()

    def done(self, resultado: int) -> None:
        """Se ejecuta al cerrar de cualquier forma (botón, Esc o la X): libera la cámara."""
        self._reanudar.stop()
        self._detener_camara()
        super().done(resultado)
