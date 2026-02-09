# ============================================================
# 📜 frontend/pages/farmacia_lancamentos.py
# Lançamentos Realizados - Farmácia
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, datetime
from frontend.supabase_client import get_supabase_client
from frontend.components.feedback import feedback


def fmt_date(d) -> str:
    """Formata date/datetime/str para dd/mm/aaaa."""
    if d in (None, "", "N/A"):
        return "—"
    try:
        if isinstance(d, (date, datetime)):
            return d.strftime("%d/%m/%Y")
        dt = pd.to_datetime(d, errors="coerce")
        if pd.isna(dt):
            return str(d)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def page_farmacia_lancamentos():
    """Página para visualização e gerenciamento de lançamentos."""
    st.title("📜 Lançamentos Realizados - Farmácia")
    
    try:
        supabase = get_supabase_client()
        
        # Busca movimentações
        resp_movs = supabase.table("movimentacoes").select("*").execute()
        df_movs = pd.DataFrame(resp_movs.data) if resp_movs.data else pd.DataFrame()
        
        if df_movs.empty:
            st.warning("Nenhum lançamento registrado.")
            return
        
        # Busca estudos
        resp_estudos = supabase.table("tab_app_estudos").select("id_estudo, estudo").execute()
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        
        # Busca produtos
        resp_produtos = supabase.table("produtos").select("id, nome, tipo_produto").execute()
        df_produtos = pd.DataFrame(resp_produtos.data) if resp_produtos.data else pd.DataFrame()
        
        # Normaliza colunas
        df_movs.columns = [c.lower() for c in df_movs.columns]
        df_estudos.columns = [c.lower() for c in df_estudos.columns]
        df_produtos.columns = [c.lower() for c in df_produtos.columns]
        
        # Merges
        if not df_estudos.empty:
            df_movs = df_movs.merge(
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est")
            ).rename(columns={"estudo": "nm_estudo"})
        
        if not df_produtos.empty:
            df_movs = df_movs.merge(
                df_produtos,
                left_on="produto_id",
                right_on="id",
                how="left",
                suffixes=("", "_prod")
            ).rename(columns={"nome": "nm_produto"})
        
        # Converte datas
        df_movs["data_dt"] = pd.to_datetime(df_movs["data"], errors="coerce")
        df_movs["validade_dt"] = pd.to_datetime(df_movs["validade"], errors="coerce")
        df_movs["data_brl"] = df_movs["data_dt"].apply(fmt_date)
        df_movs["validade_brl"] = df_movs["validade_dt"].apply(fmt_date)
        
        # Normaliza valores vazios
        df_movs[["nm_estudo", "nm_produto", "validade_brl", "lote", "tipo_transacao", "tipo_produto"]] = \
            df_movs[["nm_estudo", "nm_produto", "validade_brl", "lote", "tipo_transacao", "tipo_produto"]].fillna("")
        
        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")
        
        c1, c2, c3, c4 = st.columns(4)
        
        with c1:
            filtro_estudo = st.multiselect(
                "Estudo",
                sorted([x for x in df_movs["nm_estudo"].unique() if x])
            )
        
        with c2:
            filtro_produto = st.multiselect(
                "Produto",
                sorted([x for x in df_movs["nm_produto"].unique() if x])
            )
        
        with c3:
            filtro_tipo_transacao = st.multiselect(
                "Tipo de Transação",
                sorted([x for x in df_movs["tipo_transacao"].unique() if x])
            )
        
        with c4:
            dt_ini = st.date_input("Data (Início)", value=None)
            dt_fim = st.date_input("Data (Fim)", value=None)
        
        # Aplicar filtros
        df_view = df_movs.copy()
        
        if filtro_estudo:
            df_view = df_view[df_view["nm_estudo"].isin(filtro_estudo)]
        if filtro_produto:
            df_view = df_view[df_view["nm_produto"].isin(filtro_produto)]
        if filtro_tipo_transacao:
            df_view = df_view[df_view["tipo_transacao"].isin(filtro_tipo_transacao)]
        if dt_ini and dt_fim:
            df_view = df_view[(df_view["data_dt"] >= pd.to_datetime(dt_ini)) & 
                             (df_view["data_dt"] <= pd.to_datetime(dt_fim))]
        
        if df_view.empty:
            st.info("Nenhum lançamento encontrado com os filtros atuais.")
            return
        
        # =====================================================
        # VISUALIZAÇÃO
        # =====================================================
        st.markdown("### 📋 Lançamentos")
        
        cols_order = [
            "id", "data_brl", "tipo_transacao", "nm_estudo", "nm_produto", 
            "tipo_produto", "quantidade", "validade_brl", "lote", "nota", 
            "tipo_acao", "consideracoes", "responsavel", "localizacao"
        ]
        
        df_show = df_view[cols_order].rename(columns={
            "id": "ID",
            "data_brl": "Data",
            "tipo_transacao": "Tipo",
            "nm_estudo": "Estudo",
            "nm_produto": "Produto",
            "tipo_produto": "Tipo de Produto",
            "quantidade": "Quantidade",
            "validade_brl": "Validade",
            "lote": "Lote",
            "nota": "Nota",
            "tipo_acao": "Tipo Ação",
            "consideracoes": "Considerações",
            "responsavel": "Responsável",
            "localizacao": "Localização"
        })
        
        st.dataframe(
            df_show,
            use_container_width=True,
            hide_index=True
        )
        
        # Download CSV
        csv = df_show.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Baixar CSV",
            data=csv,
            file_name="lancamentos_farmacia.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # =====================================================
        # BLOCO DE EDIÇÃO
        # =====================================================
        st.markdown("---")
        st.markdown("### ✏️ Editar Lançamento")
        
        if not df_view.empty:
            df_view.columns = [c.lower() for c in df_view.columns]
            
            lancamento_labels = [
                f"[{int(row['id'])}] {row['data_brl']} - {row['nm_estudo']} - {row['nm_produto']}"
                for _, row in df_view.iterrows()
            ]
            
            lancamento_sel_label = st.selectbox("Selecione um lançamento para editar", lancamento_labels)
            
            if lancamento_sel_label:
                lancamento_id = int(lancamento_sel_label.split("]")[0].replace("[", ""))
                lancamento_data = df_view[df_view["id"] == lancamento_id].iloc[0]
                
                with st.form(f"form_editar_lancamento_{lancamento_id}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        novo_nota = st.text_input(
                            "Nota",
                            value=lancamento_data.get("nota", "")
                        )
                    
                    with col2:
                        novo_consideracoes = st.text_input(
                            "Considerações",
                            value=lancamento_data.get("consideracoes", "")
                        )
                    
                    novo_tipo_acao = st.text_input(
                        "Tipo de Ação",
                        value=lancamento_data.get("tipo_acao", "")
                    )
                    
                    novo_localizacao = st.text_input(
                        "Localização",
                        value=lancamento_data.get("localizacao", "")
                    )
                    
                    if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                        try:
                            supabase.table("movimentacoes").update({
                                "nota": novo_nota if novo_nota else None,
                                "consideracoes": novo_consideracoes if novo_consideracoes else None,
                                "tipo_acao": novo_tipo_acao if novo_tipo_acao else None,
                                "localizacao": novo_localizacao if novo_localizacao else None
                            }).eq("id", lancamento_id).execute()
                            
                            feedback("✅ Lançamento atualizado com sucesso!", "success", "💾")
                            st.rerun()
                            
                        except Exception as e:
                            feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")
        
        # =====================================================
        # BLOCO DE DELEÇÃO
        # =====================================================
        st.markdown("---")
        st.markdown("### 🗑️ Deletar Lançamento")
        
        if not df_view.empty:
            df_view.columns = [c.lower() for c in df_view.columns]
            
            lancamento_labels_delete = [
                f"[{int(row['id'])}] {row['data_brl']} - {row['nm_produto']}"
                for _, row in df_view.iterrows()
            ]
            
            lancamento_delete_label = st.selectbox(
                "Selecione um lançamento para deletar",
                lancamento_labels_delete,
                key="select_delete_lancamento"
            )
            
            if st.button("❌ Deletar Lançamento", use_container_width=True):
                try:
                    lancamento_id = int(lancamento_delete_label.split("]")[0].replace("[", ""))
                    
                    supabase.table("movimentacoes").delete().eq("id", lancamento_id).execute()
                    
                    feedback("✅ Lançamento deletado com sucesso!", "success", "🗑️")
                    st.rerun()
                    
                except Exception as e:
                    feedback(f"❌ Erro ao deletar: {str(e)}", "error", "⚠️")
    
    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_farmacia_lancamentos()