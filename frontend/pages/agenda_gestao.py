# ============================================================
# 🧭 frontend/pages/agenda_gestao.py
# Gestão de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from frontend.supabase_client import get_supabase_client, supabase_execute, registrar_log_agendamento
from frontend.components.feedback import feedback


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def parse_ts_utc(val):
    """Converte qualquer string para Timestamp com tz=UTC ou None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    ts = pd.to_datetime(val, errors="coerce", utc=True)
    if pd.isna(ts):
        return None
    return ts


def ensure_utc(ts):
    """Garante tz=UTC (tz-aware)."""
    if ts is None:
        return None
    if not isinstance(ts, pd.Timestamp):
        ts = pd.to_datetime(ts, errors="coerce")
    if ts is None or pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def parse_variaveis(valor_str: str) -> list:
    """Parse de valores a partir de uma string - removendo aspas e normalizando."""
    if not valor_str:
        return []

    valor_str = valor_str.strip('"').strip("'")

    if ";" in valor_str:
        valores = [v.strip() for v in valor_str.split(";") if v.strip()]
    elif "\n" in valor_str:
        valores = [v.strip() for v in valor_str.split("\n") if v.strip()]
    elif "," in valor_str:
        valores = [v.strip() for v in valor_str.split(",") if v.strip()]
    else:
        valores = [valor_str.strip()]

    return valores


# ============================================================
# CONSTANTES
# ============================================================
ETAPAS_TEMPO = [
    "status_medico",
    "status_enfermagem",
    "status_espirometria",
    "status_farmacia",
    "status_nutricionista",
    "status_coordenacao",
]

ETAPAS_NOMES = {
    "status_medico": "Médico",
    "status_enfermagem": "Enfermagem",
    "status_espirometria": "Espirometria",
    "status_farmacia": "Farmácia",
    "status_nutricionista": "Nutricionista",
    "status_coordenacao": "Coordenação",
}


# ============================================================
# CACHED DATA FETCHING — evita reconexões em reruns de filtro
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_usuario_id(_supabase, usuario_logado: str):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuarios")
        .select("id_usuario")
        .eq("nm_usuario", usuario_logado.lower().strip())
        .execute()
    )
    return resp.data[0]["id_usuario"] if resp.data else None


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_coordenacoes(_supabase, usuario_id):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_vinculo")
        .select("vinculo")
        .eq("id_usuario", usuario_id)
        .eq("tipo", "coordenacao")
        .eq("sn_ativo", True)
        .execute()
    )
    return [c["vinculo"] for c in resp.data] if resp.data else []


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_variaveis(_supabase):
    usos = [
        "status_medico", "status_enfermagem", "status_farmacia",
        "status_espirometria", "status_nutricionista", "status_coordenacao",
        "desfecho_atendimento",
    ]
    result = {}
    for uso in usos:
        resp = supabase_execute(
            lambda uso=uso: _supabase.table("tab_app_variaveis")
            .select("valor")
            .eq("uso", uso)
            .execute()
        )
        result[uso] = parse_variaveis(resp.data[0]["valor"]) if resp.data else []
    return result


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_estudos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("id_estudo, estudo, coordenacao")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
        df = df.drop_duplicates(subset=["id_estudo"], keep="first")
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_agendamentos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_agendamentos")
        .select("*")
        .order("data_visita", desc=False)
        .limit(5000)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_logs_etapas(_supabase, ag_ids: tuple):
    if not ag_ids:
        return []
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_log_etapas")
        .select("agendamento_id, nome_etapa, status_etapa, data_hora_etapa")
        .in_("agendamento_id", list(ag_ids))
        .execute()
    )
    return resp.data if resp.data else []


def _invalidar_cache_agendamentos():
    """Limpa o cache das queries de agendamentos após uma gravação."""
    _fetch_agendamentos.clear()
    _fetch_logs_etapas.clear()


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================
def page_agenda_gestao():
    """Página de gestão de agendamentos."""
    st.title("🧭 Gestão de Agendamentos")

    # ✅ Mostra confirmação de gravação após rerun
    if st.session_state.get("_agenda_gestao_save_ok"):
        ag_id = st.session_state.get("_agenda_gestao_save_agendamento_id")
        when = st.session_state.get("_agenda_gestao_save_when")

        try:
            st.toast(f"✅ Alterações gravadas com sucesso (Agendamento {ag_id})", icon="✅")
        except Exception:
            st.success(f"✅ Alterações gravadas com sucesso (Agendamento {ag_id})")

        if when:
            st.caption(f"Última gravação: {when}")

        st.session_state.pop("_agenda_gestao_save_ok", None)
        st.session_state.pop("_agenda_gestao_save_agendamento_id", None)
        st.session_state.pop("_agenda_gestao_save_when", None)

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # ✅ BUSCAR ID DO USUÁRIO (cacheado 5 min)
        usuario_id = _fetch_usuario_id(supabase, usuario_logado)
        if not usuario_id:
            st.error("❌ Usuário não encontrado no sistema")
            st.stop()

        # ✅ BUSCAR COORDENAÇÕES (cacheado 5 min)
        coordenacoes_usuario = _fetch_coordenacoes(supabase, usuario_id)
        if not coordenacoes_usuario:
            st.warning("⚠️ Você não está vinculado a nenhuma coordenação. Solicite à gerência.")
            st.stop()

        st.caption(f"👤 Coordenações: {', '.join(coordenacoes_usuario)}")

        # ✅ BUSCAR VARIÁVEIS (cacheado 10 min)
        variaveis = _fetch_variaveis(supabase)
        status_medico_list = variaveis["status_medico"]
        status_enfermagem_list = variaveis["status_enfermagem"]
        status_farmacia_list = variaveis["status_farmacia"]
        status_espirometria_list = variaveis["status_espirometria"]
        status_nutricionista_list = variaveis["status_nutricionista"]
        status_coordenacao_list = variaveis["status_coordenacao"]
        desfecho_list = variaveis["desfecho_atendimento"]

        # ✅ BUSCAR ESTUDOS (cacheado 2 min)
        df_estudos = _fetch_estudos(supabase)

        # ✅ BUSCAR AGENDAMENTOS (cacheado 1 min)
        df_agendamentos = _fetch_agendamentos(supabase)

        if df_agendamentos.empty:
            st.warning("Nenhum agendamento encontrado.")
            st.stop()

        # Merge com estudos
        if not df_estudos.empty and "estudo_id" in df_agendamentos.columns:
            df_agendamentos = df_agendamentos.merge(
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est"),
            ).rename(columns={"estudo": "nm_estudo"})
            df_agendamentos.columns = [c.lower() for c in df_agendamentos.columns]

        # Converte datas
        df_agendamentos["data_visita_dt"] = pd.to_datetime(df_agendamentos.get("data_visita"), errors="coerce")
        df_agendamentos["data_visita_br"] = df_agendamentos["data_visita_dt"].dt.strftime("%d/%m/%Y")

        # =====================================================
        # FILTRAR POR COORDENAÇÃO DO USUÁRIO
        # =====================================================
        if "coordenacao" in df_agendamentos.columns:
            df_view = df_agendamentos[df_agendamentos["coordenacao"].isin(coordenacoes_usuario)].copy()
        else:
            df_view = df_agendamentos.copy()

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        fc1, fc2, fc3 = st.columns(3)

        with fc1:
            estudos_vinculados = sorted([x for x in df_view.get("nm_estudo", pd.Series(dtype=str)).unique() if x])
            estudo_sel = st.selectbox("Estudo", ["(Todos)"] + estudos_vinculados, index=0)

        with fc2:
            status_unicos = sorted([x for x in df_view.get("status_confirmacao", pd.Series(dtype=str)).dropna().unique() if x])
            status_sel = st.selectbox("Status Confirmação", ["(Todos)"] + status_unicos, index=0)

        with fc3:
            dt_sel = st.date_input("Data", format="DD/MM/YYYY")

        # Aplicar filtros
        if estudo_sel != "(Todos)" and "nm_estudo" in df_view.columns:
            df_view = df_view[df_view["nm_estudo"] == estudo_sel]

        if status_sel != "(Todos)" and "status_confirmacao" in df_view.columns:
            df_view = df_view[df_view["status_confirmacao"] == status_sel]

        if dt_sel:
            df_view = df_view[df_view["data_visita_dt"].dt.date == dt_sel]

        if df_view.empty:
            st.warning("⚠️ Nenhum agendamento encontrado para sua coordenação com os filtros aplicados.")
            # Limpa seleção caso o agendamento selecionado saia do filtro
            st.session_state.pop("_agenda_selected_id", None)
            st.stop()

        st.success(f"✅ {len(df_view)} agendamento(s) encontrado(s)")

        # =====================================================
        # BUSCAR LOGS E PROCESSAR ÚLTIMO STATUS (cacheado)
        # =====================================================
        ag_ids = tuple(df_view["id"].tolist())
        logs_all = _fetch_logs_etapas(supabase, ag_ids)
        df_logs = pd.DataFrame(logs_all)

        if not df_logs.empty:
            df_logs.columns = [c.lower() for c in df_logs.columns]
            df_logs["ts"] = df_logs["data_hora_etapa"].apply(parse_ts_utc)
            df_logs = df_logs.dropna(subset=["ts"])

            if not df_logs.empty:
                df_logs_sorted = df_logs.sort_values(["agendamento_id", "nome_etapa", "ts"])

                last_status = (
                    df_logs_sorted.groupby(["agendamento_id", "nome_etapa"])["status_etapa"]
                    .last()
                    .reset_index()
                    .rename(columns={"status_etapa": "ultimo_status"})
                )

                pivot_last = (
                    last_status.pivot_table(
                        index="agendamento_id",
                        columns="nome_etapa",
                        values="ultimo_status",
                        aggfunc="last",
                    )
                    .reindex(columns=ETAPAS_TEMPO)
                    .reset_index()
                )

                for etapa in ETAPAS_TEMPO:
                    if etapa in pivot_last.columns:
                        pivot_last.rename(columns={etapa: ETAPAS_NOMES[etapa]}, inplace=True)

                df_view = df_view.merge(pivot_last, left_on="id", right_on="agendamento_id", how="left")
                if "agendamento_id" in df_view.columns:
                    df_view = df_view.drop(columns=["agendamento_id"])

        for etapa in ETAPAS_TEMPO:
            col_name = ETAPAS_NOMES[etapa]
            if col_name not in df_view.columns:
                df_view[col_name] = None

        # =====================================================
        # TABELA COM AGGRID PARA SELEÇÃO
        # =====================================================
        st.markdown("---")
        st.markdown("### 📋 Clique na linha para atualizar status dos departamentos")
        st.caption("**Legenda de Cores (linha inteira):** 🟢 Finalizado (verde) | 🔵 Reagendado (azul) | 🟡 Faltou - Remarcado (amarelo) | 🟠 Faltou - Recrutamento (laranja) | 🔴 Não compareceu (vermelho claro) | 🔴 Não realizado (vermelho médio)")
        st.caption(f"**Total:** {len(df_view)} agendamentos")

        cols_display = [
            "id", "data_visita_br", "hora_consulta", "nm_estudo", "id_paciente", "nome_paciente",
            "hora_chegada", "tipo_visita", "visita", "medico_responsavel", "status_confirmacao",
            "valor_financeiro", "desfecho_atendimento",
            "Médico", "Enfermagem", "Espirometria", "Farmácia", "Nutricionista", "Coordenação"
        ]

        cols_rename = {
            "id": "ID",
            "data_visita_br": "Data",
            "hora_consulta": "Hora Consulta",
            "nm_estudo": "Estudo",
            "id_paciente": "ID Paciente",
            "nome_paciente": "Paciente",
            "hora_chegada": "Hora Chegada",
            "tipo_visita": "Tipo Visita",
            "visita": "Visita",
            "medico_responsavel": "Médico Resp.",
            "status_confirmacao": "Status",
            "valor_financeiro": "Valor Reembolso",
            "desfecho_atendimento": "Desfecho",
        }
        cols_existentes = [col for col in cols_display if col in df_view.columns]
        if not cols_existentes:
            cols_existentes = [c for c in df_view.columns if c not in ("data_visita_dt", "data_visita")]
            cols_rename = {}
        df_grid = df_view[cols_existentes].copy()
        if "hora_consulta" in df_grid.columns:
            df_grid = df_grid.sort_values("hora_consulta", ascending=True, na_position="last")
        df_grid.rename(columns=cols_rename, inplace=True)

        # =====================================================
        # CONFIGURAR AGGRID
        # =====================================================
        gb = GridOptionsBuilder.from_dataframe(df_grid)
        gb.configure_selection(selection_mode="single", use_checkbox=False)

        if "ID" in df_grid.columns:
            gb.configure_column("ID", width=50)
        if "Data" in df_grid.columns:
            gb.configure_column("Data", width=80)
        if "Hora Consulta" in df_grid.columns:
            gb.configure_column("Hora Consulta", width=100)
        if "Estudo" in df_grid.columns:
            gb.configure_column("Estudo", width=120)
        if "ID Paciente" in df_grid.columns:
            gb.configure_column("ID Paciente", width=90)
        if "Paciente" in df_grid.columns:
            gb.configure_column("Paciente", width=150)
        if "Hora Chegada" in df_grid.columns:
            gb.configure_column("Hora Chegada", width=100)
        if "Tipo Visita" in df_grid.columns:
            gb.configure_column("Tipo Visita", width=90)
        if "Visita" in df_grid.columns:
            gb.configure_column("Visita", width=80)
        if "Médico Resp." in df_grid.columns:
            gb.configure_column("Médico Resp.", width=130)
        if "Status" in df_grid.columns:
            gb.configure_column("Status", width=150)
        if "Valor Reembolso" in df_grid.columns:
            gb.configure_column("Valor Reembolso", width=120)

        row_style_jscode = JsCode("""
