# ============================================================
# 🏠 frontend/pages/home.py
# Página inicial
# ============================================================
import streamlit as st
import pandas as pd
import hashlib

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def hash_password(password: str) -> str:
    """Hash de senha com SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def get_user_groups(usuario: str):
    """Busca os grupos atribuídos ao usuário."""
    try:
        supabase = get_supabase_client()

        # Buscar ID do usuário
        resp_usuario = supabase_execute(
            lambda: supabase.table("tab_app_usuarios")
            .select("id_usuario")
            .eq("nm_usuario", usuario.lower().strip())
            .execute()
        )

        if not resp_usuario.data:
            return []

        id_usuario = resp_usuario.data[0]["id_usuario"]

        # Buscar grupos do usuário (apenas ativos)
        resp_grupos = supabase_execute(
            lambda: supabase.table("tab_app_usuario_grupo")
            .select("tab_app_grupos(nm_grupo)")
            .eq("id_usuario", id_usuario)
            .eq("sn_ativo", True)
            .execute()
        )

        if not resp_grupos.data:
            return []

        grupos = [item["tab_app_grupos"]["nm_grupo"] for item in resp_grupos.data]
        return grupos

    except Exception as e:
        st.error(f"❌ Erro ao carregar grupos: {str(e)}")
        return []


def update_user_password(usuario: str, senha_atual: str, senha_nova: str):
    """Atualiza a senha do usuário após validação."""
    try:
        supabase = get_supabase_client()

        # 1️⃣ Busca usuário
        resp = supabase_execute(
            lambda: supabase.table("tab_app_usuarios")
            .select("ds_senha")
            .eq("nm_usuario", usuario.lower().strip())
            .execute()
        )

        if not resp.data:
            return False, "❌ Usuário não encontrado"

        # 2️⃣ Valida senha atual
        senha_atual_hash = hash_password(senha_atual)
        if resp.data[0]["ds_senha"] != senha_atual_hash:
            return False, "❌ Senha atual incorreta"

        # 3️⃣ Atualiza para nova senha
        nova_senha_hash = hash_password(senha_nova)
        supabase_execute(
            lambda: supabase.table("tab_app_usuarios")
            .update({"ds_senha": nova_senha_hash})
            .eq("nm_usuario", usuario.lower().strip())
            .execute()
        )

        return True, "✅ Senha atualizada com sucesso!"

    except Exception as e:
        return False, f"❌ Erro ao atualizar senha: {str(e)}"


def page_home():
    st.title("🩺 DataLab App")
    st.markdown("""
        Bem-vindo ao DataLab!

        Aplicação para gerenciamento de dados e permissões da **CEMEC**.
    """)

    # Informações do usuário
    if "usuario_data" in st.session_state:
        usuario = st.session_state["usuario_data"]
        st.markdown(f"### 👋 Bem-vindo, **{usuario.get('nm_usuario_label', usuario.get('nm_usuario'))}**!")

        # ✅ SEÇÃO: ALTERAR SENHA
        st.markdown("---")
        st.markdown("### 🔐 Segurança")

        if "_senha_feedback" in st.session_state:
            msg, tipo = st.session_state.pop("_senha_feedback")
            feedback(msg, tipo, "🔐")

        with st.form("form_alterar_senha"):
            st.markdown("#### Alterar Senha")

            col1, col2 = st.columns(2)

            with col1:
                senha_atual = st.text_input(
                    "Senha Atual",
                    type="password",
                    placeholder="Digite sua senha atual",
                )

            with col2:
                st.write("")  # Espaçamento

            col3, col4 = st.columns(2)

            with col3:
                senha_nova = st.text_input(
                    "Nova Senha",
                    type="password",
                    placeholder="Mínimo 8 caracteres",
                )

            with col4:
                senha_nova_confirma = st.text_input(
                    "Confirmar Nova Senha",
                    type="password",
                    placeholder="Repita a nova senha",
                )

            if st.form_submit_button("🔄 Alterar Senha", use_container_width=True, type="primary"):
                # Validações
                if not senha_atual or not senha_nova or not senha_nova_confirma:
                    st.error("⚠️ Todos os campos são obrigatórios")
                elif len(senha_nova) < 8:
                    st.error("⚠️ A nova senha deve ter no mínimo 8 caracteres")
                elif senha_nova != senha_nova_confirma:
                    st.error("⚠️ As senhas não coincidem")
                elif senha_atual == senha_nova:
                    st.error("⚠️ A nova senha deve ser diferente da senha atual")
                else:
                    # Atualiza senha
                    sucesso, mensagem = update_user_password(
                        usuario.get("nm_usuario"),
                        senha_atual,
                        senha_nova,
                    )

                    if sucesso:
                        st.session_state["_senha_feedback"] = (mensagem, "success")
                        st.rerun()
                    else:
                        feedback(mensagem, "error", "⚠️")

        # Informações do usuário
        st.markdown("---")
        st.markdown("### 📋 Suas Informações")
        st.info(f"📧 **Email:** {usuario.get('ds_email', 'N/A')}")

        # Grupos do usuário
        st.markdown("### 👥 Grupos Atribuídos")
        grupos = get_user_groups(usuario.get("nm_usuario"))

        if grupos:
            for grupo in grupos:
                st.success(f"✓ {grupo}")
        else:
            st.warning("⚠️ Nenhum grupo atribuído")