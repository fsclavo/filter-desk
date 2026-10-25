"""GUI internationalisation (English source strings, Spanish catalogue).

The English text is the lookup key (``tr("Family")``); the Spanish catalogue maps
it to the translated string. Unknown keys fall back to English, and a test scans
the GUI sources to make sure every used key has a Spanish entry.

Qt's own standard strings (OK/Cancel, file dialogs, …) are translated by loading
``qtbase_<lang>.qm`` from the PySide6 installation.
"""

from __future__ import annotations

from enum import StrEnum

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QTranslator

from filterdesk.domain.enums import (
    ApproximationFamily,
    ElementRole,
    FilterResponse,
    TopologyId,
)


class Language(StrEnum):
    EN = "en"
    ES = "es"


_current = Language.EN
_qt_translator: QTranslator | None = None


# --- Spanish catalogue -------------------------------------------------------
# Keys are the English source strings used in the GUI.
_ES: dict[str, str] = {
    # Common / panels ---------------------------------------------------------
    "Family": "Familia",
    "Response": "Respuesta",
    "Order": "Orden",
    "Estimate N": "Estimar N",
    "Minimum order from Ap/As and pass/stop edges (LP/HP, supported families)": (
        "Orden mínimo a partir de Ap/As y los bordes de paso/rechazo "
        "(LP/HP, familias soportadas)"
    ),
    "Passband f / cutoff": "f de paso / corte",
    "Stopband f (est.)": "f de rechazo (est.)",
    "Center": "Centro",
    "Bandwidth": "Ancho de banda",
    "Ripple / Ap (dB)": "Rizado / Ap (dB)",
    "Stopband As (dB)": "Atenuación As (dB)",
    "m parameter": "Parámetro m",
    "Zsource": "Z fuente",
    "Zload": "Z carga",
    "Topology": "Topología",
    "Butterworth": "Butterworth",
    "Chebyshev Type I": "Chebyshev tipo I",
    "Chebyshev Type II": "Chebyshev tipo II",
    "Elliptic": "Elíptico",
    "Bessel": "Bessel",
    "Gaussian": "Gaussiano",
    "Legendre": "Legendre",
    "Constant-K": "K constante",
    "M-derived": "Derivado m",
    "Low-pass": "Paso bajo",
    "High-pass": "Paso alto",
    "Band-pass": "Paso banda",
    "Band-stop": "Rechazo banda",
    "Series L input": "Entrada L serie",
    "Shunt C input": "Entrada C paralelo",
    "Series C input": "Entrada C serie",
    "Shunt L input": "Entrada L paralelo",
    "Series resonator input": "Entrada resonador serie",
    "Shunt resonator input": "Entrada resonador paralelo",
    "Series tank input": "Entrada tanque serie",
    "Shunt tank input": "Entrada tanque paralelo",
    (
        "Even-order Chebyshev I: FilterDesk uses the modified equal-termination "
        "response, not the classical unequal-termination tables. Use an odd "
        "order for textbook values."
    ): (
        "Chebyshev I de orden par: FilterDesk usa la respuesta modificada de "
        "terminaciones iguales, no las tablas clásicas de terminaciones "
        "desiguales. Use un orden impar para valores de manual."
    ),
    "Estimate order": "Estimar orden",
    "Minimum order N = {order}\\nΩs = {ratio:.6g}\\nNatural f ≈ {freq}\\n\\n{notes}": (
        "Orden mínimo N = {order}\\nΩs = {ratio:.6g}\\nf natural ≈ {freq}\\n\\n{notes}"
    ),
    "Notes: {notes}": "Notas: {notes}",
    # Component table --------------------------------------------------------
    "Ref": "Ref",
    "Role": "Rol",
    "Type": "Tipo",
    "Value": "Valor",
    "Parasitic": "Parásitos",
    "Tol": "Tol",
    "Vpk": "Vpk",
    "Ipk": "Ipk",
    # Markers ----------------------------------------------------------------
    "Frequency": "Frecuencia",
    "Label": "Etiqueta",
    "Binds": "Vincula",
    "Add at cursor": "Añadir en cursor",
    "Delete": "Eliminar",
    "Clear": "Limpiar",
    "—": "—",
    "cutoff": "Corte",
    "f_center": "Centro",
    "bandwidth": "Ancho de banda",
    # Limits -----------------------------------------------------------------
    "Passband |S21| min": "Paso |S21| mín",
    "S21 passband": "S21 paso",
    "Stopband |S21| max": "Rechazo |S21| máx",
    "S21 stopband": "S21 rechazo",
    "Return loss |S11| max": "Pérdida de retorno |S11| máx",
    "return loss": "pérdida de retorno",
    "VSWR max": "ROE máx",
    "VSWR": "ROE",
    "Smith |S11| max": "Smith |S11| máx",
    "Smith |S22| max": "Smith |S22| máx",
    "Metric": "Métrica",
    "f_low": "f_baja",
    "f_high": "f_alta",
    "y_min": "y_mín",
    "y_max": "y_máx",
    "Add limit": "Añadir límite",
    "On": "Activa",
    (
        "Add a limit region preset, then edit the cells:\\n"
        "Metric (s21_db, s11_db, vswr, s11_mag, s22_mag), f_low/f_high, "
        "y_min/y_max (blank = unbounded), On (yes/no).\\n"
        "Enabled limits are drawn as bands and drive Design → Optimize to limits…"
    ): (
        "Añada un preset de límite y edite las celdas:\\n"
        "Métrica (s21_db, s11_db, vswr, s11_mag, s22_mag), f_baja/f_alta, "
        "y_mín/y_máx (vacío = sin límite), Activa (sí/no).\\n"
        "Los límites activos se dibujan como bandas y guían "
        "Diseño → Optimizar a límites…"
    ),
    # Harmonics --------------------------------------------------------------
    "Harmonic": "Armónico",
    "Suppression (dB)": "Supresión (dB)",
    "auto (band landmark)": "auto (referencia de banda)",
    "Use landmark": "Usar referencia",
    # Plots ------------------------------------------------------------------
    "Magnitude": "Magnitud",
    "Phase": "Fase",
    "Group delay": "Retardo de grupo",
    "Impedance": "Impedancia",
    "S12 / S22": "S12 / S22",
    "|S21| / |S11| (dB)": "|S21| / |S11| (dB)",
    "|S22| / |S12| (dB)": "|S22| / |S12| (dB)",
    "Re(Γ)": "Re(Γ)",
    "Im(Γ)": "Im(Γ)",
    "S21 meas": "S21 med",
    "S11 meas": "S11 med",
    "S22 meas": "S22 med",
    "S12 meas": "S12 med",
    "∠S21 meas": "∠S21 med",
    "∠S11 meas": "∠S11 med",
    "|Zin| meas": "|Zin| med",
    "|Zin|": "|Zin|",
    "Re(Zin)": "Re(Zin)",
    "Im(Zin)": "Im(Zin)",
    "|Zout|": "|Zout|",
    "∠S21": "∠S21",
    "∠S11": "∠S11",
    "No analysis result.": "Sin resultado de análisis.",
    "No circuit — click Synthesize": "Sin circuito — pulse Sintetizar",
    "S11": "S11",
    "S12": "S12",
    "S21": "S21",
    "S22": "S22",
    "Zs = {zs} Ω": "Zs = {zs} Ω",
    "Zl = {zl} Ω": "Zl = {zl} Ω",
    "Brune (+)": "Brune (+)",
    "Brune (||)": "Brune (||)",
    # Common dialog/action words --------------------------------------------
    "Save": "Guardar",
    "Cancel": "Cancelar",
    "Close": "Cerrar",
    "Apply": "Aplicar",
    "Yes": "Sí",
    "No": "No",
    "None": "Ninguno",
    "Series": "Serie",
    "Strategy": "Estrategia",
    "System": "Sistema",
    "Light": "Claro",
    "Dark": "Oscuro",
    "Theme": "Tema",
    "Language": "Idioma",
    "English": "English",
    "Español": "Español",
    # Element roles / types --------------------------------------------------
    "series": "serie",
    "shunt": "paralelo",
    "inductor": "inductor",
    "capacitor": "condensador",
    "resistor": "resistencia",
    "series_lc": "LC serie",
    "parallel_lc": "LC paralelo",
    "brune_lc": "Brune",
    "dual_brune_lc": "Brune dual",
    "nonideal_inductor": "inductor real",
    "nonideal_capacitor": "condensador real",
    "yes": "sí",
    "no": "no",
}

