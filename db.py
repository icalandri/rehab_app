"""
Capa de acceso a datos (Postgres / Supabase).
Lee la configuración desde st.secrets["postgres"].
"""
from __future__ import annotations

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ---------------------------------------------------------------------
# Conexión (cacheada a nivel de proceso)
# ---------------------------------------------------------------------
@st.cache_resource
def get_engine() -> Engine:
    cfg = st.secrets["postgres"]
    url = (
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
        f"?sslmode={cfg.get('sslmode', 'require')}"
    )
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": "-csearch_path=rehab,public"},
    )


# ---------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------
@st.cache_data(ttl=600)
def get_antecedentes_catalogo() -> list[dict]:
    q = text(
        "SELECT id, categoria, item, alta_prioridad, orden "
        "FROM cat_antecedentes ORDER BY orden"
    )
    with get_engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(q)]


@st.cache_data(ttl=600)
def get_factores_catalogo() -> list[dict]:
    q = text("SELECT id, factor, orden FROM cat_factores_riesgo ORDER BY orden")
    with get_engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(q)]


# ---------------------------------------------------------------------
# Usuarios / login
# ---------------------------------------------------------------------
def get_usuario(usuario: str) -> dict | None:
    q = text(
        "SELECT id, usuario, nombre, password_hash, rol, activo "
        "FROM usuarios WHERE usuario = :u AND activo = true"
    )
    with get_engine().connect() as c:
        row = c.execute(q, {"u": usuario}).fetchone()
    return dict(row._mapping) if row else None


def listar_usuarios() -> list[dict]:
    q = text(
        "SELECT id, usuario, nombre, rol, activo, creado_en "
        "FROM usuarios ORDER BY creado_en"
    )
    with get_engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(q)]


def crear_usuario(usuario: str, nombre: str, password_hash: str,
                  rol: str) -> None:
    """Alta/actualización de usuario (la clave llega ya hasheada)."""
    q = text(
        """
        INSERT INTO usuarios (usuario, nombre, password_hash, rol)
        VALUES (:u, :n, :h, :r)
        ON CONFLICT (usuario) DO UPDATE
            SET nombre = EXCLUDED.nombre,
                password_hash = EXCLUDED.password_hash,
                rol = EXCLUDED.rol,
                activo = true
        """
    )
    with get_engine().begin() as c:
        c.execute(q, {"u": usuario.strip(), "n": nombre.strip(),
                      "h": password_hash, "r": rol})


def set_usuario_activo(usuario_id: int, activo: bool) -> None:
    with get_engine().begin() as c:
        c.execute(text("UPDATE usuarios SET activo = :a WHERE id = :i"),
                  {"a": activo, "i": usuario_id})


# ---------------------------------------------------------------------
# Pacientes
# ---------------------------------------------------------------------
def buscar_paciente_por_dni(dni: str) -> dict | None:
    q = text("SELECT id, dni, apellido_nombre FROM pacientes WHERE dni = :d")
    with get_engine().connect() as c:
        row = c.execute(q, {"d": dni.strip()}).fetchone()
    return dict(row._mapping) if row else None


def upsert_paciente(conn, dni: str, apellido_nombre: str,
                    fecha_nacimiento=None) -> int:
    """Devuelve el id del paciente, creándolo si no existe (por DNI)."""
    q = text(
        """
        INSERT INTO pacientes (dni, apellido_nombre, fecha_nacimiento)
        VALUES (:dni, :nom, :fnac)
        ON CONFLICT (dni) DO UPDATE
            SET apellido_nombre = EXCLUDED.apellido_nombre,
                fecha_nacimiento = COALESCE(EXCLUDED.fecha_nacimiento,
                                            pacientes.fecha_nacimiento)
        RETURNING id
        """
    )
    return conn.execute(
        q, {"dni": dni.strip(), "nom": apellido_nombre.strip(),
            "fnac": fecha_nacimiento}
    ).scalar_one()


