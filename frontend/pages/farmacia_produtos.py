# ============================================================
# 📦 frontend/pages/farmacia_produtos.py
# Cadastro de Produtos - Farmácia
# ============================================================
import streamlit as st
import pandas as pd
import time
from frontend.supabase_client import get_supabase_client
from frontend.components.feedback import feedback


def page_farmacia_produtos():
    """Página para cadastro e gerenciamento de produtos da farmácia."""
    st.title("📦 Cadastro de Produtos - Farmácia")
    
    try:
        supabase = get_supabase_client()
        
        # Busca dados
        resp_estudos = supabase.table("tab_app_estudos").select("id_estudo, estudo").execute()
        resp_produtos = supabase.table("produtos").select("*").execute()
        resp_tipos = supabase.table("tab_app_variaveis").select("valor").eq("uso", "tipo_produto").execute()
        
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_produtos = pd.DataFrame(resp_produtos.data) if resp_produtos.data else pd.DataFrame()
        
        # Normaliza colunas
        df_estudos.columns = [c.lower() for c in df_estudos.columns]
        df_produtos.columns = [c.lower() for c in df_produtos.columns]
        
        # Parse tipos de produto
        tipos_produto = []
        if resp_tipos.data and resp_tipos.data[0].get("valor"):
            valor_str = resp_tipos.data[0]["valor"]
            # Tenta separar por diferentes delimitadores
            if "\n" in valor_str:
                tipos_produto = [v.strip() for v in valor_str.split("\n") if v.strip()]
            elif ";" in valor_str:
                tipos_produto = [v.strip() for v in valor_str.split(";") if v.strip()]
            elif "," in valor_str:
                tipos_produto = [v.strip() for v in valor_str.split(",") if v.strip()]
        
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
                    help="Nome único do produto"
                )
            
            with col2:
                estudo_sel = st.selectbox(
                    "Estudo",
                    df_estudos["estudo"].tolist() if not df_estudos.empty else [],
                    help="Selecione o estudo ao qual este produto pertence"
                )
            
            tipo_produto_sel = st.selectbox(
                "Tipo de Produto",
                [""] + tipos_produto if tipos_produto else [""],
                help="Selecione o tipo de produto"
            )
            
            if st.form_submit_button("✅ Cadastrar Produto", use_container_width=True):
                if not nm_produto or not estudo_sel or not tipo_produto_sel:
                    st.error("⚠️ Todos os campos são obrigatórios")
                else:
                    try:
                        # Busca ID do estudo
                        id_estudo = int(df_estudos[df_estudos["estudo"] == estudo_sel].iloc[0]["id_estudo"])
                        
                        # Verifica se produto já existe
                        existing = supabase.table("produtos").select("id").eq("nome", nm_produto).execute()
                        if existing.data:
                            st.error("❌ Este produto já existe")
                            return
                        
                        # Insere novo produto
                        supabase.table("produtos").insert({
                            "nome": nm_produto,
                            "estudo_id": id_estudo,
                            "tipo_produto": tipo_produto_sel
                        }).execute()
                        
                        feedback(f"✅ Produto '{nm_produto}' cadastrado com sucesso!", "success", "🎉")
                        time.sleep(1)
                        st.rerun()
                        
                    except Exception as e:
                        feedback(f"❌ Erro ao cadastrar: {str(e)}", "error", "⚠️")
        
        # =====================================================
        # 👁️ VISUALIZAÇÃO DE PRODUTOS
        # =====================================================
        st.markdown("---")
        st.markdown("### 👁️ Produtos Cadastrados")
        
        if not df_produtos.empty:
            # Merge com estudos para exibir nome
            if not df_estudos.empty:
                df_produtos = df_produtos.merge(
                    df_estudos,
                    left_on="estudo_id",
                    right_on="id_estudo",
                    how="left",
                    suffixes=("", "_est")
                ).rename(columns={"estudo": "nm_estudo"})
            
            # Seleciona colunas para exibição
            df_view = df_produtos[["id", "nome", "nm_estudo", "tipo_produto"]].copy()
            df_view.columns = ["ID", "Produto", "Estudo", "Tipo de Produto"]
            
            st.dataframe(
                df_view,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhum produto cadastrado ainda.")
        
        # =====================================================
        # ✏️ EDITAR PRODUTO
        # =====================================================
        st.markdown("---")
        st.markdown("### ✏️ Editar Produto")
        
        if not df_produtos.empty:
            df_produtos.columns = [c.lower() for c in df_produtos.columns]
            
            # Cria rótulo para seleção
            produto_labels = [
                f"[{row['id']}] {row['nome']} — {row.get('nm_estudo', row.get('estudo_id', 'Sem estudo'))}"
                for _, row in df_produtos.iterrows()
            ]
            
            produto_sel_label = st.selectbox("Selecione um produto para editar", produto_labels)
            
            if produto_sel_label:
                # Extrai ID do rótulo
                produto_id = int(produto_sel_label.split("]")[0].replace("[", ""))
                produto_data = df_produtos[df_produtos["id"] == produto_id].iloc[0]
                
                with st.form(f"form_editar_produto_{produto_id}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        novo_nome = st.text_input(
                            "Nome do Produto",
                            value=produto_data.get("nome", "")
                        )
                    
                    with col2:
                        novo_estudo = st.selectbox(
                            "Estudo",
                            df_estudos["estudo"].tolist() if not df_estudos.empty else [],
                            index=0
                        )
                    
                    novo_tipo = st.selectbox(
                        "Tipo de Produto",
                        [""] + tipos_produto if tipos_produto else [""],
                        index=0
                    )
                    
                    if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                        try:
                            id_estudo = int(df_estudos[df_estudos["estudo"] == novo_estudo].iloc[0]["id_estudo"])
                            
                            supabase.table("produtos").update({
                                "nome": novo_nome,
                                "estudo_id": id_estudo,
                                "tipo_produto": novo_tipo
                            }).eq("id", produto_id).execute()
                            
                            feedback(f"✅ Produto atualizado com sucesso!", "success", "💾")
                            time.sleep(1)
                            st.rerun()
                            
                        except Exception as e:
                            feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")
        
        # =====================================================
        # 🗑️ DELETAR PRODUTO
        # =====================================================
        st.markdown("---")
        st.markdown("### 🗑️ Deletar Produto")
        
        if not df_produtos.empty:
            df_produtos.columns = [c.lower() for c in df_produtos.columns]
            
            produto_labels_delete = [
                f"[{row['id']}] {row['nome']}"
                for _, row in df_produtos.iterrows()
            ]
            
            produto_delete_label = st.selectbox(
                "Selecione um produto para deletar",
                produto_labels_delete,
                key="select_delete_produto"
            )
            
            if st.button("❌ Deletar Produto", use_container_width=True):
                try:
                    produto_id = int(produto_delete_label.split("]")[0].replace("[", ""))
                    
                    # Verifica se produto tem movimentações
                    resp_movs = supabase.table("movimentacoes").select("id").eq("produto_id", produto_id).execute()
                    
                    if resp_movs.data:
                        st.error(f"❌ Este produto possui {len(resp_movs.data)} movimentação(ões) vinculada(s). Não pode ser deletado.")
                    else:
                        supabase.table("produtos").delete().eq("id", produto_id).execute()
                        feedback(f"✅ Produto deletado com sucesso!", "success", "🗑️")
                        time.sleep(1)
                        st.rerun()
                        
                except Exception as e:
                    feedback(f"❌ Erro ao deletar: {str(e)}", "error", "⚠️")
        
    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_farmacia_produtos()