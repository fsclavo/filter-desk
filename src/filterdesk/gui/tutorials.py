"""In-app guided tutorials (English/Spanish)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from filterdesk.gui.i18n import Language, current_language, tr


@dataclass(frozen=True, slots=True)
class Tutorial:
    title: str
    title_es: str
    html: str
    html_es: str
    commands: tuple[str, ...] = ()
    example: str | None = None


TUTORIALS: tuple[Tutorial, ...] = (
    Tutorial(
        title="Receiver preselector (40 m)",
        title_es="Preselector de recepción (40 m)",
        html="""
<h2>Receiver preselector (40 m)</h2>
<p>Design a band-pass preselector for the 40 m amateur band.</p>
<ol>
<li>Open <b>Design → Band filter wizard…</b>.</li>
<li>Choose <b>Guided design</b>, band <b>40 m</b> and kind <b>Band-pass</b>.</li>
<li>Set insertion loss and rejection, then inspect the candidate-order table.</li>
<li>Apply the lowest order that meets the requirements.</li>
<li>Check the <b>Magnitude</b> plot and the component table.</li>
<li>Export a build sheet, assign real parts, or compare a measured
<b>File → Import → Touchstone…</b> capture.</li>
</ol>
<p><b>Check:</b> passband insertion loss, input return loss, and rejection
outside 7.0–7.3 MHz. The ideal LC result is a starting point; verify with a VNA.</p>
""",
        html_es="""
<h2>Preselector de recepción (40 m)</h2>
<p>Diseñar un preselector pasa-banda para la banda de 40 m.</p>
<ol>
<li>Abrir <b>Design → Band filter wizard…</b>.</li>
<li>Elegir <b>Guided design</b>, banda <b>40 m</b> y tipo <b>Band-pass</b>.</li>
<li>Definir pérdida de inserción y rechazo, y revisar la tabla de órdenes.</li>
<li>Aplicar el menor orden que cumpla los requisitos.</li>
<li>Revisar el gráfico <b>Magnitude</b> y la tabla de componentes.</li>
<li>Exportar la hoja de montaje, asignar partes reales o comparar una captura
medida con <b>File → Import → Touchstone…</b>.</li>
</ol>
<p><b>Verificar:</b> pérdida en la banda de paso, adaptación de entrada y rechazo
fuera de 7,0–7,3 MHz. El resultado LC ideal es un punto de partida; validar con VNA.</p>
""",
        commands=(
            "filterdesk analyze --band 40m --band-kind bpf "
            "--export-build-sheet rx40m.md",
        ),
        example="rx40m",
    ),
    Tutorial(
        title="100 W transmitter low-pass (80 m)",
        title_es="Paso-bajo de transmisión 100 W (80 m)",
        html="""
<h2>100 W transmitter low-pass (80 m)</h2>
<p>Design a transmit low-pass filter and inspect harmonic and voltage/current
stresses.</p>
<ol>
<li>Open <b>Design → Band filter wizard…</b> and choose
<b>Quick preset</b> with kind <b>Transmit LPF</b> for <b>80 m</b>.</li>
<li>Apply the design and set <b>TX Power</b> to 100 W.</li>
<li>Open the <b>Harmonics</b> dock and check 2f/3f suppression.</li>
<li>Inspect <b>Vpk/Ipk</b> in the component table and the status-bar worst case.</li>
<li>Export the build sheet and verify the assumptions.</li>
</ol>
<p><b>Check:</b> harmonic rejection, capacitor voltage ratings and inductor
current ratings. The stress model is linear and frequency-domain; it is not a
thermal or saturation validation.</p>
""",
        html_es="""
<h2>Paso-bajo de transmisión 100 W (80 m)</h2>
<p>Diseñar un paso-bajo de transmisión e inspeccionar armónicos y
tensiones/corrientes.</p>
<ol>
<li>Abrir <b>Design → Band filter wizard…</b> y elegir
<b>Quick preset</b> con tipo <b>Transmit LPF</b> para <b>80 m</b>.</li>
<li>Aplicar el diseño y poner <b>TX Power</b> en 100 W.</li>
<li>Abrir el dock <b>Harmonics</b> y revisar la supresión de 2f/3f.</li>
<li>Revisar <b>Vpk/Ipk</b> en la tabla de componentes y el peor caso en la
barra de estado.</li>
<li>Exportar la hoja de montaje y verificar los supuestos.</li>
</ol>
<p><b>Verificar:</b> rechazo de armónicos, tensión de capacitores y corriente de
inductores. El modelo de estrés es lineal y en frecuencia; no valida térmica ni
saturación.</p>
""",
        commands=(
            "filterdesk analyze --band 80m --band-kind lpf --power 100 "
            "--harmonics --export-build-sheet tx80m.md",
        ),
        example="tx80m",
    ),
    Tutorial(
        title="2 m diplexer and VNA comparison",
        title_es="Diplexer de 2 m y comparación con VNA",
        html="""
