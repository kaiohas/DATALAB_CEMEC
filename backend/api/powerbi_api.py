# ============================================================
# 📑 backend/api/powerbi_api.py
# ============================================================
import requests
import json
import pandas as pd
from databricks import sql
from frontend.config import get_sql_connection_dict
from backend.api.logger import log_erro_acess
from backend.api.auditoria import registrar_evento_auditoria


# ============================================================
# 🧩 Função utilitária: normalizar valores de dicionários
# ============================================================
def normalize_dict_values(record_dict):
    """
    Garante que todos os valores retornados do Databricks sejam strings puras,
    evitando erros de ambiguidade com arrays NumPy ou tipos binários.
    """
    if not record_dict:
        return None

    normalized = {}
    for k, v in record_dict.items():
        if isinstance(v, (list, tuple)):
            normalized[k] = json.dumps(v)
        elif isinstance(v, (bytes, bytearray)):
            normalized[k] = v.decode("utf-8", errors="ignore")
        else:
            normalized[k] = str(v)
    return normalized


# ============================================================
# 🔹 Função principal: gerar token de embed Power BI
# ============================================================
def generate_powerbi_embed_token(usuario_logado: str, cliente: str, dashboard_nome: str, debug: bool = False):
    try:
        # ============================================================
        # 🔍 Consultas SQL - Config do ambiente e dashboard
        # ============================================================
        env_query = """
            SELECT TENANT_ID, CLIENT_ID, CLIENT_SECRET
            FROM dbw_datahub_dev.db_app.tb_config_powerbi_env
            LIMIT 1
        """
        dash_query = f"""
            SELECT ID_WORKSPACE, ID_REPORT, ID_DATASET, DS_ROLES
            FROM dbw_datahub_dev.db_app.tb_config_powerbi_dashboard
            WHERE LOWER(TRIM(NM_CLIENTE)) = LOWER(TRIM('{cliente}'))
              AND LOWER(TRIM(NM_DASHBOARD)) = LOWER(TRIM('{dashboard_nome}'))
              AND SN_ATIVO = TRUE
            LIMIT 1
        """

        # ============================================================
        # 🧩 Conexão com Databricks SQL
        # ============================================================
        conn_dict = get_sql_connection_dict()
        with sql.connect(
            server_hostname=conn_dict["server_hostname"],
            http_path=conn_dict["http_path"],
            access_token=conn_dict["access_token"]
        ) as connection:
            df_env = pd.read_sql(env_query, connection)
            df_dash = pd.read_sql(dash_query, connection)

        # ============================================================
        # 🔧 Normalização de valores retornados
        # ============================================================
        env = normalize_dict_values(df_env.iloc[0].to_dict()) if not df_env.empty else None
        dash = normalize_dict_values(df_dash.iloc[0].to_dict()) if not df_dash.empty else None

        if debug:
            print("🔍 DEBUG Power BI -> ENV:", env)
            print("🔍 DEBUG Power BI -> DASH:", dash)

        # ============================================================
        # ❗ Validação de existência das configs
        # ============================================================
        if env is None or dash is None:
            erro_detalhado = {
                "mensagem": "Configurações do ambiente ou dashboard não encontradas.",
                "cliente": cliente,
                "dashboard": dashboard_nome,
                "resultado_env": None if env is None else "OK",
                "resultado_dash": None if dash is None else "OK"
            }
            raise Exception(json.dumps(erro_detalhado, ensure_ascii=False, indent=2))

        # ============================================================
        # 🔐 1️⃣ Autenticação no Azure AD (Client Credentials Flow)
        # ============================================================
        token_url = f"https://login.microsoftonline.com/{env['TENANT_ID']}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": env["CLIENT_ID"],
            "client_secret": env["CLIENT_SECRET"],
            "scope": "https://analysis.windows.net/powerbi/api/.default"
        }

        response = requests.post(token_url, data=data)
        access_token = response.json().get("access_token")

        if not access_token:
            raise Exception(f"Falha ao obter access token: {response.text}")

        # ============================================================
        # 🔑 2️⃣ Geração do Embed Token Power BI
        # ============================================================
        generate_token_url = (
            f"https://api.powerbi.com/v1.0/myorg/groups/"
            f"{dash['ID_WORKSPACE']}/reports/{dash['ID_REPORT']}/GenerateToken"
        )

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        # ============================================================
        # 🧠 Roles opcionais — apenas se houver RLS real
        # ============================================================
        body = {"accessLevel": "View"}
        roles = []

        if dash.get("DS_ROLES") and dash["DS_ROLES"].strip() not in ["", "None", "null", "[]"]:
            try:
                parsed_roles = json.loads(dash["DS_ROLES"])
                if isinstance(parsed_roles, list):
                    roles = parsed_roles
                elif isinstance(parsed_roles, str) and parsed_roles.strip():
                    roles = [parsed_roles]
            except Exception:
                roles = [dash["DS_ROLES"]]

        # ✅ Só adiciona identities se houver roles reais
        if roles and any(r.strip() for r in roles):
            body["identities"] = [{
                "username": usuario_logado,
                "roles": [r.strip() for r in roles if r.strip()],
                "datasets": [dash["ID_DATASET"]]
            }]

        if debug:
            print("📦 BODY ENVIADO PARA POWER BI:", json.dumps(body, indent=2))

        response = requests.post(generate_token_url, headers=headers, json=body)

        if response.status_code != 200:
            raise Exception(f"Erro ao gerar embed token: {response.text}")

        data = response.json()

        # ============================================================
        # 🪶 Auditoria e retorno
        # ============================================================
        registrar_evento_auditoria(usuario_logado, "GERAR_EMBED_POWERBI", f"{cliente} | {dashboard_nome}")

        return {
            "embedToken": data["token"],
            "embedUrl": (
                f"https://app.powerbi.com/reportEmbed?"
                f"reportId={dash['ID_REPORT']}&groupId={dash['ID_WORKSPACE']}"
            )
        }

    except Exception as e:
        log_erro_acess("generate_powerbi_embed_token", str(e))
        registrar_evento_auditoria(usuario_logado, "ERRO_EMBED_POWERBI", str(e))

        return {
            "erro": str(e),
            "cliente": cliente,
            "dashboard": dashboard_nome
        }
