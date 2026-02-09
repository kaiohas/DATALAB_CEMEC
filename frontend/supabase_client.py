# ============================================================
# 🔗 frontend/supabase_client.py
# Cliente centralizado para Supabase
# ============================================================
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_supabase_client: Client = None

def get_supabase_client() -> Client:
    """Retorna uma instância única do cliente Supabase."""
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise EnvironmentError(
                "Variáveis SUPABASE_URL e SUPABASE_KEY não configuradas no .env"
            )
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

    return _supabase_client

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