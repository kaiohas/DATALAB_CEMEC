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

        resp_grupos   = supabase_execute(lambda: supabase.table("tab_app_grupos").select("id_grupo, nm_grupo").eq("sn_ativo", True).order("nm_grupo").execute())
        resp_paginas  = supabase_execute(lambda: supabase.table("tab_app_paginas").select("id_pagina, nm_pagina").eq("sn_ativo", True).order("nm_pagina").execute())
        resp_relacoes = supabase_execute(lambda: supabase.table("tab_app_grupo_pagina").select("id_grupo, id_pagina").execute())

        df_grupos   = pd.DataFrame(resp_grupos.data)   if resp_grupos.data   else pd.DataFrame()
        df_paginas  = pd.DataFrame(resp_paginas.data)  if resp_paginas.data  else pd.DataFrame()
        df_relacoes = pd.DataFrame(resp_relacoes.data) if resp_relacoes.data else pd.DataFrame()

    except Exception as e:
        feedback(f"❌ Erro ao carregar dados: {e}", "error", "⚠️")
        return

    if df_grupos.empty or df_paginas.empty:
        st.warning("⚠️ Crie grupos e páginas primeiro!")
        return

    todas_paginas = df_paginas["nm_pagina"].tolist()

    # =====================================================
    # RESUMO
    # =====================================================
    if not df_relacoes.empty:
        df_resumo = (
            df_relacoes
            .merge(df_grupos,  on="id_grupo",  how="left")
            .merge(df_paginas, on="id_pagina", how="left")
        )
        st.markdown("### 👁️ Permissões Atuais")

        grupos_unicos = ["(Todos)"] + sorted(df_resumo["nm_grupo"].dropna().unique().tolist())
        filtro = st.selectbox("Filtrar por grupo", grupos_unicos, key="gp_filtro")

        df_exibir = df_resumo if filtro == "(Todos)" else df_resumo[df_resumo["nm_grupo"] == filtro]
        st.dataframe(
            df_exibir[["nm_grupo", "nm_pagina"]].rename(columns={"nm_grupo": "Grupo", "nm_pagina": "Página"}),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(f"Total: {len(df_exibir)} permissão(ões)")
        st.markdown("---")

    # =====================================================
    # GERENCIAR PÁGINAS DO GRUPO
    # =====================================================
    st.markdown("### ✏️ Gerenciar Páginas do Grupo")

    grupo_sel = st.selectbox(
        "Selecione um grupo",
        df_grupos["nm_grupo"].tolist(),
        key="gp_grupo_sel",
    )

    if grupo_sel:
        id_grupo = int(df_grupos[df_grupos["nm_grupo"] == grupo_sel].iloc[0]["id_grupo"])

        paginas_atuais_ids = set()
        if not df_relacoes.empty:
            paginas_atuais_ids = set(
                df_relacoes[df_relacoes["id_grupo"] == id_grupo]["id_pagina"].tolist()
            )

        paginas_atuais_nomes = set(
            df_paginas[df_paginas["id_pagina"].isin(paginas_atuais_ids)]["nm_pagina"].tolist()
        )

        paginas_sel = st.multiselect(
            "Páginas com acesso:",
            options=todas_paginas,
            default=sorted(paginas_atuais_nomes),
            key="gp_paginas_sel",
        )

        if st.button("💾 Salvar permissões", use_container_width=True, type="primary", key="gp_salvar"):
            try:
                supabase = get_supabase_client()

                selecionadas_nomes = set(paginas_sel)
                para_inserir = selecionadas_nomes - paginas_atuais_nomes
                para_remover = paginas_atuais_nomes - selecionadas_nomes

                for nm in para_inserir:
                    id_pagina = int(df_paginas[df_paginas["nm_pagina"] == nm].iloc[0]["id_pagina"])
                    ip = id_pagina
                    supabase_execute(
                        lambda ip=ip: supabase.table("tab_app_grupo_pagina")
                        .insert({"id_grupo": id_grupo, "id_pagina": ip, "sn_ativo": True})
                        .execute()
                    )

                for nm in para_remover:
                    id_pagina = int(df_paginas[df_paginas["nm_pagina"] == nm].iloc[0]["id_pagina"])
                    ip = id_pagina
                    supabase_execute(
                        lambda ip=ip: supabase.table("tab_app_grupo_pagina")
                        .delete()
                        .eq("id_grupo", id_grupo)
                        .eq("id_pagina", ip)
                        .execute()
                    )

                partes = []
                if para_inserir:
                    partes.append(f"+{len(para_inserir)} página(s)")
                if para_remover:
                    partes.append(f"-{len(para_remover)} página(s)")

                msg = f"✅ Permissões de '{grupo_sel}' atualizadas" + (f" ({', '.join(partes)})" if partes else " (sem alterações)")
                feedback(msg, "success", "💾")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro ao salvar: {e}", "error", "⚠️")