function(params) {
    if (!params.data || !params.data.Desfecho) {
        return null;
    }
    var desfecho = params.data.Desfecho.toString().trim();
    if (desfecho === 'Finalizado') {
        return {'backgroundColor': '#D4EDDA', 'color': '#155724'};
    }
    if (desfecho === 'Reagendado') {
        return {'backgroundColor': '#D1ECF1', 'color': '#0C5460'};
    }
    if (desfecho === 'Não compareceu') {
        return {'backgroundColor': '#FFE5E5', 'color': '#8B0000'};
    }
    if (desfecho === 'Faltou - Remarcado') {
        return {'backgroundColor': '#FFF8DC', 'color': '#856404'};
    }
    if (desfecho === 'Não realizado') {
        return {'backgroundColor': '#FFCCCB', 'color': '#A52A2A'};
    }
    if (desfecho === 'Faltou - Recrutamento') {
        return {'backgroundColor': '#FFE4B5', 'color': '#D2691E'};
    }
    return null;
}
""")
        gb.configure_grid_options(getRowStyle=row_style_jscode)

        if "Desfecho" in df_grid.columns:
            gb.configure_column("Desfecho", width=150)
        if "Médico" in df_grid.columns:
            gb.configure_column("Médico", width=110)
        if "Enfermagem" in df_grid.columns:
            gb.configure_column("Enfermagem", width=110)
        if "Espirometria" in df_grid.columns:
            gb.configure_column("Espirometria", width=110)
        if "Farmácia" in df_grid.columns:
            gb.configure_column("Farmácia", width=110)
        if "Nutricionista" in df_grid.columns:
            gb.configure_column("Nutricionista", width=110)
        if "Coordenação" in df_grid.columns:
            gb.configure_column("Coordenação", width=110)

        grid_options = gb.build()

        if df_grid.shape[1] == 0:
            st.warning("⚠️ Não foi possível preparar as colunas para exibição.")
            st.stop()

        grid_response = AgGrid(
            df_grid,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=False,
            height=400,
            theme="streamlit",
            allow_unsafe_jscode=True,
        )

        # =====================================================
        # PERSISTÊNCIA DA SELEÇÃO NO SESSION STATE
        # Evita que o formulário desapareça ao mudar filtros
        # =====================================================
        selected_rows = grid_response["selected_rows"]
        if selected_rows is not None and len(selected_rows) > 0:
            st.session_state["_agenda_selected_id"] = int(selected_rows.iloc[0]["ID"])

        selected_ag_id = st.session_state.get("_agenda_selected_id")

        # Valida que o agendamento selecionado ainda está na view atual
        if selected_ag_id is not None and selected_ag_id not in df_view["id"].values:
            selected_ag_id = None
            st.session_state.pop("_agenda_selected_id", None)

        # =====================================================
        # BLOCO DE ATUALIZAÇÃO DE STATUS
        # =====================================================
        if selected_ag_id is not None:
            agendamento_data = df_view[df_view["id"] == selected_ag_id].iloc[0]
            agendamento_id = selected_ag_id

            st.markdown("---")

            col_titulo, col_limpar = st.columns([5, 1])
            with col_titulo:
                st.markdown("### ✏️ Atualizar Status dos Departamentos")
            with col_limpar:
                if st.button("✖ Limpar seleção", use_container_width=True):
                    st.session_state.pop("_agenda_selected_id", None)
                    st.rerun()

            # Detalhes do agendamento selecionado
            st.markdown("#### 📌 Detalhes do Agendamento Selecionado")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.info(f"**Paciente:** {agendamento_data.get('nome_paciente', '—')}")
                st.info(f"**ID Paciente:** {agendamento_data.get('id_paciente', '—')}")
                st.info(f"**Status:** {agendamento_data.get('status_confirmacao', '—')}")

            with col2:
                st.info(f"**Data:** {agendamento_data.get('data_visita_br', '—')}")
                st.info(f"**Hora Consulta:** {agendamento_data.get('hora_consulta', '—')}")
                st.info(f"**Estudo:** {agendamento_data.get('nm_estudo', '—')}")
                st.info(f"**Tipo Visita:** {agendamento_data.get('tipo_visita', '—')}")

            with col3:
                st.info(f"**Médico:** {agendamento_data.get('medico_responsavel', '—')}")
                st.info(f"**Consultório:** {agendamento_data.get('consultorio', '—')}")

            st.markdown("#### 📝 Observações")

            col_obs1, col_obs2 = st.columns(2)

            with col_obs1:
                obs_visita = agendamento_data.get("obs_visita") or "—"
                st.info(f"**Obs. Visita:**\n{obs_visita}")

            with col_obs2:
                obs_coleta = agendamento_data.get("obs_coleta") or "—"
                st.info(f"**Obs. Coleta:**\n{obs_coleta}")

            st.markdown("---")

            # Valores atuais
            status_medico_atual = agendamento_data.get("status_medico") or ""
            status_enfermagem_atual = agendamento_data.get("status_enfermagem") or ""
            status_farmacia_atual = agendamento_data.get("status_farmacia") or ""
            status_espirometria_atual = agendamento_data.get("status_espirometria") or ""
            status_nutricionista_atual = agendamento_data.get("status_nutricionista") or ""
            status_coordenacao_atual = agendamento_data.get("status_coordenacao") or ""
            hora_chegada_atual = agendamento_data.get("hora_chegada") or ""
            hora_saida_atual = agendamento_data.get("hora_saida") or ""
            desfecho_atual = agendamento_data.get("desfecho_atendimento") or ""
            valor_uber_atual = agendamento_data.get("valor_uber") or ""
            valor_financeiro_atual = agendamento_data.get("valor_financeiro") or ""

            with st.form(f"form_status_{agendamento_id}"):
                st.markdown("#### 🏥 Status dos Departamentos")

                c0, c1, c2 = st.columns(3)

                with c0:
                    hora_chegada = st.time_input(
                        "🕘 Hora Chegada",
                        value=pd.to_datetime(hora_chegada_atual, errors="coerce").time() if hora_chegada_atual else None,
                        key=f"hora_chegada_{agendamento_id}",
                    )

                with c1:
                    valor_uber = st.text_input(
                        "🚗 Valor Uber",
                        value=valor_uber_atual,
                        placeholder="ex: R$ 25,00",
                        key=f"valor_uber_{agendamento_id}",
                    )

                with c2:
                    valor_financeiro = st.text_input(
                        "💵 Valor Reembolso",
                        value=str(valor_financeiro_atual) if valor_financeiro_atual else "",
                        placeholder="ex: 150.00",
                        key=f"valor_financeiro_{agendamento_id}",
                    )

                colA, colB, colC = st.columns(3)

                with colA:
                    idx_medico = status_medico_list.index(status_medico_atual) + 1 if status_medico_atual in status_medico_list else 0
                    status_medico = st.selectbox(
                        "🩺 Médico",
                        [""] + status_medico_list,
                        index=idx_medico,
                        key=f"status_medico_{agendamento_id}",
                    )

                    idx_enfermagem = status_enfermagem_list.index(status_enfermagem_atual) + 1 if status_enfermagem_atual in status_enfermagem_list else 0
                    status_enfermagem = st.selectbox(
                        "👩‍⚕️ Enfermagem",
                        [""] + status_enfermagem_list,
                        index=idx_enfermagem,
                        key=f"status_enfermagem_{agendamento_id}",
                    )

                with colB:
                    idx_espirometria = status_espirometria_list.index(status_espirometria_atual) + 1 if status_espirometria_atual in status_espirometria_list else 0
                    status_espirometria = st.selectbox(
                        "🫁 Espirometria",
                        [""] + status_espirometria_list,
                        index=idx_espirometria,
                        key=f"status_espirometria_{agendamento_id}",
                    )

                    idx_nutricionista = status_nutricionista_list.index(status_nutricionista_atual) + 1 if status_nutricionista_atual in status_nutricionista_list else 0
                    status_nutricionista = st.selectbox(
                        "🥗 Nutricionista",
                        [""] + status_nutricionista_list,
                        index=idx_nutricionista,
                        key=f"status_nutricionista_{agendamento_id}",
                    )

                with colC:
                    idx_farmacia = status_farmacia_list.index(status_farmacia_atual) + 1 if status_farmacia_atual in status_farmacia_list else 0
                    status_farmacia = st.selectbox(
                        "💊 Farmácia",
                        [""] + status_farmacia_list,
                        index=idx_farmacia,
                        key=f"status_farmacia_{agendamento_id}",
                    )

                    idx_coordenacao = status_coordenacao_list.index(status_coordenacao_atual) + 1 if status_coordenacao_atual in status_coordenacao_list else 0
                    status_coordenacao = st.selectbox(
                        "🧭 Coordenação",
                        [""] + status_coordenacao_list,
                        index=idx_coordenacao,
                        key=f"status_coordenacao_{agendamento_id}",
                    )

                st.markdown("#### ⏱️ Saída e Desfecho")

                col4, col5 = st.columns(2)

                with col4:
                    hora_saida = st.time_input(
                        "⏰ Hora de Saída",
                        value=pd.to_datetime(hora_saida_atual, errors="coerce").time() if hora_saida_atual else None,
                        key=f"hora_saida_{agendamento_id}",
                    )

                with col5:
                    idx_desfecho = desfecho_list.index(desfecho_atual) + 1 if desfecho_atual in desfecho_list else 0
                    desfecho = st.selectbox(
                        "📋 Desfecho do Atendimento",
                        [""] + desfecho_list,
                        index=idx_desfecho,
                        key=f"desfecho_{agendamento_id}",
                        help="Ao preencher o desfecho, etapas vazias serão automaticamente marcadas como N/A"
                    )

                if not desfecho_atual:
                    st.info("ℹ️ **Atenção:** Ao preencher o Desfecho do Atendimento, todas as etapas (Médico, Enfermagem, Espirometria, Farmácia, Nutricionista, Coordenação) que estiverem vazias serão automaticamente marcadas como **N/A**.")

                st.markdown("---")

                if st.form_submit_button("💾 Atualizar Status", use_container_width=True):
                    payload = {}
                    logs_para_inserir = []

                    timestamp_agora = datetime.now(timezone.utc).isoformat()

                    if hora_chegada:
                        novo_hora_chegada = hora_chegada.isoformat()
                        if novo_hora_chegada != (hora_chegada_atual or ""):
                            payload["hora_chegada"] = novo_hora_chegada
                    else:
                        if hora_chegada_atual:
                            payload["hora_chegada"] = None

                    if status_medico and status_medico_atual != status_medico:
                        payload["status_medico"] = status_medico
                        logs_para_inserir.append({
                            "agendamento_id": agendamento_id,
                            "nome_etapa": "status_medico",
                            "status_etapa": status_medico,
                            "data_hora_etapa": timestamp_agora,
                            "usuario_id": usuario_id,
                            "usuario_nome": usuario_logado,
                        })

                    if status_enfermagem and status_enfermagem_atual != status_enfermagem:
                        payload["status_enfermagem"] = status_enfermagem
                        logs_para_inserir.append({
                            "agendamento_id": agendamento_id,
                            "nome_etapa": "status_enfermagem",
                            "status_etapa": status_enfermagem,
                            "data_hora_etapa": timestamp_agora,
                            "usuario_id": usuario_id,
                            "usuario_nome": usuario_logado,
                        })

                    if status_farmacia and status_farmacia_atual != status_farmacia:
                        payload["status_farmacia"] = status_farmacia
                        logs_para_inserir.append({
                            "agendamento_id": agendamento_id,
                            "nome_etapa": "status_farmacia",
                            "status_etapa": status_farmacia,
                            "data_hora_etapa": timestamp_agora,
                            "usuario_id": usuario_id,
                            "usuario_nome": usuario_logado,
                        })

                    if status_espirometria and status_espirometria_atual != status_espirometria:
                        payload["status_espirometria"] = status_espirometria
                        logs_para_inserir.append({
                            "agendamento_id": agendamento_id,
                            "nome_etapa": "status_espirometria",
                            "status_etapa": status_espirometria,
                            "data_hora_etapa": timestamp_agora,
                            "usuario_id": usuario_id,
                            "usuario_nome": usuario_logado,
                        })

                    if status_nutricionista and status_nutricionista_atual != status_nutricionista:
                        payload["status_nutricionista"] = status_nutricionista
                        logs_para_inserir.append({
                            "agendamento_id": agendamento_id,
                            "nome_etapa": "status_nutricionista",
                            "status_etapa": status_nutricionista,
                            "data_hora_etapa": timestamp_agora,
                            "usuario_id": usuario_id,
                            "usuario_nome": usuario_logado,
                        })

                    if status_coordenacao and status_coordenacao_atual != status_coordenacao:
                        payload["status_coordenacao"] = status_coordenacao
                        logs_para_inserir.append({
                            "agendamento_id": agendamento_id,
                            "nome_etapa": "status_coordenacao",
                            "status_etapa": status_coordenacao,
                            "data_hora_etapa": timestamp_agora,
                            "usuario_id": usuario_id,
                            "usuario_nome": usuario_logado,
                        })

                    if hora_saida:
                        payload["hora_saida"] = hora_saida.isoformat()
                    else:
                        if hora_saida_atual:
                            payload["hora_saida"] = None

                    if desfecho:
                        payload["desfecho_atendimento"] = desfecho

                        if desfecho and not desfecho_atual:
                            etapas_verificar = [
                                ("status_medico", status_medico_atual, status_medico),
                                ("status_enfermagem", status_enfermagem_atual, status_enfermagem),
                                ("status_espirometria", status_espirometria_atual, status_espirometria),
                                ("status_farmacia", status_farmacia_atual, status_farmacia),
                                ("status_nutricionista", status_nutricionista_atual, status_nutricionista),
                                ("status_coordenacao", status_coordenacao_atual, status_coordenacao),
                            ]

                            for nome_campo, valor_atual, valor_selecionado in etapas_verificar:
                                if not valor_atual and not valor_selecionado:
                                    payload[nome_campo] = "N/A"
                                    logs_para_inserir.append({
                                        "agendamento_id": agendamento_id,
                                        "nome_etapa": nome_campo,
                                        "status_etapa": "N/A",
                                        "data_hora_etapa": timestamp_agora,
                                    })

                    if valor_uber != valor_uber_atual:
                        payload["valor_uber"] = valor_uber if valor_uber else None

                    valor_financeiro_str = str(valor_financeiro_atual) if valor_financeiro_atual else ""
                    if valor_financeiro != valor_financeiro_str:
                        payload["valor_financeiro"] = float(valor_financeiro.replace(",", ".")) if valor_financeiro else None

                    valores_anteriores_gestao = {
                        "hora_chegada": hora_chegada_atual,
                        "hora_saida": hora_saida_atual,
                        "desfecho_atendimento": desfecho_atual,
                        "valor_uber": valor_uber_atual,
                        "valor_financeiro": valor_financeiro_atual,
                        "status_medico": status_medico_atual,
                        "status_enfermagem": status_enfermagem_atual,
                        "status_farmacia": status_farmacia_atual,
                        "status_espirometria": status_espirometria_atual,
                        "status_nutricionista": status_nutricionista_atual,
                        "status_coordenacao": status_coordenacao_atual,
                    }

                    if payload:
                        try:
                            etapas_auto_preenchidas = []
                            if desfecho and not desfecho_atual:
                                for key in payload:
                                    if key.startswith("status_") and payload[key] == "N/A":
                                        etapas_auto_preenchidas.append(key.replace("status_", "").title())

                            supabase_execute(
                                lambda: supabase.table("tab_app_agendamentos")
                                .update(payload)
                                .eq("id", agendamento_id)
                                .execute()
                            )

                            for campo, novo_valor in payload.items():
                                registrar_log_agendamento(
                                    supabase, agendamento_id, usuario_id, usuario_logado,
                                    campo, valores_anteriores_gestao.get(campo), novo_valor
                                )

                            for log in logs_para_inserir:
                                supabase_execute(
                                    lambda log=log: supabase.table("tab_app_log_etapas").insert(log).execute()
                                )

                            # Invalida cache para refletir os dados atualizados
                            _invalidar_cache_agendamentos()

                            st.session_state["_agenda_gestao_save_ok"] = True
                            st.session_state["_agenda_gestao_save_agendamento_id"] = agendamento_id
                            st.session_state["_agenda_gestao_save_when"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                            mensagem_sucesso = "✅ Status atualizado e logs registrados com sucesso!"
                            if etapas_auto_preenchidas:
                                etapas_str = ", ".join(etapas_auto_preenchidas)
                                mensagem_sucesso += f"\n\n🔄 Etapas marcadas automaticamente como N/A: {etapas_str}"

                            feedback(mensagem_sucesso, "success", "💾")
                            st.rerun()

                        except Exception as e:
                            feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")
                    else:
                        st.warning("⚠️ Nenhuma alteração detectada")

            # =====================================================
            # HISTÓRICO DE ETAPAS
            # =====================================================
            st.markdown("---")
            st.markdown("### 📜 Histórico de Etapas")

            resp_logs_detalhe = supabase_execute(
                lambda: supabase.table("tab_app_log_etapas")
                .select("*")
                .eq("agendamento_id", agendamento_id)
                .order("data_hora_etapa", desc=True)
                .execute()
            )
            df_logs_detalhe = pd.DataFrame(resp_logs_detalhe.data) if resp_logs_detalhe.data else pd.DataFrame()

            if not df_logs_detalhe.empty:
                df_logs_detalhe.columns = [c.lower() for c in df_logs_detalhe.columns]
                df_logs_detalhe["data_hora_etapa"] = pd.to_datetime(
                    df_logs_detalhe["data_hora_etapa"], errors="coerce"
                ).dt.strftime("%d/%m/%Y %H:%M:%S")

                df_logs_display = df_logs_detalhe[["nome_etapa", "status_etapa", "data_hora_etapa", "usuario_nome"]].copy()
                df_logs_display.columns = ["Etapa", "Status", "Data/Hora", "Usuário"]

                st.dataframe(df_logs_display, use_container_width=True, hide_index=True)
            else:
                st.info("Nenhum log de etapas registrado ainda.")

        else:
            st.info("👆 Selecione um agendamento na tabela acima para atualizar os status dos departamentos")

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")
        import traceback
        st.code(traceback.format_exc())


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_agenda_gestao()
