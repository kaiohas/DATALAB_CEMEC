# ============================================================
# 📦 frontend/pages/farmacia_produtos.py
# Cadastro de Produtos - Farmácia
# ============================================================
import streamlit as st
import pandas as pd
import time
from datetime import datetime

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


TABLE_MOVS = "tab_app_farmacia_movimentacoes"


def parse_variaveis(valor_str: str) -> list:
    """Parse de valores a partir de uma string."""
    if not valor_str:
        return []

    valor_str = str(valor_str)

    if "\n" in valor_str:
        valores = [v.strip() for v in valor_str.split("\n") if v.strip()]
    elif ";" in valor_str:
        valores = [v.strip() for v in valor_str.split(";") if v.strip()]
    elif "," in valor_str:
        valores = [v.strip() for v in valor_str.split(",") if v.strip()]
    else:
        valores = [valor_str.strip()] if valor_str.strip() else []

    return valores


def _toast_after_rerun():
    """Mostra toast de sucesso após rerun (padrão agenda)."""
    if st.session_state.get("_farmacia_prod_save_ok"):
        msg = st.session_state.get("_farmacia_prod_save_msg") or "✅ Operação realizada com sucesso!"
        when = st.session_state.get("_farmacia_prod_save_when")

        try:
            st.toast(msg, icon="✅")
        except Exception:
            st.success(msg)

        if when:
            st.caption(f"Última ação: {when}")

        st.session_state.pop("_farmacia_prod_save_ok", None)
        st.session_state.pop("_farmacia_prod_save_msg", None)
        st.session_state.pop("_farmacia_prod_save_when", None)


