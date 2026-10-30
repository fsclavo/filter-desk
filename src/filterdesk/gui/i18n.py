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
        "Even-order Chebyshev I: classical equal-ripple prototype with an "
        "ideal output transformer (ADR-017); response and element values match "
        "the textbook tables."
    ): (
        "Chebyshev I de orden par: prototipo clásico de rizado constante con "
        "transformador de salida ideal (ADR-017); respuesta y valores coinciden "
        "con las tablas."
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
    "   | meas: —": "   | med: —",
    "   | meas: S21={s21:.2f} dB (Δ{ds21:+.2f}), "
    "S11={s11:.2f} dB (Δ{ds11:+.2f}), "
    "VSWR={vswr:.3f} (Δ{dvswr:+.3f}), "
    "∠S21={phase:.1f}° (Δ{dphase:+.1f}°)": (
        "   | med: S21={s21:.2f} dB (Δ{ds21:+.2f}), "
        "S11={s11:.2f} dB (Δ{ds11:+.2f}), "
        "VSWR={vswr:.3f} (Δ{dvswr:+.3f}), "
        "∠S21={phase:.1f}° (Δ{dphase:+.1f}°)"
    ),
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
        "&Tools": "&Herramientas",
        "&4-port mixed-mode…": "&Modo mixto de 4 puertos…",
        "4-port mixed-mode": "Modo mixto de 4 puertos",
        "Open .s4p…": "Abrir .s4p…",
        "Export CSV…": "Exportar CSV…",
        "Export JSON…": "Exportar JSON…",
        "Export mixed-mode CSV": "Exportar CSV de modo mixto",
        "Coaxial &stub notch…": "Notch con &stub coaxil…",
        "Coaxial stub notch": "Notch con stub coaxil",
        "Notch response": "Respuesta del notch",
        "Export coax CSV…": "Exportar CSV coaxil…",
        "Export coax notch CSV": "Exportar CSV de notch coaxil",
        "Design a shunt coax stub notch.": (
            "Diseñar un notch con stub coaxil en paralelo."
        ),
        "Cable preset": "Preset de cable",
        "Custom": "Personalizado",
        "Cable Z0 (Ohm)": "Z0 del cable (Ω)",
        "Through-line Z0 (Ohm)": "Z0 de la línea (Ω)",
        "Notch depth": "Profundidad del notch",
        "−3 dB bandwidth": "Ancho de banda a −3 dB",
        "Notch frequency": "Frecuencia de notch",
        "Velocity factor": "Factor de velocidad",
        "Stub type": "Tipo de stub",
        "Open λ/4": "Abierto λ/4",
        "Shorted λ/2": "Corto λ/2",
        "Cable loss (dB/m)": "Pérdida del cable (dB/m)",
        "Physical length": "Longitud física",
        "Guided wavelength": "Longitud de onda guiada",
        "Estimated loss": "Pérdida estimada",
        "Shunt stub across the feedline. Ideal narrowband notch; "
        "verify connectors, cable loss and the real velocity factor.": (
            "Stub en paralelo sobre la línea. Notch ideal de banda estrecha; "
            "verificar conectores, pérdida del cable y el factor de velocidad real."
        ),
        "Export mixed-mode JSON": "Exportar JSON de modo mixto",
        "Open 4-port Touchstone": "Abrir Touchstone de 4 puertos",
        "Open a 4-port Touchstone file to analyze.": (
            "Abrí un archivo Touchstone de 4 puertos para analizar."
        ),
        "Mixed-mode requires a 4-port file (got {ports}).": (
            "El modo mixto requiere un archivo de 4 puertos (se obtuvo {ports})."
        ),
        "4-port, {points} points, {fmin}–{fmax}; Zd={zd} Ω, Zc={zc} Ω{suffix}": (
            "4 puertos, {points} puntos, {fmin}–{fmax}; "
            "Zd={zd} Ω, Zc={zc} Ω{suffix}"
        ),
        "Mixed-mode S (dB)": "S en modo mixto (dB)",
        "Table": "Tabla",
        "Plot": "Gráfico",
        "Sdd21 (dB)": "Sdd21 (dB)",
        "Sdc21 (dB)": "Sdc21 (dB)",
        "Scd21 (dB)": "Scd21 (dB)",
        "Scc21 (dB)": "Scc21 (dB)",
        "&Synthesize + Analyze": "&Sintetizar + analizar",
        "&Band filter wizard…": "&Asistente de filtro de banda…",
        "Band filter wizard": "Asistente de filtro de banda",
        "Update spec from &circuit…": "Actualizar spec desde el &circuito…",
        "Applied {band} {kind} — analyzing…": (
            "{kind} de {band} aplicado — analizando…"
        ),
        "Quick preset": "Preset rápido",
        "Guided design": "Diseño guiado",
        "Auto": "Auto",
        "Choose a plotting range from the filter type on each synthesis": (
            "Elegir el rango del gráfico según el tipo de filtro en cada síntesis"
        ),
        "Snap after apply": "Ajustar a serie E después de aplicar",
        "Snap changed the response": "El ajuste cambió la respuesta",
        "Snapping to {series} no longer meets the passband/stopband target. "
        "Undo with Ctrl+Z or choose a finer series (E96 for VHF/UHF).": (
            "Ajustar a {series} ya no cumple el objetivo de banda de paso/rechazo. "
            "Deshacé con Ctrl+Z o elegí una serie más fina (E96 para VHF/UHF)."
        ),
        "Max insertion loss (dB)": "Pérdida de inserción máx. (dB)",
        "Min stopband attenuation (dB)": "Atenuación mín. en rechazo (dB)",
        "Pass edge (Hz)": "Borde de paso (Hz)",
        "Stop edge (Hz)": "Borde de rechazo (Hz)",
        "Stopband guard (% of band span)": "Margen de rechazo (% del ancho de banda)",
        "Max order": "Orden máximo",
        "Candidates": "Candidatos",
        "Source Z (Ohm)": "Z fuente (Ω)",
        "Load Z (Ohm)": "Z carga (Ω)",
        "Order": "Orden",
        "Passband": "Banda de paso",
        "Stop low": "Rechazo bajo",
        "Stop high": "Rechazo alto",
        "2f/3f": "2f/3f",
        "Status": "Estado",
        "Result": "Resultado",
        "Notes": "Notas",
        "Design": "Diseñar",
        "Apply to project": "Aplicar al proyecto",
        "Mode": "Modo",
        "OK": "OK",
        "No": "No",
        "Invalid band preset.": "Preset de banda inválido.",
        "No order met the requirements": "Ningún orden cumple los requisitos",
        "Order {order} Chebyshev-I {kind}; cutoff {cutoff}.": (
            "Orden {order} Chebyshev-I {kind}; corte {cutoff}."
        ),
        "Order {order} Chebyshev-I {kind}; center {center}; bandwidth {bandwidth}.": (
            "Orden {order} Chebyshev-I {kind}; centro {center}; "
            "ancho de banda {bandwidth}."
        ),
        "Update spec from circuit": "Actualizar spec desde el circuito",
        "Analyze a circuit first.": "Analiza primero un circuito.",
        "Cutoff": "Corte",
        "Center": "Centro",
        "Bandwidth": "Ancho de banda",
        "{change}\n\nDerived from {criterion}. "
        "Family, order, topology, ripple and stopband parameters stay "
        "unchanged. The circuit is not modified; Synthesize would create "
        "a new ideal circuit.": (
            "{change}\n\nDerivado de {criterion}. "
            "Familia, orden, topología, ripple y stopband no cambian. "
            "El circuito no se modifica; Synthesize crearía un circuito ideal nuevo."
        ),
        "Updated target spec from circuit response": (
            "Spec actualizado desde la respuesta del circuito"
        ),
        "&Attenuator pad…": "&Atenuador…",
        "Matching &network…": "Red de &adaptación…",
        "&Coil calculator…": "Calculadora de &bobinas…",
        "Trans&former / balun / unun…": "Transformador / &balun / unun…",
        "&Microstrip line…": "Línea &microstrip…",
        "&Distributed microstrip realization…": (
            "&Realización microstrip distribuida…"
        ),
        "Distributed microstrip realization": "Realización microstrip distribuida",
        "Export TLT SPICE…": "Exportar SPICE TLT…",
        "Export TLT SPICE": "Exportar SPICE TLT",
        "SPICE netlist (*.cir *.net);;All files (*)": (
            "Netlist SPICE (*.cir *.net);;Todos los archivos (*)"
        ),
        "Applied distributed microstrip realization on {substrate}": (
            "Realización microstrip distribuida aplicada en {substrate}"
        ),
        "Apply distributed microstrip realization": (
            "Aplicar realización microstrip distribuida"
        ),
        "Choose a low-pass specification first.": (
            "Elige primero una especificación pasabajos."
        ),
        "Confidence": "Confianza",
        "Substrate": "Sustrato",
        "Electrical length (deg)": "Longitud eléctrica (grados)",
        "Minimum Z0 (Ohm)": "Z0 mínima (Ohm)",
        "Maximum Z0 (Ohm)": "Z0 máxima (Ohm)",
        "Preview": "Vista previa",
        "Tune to &VNA measurement…": "Ajustar a medición del &VNA…",
        "Tune to VNA measurement": "Ajustar a medición del VNA",
        "VNA tuning": "Ajuste por VNA",
        "Applied VNA-guided tuning": "Ajuste guiado por VNA aplicado",
        "Import a measured Touchstone file first (File → Import).": (
            "Importa primero un archivo Touchstone medido (Archivo → Importar)."
        ),
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
        "Model &confidence…": "&Confianza de modelos…",
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
        "Sweep stop frequency, e.g. 1G": ("Frecuencia final del barrido, p. ej. 1G"),
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
        "Minimum order from Ap/As and pass/stop edges (LP/HP classical families)": (
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
        "Cleared tolerance for {ref}": "Tolerancia borrada para {ref}",
        "Component tolerance": "Tolerancia del componente",
        "Convert element": "Convertir elemento",
        "Convert {ref}": "Convertir {ref}",
        "Delete element": "Eliminar elemento",
        "Delete {ref}": "Eliminar {ref}",
        "Discard the current unsaved changes?": ("¿Descartar los cambios sin guardar?"),
        "Unsaved changes": "Cambios sin guardar",
        "Save changes before closing? Unsaved work will be lost.": (
            "¿Guardar los cambios antes de cerrar? Si no, se perderá el trabajo."
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
        "Monte-Carlo: {done}/{total} trials…": ("Monte-Carlo: {done}/{total} ensayos…"),
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
        "Only L/C arms have parasitics.": ("Solo las ramas L/C tienen parásitos."),
        "Only ideal L/C/R arms can be edited here.": (
            "Solo se pueden editar aquí ramas L/C/R ideales."
        ),
        "&Recent projects": "Proyectos &recientes",
        "No recent projects": "Sin proyectos recientes",
        "Clear recent projects": "Borrar proyectos recientes",
        "Missing recent project": "Proyecto reciente no encontrado",
        "The file no longer exists:\n{path}": "El archivo ya no existe:\n{path}",
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
        "transformer": "transformador",
        "balun": "balun",
        "Transformer / balun / unun": "Transformador / balun / unun",
        "Apply output balun": "Aplicar balun de salida",
        "Applied output balun ({kind})": "Balun de salida aplicado ({kind})",
        "Remove output balun": "Quitar balun de salida",
        "Removed output balun": "Balun de salida quitado",
        "BAL1 {ratio} ({kind})": "BAL1 {ratio} ({kind})",
        "T1 {ratio}:1 (ideal)": "T1 {ratio}:1 (ideal)",
        "ideal": "ideal",
        "Check spec &compliance…": "Verificar &cumplimiento…",
        "Spec compliance": "Cumplimiento de especificación",
        "Spec compliance: {result}": "Cumplimiento de especificación: {result}",
        "Passband ripple: {value} dB": "Rizado en banda: {value} dB",
        "Stopband attenuation: {value} dB": "Atenuación en stopband: {value} dB",
        "Edge loss: {values}": "Pérdida en bordes: {values}",
        "Issue: {detail}": "Problema: {detail}",
        "Note: {detail}": "Nota: {detail}",
        "Synthesize failed": "Síntesis fallida",
        "Synthesized — analyzing…": "Sintetizado — analizando…",
        "Theme: {mode}": "Tema: {mode}",
        "Tolerance for {ref}: ±{pct:g}%": "Tolerancia de {ref}: ±{pct:g}%",
        "Tune": "Ajuste",
        "Tune step": "Paso de ajuste",
        "Tune step for {ref}: {pct:g}%": ("Paso de ajuste de {ref}: {pct:g}%"),
        "Tuned {ref} → {value:.6g}": "Ajustado {ref} → {value:.6g}",
        "Updated parasitics on {ref}": "Parásitos actualizados en {ref}",
        "Wrote {path}": "Escrito {path}",
        "Specification": "Especificación",
        "Schematic": "Esquemático",
        "Components": "Componentes",
        "Markers": "Marcadores",
        "Limits": "Límites",
        "Harmonics": "Armónicos",
        "Name": "Nombre",
        "Source": "Origen",
        "Date": "Fecha",
        "VNA": "VNA",
        "Calibration": "Calibración",
        "Reference plane": "Plano de referencia",
        "Import…": "Importar…",
        "Use": "Usar",
        "Measurements": "Mediciones",
        "Clear measurements": "Borrar mediciones",
        "Delete all stored measurements from this project?": (
            "¿Eliminar todas las mediciones guardadas de este proyecto?"
        ),
        "Active measurement: {name}": "Medición activa: {name}",
        "Details…": "Detalles…",
        "Tune…": "Ajustar…",
        "Measurement details": "Detalles de medición",
        "VNA model": "Modelo de VNA",
        "Cables": "Cables",
        "Connectors": "Conectores",
        "Terminations": "Terminaciones",
        "Fixture": "Montaje",
        "Temperature (C)": "Temperatura (C)",
        "optional, °C": "opcional, °C",
        "Temperature must be a number.": "La temperatura debe ser un número.",
        "Updated measurement metadata: {name}": (
            "Metadatos de medición actualizados: {name}"
        ),
        "Measured at": "Medido el",
        "Operator": "Operador",
        "Comparison": "Comparación",
        "Analyze a design to compare against this measurement.": (
            "Analizá un diseño para comparar con esta medición."
        ),
        "Edit circuit": "Editar circuito",
        "Edit {ref}": "Editar {ref}",
        "Tune marker": "Ajustar marcador",
        "Realize {ref}": "Realizar {ref}",
    }
)


_ES.update(
    {
        "Add a marker at the cursor frequency.": (
            "Agregar un marcador en la frecuencia del cursor."
        ),
        "Apply finite Q, ESR/DCR and parasitic models.": (
            "Aplicar Q finito, ESR/DCR y modelos de parásitos."
        ),
        "Approximation family used for synthesis: Butterworth, Chebyshev, "
        "elliptic, Bessel, Gaussian, Legendre, constant-k or m-derived.": (
            "Familia de aproximación usada para la síntesis: Butterworth, "
            "Chebyshev, elíptica, Bessel, Gaussiana, Legendre, k constante "
            "o derivada m."
        ),
        "Calculate toroid and air-core coils.": (
            "Calcular bobinas toroidales y de aire."
        ),
        "Change the project title.": "Cambiar el título del proyecto.",
        "Check the response against the specification.": (
            "Verificar la respuesta contra la especificación."
        ),
        "Close FilterDesk.": "Cerrar FilterDesk.",
        "Compare design variants along one parameter.": (
            "Comparar variantes de diseño variando un parámetro."
        ),
        "Create a new filter project.": "Crear un proyecto de filtro nuevo.",
        "Derive center/cutoff and bandwidth from the analyzed response.": (
            "Derivar centro/corte y ancho de banda de la respuesta analizada."
        ),
        "Design an L/Pi/T matching network.": (
            "Diseñar una red de adaptación L/Pi/T."
        ),
        "Design and insert a T/Pi resistive attenuator.": (
            "Diseñar e insertar un atenuador resistivo T/Pi."
        ),
        "Design transformers, baluns, ununs and chokes.": (
            "Diseñar transformadores, baluns, ununs y choques."
        ),
        "Docks, overlays, theme and language.": (
            "Paneles, superposiciones, tema e idioma."
        ),
        "Documentation, model confidence and About.": (
            "Documentación, confianza de modelos y Acerca de."
        ),
        "Estimated stopband edge used by Estimate N; it is not part of "
        "the synthesized specification.": (
            "Borde de rechazo estimado usado por Estimar N; no forma parte "
            "de la especificación sintetizada."
        ),
        "Export the BOM and build sheet.": (
            "Exportar la lista de materiales y la hoja de construcción."
        ),
        "Filter response: low-pass, high-pass, band-pass or band-stop.": (
            "Respuesta del filtro: paso bajo, paso alto, paso banda o "
            "rechazo de banda."
        ),
        "Geometric center frequency of a band-pass or band-stop filter.": (
            "Frecuencia central geométrica de un filtro de paso banda o "
            "rechazo de banda."
        ),
        "Group delay from the slope of S21 phase (-dφ/dω).": (
            "Retardo de grupo a partir de la pendiente de la fase de S21 "
            "(-dφ/dω)."
        ),
        "Import an .s4p and inspect mixed-mode S data.": (
            "Importar un .s4p e inspeccionar datos S en modo mixto."
        ),
        "Import measured S11/S21 data from Touchstone.": (
            "Importar datos medidos de S11/S21 desde Touchstone."
        ),
        "Independent RF calculators and analysis tools.": (
            "Calculadoras y herramientas de análisis de RF independientes."
        ),
        "Input and output impedance versus frequency.": (
            "Impedancia de entrada y salida versus frecuencia."
        ),
        "Input voltage standing-wave ratio (VSWR).": (
            "Relación de onda estacionaria de tensión de entrada (ROE/VSWR)."
        ),
        "Inspect model validation and confidence levels.": (
            "Inspeccionar la validación y los niveles de confianza del modelo."
        ),
        "Ladder topology: which element faces the source.": (
            "Topología de escalera: qué elemento mira hacia la fuente."
        ),
        "Load/reference impedance at port 2.": (
            "Impedancia de carga/referencia en el puerto 2."
        ),
        "M-derived prototype parameter controlling the section shape.": (
            "Parámetro del prototipo derivado m que controla la forma de la "
            "sección."
        ),
        "Maximum passband ripple for Chebyshev-I, elliptic and related "
        "families.": (
            "Rizado máximo de banda de paso para Chebyshev-I, elíptica y "
            "familias relacionadas."
        ),
        "Microstrip line, stub and quarter-wave calculators.": (
            "Calculadoras de línea microstrip, stub y transformador de "
            "cuarto de onda."
        ),
        "Minimum stopband attenuation target used for order estimation "
        "and compliance checks.": (
            "Atenuación mínima de rechazo usada para estimar el orden y "
            "verificar el cumplimiento."
        ),
        "Number of reactive elements in the ladder. Higher order gives "
        "steeper rejection but more components.": (
            "Número de elementos reactivos en la escalera. Un orden mayor da "
            "más rechazo pero más componentes."
        ),
        "Open a saved FilterDesk project.": (
            "Abrir un proyecto FilterDesk guardado."
        ),
        "Open the user manual in a browser.": (
            "Abrir el manual de usuario en el navegador."
        ),
        "Optimize component values against the limits.": (
            "Optimizar los valores de los componentes contra los límites."
        ),
        "Passband edge or cutoff frequency. For BPF/BSF use Center and "
        "Bandwidth instead.": (
            "Frecuencia de corte o borde de paso. Para BPF/BSF usar Centro "
            "y Ancho de banda."
        ),
        "Passband width (BPF) or stopband width (BSF).": (
            "Ancho de banda de paso (BPF) o de rechazo (BSF)."
        ),
        "Project files, imports and exports.": (
            "Archivos de proyecto, importaciones y exportaciones."
        ),
        "Quick presets or guided band-filter design by requirements.": (
            "Presets rápidos o diseño guiado de filtros de banda por "
            "requisitos."
        ),
        "Rank components by sensitivity and tuning direction.": (
            "Clasificar componentes por sensibilidad y dirección de ajuste."
        ),
        "Realize a low-pass filter with microstrip lines.": (
            "Realizar un filtro pasa bajos con líneas microstrip."
        ),
        "Redo the last undone edit.": "Rehacer la última edición deshecha.",
        "Reverse transmission (S12) and output reflection (S22).": (
            "Transmisión inversa (S12) y reflexión de salida (S22)."
        ),
        "Round L/C values to a standard E-series grid.": (
            "Redondear valores de L/C a una serie E estándar."
        ),
        "Run a Monte-Carlo tolerance analysis.": (
            "Ejecutar un análisis de tolerancias Monte-Carlo."
        ),
        "S21 and S11 phase versus frequency.": (
            "Fase de S21 y S11 versus frecuencia."
        ),
        "Save the current project.": "Guardar el proyecto actual.",
        "Save the project under a new name.": (
            "Guardar el proyecto con otro nombre."
        ),
        "Scale the filter response in frequency.": (
            "Escalar la respuesta del filtro en frecuencia."
        ),
        "Show or hide harmonic marker lines.": (
            "Mostrar u ocultar las líneas de armónicos."
        ),
        "Show or hide the Monte-Carlo envelope.": (
            "Mostrar u ocultar la envolvente Monte-Carlo."
        ),
        "Show or hide the measured overlay.": (
            "Mostrar u ocultar la superposición medida."
        ),
        "Show version and license information.": (
            "Mostrar versión e información de licencia."
        ),
        "Smith chart of S11 (and S22 for 2-port data).": (
            "Carta de Smith de S11 (y S22 para datos de 2 puertos)."
        ),
        "Source/reference impedance at port 1.": (
            "Impedancia de fuente/referencia en el puerto 1."
        ),
        "Synthesis, tuning, optimization and compliance.": (
            "Síntesis, ajuste, optimización y cumplimiento."
        ),
        "Synthesize the current specification and analyze it.": (
            "Sintetizar la especificación actual y analizarla."
        ),
        "Transmission and reflection magnitude versus frequency.": (
            "Magnitud de transmisión y reflexión versus frecuencia."
        ),
        "Trim component values to a measured VNA response.": (
            "Ajustar valores de componentes a una respuesta de VNA medida."
        ),
        "Undo the last design edit.": "Deshacer la última edición de diseño.",
        "Undo, redo and measurement markers.": (
            "Deshacer, rehacer y marcadores de medición."
        ),
        "Crossover": "Cruce",
        "Design complete.": "Diseño completado.",
        "Diplexer LPF+HPF": "Diplexer LPF+HPF",
        "&Diplexer LPF+HPF…": "&Diplexer LPF+HPF…",
        "Design an LPF+HPF diplexer.": "Diseñar un diplexer LPF+HPF.",
        "Diplexer designer": "Diseñador de diplexer",
        "&Diplexer designer…": "&Diseñador de diplexer…",
        "Design an LPF+HPF or BPF+BPF diplexer.": (
            "Diseñar un diplexer LPF+HPF o BPF+BPF."
        ),
        "LPF + HPF": "LPF + HPF",
        "BPF + BPF": "BPF + BPF",
        "Type": "Tipo",
        "Low band center": "Centro de banda baja",
        "Low band bandwidth": "Ancho de banda baja",
        "High band center": "Centro de banda alta",
        "High band bandwidth": "Ancho de banda alta",
        "Port 1 = common, port 2 = low band, port 3 = high band.": (
            "Puerto 1 = común, puerto 2 = banda baja, puerto 3 = banda alta."
        ),
        "Export .s3p…": "Exportar .s3p…",
        "Export diplexer .s3p": "Exportar diplexer .s3p",
        "Export diplexer branch .s2p": "Exportar rama del diplexer .s2p",
        "Export high .s2p…": "Exportar .s2p alto…",
        "Export low .s2p…": "Exportar .s2p bajo…",
        "High band": "Banda alta",
        "High insertion loss": "Pérdida de inserción alta",
        "High out S31 (dB)": "Salida alta S31 (dB)",
        "High out-of-band": "Fuera de banda alta",
        "High return loss": "Pérdida de retorno alta",
        "High-pass cutoff": "Corte paso-alto",
        "Ideal common-node LC model: no antenna, cavity, isolation "
        "network, thermal or high-power validation. Check the combined "
        "3-port response, not each branch alone.": (
            "Modelo LC ideal con nodo común: sin antena, cavidad, red de "
            "aislamiento, validación térmica ni de alta potencia. Verifique "
            "la respuesta combinada de 3 puertos, no cada rama por separado."
        ),
        "Input S11 (dB)": "Entrada S11 (dB)",
        "Low band": "Banda baja",
        "Low branch: {low} components; high branch: {high} components.": (
            "Rama baja: {low} componentes; rama alta: {high} componentes."
        ),
        "Low insertion loss": "Pérdida de inserción baja",
        "Low out S21 (dB)": "Salida baja S21 (dB)",
        "Low out-of-band": "Fuera de banda baja",
        "Low return loss": "Pérdida de retorno baja",
        "Low-pass cutoff": "Corte paso-bajo",
        "Port 1 = common, port 2 = low-pass, port 3 = high-pass.": (
            "Puerto 1 = común, puerto 2 = paso-bajo, puerto 3 = paso-alto."
        ),
        "Reference Z0 (Ohm)": "Z0 de referencia (Ohm)",
        "Ripple (dB)": "Rizado (dB)",
        "Sweep start": "Inicio del barrido",
        "Sweep stop": "Fin del barrido",
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
