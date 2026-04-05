# ============================================================
# 🏠 app.py
# Aplicação principal Streamlit com Supabase
# ============================================================
import os
import logging
import streamlit as st
import pandas as pd
from importlib import import_module

# ============================================================
# ⚙️ CONFIGURAÇÕES INICIAIS - DEVE SER O PRIMEIRO COMANDO ST
# ============================================================
st.set_page_config(
    page_title="DataLab App", 
    layout="wide",
    page_icon="🩺",  # Estetoscópio
    initial_sidebar_state="expanded"
)

from frontend.pages import home
from frontend.components.auth import has_access, access_denied
from frontend.components.layout import render_footer
from frontend.components.menu import render_sidebar
from frontend.components.login import check_authentication, logout
from frontend.config import get_config

# ============================================================
# 🔇 CONFIGURAÇÃO DE LOGGING (Suprimir mensagens HTTP)
# ============================================================
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Oculta o menu multipágina padrão do Streamlit
st.markdown("""
    <style>
    [data-testid="stSidebarNav"], .css-1v3fvcr, .css-hby737 {
        display: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# ============================================================
# 🔐 AUTENTICAÇÃO (Middleware)
# ============================================================
usuario_logado = check_authentication()

# ============================================================
# 🧭 ESTADO DE SESSÃO
# ============================================================
BASE_ROLES = ["Analyst", "Developer", "Admin"]
st.session_state.setdefault("available_roles", BASE_ROLES.copy())
st.session_state.setdefault("user_role", "Admin")
st.session_state.setdefault("current_page", "Home")

# Carrega configuração
Config = get_config()

# ============================================================
# 🎨 TEMA FIXO: Light
# ============================================================
st._config.set_option("theme.base", "light")
st._config.set_option("theme.primaryColor", "#0a84ff")
st._config.set_option("theme.secondaryBackgroundColor", "#f0f2f6")
st._config.set_option("theme.textColor", "#262730")
st.session_state["app_theme"] = "light"

# ============================================================
# 📱 SIDEBAR (Menu + Logout)
# ============================================================
with st.sidebar:
    st.markdown(f"### 👋 Bem-vindo, **{usuario_logado}**!")
    
    if st.button("🚺 Logout", use_container_width=True):
        logout()
    
    st.markdown("---")
    render_sidebar(usuario_logado)

# ============================================================
# 🧩 CARREGAMENTO DINÂMICO DE PÁGINAS
# ============================================================
page_map = {
    "Home": home.page_home
}

try:
    from frontend.components.menu import load_pages_by_group
    
    df_paginas = load_pages_by_group(usuario_logado)
    
    if not df_paginas.empty:
        for _, row in df_paginas.iterrows():
            try:
                modulo = import_module(f"frontend.pages.{row['ds_modulo']}")
                funcao = getattr(modulo, row['nm_funcao'])
                page_map[row['nm_pagina']] = funcao
                
            except AttributeError:
                st.warning(f"⚠️ Função '{row['nm_funcao']}' não encontrada no módulo '{row['ds_modulo']}'")
            except ImportError:
                st.warning(f"⚠️ Módulo 'frontend.pages.{row['ds_modulo']}' não encontrado")
            except Exception as e:
                st.warning(f"⚠️ Erro ao carregar página '{row['nm_pagina']}': {str(e)}")

except OSError as e:
    # ✅ Tratamento específico para [Errno 11] — reseta o client inline
    import frontend.supabase_client as sc
    sc._supabase_client = None
    st.warning("⚠️ Conexão temporariamente indisponível. Recarregue a página.")

except Exception as e:
    st.error(f"❌ Erro ao carregar páginas: {str(e)}")

# ============================================================
# 🎯 RENDERIZA A PÁGINA ATUAL
# ============================================================
current_page = st.session_state.get("current_page", "Home")

if has_access(current_page):
    page_function = page_map.get(current_page)
    
    if page_function:
        try:
            page_function()
        except Exception as e:
            st.error(f"❌ Erro ao renderizar página: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    else:
        st.error(f"❌ Página '{current_page}' não encontrada")
else:
    access_denied(current_page)

# ============================================================
# 📄 RODAPÉ
# ============================================================
render_footer()