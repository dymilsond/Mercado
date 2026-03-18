from __future__ import annotations

from typing import Optional

import streamlit as st

from auth.users_store import get_user, verify_password

# ---------------------------------------------------------------------------
# Chaves do session_state
# ---------------------------------------------------------------------------
_KEY_LOGGED_IN  = "auth_logged_in"
_KEY_USERNAME   = "auth_username"
_KEY_PERFIL     = "auth_perfil"
_KEY_NOME       = "auth_nome"


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------
def login(username: str, password: str) -> bool:
    """
    Verifica credenciais e, se válidas, popula o session_state.
    Retorna True em caso de sucesso.
    """
    if not verify_password(username, password):
        return False

    user = get_user(username)
    st.session_state[_KEY_LOGGED_IN] = True
    st.session_state[_KEY_USERNAME]  = user["username"]
    st.session_state[_KEY_PERFIL]    = user["perfil"]
    st.session_state[_KEY_NOME]      = user.get("nome", username)
    return True


def logout() -> None:
    for key in (_KEY_LOGGED_IN, _KEY_USERNAME, _KEY_PERFIL, _KEY_NOME):
        st.session_state.pop(key, None)


# ---------------------------------------------------------------------------
# Consultas de sessão
# ---------------------------------------------------------------------------
def is_logged_in() -> bool:
    return bool(st.session_state.get(_KEY_LOGGED_IN, False))


def current_user() -> Optional[str]:
    return st.session_state.get(_KEY_USERNAME)


def current_perfil() -> Optional[str]:
    return st.session_state.get(_KEY_PERFIL)


def current_nome() -> Optional[str]:
    return st.session_state.get(_KEY_NOME)


def is_admin() -> bool:
    return current_perfil() == "admin"


# ---------------------------------------------------------------------------
# Guard — use no topo de cada página protegida
# ---------------------------------------------------------------------------
def require_login() -> None:
    """Para a execução da página se o usuário não estiver logado."""
    if not is_logged_in():
        st.warning("Você precisa fazer login para acessar esta página.")
        st.stop()


def require_admin() -> None:
    """Para a execução se o usuário não for admin."""
    require_login()
    if not is_admin():
        st.error("Acesso restrito a administradores.")
        st.stop()
