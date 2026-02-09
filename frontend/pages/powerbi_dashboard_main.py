# ============================================================
# 📂 frontend/pages/gestao_relatorios_main.py
# ============================================================
import streamlit as st
from backend.api.access_management_backend import get_usuario_logado

# Importa as abas modulares
from frontend.pages.powerbi.aba_powerbi_dashboard import aba_powerbi_dashboard


def powerbi_dashboard_main():
    """Centralizador do módulo Gestão de Relatórios Automatizados."""
    usuario_logado = get_usuario_logado(st.context)
    st.title("📈 Gestão de Relatórios Automatizados")
    st.caption(f"Usuário logado: `{usuario_logado}`")
    st.markdown("---")

    abas = st.tabs([
        "📚 Dashboard Power BI"
    ])
    
    with abas[0]:
        aba_powerbi_dashboard(usuario_logado) 
    