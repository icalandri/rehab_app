"""
Formulario web â€” EvaluaciÃ³n Integral de AdmisiÃ³n a RehabilitaciÃ³n
Streamlit + Postgres (Supabase). Carga 1 admisiÃ³n por envÃ­o.

Ejecutar local:   streamlit run app.py
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

import os

import auth
import db
import pdf_export

st.set_page_config(page_title="AdmisiÃ³n a RehabilitaciÃ³n",
                   page_icon="ðŸ¥", layout="wide")

# --------------------------- BRANDING AZIKNA ---------------------------
_LOGO = os.path.join(os.path.dirname(__file__), "assets", "azikna_logo.png")
if os.path.exists(_LOGO):
    try:
        st.logo(_LOGO)
    except Exception:
        pass

st.markdown(
    """
    <style>
      h1, h2, h3 { color: #2c5e6e; }
      .stTabs [data-baseweb="tab-list"] { gap: 4px; }
      .stTabs [aria-selected="true"] { color: #417f92; }
      .block-container { padding-top: 2.5rem; }
      div.stButton > button[kind="primary"] { background-color: #417f92; border-color: #417f92; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------- LOGIN ---------------------------
usuario = auth.login_gate()
auth.logout_button()

# --------------------------- NAVEGACIÃ“N ---------------------------
es_admin = usuario.get("rol") == "admin"
vistas = ["ðŸ“ Cargar evaluaciÃ³n"]
if es_admin:
    vistas.append("ðŸ‘¥ GestiÃ³n de usuarios")
vista = st.sidebar.radio("Vista", vistas) if len(vistas) > 1 else vistas[0]


def panel_usuarios():
    st.title("ðŸ‘¥ GestiÃ³n de usuarios")
    st.caption("Solo administradores. Las contraseÃ±as se guardan hasheadas (bcrypt).")

    st.subheader("Usuarios existentes")
    usuarios = db.listar_usuarios()
    if usuarios:
        st.dataframe(
            [{"Usuario": u["usuario"], "Nombre": u["nombre"], "Rol": u["rol"],
              "Activo": "SÃ­" if u["activo"] else "No"} for u in usuarios],
            hide_index=True, use_container_width=True,
        )

    st.subheader("Crear / actualizar usuario")
    with st.form("nuevo_usuario", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            nu = st.text_input("Usuario (login)")
            nnom = st.text_input("Nombre completo")
        with c2:
            nrol = st.selectbox("Rol", ["cargador", "lector", "admin"],
                                help="cargador: carga datos Â· lector: solo lectura Â· admin: ademÃ¡s gestiona usuarios")
            np1 = st.text_input("ContraseÃ±a", type="password")
            np2 = st.text_input("Repetir contraseÃ±a", type="password")
        crear = st.form_submit_button("Crear / actualizar usuario", type="primary")

    if crear:
        if not nu.strip() or not nnom.strip():
            st.error("Usuario y nombre son obligatorios.")
        elif np1 != np2:
            st.error("Las contraseÃ±as no coinciden.")
        elif len(np1) < 8:
            st.error("La contraseÃ±a debe tener al menos 8 caracteres.")
        else:
            db.crear_usuario(nu, nnom, auth.hash_password(np1), nrol)
            st.success(f"âœ… Usuario '{nu}' creado/actualizado con rol '{nrol}'.")
            st.rerun()

    st.subheader("Activar / desactivar")
    st.caption("Desactivar impide el login sin borrar el historial de cargas.")
    for u in usuarios:
        if u["usuario"] == usuario["usuario"]:
            continue  # no permitir auto-desactivarse
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{u['usuario']}** â€” {u['nombre']} ({u['rol']})")
        if u["activo"]:
            if col2.button("Desactivar", key=f"off_{u['id']}"):
                db.set_usuario_activo(u["id"], False); st.rerun()
        else:
            if col2.button("Activar", key=f"on_{u['id']}"):
                db.set_usuario_activo(u["id"], True); st.rerun()


if vista == "ðŸ‘¥ GestiÃ³n de usuarios":
    panel_usuarios()
    st.stop()

st.title("ðŸ¥ EvaluaciÃ³n Integral de AdmisiÃ³n a RehabilitaciÃ³n")
st.caption("Una fila por evaluaciÃ³n. El paciente se identifica por DNI (se crea o reutiliza).")

# CatÃ¡logos (desde la base)
CAT_ANT = db.get_antecedentes_catalogo()
CAT_FAC = db.get_factores_catalogo()


def sel(label, opciones, key, help=None):
    return st.selectbox(label, [""] + opciones, key=key, help=help) or None


def tri(label, key):
    """Booleano de 3 estados: SÃ­ / No / (sin dato)."""
    v = st.radio(label, ["â€”", "SÃ­", "No"], horizontal=True, key=key)
    return {"â€”": None, "SÃ­": True, "No": False}[v]


tabs = st.tabs([
    "0 Â· Entrevista", "1 Â· DemogrÃ¡ficos", "2 Â· Antecedentes",
    "3 Â· MedicaciÃ³n", "4 Â· Problemas activos", "5 Â· Funcional",
    "6 Â· Factores de riesgo", "7 Â· Cierre",
])

adm: dict = {}
pac: dict = {}

# ===================== MÃ“DULO 0 â€” ENTREVISTA =====================
with tabs[0]:
    c1, c2 = st.columns(2)
    with c1:
        adm["fecha_entrevista"] = st.date_input("Fecha de entrevista", dt.date.today())
        adm["profesional"] = st.text_input("Profesional") or None
        adm["modalidad"] = sel("Modalidad",
                               ["presencial", "telefonica", "videollamada"], "modalidad")
    with c2:
        adm["informante"] = sel("Informante",
                                ["paciente_solo", "con_acompanante", "solo_acompanante"],
                                "informante")
        adm["relacion_acompanante"] = st.text_input("RelaciÃ³n del acompaÃ±ante") or None

# ===================== MÃ“DULO 1 â€” DEMOGRÃFICOS =====================
with tabs[1]:
    st.subheader("1.1 Datos personales")
    c1, c2, c3 = st.columns(3)
    with c1:
        pac["apellido_nombre"] = st.text_input("Apellido y nombre *")
        pac["dni"] = st.text_input("DNI *")
    with c2:
        adm["edad"] = st.number_input("Edad", 0, 130, value=None, step=1)
        fnac = st.date_input("Fecha de nacimiento (opc.)", value=None,
                             min_value=dt.date(1900, 1, 1), max_value=dt.date.today())
        pac["fecha_nacimiento"] = fnac
    with c3:
        adm["residencia"] = sel("Tipo de residencia",
                               ["domicilio_propio", "familiar", "geriatrico", "otro"],
                               "residencia")
        adm["residencia_otro"] = st.text_input("Detalle (si 'otro')") or None

    st.subheader("1.2 Red de soporte")
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["vive_solo"] = tri("Â¿Vive solo/a?", "vive_solo")
        adm["cuidador_formal"] = tri("Â¿Servicio de cuidador formal domiciliario?", "cuid_formal")
    with c2:
        adm["cuidador_nombre"] = st.text_input("Cuidador principal (nombre)") or None
        adm["cuidador_vinculo"] = st.text_input("VÃ­nculo del cuidador") or None
    with c3:
        adm["cuidador_disponibilidad"] = sel("Disponibilidad del cuidador",
                                             ["permanente", "parcial", "ninguna"],
                                             "cuid_disp")

    st.subheader("1.3 Nivel educativo y actividad previa")
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["anios_escolaridad"] = st.number_input("AÃ±os de escolaridad formal",
                                                   0, 30, value=None, step=1)
    with c2:
        adm["actividad_laboral_previa"] = st.text_input("Actividad laboral previa") or None
    with c3:
        adm["actividad_fisica"] = sel("Actividad fÃ­sica habitual",
                                     ["sedentario", "leve", "moderada", "intensa"],
                                     "act_fis")

# ===================== MÃ“DULO 2 â€” ANTECEDENTES =====================
with tabs[2]:
    st.subheader("2.1â€“2.9 Antecedentes mÃ©dicos")
    st.caption("TildÃ¡ los presentes y completÃ¡ el detalle (fecha, tipo, territorio, etc.).")
    df_ant = pd.DataFrame([
        {"id": r["id"], "categoria": r["categoria"], "item": r["item"],
         "presente": False, "detalle": "", "observaciones": ""}
        for r in CAT_ANT
    ])
    ant_edit = st.data_editor(
        df_ant, hide_index=True, use_container_width=True, key="ant",
        column_config={
            "id": None,
            "categoria": st.column_config.TextColumn("CategorÃ­a", disabled=True),
            "item": st.column_config.TextColumn("Antecedente", disabled=True, width="large"),
            "presente": st.column_config.CheckboxColumn("Presente"),
            "detalle": st.column_config.TextColumn("Detalle"),
            "observaciones": st.column_config.TextColumn("Observaciones"),
        },
    )

    st.subheader("2.10 CirugÃ­as relevantes")
    cir_edit = st.data_editor(
        pd.DataFrame(columns=["tipo_cirugia", "fecha_aprox"]),
        num_rows="dynamic", hide_index=True, use_container_width=True, key="cir",
        column_config={
            "tipo_cirugia": st.column_config.TextColumn("Tipo de cirugÃ­a", width="large"),
            "fecha_aprox": st.column_config.TextColumn("Fecha aproximada"),
        },
    )

    st.subheader("2.11 Alergias e intolerancias")
    alg_edit = st.data_editor(
        pd.DataFrame([{"tipo": t, "descripcion": ""}
                      for t in ["medicamentosa", "alimentaria", "otras"]]),
        hide_index=True, use_container_width=True, key="alg",
        column_config={
            "tipo": st.column_config.TextColumn("Tipo", disabled=True),
            "descripcion": st.column_config.TextColumn("DescripciÃ³n (agente + reacciÃ³n)", width="large"),
        },
    )

# ===================== MÃ“DULO 3 â€” MEDICACIÃ“N =====================
with tabs[3]:
    st.subheader("3 Â· MedicaciÃ³n habitual")
    st.caption("IncluÃ­ automedicaciÃ³n y suplementos. AgregÃ¡ filas con el botÃ³n âž•.")
    med_edit = st.data_editor(
        pd.DataFrame(columns=["medicamento", "dosis", "frecuencia", "via",
                              "prescriptor", "indicacion"]),
        num_rows="dynamic", hide_index=True, use_container_width=True, key="med",
        column_config={
            "medicamento": st.column_config.TextColumn("Medicamento (genÃ©rico)"),
            "dosis": "Dosis", "frecuencia": "Frecuencia", "via": "VÃ­a",
            "prescriptor": "Prescriptor", "indicacion": "IndicaciÃ³n",
        },
    )

    st.subheader("Cribado farmacolÃ³gico adicional")
    c1, c2 = st.columns(2)
    with c1:
        adm["anticoagulado"] = tri("Â¿Anticoagulado?", "antico")
        adm["anticoag_tipo"] = sel("Tipo de anticoagulante", ["avk", "naco"], "antico_tipo",
                                   help="AVK = warfarina/acenocumarol")
        adm["anticoag_control_rin"] = tri("Â¿Control de RIN?", "rin")
        adm["toma_insulina"] = tri("Â¿Toma insulina?", "insu")
        adm["insulina_esquema"] = sel("Esquema de insulina",
                                      ["basal", "basal_bolo", "bomba"], "insu_esq")
    with c2:
        adm["corticoides_cronicos"] = tri("Â¿Corticoides crÃ³nicos?", "cort")
        adm["corticoides_detalle"] = st.text_input("Corticoides: dosis y duraciÃ³n") or None
        adm["medicacion_memoria_conducta"] = tri(
            "Â¿MedicaciÃ³n memoria/conducta? (anticolinesterÃ¡sicos, memantina, antipsicÃ³ticos)", "memo")
        adm["dificultad_autoadministracion"] = st.text_input(
            "Â¿Dificultades para administrarse la medicaciÃ³n de forma autÃ³noma?") or None

# ===================== MÃ“DULO 4 â€” PROBLEMAS ACTIVOS =====================
with tabs[4]:
    st.info("Preguntar por las Ãºltimas 4â€“8 semanas. MÃ³dulo clave para la planificaciÃ³n.")
    st.subheader("4.1 Motivo principal de rehabilitaciÃ³n")
    adm["motivo_descripcion"] = st.text_area("DescripciÃ³n clÃ­nica") or None
    c1, c2 = st.columns(2)
    with c1:
        adm["motivo_fecha_inicio"] = st.text_input("Fecha de inicio / evento desencadenante") or None
    with c2:
        adm["motivo_internacion_previa"] = tri("Â¿InternaciÃ³n previa relacionada?", "mot_int")

    st.subheader("4.2 Problemas de salud activos secundarios")
    prob_edit = st.data_editor(
        pd.DataFrame(columns=["problema", "descripcion", "estado", "medico_responsable"]),
        num_rows="dynamic", hide_index=True, use_container_width=True, key="prob",
        column_config={
            "problema": "Problema",
            "descripcion": st.column_config.TextColumn("DescripciÃ³n / EvoluciÃ³n", width="large"),
            "estado": st.column_config.SelectboxColumn(
                "Estado", options=["estable", "seguimiento", "descompensado"]),
            "medico_responsable": "MÃ©dico responsable",
        },
    )

    st.subheader("4.3 Hospitalizaciones (Ãºltimos 12 meses)")
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["hosp_12m_numero"] = st.number_input("NÂ° internaciones", 0, value=None, step=1, key="h1")
    with c2:
        adm["hosp_12m_uci"] = tri("Â¿Alguna en UCI/UTI?", "uci")
        adm["hosp_12m_uci_duracion"] = st.text_input("DuraciÃ³n aprox. en UCI") or None
    with c3:
        adm["hosp_12m_motivos"] = st.text_area("Motivos principales") or None

    st.subheader("4.4 Consultas a guardia (Ãºltimos 3 meses)")
    c1, c2 = st.columns(2)
    with c1:
        adm["guardia_3m_numero"] = st.number_input("NÂ° consultas", 0, value=None, step=1, key="g1")
    with c2:
        adm["guardia_3m_motivos"] = st.text_area("Motivos", key="g2") or None

# ===================== MÃ“DULO 5 â€” FUNCIONAL =====================
with tabs[5]:
    st.subheader("5.1 Movilidad")
    c1, c2 = st.columns(2)
    with c1:
        adm["deambulacion"] = sel("DeambulaciÃ³n independiente",
                                 ["independiente", "no", "con_ayuda_tecnica"], "deamb")
        adm["ayuda_tecnica"] = st.multiselect("Ayuda tÃ©cnica",
                                             ["baston", "andador", "silla_ruedas"], key="ayudat") or None
    with c2:
        adm["sube_escaleras"] = sel("Sube escaleras", ["si", "no", "con_ayuda"], "esc")
        adm["distancia_marcha"] = st.text_input("Distancia de marcha habitual", "50 mtrs") or None

    st.subheader("5.2 Ãndice de Barthel referido â€” independencia PREVIA al evento")
    niveles = ["independiente", "asistido", "dependiente"]
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["avd_alimentacion"] = sel("AlimentaciÃ³n", niveles, "avd1")
        adm["avd_higiene"] = sel("Higiene / BaÃ±o", niveles, "avd2")
    with c2:
        adm["avd_vestido"] = sel("Vestido", niveles, "avd3")
        adm["avd_continencia"] = sel("Continencia", niveles, "avd4")
    with c3:
        adm["avd_traslados"] = sel("Traslados / Transferencias", niveles, "avd5")
    adm["avd_observaciones"] = st.text_input("Observaciones AVD") or None

    st.subheader("5.3 CogniciÃ³n basal")
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["olvidos_previos"] = sel("Â¿Olvidos frecuentes previos?",
                                    ["si", "no", "no_sabe"], "olv")
    with c2:
        adm["dx_cognitivo_previo"] = tri("DiagnÃ³stico cognitivo previo", "dxc")
        adm["dx_cognitivo_cual"] = st.text_input("Â¿CuÃ¡l?") or None
    with c3:
        adm["mmse_puntaje"] = st.number_input("MMSE (0â€“30)", 0, 30, value=None, step=1)
        adm["orientacion_basal"] = sel("OrientaciÃ³n tempo-espacial basal",
                                      ["conservada", "parcial", "ausente"], "ori")

    st.subheader("5.4 ComunicaciÃ³n y sensopercepciÃ³n")
    c1, c2 = st.columns(2)
    with c1:
        adm["idioma_principal"] = st.text_input("Idioma principal") or None
        adm["dificultad_comunicacion"] = tri("Dificultades previas en la comunicaciÃ³n", "dcom")
        adm["dificultad_comunicacion_detalle"] = st.text_input("Especificar dificultad") or None
    with c2:
        adm["audicion"] = sel("AudiciÃ³n",
                             ["normal", "hipoacusia_con_audifono", "hipoacusia_sin_compensar"], "aud")
        adm["vision"] = sel("VisiÃ³n",
                           ["normal", "reducida_compensada", "reducida_sin_compensar"], "vis")

# ===================== MÃ“DULO 6 â€” FACTORES DE RIESGO =====================
with tabs[6]:
    st.subheader("6 Â· Factores de riesgo (banderas rojas)")
    df_fac = pd.DataFrame([
        {"id": r["id"], "factor": r["factor"], "presente": False, "detalle": ""}
        for r in CAT_FAC
    ])
    fac_edit = st.data_editor(
        df_fac, hide_index=True, use_container_width=True, key="fac",
        column_config={
            "id": None,
            "factor": st.column_config.TextColumn("Factor de riesgo", disabled=True, width="large"),
            "presente": st.column_config.CheckboxColumn("Â¿Presente?"),
            "detalle": st.column_config.TextColumn("Detalle / observaciÃ³n", width="large"),
        },
    )

# ===================== MÃ“DULO 7 â€” CIERRE =====================
with tabs[7]:
    st.subheader("7 Â· Cierre y observaciones")
    adm["observaciones"] = st.text_area(
        "ImpresiÃ³n general, alertas subjetivas y aspectos no recogidos en los mÃ³dulos anteriores",
        height=150) or None

# ===================== RECOLECCIÃ“N + ACCIONES =====================
def _cell(r, k):
    """Lee una celda de data_editor devolviendo \"\" para None/NaN."""
    v = r.get(k)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return v


def _recolectar():
    antecedentes = [
        {"cat_antecedente_id": int(r["id"]), "categoria": r["categoria"],
         "item": r["item"], "presente": True,
         "detalle": _cell(r, "detalle") or None,
         "observaciones": _cell(r, "observaciones") or None}
        for _, r in ant_edit.iterrows()
        if bool(r["presente"]) or str(_cell(r, "detalle")).strip()
        or str(_cell(r, "observaciones")).strip()
    ]
    cirugias = [
        {"tipo_cirugia": _cell(r, "tipo_cirugia"), "fecha_aprox": _cell(r, "fecha_aprox") or None}
        for _, r in cir_edit.iterrows() if str(_cell(r, "tipo_cirugia")).strip()
    ]
    alergias = [
        {"tipo": r["tipo"], "descripcion": _cell(r, "descripcion")}
        for _, r in alg_edit.iterrows() if str(_cell(r, "descripcion")).strip()
    ]
    medicacion = [
        {k: (_cell(r, k) or None) for k in ["medicamento", "dosis", "frecuencia",
                                            "via", "prescriptor", "indicacion"]}
        for _, r in med_edit.iterrows() if str(_cell(r, "medicamento")).strip()
    ]
    problemas = [
        {k: (_cell(r, k) or None) for k in ["problema", "descripcion", "estado",
                                            "medico_responsable"]}
        for _, r in prob_edit.iterrows() if str(_cell(r, "problema")).strip()
    ]
    factores = [
        {"cat_factor_id": int(r["id"]), "factor": r["factor"],
         "presente": bool(r["presente"]), "detalle": _cell(r, "detalle") or None}
        for _, r in fac_edit.iterrows()
        if bool(r["presente"]) or str(_cell(r, "detalle")).strip()
    ]
    adm_clean = {k: v for k, v in adm.items()
                 if v is not None and v != [] and v != ""}
    return adm_clean, antecedentes, cirugias, alergias, medicacion, problemas, factores


st.divider()
col_guardar, col_pdf = st.columns(2)

with col_guardar:
    if st.button("ðŸ’¾ Guardar evaluaciÃ³n", type="primary", use_container_width=True):
        errores = []
        if not pac.get("dni", "").strip():
            errores.append("Falta el DNI.")
        if not pac.get("apellido_nombre", "").strip():
            errores.append("Falta el apellido y nombre.")
        if errores:
            for e in errores:
                st.error(e)
        else:
            (adm_clean, antecedentes, cirugias, alergias,
             medicacion, problemas, factores) = _recolectar()
            try:
                admision_id = db.guardar_admision(
                    paciente=pac, admision=adm_clean,
                    antecedentes=antecedentes, cirugias=cirugias, alergias=alergias,
                    medicacion=medicacion, problemas=problemas, factores=factores,
                    creado_por=usuario["id"],
                )
                st.success(f"âœ… EvaluaciÃ³n guardada (admisiÃ³n #{admision_id}). "
                           f"Total en base: {db.contar_admisiones()}.")
                st.balloons()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

with col_pdf:
    if pac.get("dni", "").strip() or pac.get("apellido_nombre", "").strip():
        (adm_clean, antecedentes, cirugias, alergias,
         medicacion, problemas, factores) = _recolectar()
        try:
            pdf_bytes = pdf_export.generar_pdf(
                pac, adm_clean, antecedentes, cirugias, alergias,
                medicacion, problemas, factores)
            dni = (pac.get("dni") or "sin_dni").strip()
            st.download_button(
                "ðŸ“„ Descargar PDF", data=pdf_bytes,
                file_name=f"admision_{dni}.pdf", mime="application/pdf",
                use_container_width=True)
        except Exception as e:
            st.warning(f"No se pudo generar el PDF: {e}")
    else:
        st.button("ðŸ“„ Descargar PDF", disabled=True, use_container_width=True,
                  help="CompletÃ¡ al menos DNI o nombre para generar el PDF.")