# Menu mnemonics and the longer dialog/help texts (added separately to keep the
# main catalogue readable).
_ES.update(
    {
        "&File": "&Archivo",
        "&New": "&Nuevo",
        "&Open…": "&Abrir…",
        "&Save": "&Guardar",
        "Save &As…": "Guardar &como…",
        "&Rename project…": "&Renombrar proyecto…",
        "&Import Touchstone…": "&Importar Touchstone…",
        "Export &Smith chart…": "Exportar carta de &Smith…",
        "Export C&SV…": "Exportar C&SV…",
        "Export SPICE &netlist…": "Exportar &netlist SPICE…",
        "Export &Touchstone (.s2p)…": "Exportar &Touchstone (.s2p)…",
        "Export LTspice (.&asc)…": "Exportar esquema LTspice (.&asc)…",
        "Export &Qucs (.sch)…": "Exportar esquema &Qucs (.sch)…",
        "Export build sheet / &BOM…": "Exportar hoja de montaje / &BOM…",
        "&Quit": "&Salir",
        "&Import": "&Importar",
        "&Export": "&Exportar",
        "&Edit": "&Editar",
        "&Undo": "&Deshacer",
        "&Redo": "&Rehacer",
        "Add &marker at cursor": "Añadir &marcador en el cursor",
        "&View": "&Ver",
        "Show &measured overlay": "Mostrar superposición &medida",
        "Show Monte-Carlo &envelope": "Mostrar &envolvente Monte-Carlo",
        "Show &harmonic markers": "Mostrar marcadores de &armónicos",
        "&Theme": "&Tema",
        "&Language": "&Idioma",
        "&Design": "&Diseño",
        "&Synthesize + Analyze": "&Sintetizar + analizar",
        "&Band preset…": "&Preset de banda…",
        "&Attenuator pad…": "&Atenuador…",
        "Matching &network…": "Red de &adaptación…",
        "&Coil calculator…": "Calculadora de &bobinas…",
        "Sna&p to E-series…": "Ajustar a serie &E…",
        "Apply &parasitics / Q…": "Aplicar &parásitos / Q…",
        "&Monte-Carlo tolerances…": "Tolerancias &Monte-Carlo…",
        "Scale &response…": "Escalar &respuesta…",
        "&Optimize to limits…": "&Optimizar a límites…",
        "Component &sensitivity…": "&Sensibilidad de componentes…",
        "Parameter s&weep…": "Barrido de &parámetros…",
        "&Component": "&Componente",
        "&Help": "A&yuda",
        "&About FilterDesk": "&Acerca de FilterDesk",
        "About &Qt": "Acerca de &Qt",
        "&GitHub repository": "Repositorio de &GitHub",
        "&User manual": "Manual de &usuario",
        "Set tune &step…": "Definir &paso de ajuste…",
        "Set &tolerance…": "Definir &tolerancia…",
        # Toolbar / status ---------------------------------------------------
        "Synthesize": "Sintetizar",
        "Analyze": "Analizar",
        "Tune +": "Ajustar +",
        "Tune −": "Ajustar −",
        "Tune the selected component up one step (Ctrl+])": (
            "Ajustar el componente seleccionado un paso arriba (Ctrl+])"
        ),
        "Tune the selected component down one step (Ctrl+[)": (
            "Ajustar el componente seleccionado un paso abajo (Ctrl+[)"
        ),
        "TX Power": "Potencia TX",
        "Start Frequency": "Frecuencia inicial",
        "Stop Frequency": "Frecuencia final",
        "Sweep start frequency, e.g. 10M or 1G": (
            "Frecuencia inicial del barrido, p. ej. 10M o 1G"
        ),
        "Sweep stop frequency, e.g. 1G": (
            "Frecuencia final del barrido, p. ej. 1G"
        ),
        # Widgets ------------------------------------------------------------
        "Apply parasitics / finite Q": "Aplicar parásitos / Q finita",
        "Inductor Q": "Q del inductor",
        "Q reference freq": "Frec. de referencia de Q",
        "Inductor DCR": "DCR del inductor",
        "Inductor Cpar": "Cpar del inductor",
        "Capacitor ESR": "ESR del condensador",
        "Capacitor ESL": "ESL del condensador",
        "Inductor parasitics": "Parásitos del inductor",
        "Capacitor parasitics": "Parásitos del condensador",
        "optional; overrides DCR": "opcional; reemplaza a DCR",
        "e.g. 100M": "p. ej. 100M",
        "Series R (DCR)": "R serie (DCR)",
        "Parallel C (Cp)": "C paralelo (Cp)",
        "Q": "Q",
        "ESR": "ESR",
        "ESL": "ESL",
        "Snap to E-series": "Ajustar a serie E",
        "e.g. 140M, 50, 10n": "p. ej. 140M, 50, 10n",
        "Trials": "Ensayos",
        "Tolerance ± (%)": "Tolerancia ± (%)",
        "Distribution": "Distribución",
        "Seed": "Semilla",
        "optional integer": "entero opcional",
        "optional integer (global methods)": "entero opcional (métodos globales)",
        "Method": "Método",
        "Bound (± fraction)": "Límite (± fracción)",
        "Max iterations": "Iteraciones máx.",
        "e.g. 0.2 = ±20%": "p. ej. 0.2 = ±20%",
        "Transmit LPF": "LPF de transmisión",
        "Band-stop (notch)": "Rechazo (notch)",
        "Amateur band preset": "Preset de banda amateur",
        "Band": "Banda",
        "Filter": "Filtro",
        "Attenuator pad": "Atenuador",
        "T pad": "Atenuador T",
        "Pi pad": "Atenuador Pi",
        "Attenuation (dB)": "Atenuación (dB)",
        "System Z0 (Ohm)": "Z0 del sistema (Ω)",
        "Topology": "Topología",
        "Series R": "R serie",
        "Shunt R": "R paralelo",
        "L (2 elements)": "L (2 elementos)",
        "Pi (3 elements)": "Pi (3 elementos)",
        "T (3 elements)": "T (3 elementos)",
        "Matching network": "Red de adaptación",
        "auto (Pi/T only)": "auto (solo Pi/T)",
        "Model the load (series X) at the output": (
            "Modelar la carga (X serie) en la salida"
        ),
        "Input": "Entrada",
        "Output": "Salida",
        "Source Z0 (Ohm)": "Z0 de fuente (Ω)",
        "Load R (Ohm)": "R de carga (Ω)",
        "Load X (Ohm, +ind/-cap)": "X de carga (Ω, +ind/-cap)",
        "Loaded Q": "Q cargada",
        "Insert at": "Insertar en",
        "Elements": "Elementos",
        "Core": "Núcleo",
        "Target L": "L objetivo",
        "Turns (0 = auto)": "Vueltas (0 = auto)",
        "Peak current (A)": "Corriente de pico (A)",
        "Exact turns": "Vueltas exactas",
        "Use turns": "Vueltas usadas",
        "Achieved L": "L obtenida",
        "Wire": "Alambre",
        "Wire length": "Longitud de alambre",
        "Peak flux": "Flujo de pico",
        "Saturation": "Saturación",
        "auto (from L)": "auto (desde L)",
        "n/a (iron powder)": "n/d (polvo de hierro)",
        "Wire AWG": "Calibre AWG",
        "Wire diameter (mm)": "Diámetro de alambre (mm)",
        "auto (grade 1); 0 = bare": "auto (grado 1); 0 = desnudo",
        "Diameter (mm)": "Diámetro (mm)",
        "Enamel build (mm)": "Espesor de esmalte (mm)",
        "Closest below": "Inmediato inferior",
        "Coil length": "Longitud de bobina",
        "Length / diameter": "Longitud / diámetro",
        "Wire size": "Tamaño de alambre",
        "DC resistance": "Resistencia DC",
        "Coil calculator": "Calculadora de bobinas",
        "Toroid": "Toroide",
        "Air-core": "Núcleo de aire",
        "Apply to selected inductor": "Aplicar al inductor seleccionado",
        "Realize inductor": "Realizar inductor",
        "Winding notes": "Notas del bobinado",
        "Component sensitivity": "Sensibilidad de componentes",
        "d|S21| dB/%": "d|S21| dB/%",
        "RMS dB/%": "RMS dB/%",
        "Worst f": "Peor f",
        "Suggestion": "Sugerencia",
        "increase": "aumentar",
        "decrease": "disminuir",
        "A tuning suggestion requires limits/objectives.": (
            "La sugerencia de ajuste requiere límites/objetivos."
        ),
        "{count} components · step {step:g}% · backend {backend}. "
        "A tuning suggestion requires limits/objectives.": (
            "{count} componentes · paso {step:g}% · backend {backend}. "
            "La sugerencia de ajuste requiere límites/objetivos."
        ),
        "Build sheet options": "Opciones de hoja de montaje",
        "No E-series snap": "Sin ajuste a serie E",
        "Group identical parts (combine refs and quantity)": (
            "Agrupar piezas idénticas (combina refs y cantidad)"
        ),
        "E-series": "Serie E",
        "Parameter sweep": "Barrido de parámetros",
        "e.g. 3,5,7,9": "p. ej. 3,5,7,9",
        "Axis": "Eje",
        "Values": "Valores",
        "Points": "Puntos",
        "Cutoff (Hz)": "Corte (Hz)",
        "Center (Hz)": "Centro (Hz)",
        "Bandwidth (Hz)": "Ancho de banda (Hz)",
        "Passband ripple (dB)": "Rizado de paso (dB)",
        "Stopband attenuation (dB)": "Atenuación de rechazo (dB)",
        "Design sweep": "Barrido de diseño",
        "Ripple dB": "Rizado dB",
        "Stop dB": "Rechazo dB",
        "RL dB": "RL dB",
        "GD ps": "RG ps",
        "Note / error": "Nota / error",
        "Apply selected": "Aplicar seleccionado",
        # Plots --------------------------------------------------------------
        "   | MC S21 {lo:.3f} … {hi:.3f} dB (spread {spread:.3f}, "
        "p05…p95 {p05:.3f}…{p95:.3f})": (
            "   | MC S21 {lo:.3f} … {hi:.3f} dB (dispersión {spread:.3f}, "
            "p05…p95 {p05:.3f}…{p95:.3f})"
        ),
        "   | markers: ": "   | marcadores: ",
        "  Dashed = {label} overlay.": "  Discontinuo = superposición {label}.",
        "  Grey band = Monte-Carlo envelope (hover for min…max).": (
            "  Banda gris = envolvente Monte-Carlo (pase el cursor para mín…máx)."
        ),
        "Smith chart — S11 / S22": "Carta de Smith — S11 / S22",
        "Minimum order N = {order}\nΩs = {ratio:.6g}\nNatural f ≈ {freq}\n\n{notes}": (
            "Orden mínimo N = {order}\nΩs = {ratio:.6g}\nf natural ≈ {freq}\n\n{notes}"
        ),
        "Minimum order from Ap/As and pass/stop edges "
        "(LP/HP classical families)": (
            "Orden mínimo a partir de Ap/As y los bordes de paso/rechazo "
            "(LP/HP, familias clásicas)"
        ),
        "Add a limit region preset, then edit the cells:\n"
        "Metric (s21_db, s11_db, vswr, s11_mag, s22_mag), f_low/f_high, "
        "y_min/y_max (blank = unbounded), On (yes/no).\n"
        "Enabled limits are drawn as bands and drive "
        "Design → Optimize to limits…": (
            "Añada un preset de límite y edite las celdas:\n"
            "Métrica (s21_db, s11_db, vswr, s11_mag, s22_mag), "
            "f_baja/f_alta, y_mín/y_máx (vacío = sin límite), Activa (sí/no).\n"
            "Los límites activos se dibujan como bandas y guían "
            "Diseño → Optimizar a límites…"
        ),
        "Move the mouse over a plot to read frequency and values "
        "(snaps to nearest sweep point). Drag marker lines (or Smith "
        "spots) to move; bind a marker to a landmark to retune by "
        "dragging. Use Markers / Limits docks to pin.": (
            "Mueva el ratón sobre un gráfico para leer frecuencia y valores "
            "(se ajusta al punto de barrido más cercano). Arrastre líneas de "
            "marcador (o puntos Smith) para moverlas; vincule un marcador a "
            "una referencia para re-sintonizar arrastrando. Use los docks de "
            "Marcadores / Límites para fijarlos."
        ),
        "Move the mouse over a plot to read frequency and values "
        "(snaps to nearest sweep point). Drag marker lines or Smith "
        "spots to move them; bind a marker to a landmark (cutoff / "
        "f_center / bandwidth) in the Markers dock to retune the design "
        "by dragging. Smith: S11 red, S22 blue; green/purple = S11 "
        "start/stop.": (
            "Mueva el ratón sobre un gráfico para leer frecuencia y valores "
            "(se ajusta al punto de barrido más cercano). Arrastre líneas de "
            "marcador o puntos Smith para moverlos; vincule un marcador a una "
            "referencia (corte / f_center / ancho de banda) en el dock de "
            "Marcadores para re-sintonizar arrastrando. Smith: S11 rojo, "
            "S22 azul; verde/púrpura = inicio/fin de S11."
        ),
        "Forward transmit power (W) used to estimate the peak voltage and "
        "current in each L/C (the Vpk / Ipk columns). 0 disables it.\n"
        "Evaluated at the passband landmark (cutoff for LP/HP, center for "
        "BP/BS) assuming a matched Z0 system — use it to pick component "
        "voltage/current ratings (e.g. capacitor voltage) for TX filters.": (
            "Potencia directa de transmisión (W) usada para estimar la tensión "
            "y corriente de pico en cada L/C (columnas Vpk / Ipk). 0 lo "
            "desactiva.\nSe evalúa en la referencia de la banda de paso (corte "
            "para LP/HP, centro para BP/BS) suponiendo un sistema Z0 adaptado; "
            "úsela para elegir tensiones/corrientes nominales de los "
            "componentes (p. ej. tensión de condensadores) en filtros de TX."
        ),
        "Language changed. Restart FilterDesk to apply.": (
            "Idioma cambiado. Reinicie FilterDesk para aplicarlo."
        ),
        "Saved {path}": "Guardado en {path}",
        "Monte-Carlo tolerances": "Tolerancias Monte-Carlo",
        "Optimize to limits": "Optimizar a límites",
        "Q reference frequency is required when Q is set": (
            "La frecuencia de referencia de Q es obligatoria cuando se define Q"
        ),
        "e.g. 0.05 (ohm, optional)": "p. ej. 0.05 (ohm, opcional)",
        "e.g. 0.2p (F, optional)": "p. ej. 0.2p (F, opcional)",
        "e.g. 0.5 (ohm, optional)": "p. ej. 0.5 (ohm, opcional)",
        "e.g. 0.5n (H, optional)": "p. ej. 0.5n (H, opcional)",
        "e.g. 100 (blank = ideal)": "p. ej. 100 (vacío = ideal)",
        "e.g. 100M (required for Q)": "p. ej. 100M (obligatorio para Q)",
    }
)