# ---------------------------------------------------------------------
# Guardado transaccional de una admisión completa
# ---------------------------------------------------------------------
def guardar_admision(paciente: dict, admision: dict,
                     antecedentes: list[dict], cirugias: list[dict],
                     alergias: list[dict], medicacion: list[dict],
                     problemas: list[dict], factores: list[dict],
                     creado_por: int) -> int:
    """
    Inserta paciente (upsert por DNI) + admisión + todas las tablas hijas
    en una sola transacción. Devuelve el id de la admisión.
    """
    eng = get_engine()
    with eng.begin() as conn:
        paciente_id = upsert_paciente(
            conn, paciente["dni"], paciente["apellido_nombre"],
            paciente.get("fecha_nacimiento"),
        )

        cols = list(admision.keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        col_list = ", ".join(cols)
        q_adm = text(
            f"INSERT INTO admisiones (paciente_id, creado_por, {col_list}) "
            f"VALUES (:paciente_id, :creado_por, {placeholders}) RETURNING id"
        )
        params = dict(admision)
        params["paciente_id"] = paciente_id
        params["creado_por"] = creado_por
        admision_id = conn.execute(q_adm, params).scalar_one()

        for a in antecedentes:
            conn.execute(text(
                "INSERT INTO adm_antecedentes "
                "(admision_id, cat_antecedente_id, categoria, item, presente, detalle, observaciones) "
                "VALUES (:aid, :cid, :cat, :item, :pres, :det, :obs)"
            ), {"aid": admision_id, "cid": a.get("cat_antecedente_id"),
                "cat": a.get("categoria"), "item": a.get("item"),
                "pres": a.get("presente", True), "det": a.get("detalle"),
                "obs": a.get("observaciones")})

        for i, c_ in enumerate(cirugias, start=1):
            conn.execute(text(
                "INSERT INTO adm_cirugias (admision_id, orden, tipo_cirugia, fecha_aprox) "
                "VALUES (:aid, :ord, :tipo, :fec)"
            ), {"aid": admision_id, "ord": i,
                "tipo": c_.get("tipo_cirugia"), "fec": c_.get("fecha_aprox")})

        for al in alergias:
            conn.execute(text(
                "INSERT INTO adm_alergias (admision_id, tipo, descripcion) "
                "VALUES (:aid, :tipo, :desc)"
            ), {"aid": admision_id, "tipo": al["tipo"], "desc": al.get("descripcion")})

        for i, m in enumerate(medicacion, start=1):
            conn.execute(text(
                "INSERT INTO adm_medicacion "
                "(admision_id, orden, medicamento, dosis, frecuencia, via, prescriptor, indicacion) "
                "VALUES (:aid, :ord, :med, :dos, :frec, :via, :pres, :ind)"
            ), {"aid": admision_id, "ord": i, "med": m.get("medicamento"),
                "dos": m.get("dosis"), "frec": m.get("frecuencia"),
                "via": m.get("via"), "pres": m.get("prescriptor"),
                "ind": m.get("indicacion")})

        for p in problemas:
            conn.execute(text(
                "INSERT INTO adm_problemas_activos "
                "(admision_id, problema, descripcion, estado, medico_responsable) "
                "VALUES (:aid, :prob, :desc, :est, :med)"
            ), {"aid": admision_id, "prob": p.get("problema"),
                "desc": p.get("descripcion"), "est": p.get("estado"),
                "med": p.get("medico_responsable")})

        for f in factores:
            conn.execute(text(
                "INSERT INTO adm_factores_riesgo "
                "(admision_id, cat_factor_id, factor, presente, detalle) "
                "VALUES (:aid, :cid, :fac, :pres, :det)"
            ), {"aid": admision_id, "cid": f.get("cat_factor_id"),
                "fac": f.get("factor"), "pres": f.get("presente", False),
                "det": f.get("detalle")})

    return admision_id


def contar_admisiones() -> int:
    with get_engine().connect() as c:
        return c.execute(text("SELECT count(*) FROM admisiones")).scalar_one()
