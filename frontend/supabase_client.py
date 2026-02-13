# ============================================================
# 🔗 frontend/supabase_client.py
# Cliente centralizado para Supabase
# ============================================================
import os
import time
import logging
import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_supabase_client: Client = None

def get_supabase_client(max_retries: int = 3) -> Client:
    """
    Retorna uma instância única do cliente Supabase.
    Configurado para suportar 20-30 usuários simultâneos.
    """
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not SUPABASE_URL or not SUPABASE_KEY:
        raise EnvironmentError(
            "Variáveis SUPABASE_URL e SUPABASE_KEY não configuradas no .env"
        )

    # ✅ Limites calibrados para 20-30 usuários simultâneos
    limites = httpx.Limits(
        max_connections=50,
        max_keepalive_connections=25,
    )
    timeout = httpx.Timeout(
        connect=10.0,
        read=30.0,
        write=10.0,
        pool=10.0
    )

    last_error = None
    for tentativa in range(1, max_retries + 1):
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info(f"✅ Cliente Supabase criado (tentativa {tentativa})")
            return _supabase_client

        except OSError as e:
            last_error = e
            logger.warning(f"⚠️ Tentativa {tentativa}/{max_retries} falhou: {e}")
            if tentativa < max_retries:
                time.sleep(0.5 * tentativa)
            continue

    raise last_error


def reset_supabase_client():
    """
    Reseta o client singleton para forçar reconexão.
    Usar quando o client existente está com socket corrompido.
    """
    global _supabase_client
    _supabase_client = None
    logger.info("🔄 Cliente Supabase resetado")


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