_ES.update(
    {
        "About FilterDesk": "Acerca de FilterDesk",
        "About Qt": "Acerca de Qt",
        "Add at least one enabled limit region first.": (
            "Añada al menos una región de límite activa."
        ),
        "Add marker": "Añadir marcador",
        "Analysis failed": "Análisis fallido",
        "Analyze a design first (Design → Synthesize + Analyze).": (
            "Analice un diseño primero (Diseño → Sintetizar + analizar)."
        ),
        "Analyzing…": "Analizando…",
        "Applied parasitics ({count} term(s))": (
            "Parásitos aplicados ({count} término(s))"
        ),
        "Apply parasitics": "Aplicar parásitos",
        "Attenuator": "Atenuador",
        "Band preset: {name} {kind}": "Preset de banda: {name} {kind}",
        "Cleared tolerance for {ref}": "Tolerancia borrada para {ref}",
        "Component tolerance": "Tolerancia del componente",
        "Convert element": "Convertir elemento",
        "Convert {ref}": "Convertir {ref}",
        "Delete element": "Eliminar elemento",
        "Delete {ref}": "Eliminar {ref}",
        "Discard the current unsaved changes?": (
            "¿Descartar los cambios sin guardar?"
        ),
        "Edit element": "Editar elemento",
        "Edit limits": "Editar límites",
        "Edit markers": "Editar marcadores",
        "Edit parasitics": "Editar parásitos",
        "Edit {ref} parasitics": "Editar parásitos de {ref}",
        "Export CSV": "Exportar CSV",
        "Export LTspice": "Exportar LTspice",
        "Export LTspice schematic": "Exportar esquema LTspice",
        "Export Qucs": "Exportar Qucs",
        "Export Qucs schematic": "Exportar esquema Qucs",
        "Export SPICE": "Exportar SPICE",
        "Export SPICE netlist": "Exportar netlist SPICE",
        "Export Smith chart": "Exportar carta de Smith",
        "Export Touchstone": "Exportar Touchstone",
        "Export Touchstone (.s2p)": "Exportar Touchstone (.s2p)",
        "Export build sheet": "Exportar hoja de montaje",
        "Export build sheet / BOM": "Exportar hoja de montaje / BOM",
        "Export failed": "Exportación fallida",
        "Import Touchstone": "Importar Touchstone",
        "Importing measured data…": "Importando datos medidos…",
        "Insert attenuator": "Insertar atenuador",
        "Insert element": "Insertar elemento",
        "Insert matching network": "Insertar red de adaptación",
        "Insert {kind} arm": "Insertar rama {kind}",
        "Invalid specification": "Especificación inválida",
        "Invalid value": "Valor inválido",
        "Maximum number of markers reached.": (
            "Se alcanzó el número máximo de marcadores."
        ),
        "Monte-Carlo": "Monte-Carlo",
        "Monte-Carlo failed": "Monte-Carlo fallido",
        "Monte-Carlo: {done}/{total} trials…": (
            "Monte-Carlo: {done}/{total} ensayos…"
        ),
        "Monte-Carlo: {trials} trials…": "Monte-Carlo: {trials} ensayos…",
        "Move marker": "Mover marcador",
        "Move the mouse over a plot first to set the cursor frequency.": (
            "Mueva primero el ratón sobre un gráfico para fijar la "
            "frecuencia del cursor."
        ),
        "New project": "Nuevo proyecto",
        "No reference frequency available.": (
            "No hay frecuencia de referencia disponible."
        ),
        "No variants.": "Sin variantes.",
        "Only L/C arms have parasitics.": (
            "Solo las ramas L/C tienen parásitos."
        ),
        "Only ideal L/C/R arms can be edited here.": (
            "Solo se pueden editar aquí ramas L/C/R ideales."
        ),
        "Open FilterDesk project": "Abrir proyecto FilterDesk",
        "Open failed": "Apertura fallida",
        "Optimize": "Optimizar",
        "Optimize failed": "Optimización fallida",
        "Optimizing…": "Optimizando…",
        "Parameter sweep: {count} variants": (
            "Barrido de parámetros: {count} variantes"
        ),
        "Project name:": "Nombre del proyecto:",
        "Ready": "Listo",
        "Realized {ref} as a physical winding": (
            "{ref} realizado como bobinado físico"
        ),
        "Rename project": "Renombrar proyecto",
        "Save FilterDesk project": "Guardar proyecto FilterDesk",
        "Save failed": "Guardado fallido",
        "Scale response": "Escalar respuesta",
        "Scaled response ×{factor:g}": "Respuesta escalada ×{factor:g}",
        "Sensitivity: {count} components analyzed": (
            "Sensibilidad: {count} componentes analizados"
        ),
        "Snap to {series}: values already on the grid": (
            "Ajustar a {series}: los valores ya están en la rejilla"
        ),
        "Snapped to {series} ({strategy}) — max change {delta:.2f}%": (
            "Ajustado a {series} ({strategy}) — cambio máx. {delta:.2f}%"
        ),
        "Synthesize a circuit first.": "Sintetice un circuito primero.",
        "Synthesize failed": "Síntesis fallida",
        "Synthesized — analyzing…": "Sintetizado — analizando…",
        "Theme: {mode}": "Tema: {mode}",
        "Tolerance for {ref}: ±{pct:g}%": "Tolerancia de {ref}: ±{pct:g}%",
        "Tune": "Ajuste",
        "Tune step": "Paso de ajuste",
        "Tune step for {ref}: {pct:g}%": (
            "Paso de ajuste de {ref}: {pct:g}%"
        ),
        "Tuned {ref} → {value:.6g}": "Ajustado {ref} → {value:.6g}",
        "Updated parasitics on {ref}": "Parásitos actualizados en {ref}",
        "Wrote {path}": "Escrito {path}",
        "Specification": "Especificación",
        "Schematic": "Esquemático",
        "Components": "Componentes",
        "Markers": "Marcadores",
        "Limits": "Límites",
        "Harmonics": "Armónicos",
    }
)


