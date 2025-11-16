import streamlit as st
import bcrypt
from supabase_client import client


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def fetch_user_by_username(username: str):
    resp = client.table("ag_users").select("*").eq("username", username).maybe_single().execute()
    return resp.data


def fetch_user_by_id(user_id: int):
    resp = client.table("ag_users").select("*").eq("id", user_id).maybe_single().execute()
    return resp.data


def fetch_linked_agenda_users(gestao_user_id: int):
    """
    Busca todos os usuários 'agenda' vinculados a um usuário 'gestao'.
    Retorna lista de dicts com {id, username}.
    """
    resp = client.table("ag_user_links").select(
        "agenda_user_id, ag_users!ag_user_links_agenda_user_id_fkey(id, username)"
    ).eq("gestao_user_id", gestao_user_id).execute()
    
    if not resp.data:
        return []
    
    # Formata resposta: extrai dados do usuário agenda
    linked_users = []
    for row in resp.data:
        user_data = row.get("ag_users")
        if user_data:
            linked_users.append({
                "id": user_data.get("id"),
                "username": user_data.get("username")
            })
    
    return linked_users


def login(username: str, password: str):
    user = fetch_user_by_username(username)
    if not user or user.get("is_active") is not True:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    
    # Carrega info de vínculos caso perfil seja gestao
    linked_agenda_users = []
    if user.get("role") == "gestao":
        linked_agenda_users = fetch_linked_agenda_users(user["id"])
    
    session_user = {
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "is_active": user["is_active"],
        "linked_agenda_users": linked_agenda_users,  # Lista de usuários agenda vinculados
    }
    st.session_state["user"] = session_user
    return session_user


def require_auth():
    if "user" not in st.session_state:
        st.warning("Faça login para acessar a aplicação.")
        st.stop()


def require_roles(allowed_roles: list[str]):
    require_auth()
    role = st.session_state["user"]["role"]
    if role not in allowed_roles:
        st.error("Acesso negado para seu perfil.")
        st.stop()


def logout():
    if "user" in st.session_state:
        del st.session_state["user"]