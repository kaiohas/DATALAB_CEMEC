from backend.api.auditoria import registrar_evento_auditoria
from frontend.config import get_sql_connection_dict

# ============================================================
# 🔐 LOGIN
# ============================================================
def log_login(sucesso: bool = True, mensagem: str = None, usuario: str = None):
    """Registra o evento de login no Data Hub."""
    status = "SUCESSO" if sucesso else "FALHA"

    registrar_evento_auditoria(
        tp_evento="ACESSO",
        ds_acao="Login no Data Hub",
        nm_tela="Login",
        nm_usuario=usuario,
        ds_status=status,
        ds_mensagem=mensagem,
        nm_origem="STREAMLIT",
        config=get_sql_connection_dict  # ✅ passa função (sem parênteses)
    )


# ============================================================
# 🚪 LOGOUT
# ============================================================
def log_logout(usuario: str = None):
    """Registra o evento de logout do Data Hub."""
    registrar_evento_auditoria(
        tp_evento="ACESSO",
        ds_acao="Logout do Data Hub",
        nm_tela="Logout",
        nm_usuario=usuario,
        ds_status="SUCESSO",
        nm_origem="STREAMLIT",
        config=get_sql_connection_dict
    )


# ============================================================
# 📄 VISUALIZAÇÃO DE PÁGINAS
# ============================================================
def log_page_view(nome_pagina: str, parametros: dict = None, usuario: str = None):
    """
    Registra o acesso a uma página do Data Hub.
    Ideal para colocar no topo de cada página Streamlit.
    """
    registrar_evento_auditoria(
        tp_evento="VISUALIZACAO",
        ds_acao=f"Acesso à página {nome_pagina}",
        nm_tela=nome_pagina,
        nm_usuario=usuario,
        ds_parametros=parametros,
        ds_status="SUCESSO",
        nm_origem="STREAMLIT",
        config=get_sql_connection_dict
    )


# ============================================================
# ⚠️ ERROS / FALHAS DE ACESSO
# ============================================================
def log_erro_acess(nome_pagina: str, mensagem: str, usuario: str = None):
    """Registra falhas de acesso ou erros de carregamento de página."""
    registrar_evento_auditoria(
        tp_evento="ERRO",
        ds_acao=f"Erro ao acessar {nome_pagina}",
        nm_tela=nome_pagina,
        nm_usuario=usuario,
        ds_status="FALHA",
        ds_mensagem=mensagem,
        nm_origem="STREAMLIT",
        config=get_sql_connection_dict
    )
