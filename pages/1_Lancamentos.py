# pages/1_Lancamentos.py
import streamlit as st
import pandas as pd
from datetime import date
from supabase_client import client
from auth import require_roles
from utils import listar_variaveis_por_grupo, listar_estudos, map_estudos

st.set_page_config(page_title="Lançamentos | Agenda Unificada", page_icon="🗓️", layout="wide")
require_roles(["agenda", "gerencia"])
user = st.session_state["user"]

st.title("🗓️ Lançamentos de Agendamentos")

# ----------------- Helpers -----------------
def calc_programacao(data_cad: date, data_visita: date, foi_remarcado: bool = False) -> str:
    if not (data_cad and data_visita):
        return None
    delta = (data_visita - data_cad).days
    horas = (pd.Timestamp(data_visita) - pd.Timestamp(data_cad)).total_seconds() / 3600.0
    if horas < 24:
        return "Não Programada"
    if delta > 15:
        return "Programada"
    if delta > 7:
        return "Incluída"
    return "Extraordinário"

def _map_dict(grupo):
    lst = listar_variaveis_por_grupo(grupo) or []
    return {x["id"]: x["nome_variavel"] for x in lst}

# ================== Combos ==================
# Estudos agora vêm da tabela 'estudos'
op_estudo_tbl = listar_estudos()  # [{'id', 'nome'}...]
map_estudo = map_estudos()

op_reembolso    = listar_variaveis_por_grupo("Reembolso") or []
op_tipo_visita  = listar_variaveis_por_grupo("Tipo_visita") or []
op_medico       = listar_variaveis_por_grupo("Medico_responsavel") or []
op_consultorio  = listar_variaveis_por_grupo("Consultorio") or []
op_jejum        = listar_variaveis_por_grupo("Jejum") or []
op_visita       = listar_variaveis_por_grupo("Visita") or []  # <== NOVO

# ----------------- Formulário -----------------
st.subheader("Novo agendamento")
with st.form("frm_novo_agendamento", clear_on_submit=False):
    c1, c2, c3 = st.columns(3)
    with c1:
        data_visita   = st.date_input("Data da visita")
        id_paciente   = st.text_input("ID Paciente")
        nome_paciente = st.text_input("Nome do paciente")
    with c2:
        estudo = st.selectbox(
            "Estudo",
            options=[{"id": None, "nome": "(selecione)"}] + op_estudo_tbl,
            format_func=lambda x: x["nome"],
        )
        tipo_visita = st.selectbox(
            "Tipo de visita",
            options=[{"id": None, "nome_variavel": "(selecione)"}] + op_tipo_visita,
            format_func=lambda x: x["nome_variavel"],
        )
        reembolso = st.selectbox(
            "Reembolso",
            options=[{"id": None, "nome_variavel": "(selecione)"}] + op_reembolso,
            format_func=lambda x: x["nome_variavel"],
        )
    with c3:
        medico_resp = st.selectbox(
            "Médico responsável",
            options=[{"id": None, "nome_variavel": "(selecione)"}] + op_medico,
            format_func=lambda x: x["nome_variavel"],
        )
        consultorio = st.selectbox(
            "Consultório",
            options=[{"id": None, "nome_variavel": "(selecione)"}] + op_consultorio,
            format_func=lambda x: x["nome_variavel"],
        )
        jejum = st.selectbox(
            "Jejum",
            options=[{"id": None, "nome_variavel": "(selecione)"}] + op_jejum,
            format_func=lambda x: x["nome_variavel"],
        )

    c4, c5, c6 = st.columns(3)
    with c4:
        hora_consulta = st.time_input("Hora da consulta", value=None)
        horario_uber  = st.time_input("Horário do Uber", value=None)
    with c5:
        # ALTERADO: Visita agora é selectbox de variáveis
        visita = st.selectbox(
            "Visita",
            options=[{"id": None, "nome_variavel": "(selecione)"}] + op_visita,
            format_func=lambda x: x["nome_variavel"],
        )
        obs_visita = st.text_input("Obs. da visita")
    with c6:
        obs_coleta = st.text_input("Obs. de coleta")

    submitted = st.form_submit_button("Cadastrar agendamento", type="primary", use_container_width=True)

