# ============================================================
# 🔗 frontend/pages/access_tabs/aba_usuario_grupo.py
# Associação Usuário ↔ Grupo
# ============================================================
import streamlit as st
import pandas as pd

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def aba_usuario_grupo(usuario_logado: str):
    st.subheader("🔗 Associação Usuário ↔ Grupo")

    try:
        supabase = get_supabase_client()

        resp_usuarios = supabase_execute(lambda: supabase.table("tab_app_usuarios").select("id_usuario, nm_usuario").eq("sn_ativo", True).order("nm_usuario").execute())
        resp_grupos   = supabase_execute(lambda: supabase.table("tab_app_grupos").select("id_grupo, nm_grupo").eq("sn_ativo", True).order("nm_grupo").execute())
        resp_relacoes = supabase_execute(lambda: supabase.table("tab_app_usuario_grupo").select("id_usuario, id_grupo").execute())

        df_usuarios = pd.DataFrame(resp_usuarios.data) if resp_usuarios.data else pd.DataFrame()
        df_grupos   = pd.DataFrame(resp_grupos.data)   if resp_grupos.data   else pd.DataFrame()
        df_relacoes = pd.DataFrame(resp_relacoes.data) if resp_relacoes.data else pd.DataFrame()

    except Exception as e:
        feedback(f"❌ Erro ao carregar dados: {e}", "error", "⚠️")
        return

    if df_usuarios.empty or df_grupos.empty:
        st.warning("⚠️ Crie usuários e grupos primeiro!")
        return

    todos_grupos = df_grupos["nm_grupo"].tolist()

    # =====================================================
    # RESUMO
    # =====================================================
    if not df_relacoes.empty:
        df_resumo = (
            df_relacoes
            .merge(df_usuarios, on="id_usuario", how="left")
            .merge(df_grupos,   on="id_grupo",   how="left")
        )
        st.markdown("### 👁️ Associações Atuais")
        st.dataframe(
            df_resumo[["nm_usuario", "nm_grupo"]].rename(columns={"nm_usuario": "Usuário", "nm_grupo": "Grupo"}),
            use_container_width=True,
            hide_index=True,
        )
        st.markdown("---")

    # =====================================================
    # GERENCIAR GRUPOS DO USUÁRIO
    # =====================================================
    st.markdown("### ✏️ Gerenciar Grupos do Usuário")

    usuario_sel = st.selectbox(
        "Selecione um usuário",
        df_usuarios["nm_usuario"].tolist(),
        key="ug_usuario_sel",
    )

    if usuario_sel:
        id_usuario = int(df_usuarios[df_usuarios["nm_usuario"] == usuario_sel].iloc[0]["id_usuario"])

        grupos_atuais_ids = set()
        if not df_relacoes.empty:
            grupos_atuais_ids = set(
                df_relacoes[df_relacoes["id_usuario"] == id_usuario]["id_grupo"].tolist()
            )

        grupos_atuais_nomes = set(
            df_grupos[df_grupos["id_grupo"].isin(grupos_atuais_ids)]["nm_grupo"].tolist()
        )

        grupos_sel = st.multiselect(
            "Grupos vinculados:",
            options=todos_grupos,
            default=sorted(grupos_atuais_nomes),
            key="ug_grupos_sel",
        )

        if st.button("💾 Salvar vínculos", use_container_width=True, type="primary", key="ug_salvar"):
            try:
                supabase = get_supabase_client()

                selecionados_nomes = set(grupos_sel)
                para_inserir = selecionados_nomes - grupos_atuais_nomes
                para_remover = grupos_atuais_nomes - selecionados_nomes

                for nm in para_inserir:
                    id_grupo = int(df_grupos[df_grupos["nm_grupo"] == nm].iloc[0]["id_grupo"])
                    ig = id_grupo
                    supabase_execute(
                        lambda ig=ig: supabase.table("tab_app_usuario_grupo")
                        .insert({"id_usuario": id_usuario, "id_grupo": ig, "sn_ativo": True})
                        .execute()
                    )

                for nm in para_remover:
                    id_grupo = int(df_grupos[df_grupos["nm_grupo"] == nm].iloc[0]["id_grupo"])
                    ig = id_grupo
                    supabase_execute(
                        lambda ig=ig: supabase.table("tab_app_usuario_grupo")
                        .delete()
                        .eq("id_usuario", id_usuario)
                        .eq("id_grupo", ig)
                        .execute()
                    )

                partes = []
                if para_inserir:
                    partes.append(f"+{len(para_inserir)} grupo(s)")
                if para_remover:
                    partes.append(f"-{len(para_remover)} grupo(s)")

                msg = f"✅ Vínculos de '{usuario_sel}' atualizados" + (f" ({', '.join(partes)})" if partes else " (sem alterações)")
                feedback(msg, "success", "💾")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro ao salvar: {e}", "error", "⚠️")
