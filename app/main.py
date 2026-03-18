from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from auth.auth_service import (
    current_nome,
    is_admin,
    is_logged_in,
    login,
    logout,
)
from auth.users_store import init_default_admin

# Imports de páginas no topo para que o file watcher do Streamlit
# monitore mudanças nesses arquivos e recarregue automaticamente
# (reload forçado)
import pages.dashboard          # noqa: F401
import pages.executive_summary  # noqa: F401
import pages.benchmark          # noqa: F401
import pages.admin              # noqa: F401

st.set_page_config(
    page_title="Mercadinhos — Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_default_admin()

st.markdown(
    """
    <style>
        [data-testid="stSidebar"] { min-width: 230px; max-width: 260px; }
        .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
        div[data-testid="metric-container"] {
            background: #f0f4ff;
            border: 1px solid #d0d8f0;
            border-radius: 10px;
            padding: 14px 18px;
        }
        div[data-testid="stRadio"] label {
            padding: 5px 10px;
            border-radius: 6px;
            transition: background 0.15s;
            cursor: pointer;
        }
        div[data-testid="stRadio"] label:hover { background: #e8f0fe; }
        [data-testid="stSidebar"] .stButton > button {
            border: 1px solid #ff4b4b;
            color: #ff4b4b;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background: #ff4b4b; color: white;
        }
        .stDownloadButton > button {
            background: #f0f4ff;
            border: 1px solid #1565c0;
            color: #1565c0;
            font-size: 0.82rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

_PAGES_ADMIN = ["📊 Resumo Executivo", "📈 Dashboard", "🏁 Benchmark", "⚙️ Administração"]
_PAGES_USER  = ["📊 Resumo Executivo", "📈 Dashboard", "🏁 Benchmark"]
_PAGE_MAP    = {
    "📊 Resumo Executivo": "Resumo Executivo",
    "📈 Dashboard":        "Dashboard",
    "🏁 Benchmark":        "Benchmark",
    "⚙️ Administração":    "Administração",
}


def _render_login() -> None:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown(
            """
            <div style="text-align:center; padding:2rem 0 1.5rem;">
                <div style="font-size:3rem;">🛒</div>
                <h2 style="margin:4px 0; color:#1565c0;">Mercadinhos Analytics</h2>
                <p style="color:#888; margin:0; font-size:0.9rem;">Sistema de Apoio à Decisão</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("form_login", clear_on_submit=False):
            username = st.text_input("Usuário", placeholder="seu_usuario")
            password = st.text_input("Senha", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")

        if submitted:
            if not username or not password:
                st.error("Preencha usuário e senha.")
                return
            if login(username.strip(), password):
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos, ou conta desativada.")


def _render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:10px 0 6px;">
                <div style="font-size:1.05rem; font-weight:700; color:#1565c0;">🛒 Mercadinhos</div>
                <div style="font-size:0.88rem; margin-top:3px;"><strong>{current_nome()}</strong></div>
                <div style="font-size:0.75rem; color:#888;">
                    {"👑 Administrador" if is_admin() else "👤 Usuário"}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.caption("NAVEGAÇÃO")
        opcoes = _PAGES_ADMIN if is_admin() else _PAGES_USER
        default = st.session_state.get("_pagina_ativa", opcoes[0])
        if default not in opcoes:
            default = opcoes[0]
        pagina = st.radio(
            "nav",
            options=opcoes,
            index=opcoes.index(default),
            label_visibility="collapsed",
        )
        st.session_state["_pagina_ativa"] = pagina
        st.divider()
        if st.button("↩ Sair", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("f_") or k.startswith("_pagina"):
                    st.session_state.pop(k, None)
            logout()
            st.rerun()
    return _PAGE_MAP.get(pagina, pagina)


def _render_page(pagina: str) -> None:
    if pagina == "Resumo Executivo":
        from pages.executive_summary import render
        render()
    elif pagina == "Dashboard":
        from pages.dashboard import render
        render()
    elif pagina == "Benchmark":
        from pages.benchmark import render
        render()
    elif pagina == "Administração":
        from pages.admin import render
        render()


def main() -> None:
    if not is_logged_in():
        _render_login()
        return
    pagina = _render_sidebar()
    _render_page(pagina)


if __name__ == "__main__":
    main()