if submitted:
    if not data_visita or not nome_paciente.strip():
        st.warning("Preencha ao menos **Data da visita** e **Nome do paciente**.")
    else:
        data_cadastro = date.today()
        programacao = calc_programacao(data_cadastro, data_visita)

        payload = {
            "data_cadastro": str(data_cadastro),
            "responsavel_agendamento_id": user["id"],
            "responsavel_agendamento_nome": user["username"],

            "data_visita": str(data_visita),
            "estudo_id": estudo["id"] if estudo and estudo.get("id") else None,
            "id_paciente": id_paciente.strip() if id_paciente else None,
            "nome_paciente": nome_paciente.strip(),
            "hora_consulta": str(hora_consulta) if hora_consulta else None,
            "horario_uber": str(horario_uber) if horario_uber else None,

            "reembolso_id": reembolso["id"] if reembolso and reembolso.get("id") else None,
            "visita_id": visita["id"] if visita and visita.get("id") else None,  # <== ALTERADO
            "tipo_visita_id": tipo_visita["id"] if tipo_visita and tipo_visita.get("id") else None,
            "medico_responsavel_id": medico_resp["id"] if medico_resp and medico_resp.get("id") else None,
            "consultorio_id": consultorio["id"] if consultorio and consultorio.get("id") else None,
            "obs_visita": obs_visita.strip() if obs_visita else None,
            "jejum_id": jejum["id"] if jejum and jejum.get("id") else None,
            "obs_coleta": obs_coleta.strip() if obs_coleta else None,

            "programacao": programacao,
        }

        resp = client.table("ag_agendamentos").insert(payload).execute()
        if resp.data:
            st.success("Agendamento cadastrado com sucesso.")
            st.rerun()
        else:
            st.error("Falha ao cadastrar. Verifique os campos obrigatórios.")

st.divider()

# ----------------- Listagem -----------------
st.subheader("Agendamentos cadastrados")

# ===== Filtros =====
opt_estudo = [{"id": None, "nome": "(todos)"}] + op_estudo_tbl

# Responsável (distinct)
resp_q = client.table("ag_agendamentos").select("responsavel_agendamento_id, responsavel_agendamento_nome").limit(5000)
resp_rows = resp_q.execute().data or []
df_resp = pd.DataFrame(resp_rows).drop_duplicates().sort_values("responsavel_agendamento_nome") if resp_rows else pd.DataFrame()

if not df_resp.empty:
    resp_opts = [{"id": None, "nome": "(todos)"}] + [
        {"id": int(r["responsavel_agendamento_id"]), "nome": r["responsavel_agendamento_nome"]}
        for _, r in df_resp.iterrows()
    ]
else:
    resp_opts = [{"id": None, "nome": "(todos)"}]

fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 2])
with fc1:
    est_sel = st.selectbox("Estudo", options=opt_estudo, format_func=lambda x: x["nome"], index=0, key="flt_estudo_list")
with fc2:
    dt_ini = st.date_input("Data visita (início)", key="flt_dt_ini_list")
with fc3:
    dt_fim = st.date_input("Data visita (fim)", key="flt_dt_fim_list")
with fc4:
    c4a, c4b = st.columns([1, 1])
    with c4a:
        resp_sel = st.selectbox("Responsável agendamento", options=resp_opts, format_func=lambda x: x["nome"], key="flt_resp_list")
    with c4b:
        nome_like = st.text_input("Nome do paciente (contém)", key="flt_nome_list")

