# ============================================================
# 📋 frontend/components/menu.py
# Menu dinâmico baseado em grupos do usuário
# ============================================================
import streamlit as st
import pandas as pd

from frontend.supabase_client import get_supabase_client, supabase_execute


@st.cache_data(ttl=300)
def load_pages_by_group(usuario: str):
    """
    Carrega páginas que o usuário pode acessar através do seu grupo.

    Fluxo:
    1. Busca grupos que o usuário pertence (tab_app_usuario_grupo)
    2. Busca páginas vinculadas a esses grupos (tab_app_grupo_pagina)
    3. Retorna as páginas ativas ordenadas por nr_ordem
    """
    return _load_pages_by_group_internal(usuario, tentativa=1)


def _reset_client():
    """Reseta o client Supabase inline (sem depender de import separado)."""
    import frontend.supabase_client as sc
    sc._supabase_client = None


def _load_pages_by_group_internal(usuario: str, tentativa: int = 1):
    """Lógica interna com retry em caso de falha de conexão."""
    try:
        supabase = get_supabase_client()

        # 1️⃣ Buscar ID do usuário
        resp_usuario = supabase_execute(
            lambda: supabase.table("tab_app_usuarios")
            .select("id_usuario")
            .eq("nm_usuario", usuario.lower().strip())
            .execute()
        )

        if not resp_usuario.data:
            st.warning("⚠️ Usuário não encontrado")
            return pd.DataFrame()

        id_usuario = resp_usuario.data[0]["id_usuario"]

        # 2️⃣ Buscar grupos do usuário (apenas ativos)
        resp_grupos = supabase_execute(
            lambda: supabase.table("tab_app_usuario_grupo")
            .select("id_grupo")
            .eq("id_usuario", id_usuario)
            .eq("sn_ativo", True)
            .execute()
        )

        if not resp_grupos.data:
            st.info("ℹ️ Nenhum grupo vinculado a este usuário")
            return pd.DataFrame()

        ids_grupos = [g["id_grupo"] for g in resp_grupos.data]

        # 3️⃣ Buscar TODAS as páginas primeiro (com nr_ordem)
        resp_todas_paginas = supabase_execute(
            lambda: supabase.table("tab_app_paginas")
            .select("*")
            .eq("sn_ativo", True)
            .order("nr_ordem")
            .execute()
        )
        df_paginas = pd.DataFrame(resp_todas_paginas.data) if resp_todas_paginas.data else pd.DataFrame()

        # 4️⃣ Buscar permissões dos grupos
        resp_permissoes = supabase_execute(
            lambda: supabase.table("tab_app_grupo_pagina")
            .select("id_pagina")
            .in_("id_grupo", ids_grupos)
            .eq("sn_ativo", True)
            .execute()
        )

        if not resp_permissoes.data:
            st.info("ℹ️ Nenhuma página disponível para seus grupos")
            return pd.DataFrame()

        # 5️⃣ Filtrar páginas com permissão
        ids_paginas_permitidas = [p["id_pagina"] for p in resp_permissoes.data]
        df_paginas = df_paginas[df_paginas["id_pagina"].isin(ids_paginas_permitidas)]

        # 6️⃣ Normalizar colunas e ordenar por nr_ordem
        if not df_paginas.empty:
            df_paginas.columns = [c.lower() for c in df_paginas.columns]
            df_paginas = df_paginas.sort_values("nr_ordem")

        return df_paginas

    except OSError as e:
        # ✅ [Errno 11] Resource temporarily unavailable — reseta e tenta de novo
        if tentativa <= 2:
            _reset_client()
            import time
            time.sleep(0.5 * tentativa)
            return _load_pages_by_group_internal(usuario, tentativa + 1)
        else:
            st.error(f"❌ Erro ao carregar páginas após {tentativa} tentativas: {str(e)}")
            return pd.DataFrame()

    except Exception as e:
        st.error(f"❌ Erro ao carregar páginas: {str(e)}")
        return pd.DataFrame()


def render_sidebar(usuario_logado: str):
    """Renderiza o menu sidebar dinâmico baseado em grupos."""
    st.sidebar.title("📍 Menu")
    st.sidebar.image("assets/logo.png", width=195)
    df_paginas = load_pages_by_group(usuario_logado)

    if df_paginas.empty:
        st.sidebar.info("Nenhuma página disponível")
        return

    # Renderiza cada página como um botão
    for _, row in df_paginas.iterrows():
        icone = row.get("ds_icone", "📄")
        label = row.get("ds_label", row.get("nm_pagina", ""))
        nm_pagina = row.get("nm_pagina")

        if st.sidebar.button(f"{icone} {label}", use_container_width=True, key=nm_pagina):
            st.session_state["current_page"] = nm_pagina
            st.rerun()
