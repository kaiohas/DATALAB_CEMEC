import io
import pandas as pd
import datetime
from frontend.config import get_config, get_sql_connection_dict
from backend.api.auditoria import registrar_evento_auditoria
from backend.api.logger import (
    log_login,
    log_logout,
    log_page_view,
    log_erro_acess
)


# =====================================================================
# 🧩 Módulo de Exportação - Lógica + Auditoria (sem UI)
# =====================================================================
def gerar_arquivo_exportacao(
    df: pd.DataFrame,
    nome_base: str,
    tipo_exportacao: str,
    tabela_origem: str,
    usuario: str,
    filtrado: bool = False
):
    """
    Gera o arquivo em memória e registra auditoria.
    Retorna (bytes|str, nome_arquivo, mime_type).
    """


    data_hora = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_sufixo = "(filtrados)" if filtrado else "(todos)"
    nome_arquivo = f"{nome_base}_{data_hora}.{tipo_exportacao.lower()}"

    # Geração do conteúdo conforme o tipo
    if tipo_exportacao == "CSV":
        conteudo = df.to_csv(index=False).encode("utf-8")
        mime = "text/csv"

    elif tipo_exportacao == "Excel":
        tipo_exportacao = "XLSX"
        nome_arquivo = f"{nome_base}_{data_hora}.{tipo_exportacao.lower()}"
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Dados")
        conteudo = buffer.getvalue()
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    elif tipo_exportacao == "JSON":
        conteudo = df.to_json(orient="records", force_ascii=False, indent=2)
        mime = "application/json"

    else:
        raise ValueError(f"Tipo de exportação inválido: {tipo_exportacao}")

    # Registrar auditoria unificada
    from backend.api.auditoria import registrar_evento_auditoria

    registrar_evento_auditoria(
        tp_evento="EXPORTACAO",
        ds_acao=f"Exportação de dados - {tipo_exportacao} {nome_sufixo}",
        nm_tabela_afetada=tabela_origem,
        nm_arquivo=nome_arquivo,
        ds_parametros={
            "usuario": usuario,
            "tipo_exportacao": tipo_exportacao,
            "nome_sufixo": nome_sufixo,
            "qt_registros": len(df)
        },
        ds_status="SUCESSO",
        nm_origem="STREAMLIT",
        config=get_sql_connection_dict
    )

    return conteudo, nome_arquivo, mime
