# ============================================================
# 📁 frontend/config/tabelas.py
# ============================================================
# Centraliza todas as referências de tabelas do ecossistema DataHub.
# Mantém padronização e facilita manutenção entre ambientes (dev, prd, hml).
# ============================================================


# ============================================================
# 📦 TABELAS GESTAO DE GRUPOS E USUARIOS
# ============================================================

TAB_USUARIOS = "tab_app_usuarios"
TAB_GRUPOS = "tab_app_grupos"
TAB_USUARIOS_GRUPOS = "tab_app_usuarios_grupos"
TAB_PERMISSOES = "tab_app_permissoes"
TAB_GRUPOS_PERMISSOES = "tab_app_grupos_permissoes"





# ============================================================
# ⚙️ FUNÇÃO UTILITÁRIA (Opcional)
# ============================================================
def listar_tabelas(prefixo: str = "") -> dict:
    """
    Retorna um dicionário com todas as tabelas disponíveis.
    Pode ser filtrado por prefixo (ex: 'TAB_MKT').
    """
    import inspect
    globais = globals()
    return {
        nome: valor
        for nome, valor in globais.items()
        if nome.startswith(prefixo) and isinstance(valor, str)
    }
