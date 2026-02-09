import os
import json
import pandas as pd
from datetime import datetime, timezone
import traceback

# Import opcional do Streamlit
try:
    import streamlit as st
except ModuleNotFoundError:
    st = None

# ============================================================
# 🧩 Função Unificada de Auditoria - Data Hub (versão Supabase)
# ============================================================
def registrar_evento_auditoria(
    tp_evento: str,
    ds_acao: str,
    config=None,  # Pode ser dicionário ou função (get_sql_connection_dict)
    nm_tela: str = None,
    nm_usuario: str = None,
    nm_tabela_afetada: str = None,
    nm_arquivo: str = None,
    ds_parametros: dict = None,
    ds_dados_antigos: dict = None,
    ds_dados_novos: dict = None,
    ds_status: str = "SUCESSO",
    ds_mensagem: str = None,
    nm_origem: str = "STREAMLIT",
    id_referencia: str = None
):
    """
    Registra qualquer tipo de evento de auditoria do Data Hub.
    1️⃣ Usa conexão Supabase (padrão) ou Databricks (legado).
    2️⃣ Se falhar, salva localmente.
    """

    print(f"\n[AUDITORIA] {tp_evento} → {ds_acao}")

    # -------------------------------------------------------------
    # Permitir passar função (ex: get_sql_connection_dict) ou dict
    # -------------------------------------------------------------
    if callable(config):
        try:
            config = config()
        except Exception as e:
            print(f"[AUDITORIA] Erro ao obter config: {e}")
            config = None

    # -------------------------------------------------------------
    # Captura automática do usuário
    # -------------------------------------------------------------
    if not nm_usuario:
        try:
            headers = getattr(st, "context", None)
            headers = getattr(headers, "headers", {}) if headers else {}
            nm_usuario = (
                headers.get("X-Forwarded-Preferred-Username")
                or headers.get("X-Forwarded-Email")
                or headers.get("X-Forwarded-User")
                or "desconhecido"
            ).strip()
        except Exception:
            nm_usuario = "desconhecido"

    agora = datetime.now(timezone.utc).isoformat()

    def safe_json(data):
        if not data:
            return None
        try:
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception as e:
            return f"ERRO_SERIALIZACAO: {str(e)}"

    safe_params = safe_json(ds_parametros)
    safe_old = safe_json(ds_dados_antigos)
    safe_new = safe_json(ds_dados_novos)

    # ============================================================
    # 1️⃣ Tentar via Supabase (padrão)
    # ============================================================
    try:
        if not config:
            raise ValueError("Config não fornecido para conexão")

        db_type = config.get("type", "supabase")

        if db_type == "supabase":
            # Conexão Supabase
            from frontend.supabase_client import get_supabase_client
            supabase = get_supabase_client()

            registro = {
                "dt_evento": agora,
                "tp_evento": tp_evento.upper(),
                "nm_tela": nm_tela,
                "nm_usuario": nm_usuario,
                "nm_tabela_afetada": nm_tabela_afetada,
                "nm_arquivo": nm_arquivo,
                "ds_acao": ds_acao,
                "ds_parametros": safe_params,
                "ds_dados_antigos": safe_old,
                "ds_dados_novos": safe_new,
                "ds_status": ds_status.upper(),
                "ds_mensagem": ds_mensagem,
                "nm_origem": nm_origem.upper(),
                "id_referencia": str(id_referencia) if id_referencia else None
            }

            response = supabase.table("auditoria_eventos").insert(registro).execute()

            if response.data:
                print("[AUDITORIA] Registro gravado via Supabase com sucesso.")
                return True
            else:
                raise Exception(f"Erro ao inserir: {response}")

        else:
            # Conexão Databricks (legado)
            import databricks.sql as dsql

            server_hostname = config.get("server_hostname")
            http_path = config.get("http_path")
            access_token = config.get("access_token")

            connection = dsql.connect(
                server_hostname=server_hostname,
                http_path=http_path,
                access_token=access_token
            )

            # Escape para SQL
            safe_params_sql = safe_params.replace("'", "''") if safe_params else None
            safe_old_sql = safe_old.replace("'", "''") if safe_old else None
            safe_new_sql = safe_new.replace("'", "''") if safe_new else None

            insert_query = f"""
                INSERT INTO dbw_datahub_dev.db_app.tb_auditoria_eventos
                (DT_EVENTO, TP_EVENTO, NM_TELA, NM_USUARIO, NM_TABELA_AFETADA, NM_ARQUIVO,
                 DS_ACAO, DS_PARAMETROS, DS_DADOS_ANTIGOS, DS_DADOS_NOVOS,
                 DS_STATUS, DS_MENSAGEM, NM_ORIGEM, ID_REFERENCIA)
                VALUES (
                    '{agora}', '{tp_evento.upper()}', '{nm_tela}', '{nm_usuario}',
                    '{nm_tabela_afetada}', '{nm_arquivo}', '{ds_acao}',
                    {f"'{safe_params_sql}'" if safe_params_sql else "NULL"},
                    {f"'{safe_old_sql}'" if safe_old_sql else "NULL"},
                    {f"'{safe_new_sql}'" if safe_new_sql else "NULL"},
                    '{ds_status.upper()}',
                    {f"'{ds_mensagem}'" if ds_mensagem else "NULL"},
                    '{nm_origem.upper()}', '{id_referencia}'
                )
            """

            with connection.cursor() as cursor:
                cursor.execute(insert_query)
                print("[AUDITORIA] Registro gravado via Databricks SQL com sucesso.")

            connection.close()
            return True

    except Exception as e:
        print(f"[AUDITORIA] Falha na gravação: {e}")
        traceback.print_exc()

    # ============================================================
    # 2️⃣ Fallback local
    # ============================================================
    try:
        log_dir = os.path.join(os.getcwd(), "_log")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "auditoria_eventos.csv")

        df_local = pd.DataFrame([{
            "DT_EVENTO": agora,
            "TP_EVENTO": tp_evento,
            "NM_TELA": nm_tela,
            "NM_USUARIO": nm_usuario,
            "DS_ACAO": ds_acao,
            "DS_STATUS": ds_status
        }])

        if os.path.exists(log_path):
            df_antigo = pd.read_csv(log_path)
            df_local = pd.concat([df_antigo, df_local], ignore_index=True)

        df_local.to_csv(log_path, index=False)
        print(f"[AUDITORIA] Log salvo localmente em {log_path}")
        return True

    except Exception as e:
        print(f"[AUDITORIA] Falha ao gravar log local: {e}")
        traceback.print_exc()
        return False
