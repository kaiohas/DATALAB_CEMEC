# ============================================================
# 🔗 frontend/supabase_client.py
# Cliente centralizado para Supabase (seguro para múltiplas sessões Streamlit)
# ============================================================
import os
import time
import random
import logging
from datetime import datetime, timezone
from typing import Callable, TypeVar

import streamlit as st
import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# Chave onde o client ficará armazenado (por sessão)
_SESSION_KEY = "_supabase_client"


def get_supabase_client() -> Client:
    """
    Retorna um cliente Supabase por sessão do Streamlit (st.session_state).
    Isso evita corrida entre usuários e problemas com pool/socket compartilhado.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise EnvironmentError("Variáveis SUPABASE_URL e SUPABASE_KEY não configuradas no .env")

    client = st.session_state.get(_SESSION_KEY)
    if client is not None:
        return client

    # Observação:
    # O supabase-py cria internamente o client httpx.
    # Não temos como injetar facilmente Limits/Timeout aqui sem mudar a lib,
    # então mitigamos via isolamento por sessão + retry/backoff no execute.
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    st.session_state[_SESSION_KEY] = client
    logger.info("✅ Cliente Supabase criado (por sessão)")
    return client


def reset_supabase_client():
    """
    Reseta SOMENTE o client da sessão atual (não global).
    Útil se a sessão atual ficou com conexão ruim.
    """
    if _SESSION_KEY in st.session_state:
        del st.session_state[_SESSION_KEY]
    logger.info("🔄 Cliente Supabase resetado (sessão atual)")


T = TypeVar("T")


def supabase_execute(execute_fn: Callable[[], T], *, max_retries: int = 4) -> T:
    """
    Executa uma chamada .execute() (postgrest) com retry/backoff + jitter,
    tratando ReadError/timeout/erros temporários.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return execute_fn()

        except (httpx.ReadError, httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, OSError) as e:
            last_exc = e

            # Se não for a última tentativa, espera com backoff + jitter e tenta novamente
            if attempt < max_retries:
                # Backoff exponencial leve (0.3, 0.6, 1.2, 2.4...) + jitter
                base = 0.3 * (2 ** (attempt - 1))
                jitter = random.uniform(0, 0.2)
                sleep_s = base + jitter
                logger.warning(f"⚠️ Supabase temporariamente indisponível (tentativa {attempt}/{max_retries}): {e}. Sleep {sleep_s:.2f}s")
                time.sleep(sleep_s)

                # Importante: resetar apenas o client desta sessão pode ajudar
                reset_supabase_client()
                _ = get_supabase_client()
                continue

            # Última tentativa: propaga
            raise

        except Exception as e:
            # Para outros erros (ex: permissão, query inválida), não faz retry cego
            raise

    # Não deve chegar aqui
    raise last_exc if last_exc else RuntimeError("Falha desconhecida ao executar chamada Supabase")


def registrar_log_agendamento(
    supabase: Client,
    agendamento_id: int,
    usuario_id,
    usuario_nome: str,
    campo_alterado: str,
    valor_antigo,
    valor_novo,
) -> None:
    log = {
        "agendamento_id": agendamento_id,
        "data_alteracao": datetime.now(timezone.utc).isoformat(),
        "usuario_alteracao_id": usuario_id,
        "usuario_alteracao_nome": usuario_nome,
        "campo_alterado": campo_alterado,
        "valor_antigo": str(valor_antigo) if valor_antigo is not None else None,
        "valor_novo": str(valor_novo) if valor_novo is not None else None,
    }
    supabase_execute(
        lambda: supabase.table("tab_app_log_agendamentos").insert(log).execute()
    )


# ============================================================
# 📋 Mapeamento de tabelas (referência)
# ============================================================
TABELAS_SUPABASE = {
    "tab_app_usuarios": "tab_app_usuarios",
    "tab_app_grupos": "tab_app_grupos",
    "tab_app_paginas": "tab_app_paginas",
    "tab_app_usuario_grupo": "tab_app_usuario_grupo",
    "tab_app_grupo_pagina": "tab_app_grupo_pagina",
    "tab_app_menu_app": "tab_app_menu_app",
}