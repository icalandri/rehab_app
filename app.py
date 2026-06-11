"""
Formulario web — Evaluación Integral de Admisión a Rehabilitación
Streamlit + Postgres (Supabase). Carga 1 admisión por envío.

Ejecutar local:   streamlit run app.py
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

import auth
import db

st.set_page_config(page_title="Admisión a Rehabilitación",
                   page_icon="🏥", layout="wide")

# --------------------------- LOGIN ---------------------------
usuario = auth.login_gate()
auth.logout_button()

# --------------------------- NAVEGACIÓN ---------------------------
es_admin = usuario.get("rol") == "admin"
vistas = ["📝 Cargar evaluación"]
if es_admin:
    vistas.append("👥 Gestión de usuarios")
vista = st.sidebar.radio("Vista", vistas) if len(vistas) > 1 else vistas[0]


def panel_usuarios():
    st.title("👥 Gestión de usuarios")
    st.caption("Solo administradores. Las contraseñas se guardan hasheadas (bcrypt).")

    st.subheader("Usuarios existentes")
    usuarios = db.listar_usuarios()
    if usuarios:
        st.dataframe(
            [{"Usuario": u["usuario"], "Nombre": u["nombre"], "Rol": u["rol"],
              "Activo": "Sí" if u["activo"] else "No"} for u in usuarios],
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
                                help="cargador: carga datos · lector: solo lectura · admin: además gestiona usuarios")
            np1 = st.text_input("Contraseña", type="password")
            np2 = st.text_input("Repetir contraseña", type="password")
        crear = st.form_submit_button("Crear / actualizar usuario", type="primary")

    if crear:
        if not nu.strip() or not nnom.strip():
            st.error("Usuario y nombre son obligatorios.")
        elif np1 != np2:
            st.error("Las contraseñas no coinciden.")
        elif len(np1) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
        else:
            db.crear_usuario(nu, nnom, auth.hash_password(np1), nrol)
            st.success(f"✅ Usuario '{nu}' creado/actualizado con rol '{nrol}'.")
            st.rerun()

    st.subheader("Activar / desactivar")
    st.caption("Desactivar impide el login sin borrar el historial de cargas.")
    for u in usuarios:
        if u["usuario"] == usuario["usuario"]:
            continue  # no permitir auto-desactivarse
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{u['usuario']}** — {u['nombre']} ({u['rol']})")
        if u["activo"]:
            if col2.button("Desactivar", key=f"off_{u['id']}"):
                db.set_usuario_activo(u["id"], False); st.rerun()
        else:
            if col2.button("Activar", key=f"on_{u['id']}"):
                db.set_usuario_activo(u["id"], True); st.rerun()


if vista == "👥 Gestión de usuarios":
    panel_usuarios()
    st.stop()

st.title("🏥 Evaluación Integral de Admisión a Rehabilitación")
st.caption("Una fila por evaluación. El paciente se identifica por DNI (se crea o reutiliza).")

# Catálogos (desde la base)
CAT_ANT = db.get_antecedentes_catalogo()
CAT_FAC = db.get_factores_catalogo()


def sel(label, opciones, key, help=None):
    return st.selectbox(label, [""] + opciones, key=key, help=help) or None


def tri(label, key):
    """Booleano de 3 estados: Sí / No / (sin dato)."""
    v = st.radio(label, ["—", "Sí", "No"], horizontal=True, key=key)
    return {"—": None, "Sí": True, "No": False}[v]


tabs = st.tabs([
    "0 · Entrevista", "1 · Demográficos", "2 · Antecedentes",
    "3 · Medicación", "4 · Problemas activos", "5 · Funcional",
    "6 · Factores de riesgo", "7 · Cierre",
])

adm: dict = {}
pac: dict = {}

# ===================== MÓDULO 0 — ENTREVISTA =====================
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
        adm["relacion_acompanante"] = st.text_input("Relación del acompañante") or None

# ===================== MÓDULO 1 — DEMOGRÁFICOS =====================
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
        adm["vive_solo"] = tri("¿Vive solo/a?", "vive_solo")
        adm["cuidador_formal"] = tri("¿Servicio de cuidador formal domiciliario?", "cuid_formal")
    with c2:
        adm["cuidador_nombre"] = st.text_input("Cuidador principal (nombre)") or None
        adm["cuidador_vinculo"] = st.text_input("Vínculo del cuidador") or None
    with c3:
        adm["cuidador_disponibilidad"] = sel("Disponibilidad del cuidador",
                                             ["permanente", "parcial", "ninguna"],
                                             "cuid_disp")

    st.subheader("1.3 Nivel educativo y actividad previa")
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["anios_escolaridad"] = st.number_input("Años de escolaridad formal",
                                                   0, 30, value=None, step=1)
    with c2:
        adm["actividad_laboral_previa"] = st.text_input("Actividad laboral previa") or None
    with c3:
        adm["actividad_fisica"] = sel("Actividad física habitual",
                                     ["sedentario", "leve", "moderada", "intensa"],
                                     "act_fis")

# ===================== MÓDULO 2 — ANTECEDENTES =====================
with tabs[2]:
    st.subheader("2.1–2.9 Antecedentes médicos")
    st.caption("Tildá los presentes y completá el detalle (fecha, tipo, territorio, etc.).")
    df_ant = pd.DataFrame([
        {"id": r["id"], "categoria": r["categoria"], "item": r["item"],
         "presente": False, "detalle": "", "observaciones": ""}
        for r in CAT_ANT
    ])
    ant_edit = st.data_editor(
        df_ant, hide_index=True, use_container_width=True, key="ant",
        column_config={
            "id": None,
            "categoria": st.column_config.TextColumn("Categoría", disabled=True),
            "item": st.column_config.TextColumn("Antecedente", disabled=True, width="large"),
            "presente": st.column_config.CheckboxColumn("Presente"),
            "detalle": st.column_config.TextColumn("Detalle"),
            "observaciones": st.column_config.TextColumn("Observaciones"),
        },
    )

    st.subheader("2.10 Cirugías relevantes")
    cir_edit = st.data_editor(
        pd.DataFrame(columns=["tipo_cirugia", "fecha_aprox"]),
        num_rows="dynamic", hide_index=True, use_container_width=True, key="cir",
        column_config={
            "tipo_cirugia": st.column_config.TextColumn("Tipo de cirugía", width="large"),
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
            "descripcion": st.column_config.TextColumn("Descripción (agente + reacción)", width="large"),
        },
    )

# ===================== MÓDULO 3 — MEDICACIÓN =====================
with tabs[3]:
    st.subheader("3 · Medicación habitual")
    st.caption("Incluí automedicación y suplementos. Agregá filas con el botón ➕.")
    med_edit = st.data_editor(
        pd.DataFrame(columns=["medicamento", "dosis", "frecuencia", "via",
                              "prescriptor", "indicacion"]),
        num_rows="dynamic", hide_index=True, use_container_width=True, key="med",
        column_config={
            "medicamento": st.column_config.TextColumn("Medicamento (genérico)"),
            "dosis": "Dosis", "frecuencia": "Frecuencia", "via": "Vía",
            "prescriptor": "Prescriptor", "indicacion": "Indicación",
        },
    )

    st.subheader("Cribado farmacológico adicional")
    c1, c2 = st.columns(2)
    with c1:
        adm["anticoagulado"] = tri("¿Anticoagulado?", "antico")
        adm["anticoag_tipo"] = sel("Tipo de anticoagulante", ["avk", "naco"], "antico_tipo",
                                   help="AVK = warfarina/acenocumarol")
        adm["anticoag_control_rin"] = tri("¿Control de RIN?", "rin")
        adm["toma_insulina"] = tri("¿Toma insulina?", "insu")
        adm["insulina_esquema"] = sel("Esquema de insulina",
                                      ["basal", "basal_bolo", "bomba"], "insu_esq")
    with c2:
        adm["corticoides_cronicos"] = tri("¿Corticoides crónicos?", "cort")
        adm["corticoides_detalle"] = st.text_input("Corticoides: dosis y duración") or None
        adm["medicacion_memoria_conducta"] = tri(
            "¿Medicación memoria/conducta? (anticolinesterásicos, memantina, antipsicóticos)", "memo")
        adm["dificultad_autoadministracion"] = st.text_input(
            "¿Dificultades para administrarse la medicación de forma autónoma?") or None

# ===================== MÓDULO 4 — PROBLEMAS ACTIVOS =====================
with tabs[4]:
    st.info("Preguntar por las últimas 4–8 semanas. Módulo clave para la planificación.")
    st.subheader("4.1 Motivo principal de rehabilitación")
    adm["motivo_descripcion"] = st.text_area("Descripción clínica") or None
    c1, c2 = st.columns(2)
    with c1:
        adm["motivo_fecha_inicio"] = st.text_input("Fecha de inicio / evento desencadenante") or None
    with c2:
        adm["motivo_internacion_previa"] = tri("¿Internación previa relacionada?", "mot_int")

    st.subheader("4.2 Problemas de salud activos secundarios")
    prob_edit = st.data_editor(
        pd.DataFrame(columns=["problema", "descripcion", "estado", "medico_responsable"]),
        num_rows="dynamic", hide_index=True, use_container_width=True, key="prob",
        column_config={
            "problema": "Problema",
            "descripcion": st.column_config.TextColumn("Descripción / Evolución", width="large"),
            "estado": st.column_config.SelectboxColumn(
                "Estado", options=["estable", "seguimiento", "descompensado"]),
            "medico_responsable": "Médico responsable",
        },
    )

    st.subheader("4.3 Hospitalizaciones (últimos 12 meses)")
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["hosp_12m_numero"] = st.number_input("N° internaciones", 0, value=None, step=1, key="h1")
    with c2:
        adm["hosp_12m_uci"] = tri("¿Alguna en UCI/UTI?", "uci")
        adm["hosp_12m_uci_duracion"] = st.text_input("Duración aprox. en UCI") or None
    with c3:
        adm["hosp_12m_motivos"] = st.text_area("Motivos principales") or None

    st.subheader("4.4 Consultas a guardia (últimos 3 meses)")
    c1, c2 = st.columns(2)
    with c1:
        adm["guardia_3m_numero"] = st.number_input("N° consultas", 0, value=None, step=1, key="g1")
    with c2:
        adm["guardia_3m_motivos"] = st.text_area("Motivos", key="g2") or None

# ===================== MÓDULO 5 — FUNCIONAL =====================
with tabs[5]:
    st.subheader("5.1 Movilidad")
    c1, c2 = st.columns(2)
    with c1:
        adm["deambulacion"] = sel("Deambulación independiente",
                                 ["independiente", "no", "con_ayuda_tecnica"], "deamb")
        adm["ayuda_tecnica"] = st.multiselect("Ayuda técnica",
                                             ["baston", "andador", "silla_ruedas"], key="ayudat") or None
    with c2:
        adm["sube_escaleras"] = sel("Sube escaleras", ["si", "no", "con_ayuda"], "esc")
        adm["distancia_marcha"] = st.text_input("Distancia de marcha habitual", "50 mtrs") or None

    st.subheader("5.2 Índice de Barthel referido — independencia PREVIA al evento")
    niveles = ["independiente", "asistido", "dependiente"]
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["avd_alimentacion"] = sel("Alimentación", niveles, "avd1")
        adm["avd_higiene"] = sel("Higiene / Baño", niveles, "avd2")
    with c2:
        adm["avd_vestido"] = sel("Vestido", niveles, "avd3")
        adm["avd_continencia"] = sel("Continencia", niveles, "avd4")
    with c3:
        adm["avd_traslados"] = sel("Traslados / Transferencias", niveles, "avd5")
    adm["avd_observaciones"] = st.text_input("Observaciones AVD") or None

    st.subheader("5.3 Cognición basal")
    c1, c2, c3 = st.columns(3)
    with c1:
        adm["olvidos_previos"] = sel("¿Olvidos frecuentes previos?",
                                    ["si", "no", "no_sabe"], "olv")
    with c2:
        adm["dx_cognitivo_previo"] = tri("Diagnóstico cognitivo previo", "dxc")
        adm["dx_cognitivo_cual"] = st.text_input("¿Cuál?") or None
    with c3:
        adm["mmse_puntaje"] = st.number_input("MMSE (0–30)", 0, 30, value=None, step=1)
        adm["orientacion_basal"] = sel("Orientación tempo-espacial basal",
                                      ["conservada", "parcial", "ausente"], "ori")

    st.subheader("5.4 Comunicación y sensopercepción")
    c1, c2 = st.columns(2)
    with c1:
        adm["idioma_principal"] = st.text_input("Idioma principal") or None
        adm["dificultad_comunicacion"] = tri("Dificultades previas en la comunicación", "dcom")
        adm["dificultad_comunicacion_detalle"] = st.text_input("Especificar dificultad") or None
    with c2:
        adm["audicion"] = sel("Audición",
                             ["normal", "hipoacusia_con_audifono", "hipoacusia_sin_compensar"], "aud")
        adm["vision"] = sel("Visión",
                           ["normal", "reducida_compensada", "reducida_sin_compensar"], "vis")

# ===================== MÓDULO 6 — FACTORES DE RIESGO =====================
with tabs[6]:
    st.subheader("6 · Factores de riesgo (banderas rojas)")
    df_fac = pd.DataFrame([
        {"id": r["id"], "factor": r["factor"], "presente": False, "detalle": ""}
        for r in CAT_FAC
    ])
    fac_edit = st.data_editor(
        df_fac, hide_index=True, use_container_width=True, key="fac",
        column_config={
            "id": None,
            "factor": st.column_config.TextColumn("Factor de riesgo", disabled=True, width="large"),
            "presente": st.column_config.CheckboxColumn("¿Presente?"),
            "detalle": st.column_config.TextColumn("Detalle / observación", width="large"),
        },
    )

# ===================== MÓDULO 7 — CIERRE =====================
with tabs[7]:
    st.subheader("7 · Cierre y observaciones")
    adm["observaciones"] = st.text_area(
        "Impresión general, alertas subjetivas y aspectos no recogidos en los módulos anteriores",
        height=150) or None

# ===================== GUARDADO =====================
st.divider()
if st.button("💾 Guardar evaluación", type="primary", use_container_width=True):
    errores = []
    if not pac.get("dni", "").strip():
        errores.append("Falta el DNI.")
    if not pac.get("apellido_nombre", "").strip():
        errores.append("Falta el apellido y nombre.")

    if errores:
        for e in errores:
            st.error(e)
        st.stop()

    antecedentes = [
        {"cat_antecedente_id": int(r["id"]), "categoria": r["categoria"],
         "item": r["item"], "presente": True,
         "detalle": r["detalle"] or None, "observaciones": r["observaciones"] or None}
        for _, r in ant_edit.iterrows()
        if r["presente"] or (r["detalle"] or "").strip() or (r["observaciones"] or "").strip()
    ]
    cirugias = [
        {"tipo_cirugia": r["tipo_cirugia"], "fecha_aprox": r["fecha_aprox"]}
        for _, r in cir_edit.iterrows() if (r["tipo_cirugia"] or "").strip()
    ]
    alergias = [
        {"tipo": r["tipo"], "descripcion": r["descripcion"]}
        for _, r in alg_edit.iterrows() if (r["descripcion"] or "").strip()
    ]
    medicacion = [
        {k: r[k] for k in ["medicamento", "dosis", "frecuencia", "via",
                           "prescriptor", "indicacion"]}
        for _, r in med_edit.iterrows() if (r["medicamento"] or "").strip()
    ]
    problemas = [
        {k: (r[k] or None) for k in ["problema", "descripcion", "estado",
                                     "medico_responsable"]}
        for _, r in prob_edit.iterrows() if (r["problema"] or "").strip()
    ]
    factores = [
        {"cat_factor_id": int(r["id"]), "factor": r["factor"],
         "presente": bool(r["presente"]), "detalle": r["detalle"] or None}
        for _, r in fac_edit.iterrows()
        if r["presente"] or (r["detalle"] or "").strip()
    ]

    adm_clean = {k: v for k, v in adm.items()
                 if v is not None and v != [] and v != ""}

    try:
        admision_id = db.guardar_admision(
            paciente=pac, admision=adm_clean,
            antecedentes=antecedentes, cirugias=cirugias, alergias=alergias,
            medicacion=medicacion, problemas=problemas, factores=factores,
            creado_por=usuario["id"],
        )
        st.success(f"✅ Evaluación guardada (admisión #{admision_id}). "
                   f"Total en base: {db.contar_admisiones()}.")
        st.balloons()
    except Exception as e:
        st.error(f"Error al guardar: {e}")
