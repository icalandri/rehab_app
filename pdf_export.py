"""
Exportación a PDF de una Evaluación de Admisión a Rehabilitación.
Genera el documento completo (7 módulos + tablas hijas) con branding Azikna.
Sin dependencias de red: usa fpdf2 y, si existe, el logo en assets/.
"""
from __future__ import annotations

import datetime as dt
import os
from fpdf import FPDF

# --- Paleta Azikna (RGB) ---
TEAL = (65, 127, 146)      # #417f92
LIGHT = (225, 237, 244)    # #e1edf4
MID = (208, 227, 236)      # #d0e3ec
PALE = (237, 244, 248)     # #edf4f8
TEXT = (32, 50, 58)        # gris azulado oscuro

_LOGO = os.path.join(os.path.dirname(__file__), "assets", "azikna_logo.png")


def _s(x) -> str:
    """Texto seguro para fuentes core (latin-1)."""
    if x is None:
        return ""
    if isinstance(x, bool):
        return "Sí" if x else "No"
    if isinstance(x, (list, tuple)):
        x = ", ".join(str(i) for i in x)
    s = str(x)
    repl = {"—": "-", "–": "-", "·": "-", "“": '"', "”": '"', "’": "'",
            "✓": "Si", "⚑": "", "★": "*", "₂": "2"}
    for a, b in repl.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def _pretty(v) -> str:
    """Formatea valores de enum/bool/listas para mostrar."""
    if isinstance(v, bool):
        return "Sí" if v else "No"
    if isinstance(v, (list, tuple)):
        return ", ".join(_pretty(i) for i in v)
    if isinstance(v, str):
        return v.replace("_", " ").capitalize()
    return str(v)


# Etiquetas por módulo: (clave_en_adm, etiqueta)
MOD0 = [("fecha_entrevista", "Fecha de entrevista"), ("profesional", "Profesional"),
        ("modalidad", "Modalidad"), ("informante", "Informante"),
        ("relacion_acompanante", "Relación del acompañante")]
MOD1 = [("edad", "Edad"), ("residencia", "Tipo de residencia"),
        ("residencia_otro", "Residencia (otro)"),
        ("vive_solo", "¿Vive solo/a?"), ("cuidador_nombre", "Cuidador principal"),
        ("cuidador_vinculo", "Vínculo del cuidador"),
        ("cuidador_disponibilidad", "Disponibilidad del cuidador"),
        ("cuidador_formal", "Cuidador formal domiciliario"),
        ("anios_escolaridad", "Años de escolaridad"),
        ("actividad_laboral_previa", "Actividad laboral previa"),
        ("actividad_fisica", "Actividad física")]
MOD3 = [("anticoagulado", "Anticoagulado"), ("anticoag_tipo", "Tipo anticoagulante"),
        ("anticoag_control_rin", "Control RIN"), ("toma_insulina", "Toma insulina"),
        ("insulina_esquema", "Esquema insulina"),
        ("corticoides_cronicos", "Corticoides crónicos"),
        ("corticoides_detalle", "Corticoides (detalle)"),
        ("medicacion_memoria_conducta", "Medicación memoria/conducta"),
        ("dificultad_autoadministracion", "Dificultad autoadministración")]
MOD4 = [("motivo_descripcion", "Motivo principal"),
        ("motivo_fecha_inicio", "Fecha de inicio / evento"),
        ("motivo_internacion_previa", "Internación previa relacionada"),
        ("hosp_12m_numero", "Hospitalizaciones (12m)"),
        ("hosp_12m_motivos", "Motivos hospitalización"),
        ("hosp_12m_uci", "Alguna en UCI/UTI"),
        ("hosp_12m_uci_duracion", "Duración UCI"),
        ("guardia_3m_numero", "Consultas guardia (3m)"),
        ("guardia_3m_motivos", "Motivos guardia")]
MOD5 = [("deambulacion", "Deambulación"), ("ayuda_tecnica", "Ayuda técnica"),
        ("sube_escaleras", "Sube escaleras"), ("distancia_marcha", "Distancia de marcha"),
        ("avd_alimentacion", "Barthel · Alimentación"),
        ("avd_higiene", "Barthel · Higiene/Baño"),
        ("avd_vestido", "Barthel · Vestido"),
        ("avd_continencia", "Barthel · Continencia"),
        ("avd_traslados", "Barthel · Traslados"),
        ("avd_observaciones", "Barthel · Observaciones"),
        ("olvidos_previos", "Olvidos previos"),
        ("dx_cognitivo_previo", "Dx cognitivo previo"),
        ("dx_cognitivo_cual", "Dx cognitivo (cuál)"),
        ("mmse_puntaje", "MMSE"), ("orientacion_basal", "Orientación basal"),
        ("idioma_principal", "Idioma principal"),
        ("dificultad_comunicacion", "Dificultad comunicación"),
        ("dificultad_comunicacion_detalle", "Dificultad (detalle)"),
        ("audicion", "Audición"), ("vision", "Visión")]


class _PDF(FPDF):
    def header(self):
        if os.path.exists(_LOGO):
            try:
                self.image(_LOGO, x=10, y=8, h=12)
            except Exception:
                pass
        self.set_xy(0, 10)
        self.set_text_color(*TEAL)
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 6, _s("Evaluación Integral de Admisión a Rehabilitación"),
                  align="C")
        self.set_xy(0, 16)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, _s("Fundación Azikna"), align="C")
        self.ln(10)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(150, 150, 150)
        gen = dt.datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 5, _s(f"Generado {gen}  ·  Página {self.page_no()}"),
                  align="C")


