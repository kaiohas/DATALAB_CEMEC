# ============================================================
# 📐 frontend/components/layout.py
# Componentes de layout (footer, header, etc)
# ============================================================
import streamlit as st

def render_footer():
    """Renderiza o rodapé da aplicação."""
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📦 DataLab App")
        st.caption("Gestão de dados e BI Clínico")
    
    with col2:
        st.markdown("### 🔗 Links Úteis")
        st.markdown("[Sharepoint](https://careaccessresearch.sharepoint.com/:f:/r/sites/CEMECPESQUISACLINICA/Shared%20Documents/DEPARTAMENTOS/GESTAO/Dados%20-%20BI?csf=1&web=1&e=abTJxh)")
        st.markdown("[Contato suporte](https://teams.microsoft.com/l/chat/48:notes/conversations?context=%7B%22contextType%22%3A%22chat%22%7D)")
    
    with col3:
        st.markdown("### ℹ️ Informações")
        usuario = st.session_state.get("usuario_logado", "desconhecido")
        st.caption(f"Usuário: {usuario}")
        st.caption("v1.0.0")
