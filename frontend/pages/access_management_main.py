# ============================================================
# 🔐 frontend/pages/access_management_main.py
# Gestão de Acesso (Usuários, Grupos, Permissões)
# ============================================================
import streamlit as st
from frontend.pages.access_tabs.aba_usuarios import aba_usuarios
from frontend.pages.access_tabs.aba_grupos import aba_grupos
from frontend.pages.access_tabs.aba_usuario_grupo import aba_usuario_grupo
from frontend.pages.access_tabs.aba_paginas import aba_paginas
from frontend.pages.access_tabs.aba_grupo_pagina import aba_grupo_pagina


def page_access_management():
    """
    Centralizador do módulo Access Management (RLS do APP).
    Gerencia usuários, grupos e permissões de acesso.
    """
    usuario_logado = st.session_state.get("usuario_logado", "desconhecido")
    
    st.title("🔐 Gestão de Acesso (RLS)")
    st.caption(f"Usuário logado: `{usuario_logado}`")
    st.markdown("---")

    # Abas para cada funcionalidade
    abas = st.tabs([
        "🧍 Usuários",
        "🧩 Grupos",
        "🔗 Usuário ↔ Grupo",
        "📄 Páginas",
        "🔒 Grupo ↔ Página"
    ])

    with abas[0]:
        aba_usuarios(usuario_logado)
    
    with abas[1]:
        aba_grupos(usuario_logado)
    
    with abas[2]:
        aba_usuario_grupo(usuario_logado)
    
    with abas[3]:
        aba_paginas(usuario_logado)
    
    with abas[4]:
        aba_grupo_pagina(usuario_logado)