<h2>2 m diplexer and VNA comparison</h2>
<p>Split a 2 m antenna between a low and a high sub-band.</p>
<ol>
<li>Open <b>Tools → Diplexer / multiplexer designer…</b> and choose
<b>LPF + HPF</b>.</li>
<li>Set the low/high cutoffs and a sweep covering both bands.</li>
<li>Design and inspect the metrics, <b>Magnitude</b> plot and branch schematics.</li>
<li>Try an <b>E-series snap</b> and <b>Parasitics…</b>; check whether the metrics
still meet the requirement.</li>
<li>Export the <b>.s3p</b>, build sheet and HTML/PDF report.</li>
<li>Use <b>Compare measurements…</b> with two-port VNA captures: common→low and
common→high, terminating the unused port in 50 Ω.</li>
</ol>
<p><b>Check:</b> insertion loss and return loss in each band, out-of-band
rejection and crossover. The 2-port comparison is not a true N-port VNA measurement.</p>
""",
        html_es="""
<h2>Diplexer de 2 m y comparación con VNA</h2>
<p>Dividir una antena de 2 m entre una sub-banda baja y una alta.</p>
<ol>
<li>Abrir <b>Tools → Diplexer / multiplexer designer…</b> y elegir
<b>LPF + HPF</b>.</li>
<li>Definir los cortes y un barrido que cubra ambas bandas.</li>
<li>Diseñar y revisar métricas, gráfico <b>Magnitude</b> y esquemáticos por rama.</li>
<li>Probar <b>E-series snap</b> y <b>Parasitics…</b>; verificar que las métricas
sigan cumpliendo el requisito.</li>
<li>Exportar el <b>.s3p</b>, la hoja de montaje y el informe HTML/PDF.</li>
<li>Usar <b>Compare measurements…</b> con capturas de VNA de 2 puertos:
común→baja y común→alta, terminando el puerto no usado en 50 Ω.</li>
</ol>
<p><b>Verificar:</b> pérdida y adaptación en cada banda, rechazo fuera de banda y
cruce. La comparación de 2 puertos no es una medición de VNA de N puertos.</p>
""",
        commands=(
            "filterdesk diplexer --low-cutoff 144M --high-cutoff 148M "
            "--order 5 --ripple 0.1 --f-start 100M --f-stop 200M "
            "--output diplexer.s3p --export-build-sheet diplexer_bom.md",
        ),
        example="diplexer2m",
    ),
)


class TutorialDialog(QDialog):
    """Guided tutorials with copyable CLI commands and example projects."""

    example_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Tutorials"))
        self.setMinimumSize(900, 600)
        self._language = current_language()
        self._list = QListWidget()
        self._list.setFixedWidth(260)
        for tutorial in TUTORIALS:
            self._list.addItem(self._title(tutorial))
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("Choose a tutorial")))
        left.addWidget(self._list, 1)
        right = QVBoxLayout()
        right.addWidget(self._browser, 1)
        right.addWidget(self._status)
        body = QHBoxLayout()
        body.addLayout(left)
        body.addLayout(right, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        copy_button = buttons.addButton(
            tr("Copy commands"), QDialogButtonBox.ButtonRole.ActionRole
        )
        copy_button.clicked.connect(self._copy_commands)
        self._open_button = buttons.addButton(
            tr("Open example"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self._open_button.setToolTip(tr("Open the example project for this tutorial."))
        self._open_button.clicked.connect(self._open_example)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(buttons)
        self._list.currentRowChanged.connect(self._show)
        self._list.setCurrentRow(0)

    def _title(self, tutorial: Tutorial) -> str:
        return tutorial.title_es if self._language is Language.ES else tutorial.title

    def _html(self, tutorial: Tutorial) -> str:
        return tutorial.html_es if self._language is Language.ES else tutorial.html

    def _show(self, row: int) -> None:
        if not 0 <= row < len(TUTORIALS):
            return
        self._browser.setHtml(self._html(TUTORIALS[row]))
        self._status.setText("")
        self._open_button.setEnabled(TUTORIALS[row].example is not None)

    def _open_example(self) -> None:
        row = self._list.currentRow()
        if not 0 <= row < len(TUTORIALS):
            return
        example = TUTORIALS[row].example
        if example is None:
            return
        self.accept()
        self.example_requested.emit(example)

    def _copy_commands(self) -> None:
        row = self._list.currentRow()
        if not 0 <= row < len(TUTORIALS):
            return
        commands = TUTORIALS[row].commands
        if not commands:
            self._status.setText(tr("No commands for this tutorial."))
            return
        QApplication.clipboard().setText("\n".join(commands))
        self._status.setText(tr("Copied tutorial commands."))


__all__ = ["TUTORIALS", "Tutorial", "TutorialDialog"]
