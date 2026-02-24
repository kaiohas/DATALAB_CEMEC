# ============================================================
# ⚙️ frontend/pages/settings.py
# Página de configurações
# ============================================================
import streamlit as st

from frontend.supabase_client import get_supabase_client, supabase_execute


def page_settings():
    st.title("⚙️ Configurações")

    # Busca dados do usuário
    if "usuario_data" in st.session_state:
        usuario = st.session_state["usuario_data"]

        st.markdown("### 👤 Seus Dados")

        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Usuário", value=usuario.get("nm_usuario"), disabled=True)
        with col2:
            st.text_input("Email", value=usuario.get("ds_email"), disabled=True)

        st.markdown("### 🎨 Preferências")

        tema_atual = usuario.get("tp_tema", "light")
        novo_tema = st.radio("Tema", ["light", "dark"], index=0 if tema_atual == "light" else 1)

        if st.button("💾 Salvar Preferências"):
            try:
                supabase = get_supabase_client()
                supabase_execute(
                    lambda: supabase.table("tab_app_usuarios")
                    .update({"tp_tema": novo_tema})
                    .eq("id_usuario", usuario["id_usuario"])
                    .execute()
                )

                st.success("✅ Preferências salvas com sucesso!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro: {str(e)}")