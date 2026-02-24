import streamlit as st
import os
import json
import urllib.request
import urllib.parse
from frontend.config import get_sql_connection_dict

# ============================================================
# ⚙️ Configurações do ambiente e workspace federado
# ============================================================
# Estes valores devem estar no st.secrets ou nas variáveis de ambiente.
CONF = {
    "instance_url": "xxxxxxx",
    "workspace_id": "xxxxxxxx",
    "dashboard_id": "xxxxxxxx",
    "service_principal_id": "xxxxxxxxx",
    "service_principal_secret": "xxxxxxxxxe",
    "external_viewer_id": "x909s",
    "external_value": "xxxxxx",
}

# ============================================================
# 🔗 Função auxiliar — Requisição HTTP genérica
# ============================================================
def http_request(url, method="GET", headers=None, body=None):
    headers = headers or {}
    req = urllib.request.Request(url, method=method, headers=headers)
    if body is not None:
        if isinstance(body, str):
            body = body.encode()
        req.data = body
    with urllib.request.urlopen(req) as resp:
        data = resp.read().decode()
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data


# ============================================================
# 🪄 Gera token federado (Embed with SSO Preview)
# ============================================================
@st.cache_data(ttl=300)
def get_federated_scoped_token(subject_token: str) -> str:
    """
    Troca um token federado (emitido pelo IdP) por um token Databricks scoped
    para o dashboard Lakeview. Segue a RFC 8693 (token exchange).
    """
    base = CONF["instance_url"]

    # 1️⃣ Obter informações de escopo do dashboard (tokeninfo)
    tokeninfo_url = (
        f"{base}/api/2.0/lakeview/dashboards/{CONF['dashboard_id']}/published/tokeninfo"
        f"?external_viewer_id={urllib.parse.quote(CONF['external_viewer_id'])}"
        f"&external_value={urllib.parse.quote(CONF['external_value'])}"
    )
    token_info = http_request(
        tokeninfo_url, headers={"Authorization": f"Bearer {subject_token}"}
    )

    # 2️⃣ Gerar token de escopo com autorização detalhada
    params = token_info.copy()
    auth_details = params.pop("authorization_details", None)
    params.update({
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "subject_token": subject_token,
        "authorization_details": json.dumps(auth_details),
    })
    body = urllib.parse.urlencode(params)

    scoped = http_request(
        f"{base}/oidc/v1/token",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=body,
    )

    return scoped["access_token"]


# ============================================================
# 📊 Página principal — Meus Dashboards (Embed com SSO)
# ============================================================
def page_dashboards():
    st.title("📊 Meus Dashboards (Embed com SSO Preview)")
    st.caption("Visualização incorporada com Token Federation (Databricks AWS Preview).")

    # ------------------------------------------------------------
    # 🔐 Recupera o token federado do usuário autenticado
    # ------------------------------------------------------------
    st.markdown("#### 🔐 Token federado (emitido pelo seu IdP)")
    subject_token = st.text_input(
        "Cole aqui o token JWT do seu IdP (para testes manuais do fluxo federado):",
        type="password",
        placeholder="xxxxxx"
    )

    col1, col2 = st.columns([1, 4])
    with col1:
        atualizar = st.button("🔄 Atualizar Dashboard")

    if atualizar:
        get_federated_scoped_token.clear()

    if not subject_token:
        st.info("Insira um token federado válido para gerar o embed token.")
        return

    # ------------------------------------------------------------
    # 🔄 Geração do token de incorporação
    # ------------------------------------------------------------
    with st.spinner("Trocando token federado por token Databricks (scoped)..."):
        try:
            embed_token = get_federated_scoped_token(subject_token)
        except Exception as e:
            st.error(f"Erro ao gerar token scoped: {e}")
            return

    # ------------------------------------------------------------
    # 🖥️ Renderização do dashboard incorporado (Databricks CDN)
    # ------------------------------------------------------------
    html = f"""
    <div id="dashboard-container" style="height:90vh;"></div>
    <script type="module">
        import {{ DatabricksDashboard }} from "https://cdn.jsdelivr.net/npm/@databricks/aibi-client@0.0.0-alpha.7/+esm";
        const dash = new DatabricksDashboard({{
            workspaceId: "{CONF['workspace_id']}",
            instanceUrl: "{CONF['instance_url']}",
            dashboardId: "{CONF['dashboard_id']}",
            token: "{embed_token}",
            container: document.getElementById("dashboard-container")
        }});
        dash.initialize();
    </script>
    """
    st.components.v1.html(html, height=900, scrolling=False)
    st.success("✅ Dashboard incorporado com autenticação federada (SSO Preview).")