def tr(text: str, **fmt: object) -> str:
    """Translate an English source string (with optional ``str.format`` fields)."""
    translated = _ES.get(text, text) if _current is Language.ES else text
    return translated.format(**fmt) if fmt else translated


def set_language(language: Language) -> None:
    """Set the active GUI language and install/remove Qt's own translator."""
    global _current
    _current = language
    _install_qt_translator(language)


def current_language() -> Language:
    return _current


def language_from_code(code: str) -> Language:
    try:
        return Language(code)
    except ValueError:
        return Language.EN


def _install_qt_translator(language: Language) -> None:
    global _qt_translator
    app = QCoreApplication.instance()
    if app is None:
        return
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    if language is Language.EN:
        return
    translator = QTranslator()
    translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(f"qtbase_{language.value}", translations):
        app.installTranslator(translator)
        _qt_translator = translator


# --- Enum display labels ----------------------------------------------------
_FAMILY_LABELS = {
    ApproximationFamily.BUTTERWORTH: "Butterworth",
    ApproximationFamily.CHEBYSHEV_TYPE_I: "Chebyshev Type I",
    ApproximationFamily.CHEBYSHEV_TYPE_II: "Chebyshev Type II",
    ApproximationFamily.ELLIPTIC: "Elliptic",
    ApproximationFamily.BESSEL: "Bessel",
    ApproximationFamily.GAUSSIAN: "Gaussian",
    ApproximationFamily.LEGENDRE: "Legendre",
    ApproximationFamily.CONSTANT_K: "Constant-K",
    ApproximationFamily.M_DERIVED: "M-derived",
}

