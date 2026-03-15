# ============================================================
# 📊 frontend/pages/farmacia_geral.py
# Visão Geral do Estoque da Farmácia
# ============================================================
import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


TABLE_MOVS = "tab_app_farmacia_movimentacoes"


def fmt_date_br(d) -> str:
    """Formata datas (str/date/datetime) para dd/mm/aaaa apenas para exibição."""
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


def farol(validade_value):
    """Retorna emoji do farol conforme dias para vencer."""
    if validade_value in (None, "", "N/A"):
        return ""
    try:
        # suporta tanto string ISO quanto date/datetime
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

        # ---------------------------
        # Carregar dados
        # ---------------------------
        resp_movs = supabase_execute(lambda: supabase.table(TABLE_MOVS).select("*").execute())
        df_movs = pd.DataFrame(resp_movs.data) if resp_movs.data else pd.DataFrame()

        if df_movs.empty:
            st.warning("Nenhuma movimentação registrada.")
            return

        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos").select("id_estudo, estudo").execute()
        )
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()

        resp_produtos = supabase_execute(
            lambda: supabase.table("produtos").select("id, nome, tipo_produto").execute()
        )
        df_produtos = pd.DataFrame(resp_produtos.data) if resp_produtos.data else pd.DataFrame()

        # ---------------------------
        # Normalização + enriquecimento
        # ---------------------------
        df_movs.columns = [c.lower() for c in df_movs.columns]
        if not df_estudos.empty:
            df_estudos.columns = [c.lower() for c in df_estudos.columns]
        if not df_produtos.empty:
            df_produtos.columns = [c.lower() for c in df_produtos.columns]

        if not df_estudos.empty:
            df_movs = pd.merge(
                df_movs,
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est"),
            ).rename(columns={"estudo": "nm_estudo"})

        if not df_produtos.empty:
            df_movs = pd.merge(
                df_movs,
                df_produtos,
                left_on="produto_id",
                right_on="id",
                how="left",
                suffixes=("", "_prod"),
            ).rename(columns={"nome": "nm_produto"})

        # Campos de interesse (mantendo validade como string)
        df = df_movs[
            [
                "id",
                "data",
                "tipo_transacao",
                "nm_estudo",
                "nm_produto",
                "tipo_produto",
                "quantidade",
                "validade",
                "lote",
            ]
        ].copy()

        # Normalização para evitar NaN no agrupamento
        df[["nm_estudo", "nm_produto", "validade", "lote", "tipo_transacao", "tipo_produto"]] = (
            df[["nm_estudo", "nm_produto", "validade", "lote", "tipo_transacao", "tipo_produto"]].fillna("")
        )

        # Tipos numéricos
        df["quantidade"] = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0)

        # ---------------------------
        # Filtros superiores
        # ---------------------------
        st.markdown("### 🔍 Filtros")

        c1, c2, c3 = st.columns(3)

        with c1:
            estudo_filter = st.multiselect(
                "Filtrar por Estudo",
                sorted([x for x in df["nm_estudo"].unique() if x]),
            )
        with c2:
            produto_filter = st.multiselect(
                "Filtrar por Produto",
                sorted([x for x in df["nm_produto"].unique() if x]),
            )
        with c3:
            tipo_produto_filter = st.multiselect(
                "Filtrar por Tipo de Produto",
                sorted([x for x in df["tipo_produto"].unique() if x]),
            )

        if estudo_filter:
            df = df[df["nm_estudo"].isin(estudo_filter)]
        if produto_filter:
            df = df[df["nm_produto"].isin(produto_filter)]
        if tipo_produto_filter:
            df = df[df["tipo_produto"].isin(tipo_produto_filter)]

        # Filtro opcional por período de validade
        c_chk, c_periodo = st.columns([1, 3])
        with c_chk:
            considerar_validade = st.checkbox("Filtrar por intervalo de validade", value=False)

        if considerar_validade:
            df["validade_dt"] = pd.to_datetime(df["validade"], errors="coerce")
            min_valid = df["validade_dt"].min(skipna=True)
            max_valid = df["validade_dt"].max(skipna=True)
            if pd.isna(min_valid) or pd.isna(max_valid):
                default_range = (date.today(), date.today())
            else:
                default_range = (min_valid.date(), max_valid.date())

            with c_periodo:
                intervalo_validade = st.date_input(
                    "Intervalo de Validade",
                    value=default_range,
                    help="Selecione início e fim do intervalo de validade.",
                )

            if isinstance(intervalo_validade, (list, tuple)) and len(intervalo_validade) == 2:
                dt_ini, dt_fim = intervalo_validade
            else:
                dt_ini = dt_fim = intervalo_validade

            dt_ini = pd.to_datetime(dt_ini) if dt_ini else None
            dt_fim = pd.to_datetime(dt_fim) if dt_fim else None

            if (dt_ini is not None) and (dt_fim is not None):
                df = df[df["validade_dt"].between(dt_ini, dt_fim, inclusive="both")].copy()

        # ---------------------------
        # Agregação "fiel"
        # ---------------------------
        st.markdown("### 📦 Resumo do Estoque")

        if df.empty:
            st.info("Nenhum item para exibir com os filtros atuais.")
            return

        df["Entradas"] = (df["tipo_transacao"] == "Entrada").astype(int) * df["quantidade"].astype(float)
        df["Saidas"] = (df["tipo_transacao"] == "Saída").astype(int) * df["quantidade"].astype(float)

        agrupado = (
            df.groupby(["nm_estudo", "nm_produto", "tipo_produto", "validade", "lote"], dropna=False)
            .agg(Entradas=("Entradas", "sum"), Saidas=("Saidas", "sum"))
            .reset_index()
        )

        agrupado["Saldo Total"] = agrupado["Entradas"] - agrupado["Saidas"]

        # Farol e validade BR: calculados DIRETO do campo 'validade' (string), igual app antigo
        agrupado["Farol"] = agrupado["validade"].apply(farol)
        agrupado["Validade (BR)"] = agrupado["validade"].apply(fmt_date_br)

        # ---------------------------
        # Filtro de saldos zerados
        # ---------------------------
        c_zero, _ = st.columns([1, 3])
        with c_zero:
            apenas_saldos_zerados = st.checkbox("Mostrar apenas saldos zerados", value=False)

        agrupado = agrupado.fillna({"lote": "", "tipo_produto": ""})

        # arredondar e converter para int (compatível com o antigo)
        for col in ["Entradas", "Saidas", "Saldo Total"]:
            agrupado[col] = pd.to_numeric(agrupado[col], errors="coerce").fillna(0).round(0).astype(int)

        if apenas_saldos_zerados:
            agrupado = agrupado[agrupado["Saldo Total"].fillna(0) == 0]

        agrupado = agrupado.sort_values(
            by=["nm_estudo", "nm_produto", "tipo_produto", "validade", "lote"],
            na_position="last",
        )

        # ---------------------------
        # Métricas (big numbers)
        # ---------------------------
        st.divider()
        st.subheader("Métricas Gerais")

        total_entradas = int(agrupado["Entradas"].sum()) if not agrupado.empty else 0
        total_saidas = int(agrupado["Saidas"].sum()) if not agrupado.empty else 0
        saldo_geral = int(agrupado["Saldo Total"].sum()) if not agrupado.empty else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Total de Entradas", f"{total_entradas}")
        m2.metric("Total de Saídas", f"{total_saidas}")
        m3.metric("Saldo Geral", f"{saldo_geral}")

        # Contagem por farol (considera só itens com saldo != 0)
        st.subheader("Itens por Farol (saldo ≠ 0)")

        base_farol = agrupado[agrupado["Saldo Total"] != 0].copy()
        counts = base_farol["Farol"].value_counts(dropna=False).to_dict()

        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("🔴 vencido", str(int(counts.get("🔴", 0))))
        f2.metric("🟠 0-30d", str(int(counts.get("🟠", 0))))
        f3.metric("🟡 31-60d", str(int(counts.get("🟡", 0))))
        f4.metric("🔵 61-90d", str(int(counts.get("🔵", 0))))
        f5.metric("🟢 >90d", str(int(counts.get("🟢", 0))))

        # ---------------------------
        # Tabela
        # ---------------------------
        if not agrupado.empty:
            cols_show = [
                "Farol",
                "nm_estudo",
                "nm_produto",
                "tipo_produto",
                "Validade (BR)",
                "lote",
                "Entradas",
                "Saidas",
                "Saldo Total",
            ]

            st.dataframe(
                agrupado[cols_show].rename(
                    columns={
                        "nm_estudo": "Estudo",
                        "nm_produto": "Produto",
                        "tipo_produto": "Tipo de Produto",
                        "Validade (BR)": "Validade",
                        "lote": "Lote",
                        "Saidas": "Saídas",
                    }
                ),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Farol": st.column_config.Column(width="small"),
                    "Estudo": st.column_config.Column(width="medium"),
                    "Produto": st.column_config.Column(width="large"),
                    "Tipo de Produto": st.column_config.Column(width="medium"),
                    "Validade": st.column_config.Column(width="small"),
                    "Lote": st.column_config.Column(width="small"),
                    "Entradas": st.column_config.Column(width="small"),
                    "Saídas": st.column_config.Column(width="small"),
                    "Saldo Total": st.column_config.Column(width="small"),
                },
            )

            excel_buffer = BytesIO()
            agrupado.to_excel(excel_buffer, index=False, sheet_name="Dados")
            excel_buffer.seek(0)
            st.download_button(
                "📥 Baixar XLSX",
                data=excel_buffer,
                file_name="estoque_farmacia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.info("Nenhum item para exibir com os filtros atuais.")

    except Exception as e:
        feedback(f"❌ Erro ao carregar dados: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_farmacia_geral()