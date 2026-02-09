# ============================================================
# 📊 frontend/pages/farmacia_geral.py
# Visão Geral do Estoque da Farmácia
# ============================================================
import streamlit as st
import pandas as pd
from datetime import datetime, date
from frontend.supabase_client import get_supabase_client
from frontend.components.feedback import feedback


def fmt_date_br(d) -> str:
    """Formata datas para dd/mm/aaaa."""
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


def farol(validade_value) -> str:
    """Retorna emoji do farol conforme dias para vencer."""
    if validade_value in (None, "", "N/A"):
        return ""
    try:
        if isinstance(validade_value, (date, datetime)):
            validade_date = validade_value if isinstance(validade_value, date) else validade_value.date()
        else:
            validade_date = pd.to_datetime(validade_value, errors="coerce")
            if pd.isna(validade_date):
                return ""
            validade_date = validade_date.date()
        
        dias = (validade_date - date.today()).days
        if dias < 0:
            return "🔴"  # vencido
        elif dias <= 30:
            return "🟠"  # 0-30d
        elif dias <= 60:
            return "🟡"  # 31-60d
        elif dias <= 90:
            return "🔵"  # 61-90d
        else:
            return "🟢"  # >90d
    except Exception:
        return ""


def page_farmacia_geral():
    """Página de visão geral do estoque da farmácia."""
    st.title("📊 Visão Geral do Estoque - Farmácia")
    
    try:
        supabase = get_supabase_client()
        
        # Busca movimentações
        resp_movs = supabase.table("movimentacoes").select("*").execute()
        df_movs = pd.DataFrame(resp_movs.data) if resp_movs.data else pd.DataFrame()
        
        if df_movs.empty:
            st.warning("Nenhuma movimentação registrada.")
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
        
        # Seleciona colunas relevantes
        df_movs = df_movs[[
            "id", "data", "tipo_transacao", "nm_estudo", "nm_produto", 
            "tipo_produto", "quantidade", "validade", "lote"
        ]].copy()
        
        # Preenche valores vazios
        df_movs[["nm_estudo", "nm_produto", "validade", "lote", "tipo_transacao", "tipo_produto"]] = \
            df_movs[["nm_estudo", "nm_produto", "validade", "lote", "tipo_transacao", "tipo_produto"]].fillna("")
        
        # Converte data para datetime
        df_movs["data_dt"] = pd.to_datetime(df_movs["data"], errors="coerce")
        df_movs["validade_dt"] = pd.to_datetime(df_movs["validade"], errors="coerce")
        
        # Formatação para exibição
        df_movs["Data (BR)"] = df_movs["data_dt"].apply(fmt_date_br)
        df_movs["Validade (BR)"] = df_movs["validade_dt"].apply(fmt_date_br)
        df_movs["Farol"] = df_movs["validade_dt"].apply(farol)
        
        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")
        
        c1, c2, c3 = st.columns(3)
        
        with c1:
            estudo_filter = st.multiselect(
                "Filtrar por Estudo",
                sorted([x for x in df_movs["nm_estudo"].unique() if x])
            )
        
        with c2:
            produto_filter = st.multiselect(
                "Filtrar por Produto",
                sorted([x for x in df_movs["nm_produto"].unique() if x])
            )
        
        with c3:
            tipo_produto_filter = st.multiselect(
                "Filtrar por Tipo de Produto",
                sorted([x for x in df_movs["tipo_produto"].unique() if x])
            )
        
        # Aplicar filtros
        df_filtered = df_movs.copy()
        
        if estudo_filter:
            df_filtered = df_filtered[df_filtered["nm_estudo"].isin(estudo_filter)]
        if produto_filter:
            df_filtered = df_filtered[df_filtered["nm_produto"].isin(produto_filter)]
        if tipo_produto_filter:
            df_filtered = df_filtered[df_filtered["tipo_produto"].isin(tipo_produto_filter)]
        
        # =====================================================
        # AGRUPAMENTO E EXIBIÇÃO
        # =====================================================
        st.markdown("### 📦 Resumo do Estoque")
        
        if df_filtered.empty:
            st.info("Nenhum resultado com os filtros aplicados.")
            return
        
        # Agrupamento
        agrupado = df_filtered.groupby(["nm_estudo", "nm_produto", "Validade (BR)", "lote", "tipo_produto"]).agg({
            "quantidade": lambda x: (df_filtered[df_filtered["tipo_transacao"] == "Entrada"]["quantidade"].sum() if "Entrada" in df_filtered["tipo_transacao"].values else 0) -
                                  (df_filtered[df_filtered["tipo_transacao"] == "Saída"]["quantidade"].sum() if "Saída" in df_filtered["tipo_transacao"].values else 0),
            "Farol": "first"
        }).reset_index()
        
        agrupado.columns = ["Estudo", "Produto", "Validade", "Lote", "Tipo de Produto", "Saldo", "Farol"]
        
        # Reordena colunas
        cols_show = ["Farol", "Estudo", "Produto", "Tipo de Produto", "Validade", "Lote", "Saldo"]
        
        st.dataframe(
            agrupado[cols_show],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Farol": st.column_config.Column(width="small"),
                "Estudo": st.column_config.Column(width="medium"),
                "Produto": st.column_config.Column(width="large"),
                "Tipo de Produto": st.column_config.Column(width="medium"),
                "Validade": st.column_config.Column(width="small"),
                "Lote": st.column_config.Column(width="small"),
                "Saldo": st.column_config.Column(width="small")
            }
        )
        
        # Download CSV
        csv = agrupado.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Baixar CSV",
            data=csv,
            file_name="estoque_farmacia.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    except Exception as e:
        feedback(f"❌ Erro ao carregar dados: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_farmacia_geral()