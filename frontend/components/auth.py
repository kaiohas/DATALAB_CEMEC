import streamlit as st

def has_access(page_name):
    perms = st.session_state.get("page_permissions", {})
    user = st.session_state.user_role
    if not perms:
        return True
    if page_name not in perms:
        return True
    return user in perms[page_name]

def access_denied(page_name):
    st.error("🚫 Acesso Negado")
    st.warning(
        f"Você não tem permissão para acessar **{page_name}**.\n\n"
        f"Função atual: `{st.session_state.user_role}`"
    )
