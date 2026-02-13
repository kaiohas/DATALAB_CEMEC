# ============================================================
# 🔐 frontend/components/login.py
# Autenticação com nm_usuario/senha via Supabase
# ============================================================
import streamlit as st
import hashlib
from frontend.supabase_client import get_supabase_client


def hash_password(password: str) -> str:
    """Hash de senha com SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()

def verificar_senha(password: str, hash_stored: str) -> bool:
    """Verifica se a senha corresponde ao hash."""
    return hash_password(password) == hash_stored

def login_page():
    """Página de login com nm_usuario e senha."""
    st.set_page_config(page_title="DataLab - Login", layout="centered", page_icon="🩺")
    
    # =====================================================
    # HEADER COM IMAGEM E TÍTULO
    # =====================================================
    col_img, col_titulo = st.columns([1, 3], gap="medium")


    with col_titulo:
        st.title("DataLab CEMEC")
        st.caption("Sistema de Gestão de dados")

    st.markdown("---")

    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Faça login na sua conta")
        
        nm_usuario = st.text_input(
            "👤 Nome de Usuário",
            placeholder="Digite seu nome de usuário"
        )
        senha = st.text_input(
            "🔑 Senha",
            type="password",
            placeholder="Digite sua senha"
        )
        
        if st.button("✅ Entrar", use_container_width=True, type="primary"):
            if not nm_usuario or not senha:
                st.error("⚠️ Por favor, preencha nome de usuário e senha")
                return
            
            try:
                supabase = get_supabase_client()
                
                # 1️⃣ Busca usuário no banco por nm_usuario
                response = supabase.table("tab_app_usuarios").select("*").eq("nm_usuario", nm_usuario.lower().strip()).execute()
                
                if not response.data:
                    st.error("❌ Nome de usuário ou senha inválidos")
                    return
                
                usuario = response.data[0]
                
                # 2️⃣ Verifica ativação
                if not usuario.get("sn_ativo"):
                    st.error("❌ Sua conta foi desativada. Contate o administrador.")
                    return
                
                # 3️⃣ Verifica senha
                if not verificar_senha(senha, usuario.get("ds_senha", "")):
                    st.error("❌ Nome de usuário ou senha inválidos")
                    return
                
                # 4️⃣ ✅ Login com sucesso!
                st.session_state["usuario_logado"] = usuario["nm_usuario"]
                st.session_state["id_usuario"] = usuario["id_usuario"]
                st.session_state["email"] = usuario.get("ds_email", "")
                st.session_state["usuario_data"] = usuario
                
                st.success("✅ Login realizado com sucesso!")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro ao fazer login: {str(e)}")
        
        # =====================================================
        # BOTÃO DE SUPORTE
        # =====================================================
        st.markdown("---")
        
        LINK_SUPORTE = "https://teams.microsoft.com/l/chat/48:notes/conversations?context=%7B%22contextType%22%3A%22chat%22%7D"
        
        st.link_button(
            "💬 Suporte via Teams",
            url=LINK_SUPORTE,
            use_container_width=True
        )


def logout():
    """Realiza logout."""
    st.session_state.clear()
    st.rerun()


def get_usuario_logado_supabase() -> str:
    """
    Retorna o usuário atualmente logado via session_state.
    """
    if "usuario_logado" in st.session_state:
        return st.session_state["usuario_logado"]
    
    return None


def check_authentication() -> str:
    """
    Middleware: verifica se usuário está autenticado.
    Se não estiver, redireciona para página de login.
    Retorna o nome de usuário.
    """
    usuario = get_usuario_logado_supabase()
    
    if not usuario:
        login_page()
        st.stop()
    
    return usuario