def _section(pdf: _PDF, titulo: str):
    pdf.ln(2)
    pdf.set_fill_color(*TEAL)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, _s("  " + titulo), fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*TEXT)


def _kv_rows(pdf: _PDF, data: dict, campos: list):
    pdf.set_font("Helvetica", "", 9)
    fill = False
    for clave, etiqueta in campos:
        if clave not in data:
            continue
        val = _pretty(data[clave])
        if val == "":
            continue
        pdf.set_fill_color(*(PALE if fill else (255, 255, 255)))
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(60, 6, _s(etiqueta), border=0, fill=True)
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 6, _s(val), border=0, fill=True,
                       new_x="LMARGIN", new_y="NEXT")
        fill = not fill


def _tabla(pdf: _PDF, titulo: str, headers: list, filas: list, anchos: list):
    if not filas:
        return
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*TEAL)
    pdf.cell(0, 6, _s(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*TEXT)
    # cabecera
    pdf.set_fill_color(*MID)
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(headers, anchos):
        pdf.cell(w, 6, _s(h), border=1, fill=True, align="C")
    pdf.ln()
    # filas
    pdf.set_font("Helvetica", "", 8)
    fill = False
    for fila in filas:
        pdf.set_fill_color(*(PALE if fill else (255, 255, 255)))
        y0 = pdf.get_y()
        x0 = pdf.get_x()
        # altura dinámica simple: 6 por defecto
        for val, w in zip(fila, anchos):
            pdf.cell(w, 6, _s(str(val) if val is not None else ""),
                     border=1, fill=True)
        pdf.ln()
        fill = not fill


def generar_pdf(paciente: dict, admision: dict,
                antecedentes: list, cirugias: list, alergias: list,
                medicacion: list, problemas: list, factores: list) -> bytes:
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # --- Identificación del paciente ---
    pdf.set_fill_color(*LIGHT)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, _s(f"  {paciente.get('apellido_nombre','')}"),
             fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    fnac = paciente.get("fecha_nacimiento")
    sub = f"  DNI: {paciente.get('dni','')}"
    if fnac:
        sub += f"    Fecha de nacimiento: {fnac}"
    pdf.cell(0, 6, _s(sub), fill=True, new_x="LMARGIN", new_y="NEXT")

    _section(pdf, "Módulo 0 · Datos de la entrevista")
    _kv_rows(pdf, admision, MOD0)
    _section(pdf, "Módulo 1 · Demográficos y situación basal")
    _kv_rows(pdf, admision, MOD1)

    _section(pdf, "Módulo 2 · Antecedentes médicos")
    _tabla(pdf, "Antecedentes presentes",
           ["Categoría", "Antecedente", "Detalle"],
           [(_pretty(a.get("categoria")), a.get("item"),
             (a.get("detalle") or "") + ((" / " + a["observaciones"]) if a.get("observaciones") else ""))
            for a in antecedentes],
           [38, 60, 92])
    _tabla(pdf, "Cirugías", ["#", "Tipo", "Fecha aprox."],
           [(i + 1, c.get("tipo_cirugia"), c.get("fecha_aprox"))
            for i, c in enumerate(cirugias)], [10, 120, 60])
    _tabla(pdf, "Alergias", ["Tipo", "Descripción"],
           [(_pretty(a.get("tipo")), a.get("descripcion")) for a in alergias],
           [40, 150])

    _section(pdf, "Módulo 3 · Medicación y cribado farmacológico")
    _tabla(pdf, "Medicación habitual",
           ["Medicamento", "Dosis", "Frec.", "Vía", "Prescriptor", "Indicación"],
           [(m.get("medicamento"), m.get("dosis"), m.get("frecuencia"),
             m.get("via"), m.get("prescriptor"), m.get("indicacion"))
            for m in medicacion], [45, 25, 25, 18, 32, 45])
    _kv_rows(pdf, admision, MOD3)

    _section(pdf, "Módulo 4 · Problemas de salud activos")
    _kv_rows(pdf, admision, MOD4)
    _tabla(pdf, "Problemas activos secundarios",
           ["Problema", "Descripción", "Estado", "Médico"],
           [(p.get("problema"), p.get("descripcion"), _pretty(p.get("estado")),
             p.get("medico_responsable")) for p in problemas],
           [45, 70, 35, 40])

    _section(pdf, "Módulo 5 · Valoración funcional basal")
    _kv_rows(pdf, admision, MOD5)

    _section(pdf, "Módulo 6 · Factores de riesgo (banderas rojas)")
    n_fac = sum(1 for f in factores if f.get("presente"))
    if n_fac <= 2:
        sem_rgb, sem_txt = (46, 125, 50), "Riesgo bajo"
    elif n_fac <= 5:
        sem_rgb, sem_txt = (249, 168, 37), "Riesgo moderado"
    else:
        sem_rgb, sem_txt = (198, 40, 40), "Riesgo alto"
    pdf.ln(1)
    pdf.set_fill_color(*sem_rgb)
    pdf.cell(7, 7, "", fill=True, border=0)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*TEXT)
    pdf.cell(0, 7, _s(f"  Semáforo: {sem_txt}  -  {n_fac}/10 factores presentes"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    _tabla(pdf, "Factores presentes", ["Factor", "Detalle"],
           [(f.get("factor"), f.get("detalle")) for f in factores if f.get("presente")],
           [80, 110])

    _section(pdf, "Módulo 7 · Cierre y observaciones")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 6, _s(admision.get("observaciones") or "—"))

    out = pdf.output()
    return bytes(out)
