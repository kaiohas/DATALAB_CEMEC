# ============================================================
# ⚙️ frontend/pages/dimensoes.py
# Gestão de Dimensões (Variáveis e Estudos)
# ============================================================
import streamlit as st
from frontend.pages.dimensoes_tabs.aba_variaveis import aba_variaveis
from frontend.pages.dimensoes_tabs.aba_estudos import aba_estudos


def page_dimensoes():
    """
    Centralizador do módulo Gestão de Dimensões.
    Gerencia variáveis e estudos.
    """
    usuario_logado = st.session_state.get("usuario_logado", "desconhecido")
    
    st.title("⚙️ Gestão de Dimensões")
    st.caption(f"Usuário logado: `{usuario_logado}`")
    st.markdown("---")

    # Abas para cada funcionalidade
    abas = st.tabs([
        "📋 Variáveis",
        "📚 Estudos"
    ])

    with abas[0]:
        aba_variaveis(usuario_logado)
    
    with abas[1]:
        aba_estudos(usuario_logado)