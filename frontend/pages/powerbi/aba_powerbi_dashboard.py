# ============================================================
# 📑 frontend/pages/aba_powerbi_dashboard.py
# ============================================================
import streamlit as st
import json
import pandas as pd
from databricks import sql
from backend.api.powerbi_api import generate_powerbi_embed_token
from backend.api.auditoria import registrar_evento_auditoria
from backend.api.logger import log_erro_acess
from frontend.config import get_sql_connection_dict


# ============================================================
# 🖼️ Cabeçalho
# ============================================================
def render_cabecalho():
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;">
            <img src="https://app.powerbi.com/images/PowerBI_Favicon.ico" 
                 alt="Power BI" width="42" style="border-radius:8px;">
            <h2 style="margin:0;">Dashboards Power BI</h2>
        </div>
        <p style="color:gray;margin-top:4px;">📊 Origem: 
            <code>dbw_datahub_dev.db_app.tb_config_powerbi_dashboard</code>
        </p>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# 🔹 Carregar dashboards ativos
# ============================================================
@st.cache_data(ttl=600)
def listar_dashboards():
    try:
        conn_dict = get_sql_connection_dict()
        with sql.connect(
            server_hostname=conn_dict["server_hostname"],
            http_path=conn_dict["http_path"],
            access_token=conn_dict["access_token"]
        ) as connection:
            query = """
                SELECT NM_CLIENTE, NM_DASHBOARD, DS_DESCRICAO
                FROM dbw_datahub_dev.db_app.tb_config_powerbi_dashboard
                WHERE SN_ATIVO = TRUE
                ORDER BY NM_CLIENTE, NM_DASHBOARD
            """
            return pd.read_sql(query, connection)
    except Exception as e:
        st.error(f"Erro ao carregar dashboards: {e}")
        log_erro_acess("listar_dashboards_powerbi", str(e))
        return pd.DataFrame()


# ============================================================
# 🧾 Aba principal
# ============================================================
def aba_powerbi_dashboard(usuario_logado: str):
    if "expandido" not in st.session_state:
        st.session_state.expandido = False

    # ============================================================
    # ⚙️ CSS Global
    # ============================================================
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #fafafa;
        }

        /* ====== Cabeçalho visual padrão ====== */
        .header-container {
            width: 70%;
            margin: 0 auto 25px auto;
            background: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            box-shadow: 0 3px 8px rgba(0,0,0,0.05);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 28px;
        }

        .header-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: #1a1a1a;
            text-align: right;
        }

        .btn-voltar {
            background-color: #0063B1 !important;
            color: #fff !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 10px 24px !important;
            font-size: 15px !important;
            font-weight: 600 !important;
            cursor: pointer !important;
            transition: all 0.2s ease-in-out !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important;
        }

        .btn-voltar:hover {
            background-color: #00529b !important;
            transform: translateY(-2px);
        }

        @media (max-width: 768px) {
            .header-container {
                flex-direction: column;
                gap: 10px;
                text-align: center;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ============================================================
    # Estado normal
    # ============================================================
    if not st.session_state.expandido:
        render_cabecalho()
        df_dash = listar_dashboards()

        if df_dash.empty:
            st.warning("Nenhum dashboard Power BI configurado.")
            return

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            clientes = sorted(df_dash["NM_CLIENTE"].unique().tolist())
            cliente_sel = st.selectbox("🔍 CLIENTE", clientes, key="cliente_powerbi")

        with col2:
            dash_cliente = df_dash[df_dash["NM_CLIENTE"] == cliente_sel]
            dash_sel = st.selectbox("📊 Dashboard", dash_cliente["NM_DASHBOARD"].tolist(), key="dash_powerbi")

        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            carregar = st.button("🚀 Carregar Dashboard", use_container_width=True)

        dash_desc = dash_cliente.loc[dash_cliente["NM_DASHBOARD"] == dash_sel, "DS_DESCRICAO"].values
        if len(dash_desc) > 0 and pd.notna(dash_desc[0]) and dash_desc[0].strip() != "":
            st.markdown(
                f"""
                <div style="background-color:#f9f9f9;border-left:4px solid #ccc;
                padding:10px 16px;border-radius:6px;margin-top:8px;font-size:0.95rem;color:#444;">
                🛈 <strong>Descrição:</strong> {dash_desc[0]}
                </div>
                """,
                unsafe_allow_html=True
            )

        st.markdown("---")

        if carregar:
            with st.spinner("Gerando token de embed..."):
                embed_info = generate_powerbi_embed_token(
                    usuario_logado=usuario_logado,
                    cliente=cliente_sel,
                    dashboard_nome=dash_sel,
                    debug=False
                )

            if "erro" in embed_info:
                st.error("❌ Erro ao gerar token de embed.")
                st.markdown("#### 🔍 Detalhes do erro:")
                st.code(json.dumps(embed_info, indent=2, ensure_ascii=False), language="json")
                return

            st.session_state.embed_info = embed_info
            st.session_state.cliente_sel = cliente_sel
            st.session_state.dash_sel = dash_sel
            st.session_state.expandido = True
            st.rerun()

    # ============================================================
    # Estado expandido com Power BI Client (UI refinada)
    # ============================================================
    else:
        embed_info = st.session_state.embed_info
        cliente_sel = st.session_state.cliente_sel
        dash_sel = st.session_state.dash_sel

        embed_url = embed_info["embedUrl"]
        embed_token = embed_info["embedToken"]

        # ============================================================
        # 💅 Cabeçalho refinado e funcional
        # ============================================================
        st.markdown("<div class='header-container'>", unsafe_allow_html=True)
        col1, col2 = st.columns([1, 3])

        with col1:
            voltar = st.button("🔙 Voltar", key="btn_voltar", help="Voltar para seleção de dashboards")
            if voltar:
                st.session_state.expandido = False
                st.session_state.embed_info = None
                st.rerun()

        with col2:
            st.markdown(
                f"<div class='header-title'>{cliente_sel} — {dash_sel}</div>",
                unsafe_allow_html=True
            )

        st.markdown("</div>", unsafe_allow_html=True)

        # ============================================================
        # 🌐 Power BI Client (altura fixa - 1300px)
        # ============================================================
        html_embed = f"""
        <div id="reportContainerWrapper" style="width:100%;height:1300px;border:none;">
            <div id="reportContainer" style="width:100%;height:100%;"></div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/powerbi-client@2.21.0/dist/powerbi.min.js"></script>
        <script>
            const models = window['powerbi-client'].models;
            const embedConfig = {{
                type: 'report',
                tokenType: models.TokenType.Embed,
                accessToken: '{embed_token}',
                embedUrl: '{embed_url}',
                settings: {{
                    panes: {{
                        filters: {{ visible: false }},
                        pageNavigation: {{ visible: true }}
                    }},
                    navContentPaneEnabled: true
                }}
            }};
            const container = document.getElementById('reportContainer');
            const powerbiService = new window['powerbi-client'].service.Service(
                window['powerbi-client'].factories.hpmFactory,
                window['powerbi-client'].factories.wpmpFactory,
                window['powerbi-client'].factories.routerFactory
            );
            powerbiService.reset(container);
            powerbiService.embed(container, embedConfig);
        </script>
        """

        st.components.v1.html(html_embed, height=3900, scrolling=False)


# ============================================================
# 🧪 Teste local
# ============================================================
if __name__ == "__main__":
    st.set_page_config(page_title="Power BI Embed", layout="wide")
    aba_powerbi_dashboard(usuario_logado="teste@databricks.com")
