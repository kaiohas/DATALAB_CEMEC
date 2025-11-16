from datetime import datetime, date, time, timedelta, timezone
import os
import pytz
from supabase_client import client


# Etapas padronizadas conforme especificação
ETAPAS = [
"status_medico",
"status_enfermagem",
"status_farmacia",
"status_espirometria",
"status_nutricionista",
"status_coordenacao",
"status_recepcao",
]


# Grupos de variáveis usados nos selects
GRUPOS_VARIAVEIS = [
    "Reembolso",
    "Tipo_visita",
    "Medico_responsavel",
    "Consultorio",
    "Jejum",
    "Desfecho_atendimento",
    "Visita",
]




APP_TZ = os.getenv("APP_TZ", "America/Sao_Paulo")
TZ = pytz.timezone(APP_TZ)




def now_tz() -> datetime:
    return datetime.now(tz=TZ)


def calcular_programacao(data_cadastro: datetime, data_visita: date, hora_consulta: time | None) -> str:
    """Calcula status de programação conforme regras informadas.
    Regras priorizadas:
    - "Não Programada": incluídos com antecedência < 24 horas
    - "Programada": > 15 dias
    - "Incluída": > 7 dias
    - "Extraordinário": entre 24h e 7 dias
    Obs.: "Remanejada" exigiria rastrear reagendamentos; pode ser adicionada em futuras melhorias.
    """
    if hora_consulta:
        dt_visita = datetime.combine(data_visita, hora_consulta)
    else:
    # caso não tenha hora, compara meio-dia
        dt_visita = datetime.combine(data_visita, time(12, 0))
    dt_visita = TZ.localize(dt_visita)

    diff = dt_visita - data_cadastro
    hours = diff.total_seconds() / 3600.0
    days = diff.days


    if hours < 24:
        return "Não Programada"
    if days > 15:
        return "Programada"
    if days > 7:
        return "Incluída"
    return "Extraordinário"

def listar_variaveis_por_grupo(grupo: str):
    return (
        client.table("ag_variaveis")
        .select("id, nome_variavel")
        .eq("grupo_variavel", grupo)
        .eq("is_active", True)
        .order("nome_variavel")
        .execute()
        .data
    )


# ------------------ NOVO: Estudos ------------------
def listar_estudos():
    """
    Busca estudos na tabela 'estudos' (id, nome).
    Se não existir / vier vazia, tenta 'ag_estudos' como fallback.
    Retorna lista de dicts: [{'id': 1, 'nome': 'XYZ'}, ...]
    """
    data = (client.table("estudos").select("id, nome").order("nome").execute().data or [])
    if not data:
        # fallback opcional, caso o nome da tabela seja 'ag_estudos'
        data = client.table("ag_estudos").select("id, nome").order("nome").execute().data or []
    return data

def map_estudos():
    """Retorna dict {id: nome} a partir da tabela estudos."""
    lst = listar_estudos()
    return {it["id"]: it["nome"] for it in lst}


def listar_status_da_etapa(nome_etapa: str):
    return (
        client.table("ag_status_tipos")
        .select("id, nome_status")
        .eq("nome_etapa", nome_etapa)
        .order("nome_status")
        .execute()
        .data
    )




def status_atual_por_etapa(agendamento_id: int) -> dict:
    """Retorna o último status por etapa a partir do log."""
    # Busca logs ordenados por data desc e agrupa na aplicação
    logs = (
        client.table("ag_log_agendamentos")
        .select("nome_etapa, status_etapa, data_hora_etapa")
        .eq("agendamento_id", agendamento_id)
        .order("data_hora_etapa", desc=True)
        .execute()
        .data or []
    )
    out = {}
    for row in logs:
        etapa = row["nome_etapa"]
        if etapa not in out:
            out[etapa] = row["status_etapa"]
    return out




def atualizar_hora_saida(agendamento_id: int):
    """Atualiza hora_saida como o maior timestamp do log para o agendamento."""
    resp = (
        client.rpc("", {}) # placeholder para compat v2 se tivéssemos função. Faremos via select.
    )
    # Seleciona max(data_hora_etapa)
    max_dt = (
        client.table("ag_log_agendamentos")
        .select("data_hora_etapa")
        .eq("agendamento_id", agendamento_id)
        .order("data_hora_etapa", desc=True)
        .limit(1)
        .execute()
        .data
    )
    if max_dt:
        ultimo = max_dt[0]["data_hora_etapa"]
        client.table("ag_agendamentos").update({"hora_saida": ultimo}).eq("id", agendamento_id).execute()

