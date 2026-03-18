from __future__ import annotations

import streamlit as st

from auth.auth_service import current_user, require_admin
from auth.users_store import (
    create_user,
    delete_user,
    generate_temp_password,
    get_all_users,
    reset_password,
    set_active,
    update_user,
)


# ---------------------------------------------------------------------------
# Sub-páginas internas
# ---------------------------------------------------------------------------
def _render_lista_usuarios() -> None:
    st.markdown("### 👥 Usuários cadastrados")

    users = get_all_users()
    if not users:
        st.info("Nenhum usuário cadastrado.")
        return

    for user in users:
        is_self = user["username"] == current_user()
        status_icon = "🟢" if user["ativo"] else "🔴"
        perfil_badge = "👑 Admin" if user["perfil"] == "admin" else "👤 User"

        with st.expander(
            f"{status_icon} **{user['username']}** — {user.get('nome', '')} | {perfil_badge}",
            expanded=False,
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.text(f"Nome: {user.get('nome', '—')}")
                st.text(f"E-mail: {user.get('email', '—')}")
                st.text(f"Perfil: {user['perfil']}")
                st.text(f"Status: {'Ativo' if user['ativo'] else 'Inativo'}")

            with col2:
                # Ativar / desativar
                if not is_self:
                    btn_label = "Desativar" if user["ativo"] else "Ativar"
                    if st.button(btn_label, key=f"toggle_{user['username']}"):
                        try:
                            set_active(user["username"], not user["ativo"])
                            st.success(f"Usuário {btn_label.lower()}do com sucesso.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))

                # Reset de senha
                if st.button("Resetar senha", key=f"reset_{user['username']}"):
                    temp = generate_temp_password()
                    try:
                        reset_password(user["username"], temp)
                        st.success(f"Senha resetada. Nova senha temporária: `{temp}`")
                    except ValueError as e:
                        st.error(str(e))

                # Excluir
                if not is_self and user["username"] != "admin":
                    if st.button("Excluir", key=f"del_{user['username']}", type="secondary"):
                        st.session_state[f"confirm_del_{user['username']}"] = True

                    if st.session_state.get(f"confirm_del_{user['username']}", False):
                        st.warning(f"Confirma exclusão de **{user['username']}**?")
                        c1, c2 = st.columns(2)
                        if c1.button("Sim, excluir", key=f"yes_del_{user['username']}", type="primary"):
                            try:
                                delete_user(user["username"])
                                st.session_state.pop(f"confirm_del_{user['username']}", None)
                                st.success("Usuário excluído.")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                        if c2.button("Cancelar", key=f"no_del_{user['username']}"):
                            st.session_state.pop(f"confirm_del_{user['username']}", None)
                            st.rerun()


def _render_criar_usuario() -> None:
    st.markdown("### ➕ Criar novo usuário")

    with st.form("form_criar_usuario", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username *", placeholder="joao.silva")
            nome     = st.text_input("Nome completo *", placeholder="João Silva")
        with col2:
            email   = st.text_input("E-mail", placeholder="joao@empresa.com")
            perfil  = st.selectbox("Perfil *", options=["user", "admin"])

        col3, col4 = st.columns(2)
        with col3:
            senha   = st.text_input("Senha *", type="password")
        with col4:
            senha2  = st.text_input("Confirmar senha *", type="password")

        submitted = st.form_submit_button("Criar usuário", use_container_width=True)

    if submitted:
        erros = []
        if not username:
            erros.append("Username é obrigatório.")
        if not nome:
            erros.append("Nome é obrigatório.")
        if not senha:
            erros.append("Senha é obrigatória.")
        if senha != senha2:
            erros.append("As senhas não coincidem.")
        if len(senha) < 6:
            erros.append("Senha deve ter pelo menos 6 caracteres.")

        if erros:
            for e in erros:
                st.error(e)
        else:
            try:
                create_user(
                    username=username.strip(),
                    password=senha,
                    perfil=perfil,
                    nome=nome.strip(),
                    email=email.strip(),
                )
                st.success(f"Usuário **{username}** criado com sucesso!")
            except ValueError as e:
                st.error(str(e))


def _render_editar_usuario() -> None:
    st.markdown("### ✏️ Editar usuário")

    users = get_all_users()
    if not users:
        st.info("Nenhum usuário disponível.")
        return

    usernames = [u["username"] for u in users]
    selecionado = st.selectbox("Selecione o usuário", options=usernames)

    user_data = next((u for u in users if u["username"] == selecionado), None)
    if not user_data:
        return

    with st.form("form_editar_usuario"):
        col1, col2 = st.columns(2)
        with col1:
            novo_nome  = st.text_input("Nome completo", value=user_data.get("nome", ""))
            novo_email = st.text_input("E-mail", value=user_data.get("email", ""))
        with col2:
            novo_perfil = st.selectbox(
                "Perfil",
                options=["user", "admin"],
                index=0 if user_data["perfil"] == "user" else 1,
                disabled=(selecionado == "admin"),
            )

        submitted = st.form_submit_button("Salvar alterações", use_container_width=True)

    if submitted:
        try:
            update_user(
                username=selecionado,
                nome=novo_nome,
                email=novo_email,
                perfil=novo_perfil if selecionado != "admin" else None,
            )
            st.success("Dados atualizados com sucesso.")
        except ValueError as e:
            st.error(str(e))


def _render_alterar_senha() -> None:
    st.markdown("### 🔑 Alterar senha")

    users = get_all_users()
    usernames = [u["username"] for u in users]
    selecionado = st.selectbox("Usuário", options=usernames, key="sel_senha")

    with st.form("form_senha"):
        col1, col2 = st.columns(2)
        with col1:
            nova_senha  = st.text_input("Nova senha", type="password")
        with col2:
            nova_senha2 = st.text_input("Confirmar nova senha", type="password")

        submitted = st.form_submit_button("Alterar senha", use_container_width=True)

    if submitted:
        if not nova_senha:
            st.error("Digite a nova senha.")
        elif nova_senha != nova_senha2:
            st.error("As senhas não coincidem.")
        elif len(nova_senha) < 6:
            st.error("Senha deve ter pelo menos 6 caracteres.")
        else:
            try:
                reset_password(selecionado, nova_senha)
                st.success(f"Senha de **{selecionado}** alterada com sucesso.")
            except ValueError as e:
                st.error(str(e))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def render() -> None:
    require_admin()

    st.title("⚙️ Administração de Usuários")
    st.caption("Gerencie usuários, perfis e credenciais de acesso ao sistema.")

    tab_lista, tab_criar, tab_editar, tab_senha = st.tabs([
        "Usuários", "Novo usuário", "Editar", "Alterar senha"
    ])

    with tab_lista:
        _render_lista_usuarios()

    with tab_criar:
        _render_criar_usuario()

    with tab_editar:
        _render_editar_usuario()

    with tab_senha:
        _render_alterar_senha()


# Executado apenas quando o Streamlit roda este arquivo diretamente como página nativa.
# Quando importado por main.py, __name__ != "__main__" e render() NÃO é chamado aqui.
if __name__ == "__main__":
    render()
