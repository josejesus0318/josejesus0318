"""Pantalla de inicio: indicadores del día y personas dentro del edificio."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from control_acceso.dao.acceso_dao import AccesoDAO
from control_acceso.dao.sesion_dao import SesionDAO
from control_acceso.utils.conexion import sesion
from control_acceso.utils.errores import ErrorAplicacion
from control_acceso.utils.permisos import tiene_capacidad
from control_acceso.views.componentes import Columna, TablaDatos, Tarjeta, titulo_seccion

INDICADORES = [
    ("accesos_permitidos", "Accesos permitidos hoy"),
    ("accesos_denegados", "Accesos denegados hoy"),
    ("personas_dentro", "Personas dentro"),
    ("visitas_hoy", "Visitas de hoy"),
    ("credenciales_por_vencer", "Credenciales por vencer (30 días)"),
    ("colaboradores_activos", "Colaboradores activos"),
]


class InicioView(QWidget):

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ver_dentro = tiene_capacidad("ver_personas_dentro")
        layout = QVBoxLayout(self)

        cabecera = QHBoxLayout()
        bienvenida = QLabel(f"Bienvenido(a), <b>{sesion.nombre_completo}</b>")
        bienvenida.setObjectName("bienvenida")
        self.lbl_actualizado = QLabel()
        btn_actualizar = QPushButton("Actualizar")
        btn_actualizar.clicked.connect(self.refrescar)
        cabecera.addWidget(bienvenida)
        cabecera.addStretch()
        cabecera.addWidget(self.lbl_actualizado)
        cabecera.addWidget(btn_actualizar)
        layout.addLayout(cabecera)

        rejilla = QGridLayout()
        self.tarjetas: dict[str, Tarjeta] = {}
        for i, (clave, titulo) in enumerate(INDICADORES):
            tarjeta = Tarjeta(titulo)
            self.tarjetas[clave] = tarjeta
            rejilla.addWidget(tarjeta, i // 3, i % 3)
        layout.addLayout(rejilla)

        self.tabla = TablaDatos([
            Columna("persona", "Persona"), Columna("tipo_persona", "Tipo"),
            Columna("codigo_qr", "Código QR"), Columna("punto_acceso", "Entró por"),
            Columna("hora_entrada", "Hora de entrada"),
        ])
        if self.ver_dentro:
            layout.addWidget(titulo_seccion("Personas dentro del edificio"))
            layout.addWidget(self.tabla, 1)
        else:
            layout.addStretch(1)

        # Actualización automática cada 30 segundos mientras la pantalla está visible
        self._temporizador = QTimer(self)
        self._temporizador.setInterval(30_000)
        self._temporizador.timeout.connect(self.refrescar)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refrescar()
        self._temporizador.start()

    def hideEvent(self, event) -> None:  # noqa: N802
        super().hideEvent(event)
        self._temporizador.stop()

    def refrescar(self) -> None:
        if not sesion.activa:
            return
        try:
            resumen = SesionDAO().resumen_hoy()
            for clave, tarjeta in self.tarjetas.items():
                tarjeta.establecer(resumen.get(clave))
            if self.ver_dentro:
                self.tabla.cargar(AccesoDAO().personas_dentro())
        except ErrorAplicacion as error:
            self.lbl_actualizado.setText(f"Error al actualizar: {error.mensaje}")
            return
        self.lbl_actualizado.setText(f"Actualizado a las {datetime.now():%H:%M:%S}")
