"""
Autenticación simple por usuario/clave contra la tabla 'usuarios'.
Las contraseñas se guardan con hash bcrypt (nunca en texto plano).
"""
from __future__ import annotations

import bcrypt
import streamlit as st

import db


def hash_password(plano: str) -> str:
    """Devuelve el hash bcrypt de una contraseña en texto plano."""
    return bcrypt.hashpw(plano.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verificar_password(plano: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(plano.encode("utf-8"),
                              hash_guardado.encode("utf-8"))
    except ValueError:
        return False


def login_gate() -> dict | None:
    """
    Muestra el formulario de login si el usuario no está autenticado.
    Devuelve el dict del usuario autenticado, o None (y detiene el render).
    """
    if "usuario" in st.session_state:
        return st.session_state["usuario"]

    st.title("🔐 Acceso — Admisión a Rehabilitación")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        ok = st.form_submit_button("Ingresar")

    if ok:
        registro = db.get_usuario(u.strip())
        if registro and _verificar_password(p, registro["password_hash"]):
            registro.pop("password_hash", None)
            st.session_state["usuario"] = registro
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()


def logout_button():
    with st.sidebar:
        u = st.session_state.get("usuario", {})
        st.caption(f"Conectado: **{u.get('nombre','?')}** ({u.get('rol','?')})")
        if st.button("Cerrar sesión"):
            st.session_state.clear()
            st.rerun()
