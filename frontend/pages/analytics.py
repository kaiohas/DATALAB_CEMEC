import streamlit as st
import pandas as pd
import altair as alt
from databricks import sql
from frontend.config import get_sql_connection_dict

# ============================================================
# 🔍 Função auxiliar — Busca dados do DataHub
# ============================================================
@st.cache_data(ttl=300)
def fetch_analytics_data(periodo: str):
    """Busca dados agregados de vendas com base no período (3M ou 6M)."""
    filtro_meses = 6 if periodo == "6M" else 3

    query = f"""
        SELECT 
          date_format(OrderDate, 'yyyy-MM') AS DT_PERIODO_MENSAL,
          concat(year(OrderDate), '-Q', quarter(OrderDate)) AS DT_PERIODO_TRIMESTRAL,
          b.NM_PROJETO,
          c.NM_CLIENTE,
          COUNT(DISTINCT Id) AS TT_PEDIDOS,
          SUM(OrderValue) AS VR_TOTAL
        FROM dbw_datahub_dev.db_sandbox.vw_raw_tb_order a 
        INNER JOIN dbw_recompensas_prd.db_marketplace_silver.dim_projeto b 
            ON a.ProjectId = b.ID_PROJETO 
            AND a.ClientId = try_cast(b.ID_CLIENTE AS bigint)
        INNER JOIN dbw_recompensas_prd.db_marketplace_silver.dim_cliente c 
            ON a.ClientId = c.ID_CLIENTE
        WHERE OrderDate >= add_months(current_date(), -{filtro_meses})
        GROUP BY 
          date_format(OrderDate, 'yyyy-MM'),
          concat(year(OrderDate), '-Q', quarter(OrderDate)),
          b.NM_PROJETO,
          c.NM_CLIENTE
        ORDER BY DT_PERIODO_MENSAL
    """

    conn_dict = get_sql_connection_dict()
    with sql.connect(
        server_hostname=conn_dict["server_hostname"],
        http_path=conn_dict["http_path"],
        access_token=conn_dict["access_token"]
    ) as connection:
        df = pd.read_sql(query, connection)

    return df


