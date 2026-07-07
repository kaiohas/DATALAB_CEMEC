# ============================================================
# 📋 frontend/pages/dimensoes_tabs/aba_variaveis.py
# Gestão de Variáveis (Dimensões)
# ============================================================
import streamlit as st
import pandas as pd

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def aba_variaveis(usuario_logado: str):
    st.subheader("📋 Gestão de Variáveis")

    try:
        supabase = get_supabase_client()

        # Busca todas as variáveis
        response = supabase_execute(
            lambda: supabase.table("tab_app_variaveis")
            .select("*")
            .order("grupo_destino")
            .execute()
        )
        df_variaveis = pd.DataFrame(response.data) if response.data else pd.DataFrame()

    except Exception as e:
        feedback(f"❌ Erro ao carregar variáveis: {e}", "error", "⚠️")
        return

    # =====================================================
    # 👁️ VISUALIZAÇÃO
    # =====================================================
    st.markdown("### 👁️ Variáveis Cadastradas")

    if not df_variaveis.empty:
        df_variaveis.columns = [c.lower() for c in df_variaveis.columns]

        # Agrupa por grupo_destino
        for grupo in df_variaveis["grupo_destino"].unique():
            with st.expander(f"📁 {grupo}"):
                df_grupo = df_variaveis[df_variaveis["grupo_destino"] == grupo]
                st.dataframe(
                    df_grupo[["uso", "valor"]],
                    use_container_width=True,
                    hide_index=True,
                )
    else:
        st.info("Nenhuma variável cadastrada ainda.")

    # =====================================================
    # ➕ CRIAR NOVA VARIÁVEL
    # =====================================================
    st.markdown("---")
    st.markdown("### ➕ Criar Nova Variável")

    with st.form("form_nova_variavel"):
        col1, col2 = st.columns(2)

        with col1:
            grupo_destino = st.text_input(
                "Grupo de Destino",
                placeholder="ex: campos_estudo, opcoes_modelo",
                help="Agrupa variáveis por categoria",
            )

        with col2:
            uso = st.text_input(
                "Uso (Identificador único)",
                placeholder="ex: centro, disciplina, coordenacao",
                help="Chave única para identificar a variável",
            )

        valor = st.text_area(
            "Valor",
            placeholder="ex: Endocrinologia, Cardiologia, etc",
            height=100,
            help="Valor ou lista de valores da variável",
        )

        if st.form_submit_button("✅ Criar Variável", use_container_width=True):
            if not grupo_destino or not uso or not valor:
                st.error("⚠️ Todos os campos são obrigatórios")
            else:
                try:
                    supabase = get_supabase_client()

                    # Verifica se uso já existe
                    existing = supabase_execute(
                        lambda: supabase.table("tab_app_variaveis")
                        .select("id_variavel")
                        .eq("uso", uso)
                        .execute()
                    )
                    if existing.data:
                        st.error("❌ Este 'uso' já existe")
                        return

                    # Cria nova variável
                    supabase_execute(
                        lambda: supabase.table("tab_app_variaveis")
                        .insert({
                            "grupo_destino": grupo_destino,
                            "uso": uso,
                            "valor": valor,
                        })
                        .execute()
                    )

                    feedback(f"✅ Variável '{uso}' criada com sucesso!", "success", "🎉")
                    st.rerun()

                except Exception as e:
                    feedback(f"❌ Erro ao criar variável: {e}", "error", "⚠️")

    # =====================================================
    # ✏️ EDITAR VARIÁVEL
    # =====================================================
    st.markdown("---")
    st.markdown("### ✏️ Editar Variável")

    if not df_variaveis.empty:
        df_variaveis.columns = [c.lower() for c in df_variaveis.columns]

        grupos_opts = sorted([g for g in df_variaveis["grupo_destino"].dropna().unique() if g])
        grupo_filtro = st.selectbox(
            "Filtrar por Grupo de Destino",
            ["(Todos)"] + grupos_opts,
            key="filtro_grupo_editar_variavel",
        )

        df_variaveis_filtro = (
            df_variaveis[df_variaveis["grupo_destino"] == grupo_filtro]
            if grupo_filtro != "(Todos)" else df_variaveis
        )

        if df_variaveis_filtro.empty:
            st.info("Nenhuma variável neste grupo.")
        else:
            variavel_sel = st.selectbox("Selecione uma variável", df_variaveis_filtro["uso"].tolist())

            if variavel_sel:
                variavel_data = df_variaveis[df_variaveis["uso"] == variavel_sel].iloc[0]

                with st.form(f"form_editar_{variavel_sel}"):
                    novo_uso = st.text_input(
                        "Uso (Identificador único)",
                        value=variavel_data.get("uso", ""),
                    )
                    novo_grupo = st.text_input(
                        "Grupo de Destino",
                        value=variavel_data.get("grupo_destino", ""),
                    )
                    novo_valor = st.text_area(
                        "Valor",
                        value=variavel_data.get("valor", ""),
                        height=100,
                    )

                    if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                        if not novo_uso:
                            st.error("⚠️ 'Uso' é obrigatório")
                        else:
                            try:
                                supabase = get_supabase_client()

                                if novo_uso != variavel_sel:
                                    existing = supabase_execute(
                                        lambda: supabase.table("tab_app_variaveis")
                                        .select("id_variavel")
                                        .eq("uso", novo_uso)
                                        .execute()
                                    )
                                    if existing.data:
                                        st.error("❌ Este 'uso' já existe")
                                        st.stop()

                                supabase_execute(
                                    lambda: supabase.table("tab_app_variaveis")
                                    .update({
                                        "uso": novo_uso,
                                        "grupo_destino": novo_grupo,
                                        "valor": novo_valor,
                                    })
                                    .eq("uso", variavel_sel)
                                    .execute()
                                )

                                feedback(f"✅ Variável '{novo_uso}' atualizada!", "success", "💾")
                                st.rerun()

                            except Exception as e:
                                feedback(f"❌ Erro ao atualizar: {e}", "error", "⚠️")
    else:
        st.info("Crie uma variável primeiro para poder editá-la")

    # =====================================================
    # 🗑️ DELETAR VARIÁVEL
    # =====================================================
    st.markdown("---")
    st.markdown("### 🗑️ Deletar Variável")

    if not df_variaveis.empty:
        df_variaveis.columns = [c.lower() for c in df_variaveis.columns]
        variavel_deletar = st.selectbox(
            "Selecione uma variável para deletar",
            df_variaveis["uso"].tolist(),
            key="select_deletar",
        )

        if st.button("❌ Deletar", use_container_width=True):
            try:
                supabase = get_supabase_client()
                supabase_execute(
                    lambda: supabase.table("tab_app_variaveis")
                    .delete()
                    .eq("uso", variavel_deletar)
                    .execute()
                )

                feedback(f"✅ Variável '{variavel_deletar}' deletada!", "success", "🗑️")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro ao deletar: {e}", "error", "⚠️")