def _set_toast(msg: str):
    st.session_state["_farmacia_prod_save_ok"] = True
    st.session_state["_farmacia_prod_save_msg"] = msg
    st.session_state["_farmacia_prod_save_when"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")


def page_farmacia_produtos():
    """Página para cadastro e gerenciamento de produtos da farmácia."""
    st.title("📦 Cadastro de Produtos - Farmácia")

    # ✅ toast pós-rerun
    _toast_after_rerun()

    try:
        supabase = get_supabase_client()

        # Busca dados
        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos").select("id_estudo, estudo").order("estudo").execute()
        )
        resp_produtos = supabase_execute(lambda: supabase.table("produtos").select("*").order("nome").execute())
        resp_tipos = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "tipo_produto").execute()
        )

        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_produtos = pd.DataFrame(resp_produtos.data) if resp_produtos.data else pd.DataFrame()

        # Normaliza colunas
        if not df_estudos.empty:
            df_estudos.columns = [c.lower() for c in df_estudos.columns]
        if not df_produtos.empty:
            df_produtos.columns = [c.lower() for c in df_produtos.columns]

        # Parse tipos de produto (variáveis)
        tipos_produto = []
        if resp_tipos.data and resp_tipos.data[0].get("valor"):
            tipos_produto = parse_variaveis(resp_tipos.data[0]["valor"])

        # =====================================================
        # 📥 CADASTRAR NOVO PRODUTO
        # =====================================================
        st.markdown("### ➕ Cadastrar Novo Produto")

        with st.form("form_novo_produto"):
            col1, col2 = st.columns(2)

            with col1:
                nm_produto = st.text_input(
                    "Nome do Produto",
                    placeholder="ex: Ibuprofeno 200mg",
                    help="Nome único do produto",
                )

            with col2:
                estudo_sel = st.selectbox(
                    "Estudo",
                    df_estudos["estudo"].tolist() if not df_estudos.empty else [],
                    help="Selecione o estudo ao qual este produto pertence",
                )

            tipo_produto_sel = st.selectbox(
                "Tipo de Produto",
                [""] + tipos_produto if tipos_produto else [""],
                help="Selecione o tipo de produto",
            )

            if st.form_submit_button("✅ Cadastrar Produto", use_container_width=True):
                nm_produto_norm = (nm_produto or "").strip()
                if not nm_produto_norm or not estudo_sel or not tipo_produto_sel:
                    st.error("⚠️ Todos os campos são obrigatórios")
                else:
                    try:
                        id_estudo = int(df_estudos[df_estudos["estudo"] == estudo_sel].iloc[0]["id_estudo"])

                        existing = supabase_execute(lambda: supabase.table("produtos").select("id, nome").execute())
                        df_exist = pd.DataFrame(existing.data) if existing.data else pd.DataFrame()
                        if not df_exist.empty:
                            df_exist.columns = [c.lower() for c in df_exist.columns]
                            ja_existe = any(
                                (str(n).strip().lower() == nm_produto_norm.lower()) for n in df_exist["nome"].tolist()
                            )
                            if ja_existe:
                                st.error("❌ Este produto já existe")
                                st.stop()

                        supabase_execute(
                            lambda: supabase.table("produtos")
                            .insert(
                                {
                                    "nome": nm_produto_norm,
                                    "estudo_id": id_estudo,
                                    "tipo_produto": tipo_produto_sel,
                                }
                            )
                            .execute()
                        )

                        _set_toast(f"✅ Produto '{nm_produto_norm}' cadastrado com sucesso!")
                        feedback(f"✅ Produto '{nm_produto_norm}' cadastrado com sucesso!", "success", "🎉")
                        time.sleep(0.2)
                        st.rerun()

                    except Exception as e:
                        feedback(f"❌ Erro ao cadastrar: {str(e)}", "error", "⚠️")

        # =====================================================
        # 🔍 FILTRO (ESTUDO) PARA LISTAGEM/EDITAR/DELETAR
        # =====================================================
        st.markdown("---")
        st.markdown("### 🔍 Filtro de Produtos")

        estudos_opts_filtro = ["(Todos)"] + (df_estudos["estudo"].tolist() if not df_estudos.empty else [])
        filtro_estudo_produtos = st.selectbox(
            "Filtrar produtos por Estudo",
            estudos_opts_filtro,
            index=0,
            key="filtro_estudo_produtos",
        )

        # resolve id do estudo selecionado (se houver)
        filtro_estudo_id = None
        if filtro_estudo_produtos and filtro_estudo_produtos != "(Todos)" and not df_estudos.empty:
            filtro_estudo_id = int(df_estudos[df_estudos["estudo"] == filtro_estudo_produtos].iloc[0]["id_estudo"])

        # aplica filtro no dataframe base
        df_produtos_filtrados = df_produtos.copy()
        if (filtro_estudo_id is not None) and (not df_produtos_filtrados.empty) and ("estudo_id" in df_produtos_filtrados.columns):
            df_produtos_filtrados = df_produtos_filtrados[df_produtos_filtrados["estudo_id"] == filtro_estudo_id]

        # =====================================================
        # 👁️ VISUALIZAÇÃO DE PRODUTOS
        # =====================================================
        st.markdown("### 👁️ Produtos Cadastrados")

        df_produtos_view = df_produtos_filtrados.copy()

        if not df_produtos_view.empty:
            if not df_estudos.empty and "estudo_id" in df_produtos_view.columns:
                df_produtos_view = df_produtos_view.merge(
                    df_estudos,
                    left_on="estudo_id",
                    right_on="id_estudo",
                    how="left",
                    suffixes=("", "_est"),
                ).rename(columns={"estudo": "nm_estudo"})

            cols = [c for c in ["id", "nome", "nm_estudo", "tipo_produto"] if c in df_produtos_view.columns]
            df_view = df_produtos_view[cols].copy()
            df_view.columns = ["ID", "Produto", "Estudo", "Tipo de Produto"][: len(cols)]

            st.dataframe(df_view, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum produto encontrado para o filtro selecionado.")

        # =====================================================
        # ✏️ EDITAR PRODUTO (respeita filtro)
        # =====================================================
        st.markdown("---")
        st.markdown("### ✏️ Editar Produto")

        if not df_produtos_view.empty:
            df_produtos_edit = df_produtos_view.copy()
            df_produtos_edit.columns = [c.lower() for c in df_produtos_edit.columns]

            produto_labels = [
                f"[{row['id']}] {row['nome']} — {row.get('nm_estudo', row.get('estudo_id', 'Sem estudo'))}"
                for _, row in df_produtos_edit.iterrows()
            ]

            produto_sel_label = st.selectbox(
                "Selecione um produto para editar",
                produto_labels,
                key="select_editar_produto",
            )

            if produto_sel_label:
                produto_id = int(produto_sel_label.split("]")[0].replace("[", ""))
                produto_data = df_produtos_edit[df_produtos_edit["id"] == produto_id].iloc[0]

                estudo_atual_nome = str(produto_data.get("nm_estudo") or "")
                tipo_atual = str(produto_data.get("tipo_produto") or "")

                estudos_opts = df_estudos["estudo"].tolist() if not df_estudos.empty else []
                tipos_opts = [""] + tipos_produto if tipos_produto else [""]

                idx_estudo = estudos_opts.index(estudo_atual_nome) if estudo_atual_nome in estudos_opts else 0
                idx_tipo = tipos_opts.index(tipo_atual) if tipo_atual in tipos_opts else 0

                with st.form(f"form_editar_produto_{produto_id}"):
                    col1, col2 = st.columns(2)

                    with col1:
                        novo_nome = st.text_input("Nome do Produto", value=str(produto_data.get("nome") or ""))

                    with col2:
                        novo_estudo = st.selectbox("Estudo", estudos_opts, index=idx_estudo)

                    novo_tipo = st.selectbox("Tipo de Produto", tipos_opts, index=idx_tipo)

                    if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                        try:
                            novo_nome_norm = (novo_nome or "").strip()
                            if not novo_nome_norm:
                                st.error("⚠️ Nome do produto é obrigatório")
                                st.stop()
                            if not novo_estudo:
                                st.error("⚠️ Estudo é obrigatório")
                                st.stop()
                            if not novo_tipo:
                                st.error("⚠️ Tipo de Produto é obrigatório")
                                st.stop()

                            id_estudo = int(df_estudos[df_estudos["estudo"] == novo_estudo].iloc[0]["id_estudo"])

                            supabase_execute(
                                lambda: supabase.table("produtos")
                                .update(
                                    {
                                        "nome": novo_nome_norm,
                                        "estudo_id": id_estudo,
                                        "tipo_produto": novo_tipo,
                                    }
                                )
                                .eq("id", produto_id)
                                .execute()
                            )

                            _set_toast("✅ Produto atualizado com sucesso!")
                            feedback("✅ Produto atualizado com sucesso!", "success", "💾")
                            time.sleep(0.2)
                            st.rerun()

                        except Exception as e:
                            feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")

        else:
            st.info("Selecione um estudo com produtos para habilitar a edição.")

        # =====================================================
        # 🗑️ DELETAR PRODUTO (respeita filtro)
        # =====================================================
        st.markdown("---")
        st.markdown("### 🗑️ Deletar Produto")

        if not df_produtos_view.empty:
            df_produtos_del = df_produtos_view.copy()
            df_produtos_del.columns = [c.lower() for c in df_produtos_del.columns]

            produto_labels_delete = [f"[{row['id']}] {row['nome']}" for _, row in df_produtos_del.iterrows()]

            produto_delete_label = st.selectbox(
                "Selecione um produto para deletar",
                produto_labels_delete,
                key="select_delete_produto",
            )

            if st.button("❌ Deletar Produto", use_container_width=True):
                try:
                    produto_id = int(produto_delete_label.split("]")[0].replace("[", ""))

                    resp_movs = supabase_execute(
                        lambda: supabase.table(TABLE_MOVS).select("id").eq("produto_id", produto_id).limit(1).execute()
                    )

                    if resp_movs.data:
                        st.error("❌ Este produto possui movimentações vinculadas. Não pode ser deletado.")
                    else:
                        supabase_execute(lambda: supabase.table("produtos").delete().eq("id", produto_id).execute())
                        _set_toast("✅ Produto deletado com sucesso!")
                        feedback("✅ Produto deletado com sucesso!", "success", "🗑️")
                        time.sleep(0.2)
                        st.rerun()

                except Exception as e:
                    feedback(f"❌ Erro ao deletar: {str(e)}", "error", "⚠️")
        else:
            st.info("Selecione um estudo com produtos para habilitar a deleção.")

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


if __name__ == "__main__":
    page_farmacia_produtos()