# ===== Query com filtros =====
q = client.table("ag_agendamentos").select(
    "id, data_visita, data_cadastro, nome_paciente, id_paciente, estudo_id, "
    "hora_consulta, horario_uber, reembolso_id, "
    "visita_id, tipo_visita_id, medico_responsavel_id, consultorio_id, "  # <== ALTERADO: visita_id
    "obs_visita, jejum_id, obs_coleta, programacao, "
    "hora_chegada, hora_saida, responsavel_agendamento_nome, responsavel_agendamento_id"
)

if est_sel and est_sel["id"] is not None:
    q = q.eq("estudo_id", est_sel["id"])
if dt_ini:
    q = q.gte("data_visita", str(dt_ini))
if dt_fim:
    q = q.lte("data_visita", str(dt_fim))
if resp_sel and resp_sel["id"] is not None:
    q = q.eq("responsavel_agendamento_id", resp_sel["id"])
if nome_like:
    q = q.ilike("nome_paciente", f"%{nome_like}%")

rows = q.order("data_visita", desc=True).order("hora_consulta").limit(5000).execute().data or []
df = pd.DataFrame(rows)

# Mapeamentos de texto
map_reembolso   = _map_dict("Reembolso")
map_tipo        = _map_dict("Tipo_visita")
map_medico      = _map_dict("Medico_responsavel")
map_consultorio = _map_dict("Consultorio")
map_jejum       = _map_dict("Jejum")
map_visita      = _map_dict("Visita")  # <== NOVO

# ===== Resumo por data × consultório =====
st.markdown("### 📊 Resumo por data × consultório")
if df.empty:
    st.info("Sem registros para os filtros aplicados.")
else:
    df_resumo = df.copy()
    df_resumo["consultorio_txt"] = df_resumo["consultorio_id"].map(map_consultorio).fillna("(sem consultório)")
    df_resumo["data_visita"] = pd.to_datetime(df_resumo["data_visita"], errors="coerce").dt.date

    piv = pd.pivot_table(
        df_resumo,
        index="data_visita",
        columns="consultorio_txt",
        values="id",
        aggfunc="count",
        fill_value=0,
    ).sort_index()

    piv["Total"] = piv.sum(axis=1)
    cols = [c for c in piv.columns if c != "Total"] + ["Total"]
    piv = piv[cols]

    piv_out = piv.reset_index()
    piv_out["data_visita"] = pd.to_datetime(piv_out["data_visita"]).dt.strftime("%d/%m/%Y")

    st.dataframe(piv_out, use_container_width=True)

st.markdown("---")

# ===== Matriz principal - APENAS COLUNAS SOLICITADAS =====
st.markdown("### 📋 Detalhamento dos agendamentos")
if df.empty:
    st.info("Sem registros para os filtros aplicados.")
else:
    # Mapeamentos de texto
    df["Estudo"] = df["estudo_id"].map(map_estudo).fillna("(sem estudo)")
    df["Tipo de Visita"] = df["tipo_visita_id"].map(map_tipo).fillna("(não informado)")
    df["Médico"] = df["medico_responsavel_id"].map(map_medico).fillna("(não informado)")
    
    # Renomeia colunas diretas
    df["Responsável Agendamento"] = df["responsavel_agendamento_nome"]
    df["ID"] = df["id_paciente"]
    
    # Formata data da visita
    df["Data da Visita"] = pd.to_datetime(df["data_visita"], errors="coerce").dt.strftime("%d/%m/%Y")
    
    # Formata hora da consulta (apenas HH:MM)
    df["Hora da Visita"] = pd.to_datetime(df["hora_consulta"], errors="coerce").dt.strftime("%H:%M")

    # Define as colunas a serem exibidas na ordem solicitada
    cols_show = [
        "Responsável Agendamento",
        "Estudo",
        "ID",
        "Data da Visita",
        "Hora da Visita",
        "Tipo de Visita",
        "Médico"
    ]
    
    # Exibe apenas as colunas solicitadas
    st.dataframe(df[cols_show], use_container_width=True, hide_index=True)