# ============================================================
# 📊 Página principal — Dashboard de Análise de Vendas
# ============================================================
def page_analytics():
    st.title("📈 Análise de Vendas")
    st.caption("Monitoramento consolidado de performance de vendas por cliente e projeto.")

    # ------------------------------------------------------------
    # 🔘 Filtros principais
    # ------------------------------------------------------------
    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        timeframe = st.selectbox("⏳ Período:", ["3M", "6M"], index=1)

    with col2:
        tipo_visualizacao = st.radio("📅 Agrupar por:", ["Mensal", "Trimestral"], horizontal=True)

    try:
        df = fetch_analytics_data(timeframe)
        if df.empty:
            st.warning("Nenhum dado encontrado para o período selecionado.")
            return
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return

    # ------------------------------------------------------------
    # 🎯 Filtros adicionais
    # ------------------------------------------------------------
    clientes = sorted(df["NM_CLIENTE"].unique().tolist())
    projetos = sorted(df["NM_PROJETO"].unique().tolist())

    with col3:
        cliente_sel = st.selectbox("🎯 Cliente:", ["Todos"] + clientes)
    projeto_sel = st.selectbox("🧩 Projeto:", ["Todos"] + projetos)

    if cliente_sel != "Todos":
        df = df[df["NM_CLIENTE"] == cliente_sel]
    if projeto_sel != "Todos":
        df = df[df["NM_PROJETO"] == projeto_sel]

    # ------------------------------------------------------------
    # 📈 Cálculos base
    # ------------------------------------------------------------
    col_periodo = "DT_PERIODO_MENSAL" if tipo_visualizacao == "Mensal" else "DT_PERIODO_TRIMESTRAL"
    df_periodo = df.groupby(col_periodo, as_index=False).agg({"TT_PEDIDOS": "sum", "VR_TOTAL": "sum"})

    total_pedidos = int(df["TT_PEDIDOS"].sum())
    total_vendas = float(df["VR_TOTAL"].sum())
    ticket_medio = total_vendas / total_pedidos if total_pedidos else 0
    crescimento = (
        (df_periodo["VR_TOTAL"].iloc[-1] / df_periodo["VR_TOTAL"].iloc[0] - 1) * 100
        if len(df_periodo) > 1
        else 0
    )
    total_projetos = df["NM_PROJETO"].nunique()

    # ------------------------------------------------------------
    # 💎 Indicadores principais (KPIs)
    # ------------------------------------------------------------
    st.markdown("### 📊 Indicadores Gerais")

    colA, colB, colC, colD, colE = st.columns(5)
    colA.metric("🧾 Total de Pedidos", f"{total_pedidos:,}".replace(",", "."))
    colB.metric("💰 Valor Total", f"R$ {total_vendas/1e6:.2f} M")
    colC.metric("🎟️ Ticket Médio", f"R$ {ticket_medio:,.2f}".replace(",", "."))
    colD.metric("📈 Crescimento", f"{crescimento:.1f} %")
    colE.metric("🚀 Projetos Ativos", f"{total_projetos}")

    # ------------------------------------------------------------
    # 📊 Gráfico duplo — Pedidos × Vendas
    # ------------------------------------------------------------
    st.markdown("### 📈 Evolução de Pedidos e Vendas")

    base = df_periodo.rename(columns={"TT_PEDIDOS": "Total de Pedidos", "VR_TOTAL": "Valor Total (R$)"})
    scale_ped = alt.Scale(domain=[0, base["Total de Pedidos"].max() * 1.1])
    scale_val = alt.Scale(domain=[0, base["Valor Total (R$)"].max() * 1.1])

    bar = (
        alt.Chart(base)
        .mark_bar(color="#4C78A8", opacity=0.7)
        .encode(
            x=alt.X(col_periodo, title="Período"),
            y=alt.Y("Total de Pedidos", axis=alt.Axis(titleColor="#4C78A8"), scale=scale_ped),
            tooltip=[alt.Tooltip("Total de Pedidos"), alt.Tooltip("Valor Total (R$)", format=",.2f")],
        )
    )

    line = (
        alt.Chart(base)
        .mark_line(color="#F58518", point=True, size=3)
        .encode(
            x=col_periodo,
            y=alt.Y("Valor Total (R$)", axis=alt.Axis(titleColor="#F58518"), scale=scale_val),
            tooltip=[alt.Tooltip("Total de Pedidos"), alt.Tooltip("Valor Total (R$)", format=",.2f")],
        )
    )

    st.altair_chart(alt.layer(bar, line).resolve_scale(y="independent").properties(height=400), use_container_width=True)

    # ------------------------------------------------------------
    # 🎨 Evolução colorida — Cliente ou Projeto
    # ------------------------------------------------------------
    cor_agrupamento = st.radio("🎨 Cor por:", ["Cliente", "Projeto"], horizontal=True)
    col_color = "NM_CLIENTE" if cor_agrupamento == "Cliente" else "NM_PROJETO"

    st.markdown(f"### 📊 Evolução de Vendas por {cor_agrupamento}")

    chart_color = (
        alt.Chart(df)
        .mark_line(point=True)
        .encode(
            x=alt.X(col_periodo, title="Período"),
            y=alt.Y("VR_TOTAL:Q", title="Valor Total (R$)"),
            color=alt.Color(col_color, title=cor_agrupamento),
            tooltip=[
                alt.Tooltip("NM_CLIENTE:N", title="Cliente"),
                alt.Tooltip("NM_PROJETO:N", title="Projeto"),
                alt.Tooltip("VR_TOTAL:Q", title="Vendas (R$)", format=",.2f"),
            ],
        )
        .properties(height=400)
    )
    st.altair_chart(chart_color, use_container_width=True)

    # ------------------------------------------------------------
    # 🔥 Heatmap — Cliente × Projeto
    # ------------------------------------------------------------
    st.markdown("### 🔥 Mapa de Valor — Cliente × Projeto")

    heatmap = (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X("NM_PROJETO:N", title="Projeto"),
            y=alt.Y("NM_CLIENTE:N", title="Cliente"),
            color=alt.Color("VR_TOTAL:Q", scale=alt.Scale(scheme="blues"), title="Vendas (R$)"),
            tooltip=[
                alt.Tooltip("NM_CLIENTE:N", title="Cliente"),
                alt.Tooltip("NM_PROJETO:N", title="Projeto"),
                alt.Tooltip("VR_TOTAL:Q", title="Vendas (R$)", format=",.2f"),
            ],
        )
        .properties(height=400)
    )
    st.altair_chart(heatmap, use_container_width=True)

    # ------------------------------------------------------------
    # 🏆 Top 5 Clientes e Projetos
    # ------------------------------------------------------------
    st.markdown("### 🏆 Top 5 Clientes e Projetos")
    col1, col2 = st.columns(2)

    top_clientes = df.groupby("NM_CLIENTE", as_index=False)["VR_TOTAL"].sum().nlargest(5, "VR_TOTAL")
    col1.bar_chart(top_clientes.set_index("NM_CLIENTE")["VR_TOTAL"])

    top_projetos = df.groupby("NM_PROJETO", as_index=False)["VR_TOTAL"].sum().nlargest(5, "VR_TOTAL")
    col2.bar_chart(top_projetos.set_index("NM_PROJETO")["VR_TOTAL"])

    # ------------------------------------------------------------
    # 🧾 Tabela resumo
    # ------------------------------------------------------------
    st.markdown("### 🧾 Desempenho por Período")
    st.dataframe(
        df_periodo.rename(columns={"TT_PEDIDOS": "Pedidos", "VR_TOTAL": "Vendas (R$)"}).sort_values(col_periodo),
        use_container_width=True
    )

    # ------------------------------------------------------------
    # 💡 Insight automático
    # ------------------------------------------------------------
    if not df_periodo.empty:
        melhor = df_periodo.loc[df_periodo["VR_TOTAL"].idxmax(), col_periodo]
        pior = df_periodo.loc[df_periodo["VR_TOTAL"].idxmin(), col_periodo]
        dif = (df_periodo["VR_TOTAL"].max() - df_periodo["VR_TOTAL"].min()) / 1e6
        st.info(
            f"💡 Melhor período: **{melhor}**, pior: **{pior}** — diferença de **R$ {dif:.2f} M** em vendas.",
            icon="💬"
        )
