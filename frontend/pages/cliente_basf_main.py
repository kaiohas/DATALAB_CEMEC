# ============================================================
# 📂 frontend/pages/gestao_relatorios_main.py
# ============================================================
import streamlit as st
from backend.api.access_management_backend import get_usuario_logado

# Importa as abas modulares
from frontend.pages.clientes.basf.aba_venda_malhafina_nf import aba_venda_malhafina_nf


def page_cliente_basf_main():
    """Centralizador do módulo Gestão de Relatórios Automatizados."""
    usuario_logado = get_usuario_logado(st.context)
    st.title("📈 Gestão de Relatórios Automatizados")
    st.caption(f"Usuário logado: `{usuario_logado}`")
    st.markdown("---")

    abas = st.tabs([
        "📚 Malha Fina Notas Fiscais"
    ])
    
    with abas[0]:
        aba_venda_malhafina_nf(usuario_logado) 
    