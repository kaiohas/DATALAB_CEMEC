# ============================================================
# 🧩 frontend/pages/access_tabs/aba_grupos.py
# Gestão de Grupos
# ============================================================
import streamlit as st
import pandas as pd

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def aba_grupos(usuario_logado: str):
    st.subheader("🧩 Gestão de Grupos")

    try:
        supabase = get_supabase_client()
        response = supabase_execute(lambda: supabase.table("tab_app_grupos").select("*").execute())
        df_grupos = pd.DataFrame(response.data) if response.data else pd.DataFrame()

    except Exception as e:
        feedback(f"❌ Erro ao carregar grupos: {e}", "error", "⚠️")
        return

    if not df_grupos.empty:
        df_grupos.columns = [c.lower() for c in df_grupos.columns]

        st.markdown("### 👁️ Grupos Cadastrados")
        st.dataframe(
            df_grupos[["nm_grupo", "ds_grupo", "sn_ativo"]],
            use_container_width=True,
            hide_index=True,
        )

    # =====================================================
    # ➕ CRIAR NOVO GRUPO
    # =====================================================
    st.markdown("---")
    st.markdown("### ➕ Criar Novo Grupo")

    with st.form("form_novo_grupo"):
        nm_grupo = st.text_input("Nome do grupo (único)", placeholder="Gerentes")
        ds_grupo = st.text_area("Descrição", placeholder="Descrição do grupo...", height=100)

        if st.form_submit_button("✅ Criar Grupo", use_container_width=True):
            if not nm_grupo:
                st.error("⚠️ Nome do grupo é obrigatório")
            else:
                try:
                    supabase = get_supabase_client()

                    # Verifica se grupo já existe
                    existing = supabase_execute(
                        lambda: supabase.table("tab_app_grupos")
                        .select("id_grupo")
                        .eq("nm_grupo", nm_grupo)
                        .execute()
                    )
                    if existing.data:
                        st.error("❌ Este grupo já existe")
                        return

                    # Cria novo grupo
                    supabase_execute(
                        lambda: supabase.table("tab_app_grupos")
                        .insert({
                            "nm_grupo": nm_grupo,
                            "ds_grupo": ds_grupo,
                            "sn_ativo": True,
                        })
                        .execute()
                    )

                    feedback(f"✅ Grupo '{nm_grupo}' criado com sucesso!", "success", "🎉")
                    st.rerun()

                except Exception as e:
                    feedback(f"❌ Erro ao criar grupo: {e}", "error", "⚠️")

    # =====================================================
    # ✏️ EDITAR GRUPO
    # =====================================================
    st.markdown("---")
    st.markdown("### ✏️ Editar Grupo")

    if not df_grupos.empty:
        df_grupos.columns = [c.lower() for c in df_grupos.columns]
        grupo_sel = st.selectbox("Selecione um grupo para editar", df_grupos["nm_grupo"].tolist())

        if grupo_sel:
            grupo_data = df_grupos[df_grupos["nm_grupo"] == grupo_sel].iloc[0]

            with st.form(f"form_editar_{grupo_sel}"):
                nova_descricao = st.text_area(
                    "Descrição",
                    value=grupo_data.get("ds_grupo", ""),
                    height=100,
                )
                novo_status = st.checkbox(
                    "Ativo",
                    value=bool(grupo_data.get("sn_ativo", True)),
                )

                if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                    try:
                        supabase = get_supabase_client()
                        supabase_execute(
                            lambda: supabase.table("tab_app_grupos")
                            .update({
                                "ds_grupo": nova_descricao,
                                "sn_ativo": novo_status,
                            })
                            .eq("nm_grupo", grupo_sel)
                            .execute()
                        )

                        feedback(f"✅ Grupo '{grupo_sel}' atualizado!", "success", "💾")
                        st.rerun()

                    except Exception as e:
                        feedback(f"❌ Erro ao atualizar: {e}", "error", "⚠️")

    # =====================================================
    # 🗑️ DELETAR GRUPO
    # =====================================================
    st.markdown("---")
    st.markdown("### 🗑️ Deletar Grupo")

    if not df_grupos.empty:
        df_grupos.columns = [c.lower() for c in df_grupos.columns]
        grupo_deletar = st.selectbox(
            "Selecione um grupo para deletar",
            df_grupos["nm_grupo"].tolist(),
            key="select_delete_grupo",
        )

        if st.button("❌ Deletar Grupo", use_container_width=True):
            try:
                supabase = get_supabase_client()
                supabase_execute(
                    lambda: supabase.table("tab_app_grupos")
                    .delete()
                    .eq("nm_grupo", grupo_deletar)
                    .execute()
                )

                feedback(f"✅ Grupo '{grupo_deletar}' deletado!", "success", "🗑️")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro ao deletar: {e}", "error", "⚠️")