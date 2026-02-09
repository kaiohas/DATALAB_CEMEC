# ============================================================
# ⚙️ frontend/config.py
# Configuração unificada para Supabase
# ============================================================
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ============================================================
# 🧰 Classe de Configuração (Supabase)
# ============================================================
class Config:
    """Configuração centralizada."""
    
    ENVIRONMENT = os.getenv("APP_ENV", "dev").lower()
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    
    # Debug
    DEBUG = ENVIRONMENT == "dev"

    @classmethod
    def check(cls):
        """Valida se as variáveis obrigatórias estão definidas."""
        missing = []
        
        if not cls.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not cls.SUPABASE_KEY:
            missing.append("SUPABASE_KEY")

        if missing:
            logger.error(f"❌ Variáveis ausentes: {', '.join(missing)}")
            raise EnvironmentError(f"Variáveis ausentes: {', '.join(missing)}")

        logger.info(f"✅ Configuração validada ({cls.ENVIRONMENT.upper()})")

def get_config():
    """Retorna instância de Config."""
    return Config

def get_supabase_client():
    """Retorna o cliente Supabase."""
    from frontend.supabase_client import get_supabase_client as _get_client
    return _get_client()