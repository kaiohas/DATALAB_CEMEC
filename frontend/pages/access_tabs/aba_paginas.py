# ============================================================
# 📄 frontend/pages/access_tabs/aba_paginas.py
# Gestão de Páginas
# ============================================================
import streamlit as st
import pandas as pd
from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def aba_paginas(usuario_logado: str):
    st.subheader("📄 Gestão de Páginas")

    try:
        supabase = get_supabase_client()
        response = supabase.table("tab_app_paginas").select("*").execute()
        df_paginas = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        
    except Exception as e:
        feedback(f"❌ Erro ao carregar páginas: {e}", "error", "⚠️")
        return

    st.markdown("### 👁️ Páginas Cadastradas")
    
    if not df_paginas.empty:
        df_paginas.columns = [c.lower() for c in df_paginas.columns]
        st.dataframe(
            df_paginas[["nm_pagina", "ds_label", "ds_modulo", "nm_funcao", "sn_ativo"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhuma página cadastrada.")

    # =====================================================
    # ➕ CRIAR NOVA PÁGINA
    # =====================================================
    st.markdown("---")
    st.markdown("### ➕ Criar Nova Página")
    
    with st.form("form_nova_pagina"):
        col1, col2 = st.columns(2)

        with col1:
            nm_pagina = st.text_input("Nome técnico (único)", placeholder="dashboard_vendas")
            ds_label = st.text_input("Label (exibição)", placeholder="📊 Vendas")

        with col2:
            ds_modulo = st.text_input("Módulo", placeholder="dashboards")
            nm_funcao = st.text_input("Função", placeholder="page_vendas")

        ds_icone = st.text_input("Ícone", placeholder="📊")
        grupo_novo = st.text_input("Grupo", placeholder="agenda")
        nr_ordem = st.number_input("Ordem de exibição", value=999, min_value=1)
        sn_ativo = st.checkbox("Ativa", value=True)

        if st.form_submit_button("✅ Criar Página", use_container_width=True):
            if not nm_pagina:
                st.error("⚠️ Nome técnico é obrigatório")
            else:
                try:
                    supabase = get_supabase_client()

                    supabase.table("tab_app_paginas").insert({
                        "nm_pagina": nm_pagina,
                        "ds_label": ds_label,
                        "ds_icone": ds_icone,
                        "ds_modulo": ds_modulo,
                        "nm_funcao": nm_funcao,
                        "grupo": grupo_novo or None,
                        "nr_ordem": int(nr_ordem),
                        "sn_ativo": sn_ativo
                    }).execute()
                    
                    feedback(f"✅ Página '{nm_pagina}' criada!", "success", "🎉")
                    st.rerun()
                    
                except Exception as e:
                    feedback(f"❌ Erro: {e}", "error", "⚠️")

    # =====================================================
    # ✏️ EDITAR PÁGINA
    # =====================================================
    st.markdown("---")
    st.markdown("### ✏️ Editar Página")
    
    if not df_paginas.empty:
        df_paginas.columns = [c.lower() for c in df_paginas.columns]
        pagina_sel = st.selectbox("Selecione uma página", df_paginas["nm_pagina"].tolist())
        
        if pagina_sel:
            pagina_data = df_paginas[df_paginas["nm_pagina"] == pagina_sel].iloc[0]
            
            with st.form(f"form_editar_{pagina_sel}"):
                novo_nm_pagina = st.text_input("Nome técnico", value=pagina_data.get("nm_pagina", ""))

                col1, col2 = st.columns(2)

                with col1:
                    nova_label = st.text_input("Label", value=pagina_data.get("ds_label", ""))
                    novo_modulo = st.text_input("Módulo", value=pagina_data.get("ds_modulo", ""))

                with col2:
                    novo_icone = st.text_input("Ícone", value=pagina_data.get("ds_icone", ""))
                    nova_funcao = st.text_input("Função", value=pagina_data.get("nm_funcao", ""))

                novo_grupo = st.text_input("Grupo", value=pagina_data.get("grupo", "") or "")
                nova_ordem = st.number_input(
                    "Ordem",
                    min_value=1,
                    value=int(pagina_data.get("nr_ordem", 999))
                )
                novo_ativo = st.checkbox(
                    "Ativa",
                    value=bool(pagina_data.get("sn_ativo", True))
                )

                if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                    if not novo_nm_pagina.strip():
                        st.error("⚠️ Nome técnico é obrigatório")
                    else:
                        try:
                            supabase = get_supabase_client()
                            nn = novo_nm_pagina.strip()

                            if nn != pagina_sel:
                                existing = supabase_execute(
                                    lambda: supabase.table("tab_app_paginas")
                                    .select("nm_pagina")
                                    .eq("nm_pagina", nn)
                                    .execute()
                                )
                                if existing.data:
                                    st.error(f"❌ Já existe uma página com o nome '{nn}'")
                                    st.stop()

                            nome_ant = pagina_sel
                            supabase_execute(
                                lambda: supabase.table("tab_app_paginas").update({
                                    "nm_pagina": nn,
                                    "ds_label": nova_label,
                                    "ds_icone": novo_icone,
                                    "ds_modulo": novo_modulo,
                                    "nm_funcao": nova_funcao,
                                    "grupo": novo_grupo.strip() or None,
                                    "nr_ordem": int(nova_ordem),
                                    "sn_ativo": novo_ativo,
                                }).eq("nm_pagina", nome_ant).execute()
                            )

                            feedback(f"✅ Página '{nn}' atualizada!", "success", "💾")
                            st.rerun()

                        except Exception as e:
                            feedback(f"❌ Erro ao atualizar: {e}", "error", "⚠️")

    # =====================================================
    # 🗑️ DELETAR PÁGINA
    # =====================================================
    st.markdown("---")
    st.markdown("### 🗑️ Deletar Página")
    
    if not df_paginas.empty:
        df_paginas.columns = [c.lower() for c in df_paginas.columns]
        pagina_deletar = st.selectbox(
            "Selecione uma página para deletar",
            df_paginas["nm_pagina"].tolist(),
            key="select_delete_pagina"
        )
        
        if st.button("❌ Deletar Página", use_container_width=True):
            try:
                supabase = get_supabase_client()
                supabase.table("tab_app_paginas").delete().eq("nm_pagina", pagina_deletar).execute()
                
                feedback(f"✅ Página '{pagina_deletar}' deletada!", "success", "🗑️")
                st.rerun()
                
            except Exception as e:
                feedback(f"❌ Erro ao deletar: {e}", "error", "⚠️")