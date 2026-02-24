# ============================================================
# 🔒 frontend/pages/access_tabs/aba_grupo_pagina.py
# Associação Grupo ↔ Página (Permissões)
# ============================================================
import streamlit as st
import pandas as pd

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def aba_grupo_pagina(usuario_logado: str):
    st.subheader("🔒 Associação Grupo ↔ Página (Permissões)")

    try:
        supabase = get_supabase_client()

        resp_grupos = supabase_execute(lambda: supabase.table("tab_app_grupos").select("*").execute())
        resp_paginas = supabase_execute(lambda: supabase.table("tab_app_paginas").select("*").execute())
        resp_relacoes = supabase_execute(lambda: supabase.table("tab_app_grupo_pagina").select("*").execute())

        df_grupos = pd.DataFrame(resp_grupos.data) if resp_grupos.data else pd.DataFrame()
        df_paginas = pd.DataFrame(resp_paginas.data) if resp_paginas.data else pd.DataFrame()
        df_relacoes = pd.DataFrame(resp_relacoes.data) if resp_relacoes.data else pd.DataFrame()

    except Exception as e:
        feedback(f"❌ Erro ao carregar dados: {e}", "error", "⚠️")
        return

    # =====================================================
    # 👁️ VISUALIZAÇÃO
    # =====================================================
    st.markdown("### 👁️ Permissões Atuais")

    if not df_relacoes.empty:
        df_relacoes_display = df_relacoes.copy()
        df_relacoes_display = df_relacoes_display.merge(
            df_grupos[["id_grupo", "nm_grupo"]],
            on="id_grupo",
            how="left",
        )
        df_relacoes_display = df_relacoes_display.merge(
            df_paginas[["id_pagina", "nm_pagina", "ds_label"]],
            on="id_pagina",
            how="left",
        )

        # ✅ FILTRO POR GRUPO
        st.markdown("#### 🔍 Filtros")

        col1, col2 = st.columns([2, 2])

        with col1:
            grupos_unicos = ["(Todos)"] + sorted(df_relacoes_display["nm_grupo"].unique().tolist())
            grupo_filtro = st.selectbox(
                "Filtrar por Grupo",
                grupos_unicos,
                index=0,
                key="filtro_grupo_permissoes",
            )

        # ✅ APLICAR FILTRO
        if grupo_filtro != "(Todos)":
            df_relacoes_filtrado = df_relacoes_display[df_relacoes_display["nm_grupo"] == grupo_filtro]
        else:
            df_relacoes_filtrado = df_relacoes_display

        st.dataframe(
            df_relacoes_filtrado[["nm_grupo", "nm_pagina", "ds_label", "sn_ativo"]],
            use_container_width=True,
            hide_index=True,
        )

        st.caption(f"Total de permissões: {len(df_relacoes_filtrado)}")
    else:
        st.info("Nenhuma permissão configurada.")

    # =====================================================
    # ➕ ATRIBUIR PERMISSÃO
    # =====================================================
    st.markdown("---")
    st.markdown("### ➕ Atribuir Permissão")

    if df_grupos.empty or df_paginas.empty:
        st.warning("⚠️ Crie grupos e páginas primeiro!")
        return

    with st.form("form_permissao"):
        grupo_sel = st.selectbox("Selecione um grupo", df_grupos["nm_grupo"].tolist())
        pagina_sel = st.selectbox("Selecione uma página", df_paginas["nm_pagina"].tolist())
        sn_ativo = st.checkbox("Ativa", value=True)

        if st.form_submit_button("✅ Atribuir Permissão", use_container_width=True):
            try:
                supabase = get_supabase_client()

                # Busca IDs e converte para int (Python nativo)
                grupo_row = df_grupos[df_grupos["nm_grupo"] == grupo_sel].iloc[0]
                pagina_row = df_paginas[df_paginas["nm_pagina"] == pagina_sel].iloc[0]

                id_grupo = int(grupo_row["id_grupo"])
                id_pagina = int(pagina_row["id_pagina"])

                # Verifica se já existe
                existing = supabase_execute(
                    lambda: supabase.table("tab_app_grupo_pagina")
                    .select("id_grupo_pagina")
                    .eq("id_grupo", id_grupo)
                    .eq("id_pagina", id_pagina)
                    .execute()
                )
                if existing.data:
                    st.error("❌ Este grupo já tem acesso a esta página")
                    return

                # Insere com valores convertidos
                supabase_execute(
                    lambda: supabase.table("tab_app_grupo_pagina")
                    .insert({
                        "id_grupo": id_grupo,
                        "id_pagina": id_pagina,
                        "sn_ativo": sn_ativo,
                    })
                    .execute()
                )

                feedback("✅ Permissão atribuída!", "success", "🎉")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro: {str(e)}", "error", "⚠️")

    # =====================================================
    # 🗑️ REMOVER PERMISSÃO
    # =====================================================
    st.markdown("---")
    st.markdown("### 🗑️ Remover Permissão")

    if not df_relacoes.empty:
        df_relacoes_display = df_relacoes.copy()
        df_relacoes_display = df_relacoes_display.merge(
            df_grupos[["id_grupo", "nm_grupo"]],
            on="id_grupo",
            how="left",
        )
        df_relacoes_display = df_relacoes_display.merge(
            df_paginas[["id_pagina", "nm_pagina"]],
            on="id_pagina",
            how="left",
        )

        # Cria labels para seleção
        perm_labels = [
            f"{row['nm_grupo']} → {row['nm_pagina']}"
            for _, row in df_relacoes_display.iterrows()
        ]

        perm_sel = st.selectbox(
            "Selecione uma permissão para remover",
            perm_labels,
            key="select_remove_perm",
        )

        if st.button("❌ Remover Permissão", use_container_width=True):
            try:
                partes = perm_sel.split(" → ")
                grupo_remove = partes[0]
                pagina_remove = partes[1]

                id_grupo = int(df_grupos[df_grupos["nm_grupo"] == grupo_remove].iloc[0]["id_grupo"])
                id_pagina = int(df_paginas[df_paginas["nm_pagina"] == pagina_remove].iloc[0]["id_pagina"])

                supabase = get_supabase_client()
                supabase_execute(
                    lambda: supabase.table("tab_app_grupo_pagina")
                    .delete()
                    .eq("id_grupo", id_grupo)
                    .eq("id_pagina", id_pagina)
                    .execute()
                )

                feedback("✅ Permissão removida!", "success", "🗑️")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro ao remover: {e}", "error", "⚠️")
    else:
        st.info("Nenhuma permissão para remover")