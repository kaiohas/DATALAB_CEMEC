# ============================================================
# 🔗 frontend/pages/access_tabs/aba_usuario_grupo.py
# Associação Usuário ↔ Grupo
# ============================================================
import streamlit as st
import pandas as pd
from frontend.supabase_client import get_supabase_client
from frontend.components.feedback import feedback


def aba_usuario_grupo(usuario_logado: str):
    st.subheader("🔗 Associação Usuário ↔ Grupo")

    try:
        supabase = get_supabase_client()
        
        # Busca dados
        resp_usuarios = supabase.table("tab_app_usuarios").select("*").execute()
        resp_grupos = supabase.table("tab_app_grupos").select("*").execute()
        resp_relacoes = supabase.table("tab_app_usuario_grupo").select("*").execute()
        
        df_usuarios = pd.DataFrame(resp_usuarios.data) if resp_usuarios.data else pd.DataFrame()
        df_grupos = pd.DataFrame(resp_grupos.data) if resp_grupos.data else pd.DataFrame()
        df_relacoes = pd.DataFrame(resp_relacoes.data) if resp_relacoes.data else pd.DataFrame()
        
    except Exception as e:
        feedback(f"❌ Erro ao carregar dados: {e}", "error", "⚠️")
        return

    # =====================================================
    # 👁️ VISUALIZAÇÃO
    # =====================================================
    st.markdown("### 👁️ Associações Atuais")
    
    if not df_relacoes.empty:
        # Merge para exibir nomes
        df_relacoes_display = df_relacoes.copy()
        df_relacoes_display = df_relacoes_display.merge(
            df_usuarios[["id_usuario", "nm_usuario"]], 
            on="id_usuario", 
            how="left"
        )
        df_relacoes_display = df_relacoes_display.merge(
            df_grupos[["id_grupo", "nm_grupo"]], 
            on="id_grupo", 
            how="left"
        )
        
        st.dataframe(
            df_relacoes_display[["nm_usuario", "nm_grupo", "sn_ativo"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhuma associação cadastrada ainda.")

    # =====================================================
    # ➕ VINCULAR USUÁRIO A GRUPO
    # =====================================================
    st.markdown("---")
    st.markdown("### ➕ Vincular Usuário a Grupo")
    
    if df_usuarios.empty or df_grupos.empty:
        st.warning("⚠️ Crie usuários e grupos primeiro!")
        return
    
    with st.form("form_vincular"):
        usuario_sel = st.selectbox("Selecione um usuário", df_usuarios["nm_usuario"].tolist())
        grupo_sel = st.selectbox("Selecione um grupo", df_grupos["nm_grupo"].tolist())
        
        if st.form_submit_button("🔗 Vincular", use_container_width=True):
            try:
                supabase = get_supabase_client()
                
                # Pega IDs
                id_usuario = int(df_usuarios[df_usuarios["nm_usuario"] == usuario_sel].iloc[0]["id_usuario"])
                id_grupo = int(df_grupos[df_grupos["nm_grupo"] == grupo_sel].iloc[0]["id_grupo"])
                
                # Verifica se já está vinculado
                existing = supabase.table("tab_app_usuario_grupo").select("id_usuario_grupo").eq("id_usuario", id_usuario).eq("id_grupo", id_grupo).execute()
                if existing.data:
                    st.error("❌ Este usuário já está neste grupo")
                    return
                
                # Cria vinculação
                supabase.table("tab_app_usuario_grupo").insert({
                    "id_usuario": id_usuario,
                    "id_grupo": id_grupo,
                    "sn_ativo": True
                }).execute()
                
                feedback(f"✅ {usuario_sel} vinculado ao grupo {grupo_sel}!", "success", "🎉")
                st.rerun()
                
            except Exception as e:
                feedback(f"❌ Erro: {e}", "error", "⚠️")

    # =====================================================
    # 🗑️ REMOVER USUÁRIO DE GRUPO
    # =====================================================
    st.markdown("---")
    st.markdown("### 🗑️ Remover Usuário de Grupo")
    
    if not df_relacoes.empty:
        df_relacoes_display = df_relacoes.copy()
        df_relacoes_display = df_relacoes_display.merge(
            df_usuarios[["id_usuario", "nm_usuario"]], 
            on="id_usuario", 
            how="left"
        )
        df_relacoes_display = df_relacoes_display.merge(
            df_grupos[["id_grupo", "nm_grupo"]], 
            on="id_grupo", 
            how="left"
        )
        
        # Cria labels para seleção
        assoc_labels = [
            f"{row['nm_usuario']} → {row['nm_grupo']}"
            for _, row in df_relacoes_display.iterrows()
        ]
        
        assoc_sel = st.selectbox(
            "Selecione uma associação para remover",
            assoc_labels,
            key="select_remove_assoc"
        )
        
        if st.button("❌ Remover Associação", use_container_width=True):
            try:
                partes = assoc_sel.split(" → ")
                usuario_remove = partes[0]
                grupo_remove = partes[1]
                
                id_usuario = int(df_usuarios[df_usuarios["nm_usuario"] == usuario_remove].iloc[0]["id_usuario"])
                id_grupo = int(df_grupos[df_grupos["nm_grupo"] == grupo_remove].iloc[0]["id_grupo"])
                
                supabase = get_supabase_client()
                supabase.table("tab_app_usuario_grupo").delete().eq(
                    "id_usuario", id_usuario
                ).eq("id_grupo", id_grupo).execute()
                
                feedback(f"✅ {usuario_remove} removido do grupo {grupo_remove}!", "success", "🗑️")
                st.rerun()
                
            except Exception as e:
                feedback(f"❌ Erro ao remover: {e}", "error", "⚠️")
    else:
        st.info("Nenhuma associação para remover")