_RESPONSE_LABELS = {
    FilterResponse.LOW_PASS: "Low-pass",
    FilterResponse.HIGH_PASS: "High-pass",
    FilterResponse.BAND_PASS: "Band-pass",
    FilterResponse.BAND_STOP: "Band-stop",
}

_TOPOLOGY_LABELS = {
    TopologyId.LADDER_LP_SERIES_L_INPUT: "Series L input",
    TopologyId.LADDER_LP_SHUNT_C_INPUT: "Shunt C input",
    TopologyId.LADDER_HP_SERIES_C_INPUT: "Series C input",
    TopologyId.LADDER_HP_SHUNT_L_INPUT: "Shunt L input",
    TopologyId.LADDER_BP_SERIES_RES_INPUT: "Series resonator input",
    TopologyId.LADDER_BP_SHUNT_RES_INPUT: "Shunt resonator input",
    TopologyId.LADDER_BS_SERIES_TANK_INPUT: "Series tank input",
    TopologyId.LADDER_BS_SHUNT_TANK_INPUT: "Shunt tank input",
}

_ROLE_LABELS = {
    ElementRole.SERIES: "series",
    ElementRole.SHUNT: "shunt",
}


def family_label(family: ApproximationFamily) -> str:
    return tr(_FAMILY_LABELS[family])


def response_label(response: FilterResponse) -> str:
    return tr(_RESPONSE_LABELS[response])


def topology_label(topology: TopologyId) -> str:
    return tr(_TOPOLOGY_LABELS[topology])


def role_label(role: ElementRole) -> str:
    return tr(_ROLE_LABELS[role])


__all__ = [
    "Language",
    "current_language",
    "family_label",
    "language_from_code",
    "response_label",
    "role_label",
    "set_language",
    "topology_label",
    "tr",
]
