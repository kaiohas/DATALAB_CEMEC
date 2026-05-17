# ============================================================
# 📊 frontend/pages/agenda_relatorio.py
# Relatório e Estatísticas de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta, datetime, timezone
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


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


def hhmm_from_seconds(total_seconds: float) -> str:
    """Converte segundos para formato HH:MM."""
    if pd.isna(total_seconds) or total_seconds is None:
        return "00:00"
    total_seconds = int(total_seconds)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


# ============================================================
# CACHED DATA FETCHING — evita reconexões em reruns de filtro
# ============================================================

@st.cache_data(ttl=120, show_spinner=False)
def _fetch_estudos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("id_estudo, estudo, disciplina, coordenacao")
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
        lambda: _supabase.table("tab_app_agendamentos").select("*").limit(5000).execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_logs(_supabase, ag_ids: tuple):
    if not ag_ids:
        return []
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_log_etapas")
        .select("agendamento_id, nome_etapa, status_etapa, data_hora_etapa")
        .in_("agendamento_id", list(ag_ids))
        .execute()
    )
    return resp.data if resp.data else []


def page_agenda_relatorio():
    """Página de relatórios e estatísticas."""
    st.title("📊 Relatório de Agendamentos")

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # ✅ BUSCAR DADOS (cacheados)
        df_estudos = _fetch_estudos(supabase)
        df_agendamentos = _fetch_agendamentos(supabase)

        if df_agendamentos.empty:
            st.warning("Nenhum agendamento encontrado.")
            st.stop()

        if not df_estudos.empty:
            df_agendamentos = df_agendamentos.merge(
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est"),
            ).rename(columns={"estudo": "nm_estudo"})

        df_agendamentos["data_visita_dt"] = pd.to_datetime(df_agendamentos["data_visita"], errors="coerce")
        df_agendamentos["data_cadastro_dt"] = pd.to_datetime(df_agendamentos["data_cadastro"], errors="coerce")

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)

        with fc1:
            estudos_unicos = sorted([x for x in df_estudos["estudo"].dropna().unique() if x])
            estudo_sel = st.selectbox("Estudo", ["(Todos)"] + estudos_unicos, index=0)

        with fc2:
            if estudo_sel != "(Todos)":
                disciplinas_estudo = sorted(
                    [x for x in df_estudos[df_estudos["estudo"] == estudo_sel]["disciplina"].dropna().unique() if x]
                )
            else:
                disciplinas_estudo = sorted([x for x in df_estudos["disciplina"].dropna().unique() if x])

            disciplina_sel = st.selectbox("Disciplina", ["(Todas)"] + disciplinas_estudo, index=0)

        with fc3:
            status_unicos = sorted([x for x in df_agendamentos["status_confirmacao"].dropna().unique() if x])
            status_sel = st.selectbox("Status Confirmação", ["(Todos)"] + status_unicos, index=0)

        with fc4:
            coordenacoes_unicas = sorted([x for x in df_agendamentos["coordenacao"].dropna().unique() if x])
            coordenacao_sel = st.selectbox("Coordenação", ["(Todas)"] + coordenacoes_unicas, index=0)

        with fc5:
            dt_ini = st.date_input("Data (Início)", value=date.today() - timedelta(days=30))

        with fc6:
            dt_fim = st.date_input("Data (Fim)", value=date.today())

        # =====================================================
        # APLICAR FILTROS
        # =====================================================
        df_view = df_agendamentos.copy()

        if estudo_sel != "(Todos)":
            df_view = df_view[df_view["nm_estudo"] == estudo_sel]

        if disciplina_sel != "(Todas)":
            df_view = df_view[df_view["disciplina"] == disciplina_sel]

        if status_sel != "(Todos)":
            df_view = df_view[df_view["status_confirmacao"] == status_sel]

        if coordenacao_sel != "(Todas)":
            df_view = df_view[df_view["coordenacao"] == coordenacao_sel]

        if dt_ini and dt_fim:
            df_view = df_view[
                (df_view["data_visita_dt"] >= pd.to_datetime(dt_ini)) &
                (df_view["data_visita_dt"] <= pd.to_datetime(dt_fim))
            ]

        if df_view.empty:
            st.info("Nenhum agendamento encontrado com os filtros aplicados.")
            st.stop()

        # =====================================================
        # MÉTRICAS PRINCIPAIS
        # =====================================================
        st.markdown("---")
        st.markdown("### 📈 Métricas Principais")

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            total_agendamentos = len(df_view)
            st.metric("Total de Agendamentos", total_agendamentos)

        with col2:
            agendamentos_confirmados = len(df_view[df_view["status_confirmacao"] == "Confirmado"])
            st.metric("Confirmados", agendamentos_confirmados)

        with col3:
            agendamentos_pendentes = len(df_view[df_view["status_confirmacao"].isnull() | (df_view["status_confirmacao"] == "")])
            st.metric("Pendentes", agendamentos_pendentes)

        with col4:
            agendamentos_reagendados = len(df_view[df_view["status_confirmacao"] == "Reagendado"])
            st.metric("Reagendados", agendamentos_reagendados)

        with col5:
            taxa_confirmacao = (agendamentos_confirmados / total_agendamentos * 100) if total_agendamentos > 0 else 0
            st.metric("Taxa de Confirmação", f"{taxa_confirmacao:.1f}%")

        # =====================================================
        # GRÁFICOS
        # =====================================================
        st.markdown("---")
        st.markdown("### 📊 Visualizações")

        col1, col2 = st.columns(2)

        with col1:
            if not df_view.empty:
                df_status = df_view["status_confirmacao"].fillna("Sem Status").value_counts().reset_index()
                df_status.columns = ["Status", "Quantidade"]

                fig_status = px.bar(
                    df_status, x="Status", y="Quantidade",
                    title="Agendamentos por Status de Confirmação",
                    color="Status", text="Quantidade",
                )
                fig_status.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("Sem dados para exibir")

        with col2:
            if not df_view.empty:
                df_estudo = df_view["nm_estudo"].fillna("Sem Estudo").value_counts().reset_index()
                df_estudo.columns = ["Estudo", "Quantidade"]

                fig_estudo = px.pie(
                    df_estudo, values="Quantidade", names="Estudo",
                    title="Distribuição de Agendamentos por Estudo",
                )
                fig_estudo.update_layout(height=400)
                st.plotly_chart(fig_estudo, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            if not df_view.empty and not df_view["data_visita_dt"].isnull().all():
                df_timeline = df_view.groupby(df_view["data_visita_dt"].dt.date).size().reset_index(name="Quantidade")
                df_timeline.columns = ["Data", "Quantidade"]
                df_timeline = df_timeline.sort_values("Data")
                df_timeline["Data"] = pd.to_datetime(df_timeline["Data"]).dt.strftime("%d/%m/%Y")

                fig_timeline = px.bar(
                    df_timeline, x="Data", y="Quantidade",
                    title="Agendamentos ao Longo do Tempo", text="Quantidade",
                )
                fig_timeline.update_layout(height=400, xaxis_tickangle=-45)
                fig_timeline.update_traces(textposition="outside")
                st.plotly_chart(fig_timeline, use_container_width=True)
            else:
                st.info("Sem dados para exibir")

        with col4:
            if not df_view.empty and not df_view["medico_responsavel"].isnull().all():
                df_medicos = df_view["medico_responsavel"].value_counts().head(10).reset_index()
                df_medicos.columns = ["Médico", "Quantidade"]

                fig_medicos = go.Figure(data=[
                    go.Bar(
                        y=df_medicos["Médico"], x=df_medicos["Quantidade"],
                        orientation="h", text=df_medicos["Quantidade"], textposition="auto",
                    )
                ])
                fig_medicos.update_layout(
                    title="Top 10 Médicos com Mais Agendamentos",
                    height=400,
                    yaxis={"categoryorder": "total ascending"},
                )
                st.plotly_chart(fig_medicos, use_container_width=True)
            else:
                st.info("Sem dados para exibir")

        # =====================================================
        # BUSCAR LOGS (cacheado) — usado nas duas seções abaixo
        # =====================================================
        ETAPAS_MAPA = {
            "status_medico": "Tempo Médico",
            "status_enfermagem": "Tempo Enfermagem",
            "status_espirometria": "Tempo Espirometria",
            "status_nutricionista": "Tempo Nutricionista",
            "status_farmacia": "Tempo Farmácia",
        }
        ETAPAS_TEMPO = [
            "status_medico", "status_enfermagem", "status_espirometria",
            "status_farmacia", "status_nutricionista",
        ]
        STATUS_INICIO = {"Atendendo", "Em atendimento"}

        ag_ids = tuple(df_view["id"].tolist())
        logs_all = _fetch_logs(supabase, ag_ids)

        # =====================================================
        # GRÁFICO DE TEMPO POR ETAPA
        # =====================================================
        st.markdown("---")
        st.markdown("### ⏱️ Tempo por Etapa")

        if logs_all:
            df_logs = pd.DataFrame(logs_all)
            df_logs.columns = [c.lower() for c in df_logs.columns]
            df_logs["ts"] = df_logs["data_hora_etapa"].apply(parse_ts_utc)
            df_logs = df_logs.dropna(subset=["ts"])

            if not df_logs.empty:
                now_utc = pd.Timestamp(datetime.now(timezone.utc))
                df_logs_sorted = df_logs.sort_values(["agendamento_id", "nome_etapa", "ts"])

                durations = []
                for (ag_id, etapa), grp in df_logs_sorted.groupby(["agendamento_id", "nome_etapa"]):
                    grp = grp.reset_index(drop=True)
                    total_sec = 0.0
                    for i, row in grp.iterrows():
                        if row["status_etapa"] not in STATUS_INICIO:
                            continue
                        t_ini = ensure_utc(row["ts"])
                        t_fim = ensure_utc(grp.loc[i + 1, "ts"]) if i + 1 < len(grp) else now_utc
                        if t_ini is None or t_fim is None:
                            continue
                        delta = (t_fim - t_ini).total_seconds()
                        if delta > 0:
                            total_sec += delta
                    durations.append({"nome_etapa": etapa, "tempo_sec": total_sec})

                df_tempo_etapa = pd.DataFrame(durations)
                tempo_total_etapa = df_tempo_etapa.groupby("nome_etapa")["tempo_sec"].sum().reset_index()
                tempo_total_etapa.columns = ["Etapa", "Tempo (segundos)"]
                tempo_total_etapa["Etapa"] = tempo_total_etapa["Etapa"].map(ETAPAS_MAPA).fillna(tempo_total_etapa["Etapa"])
                tempo_total_etapa = tempo_total_etapa.sort_values("Tempo (segundos)", ascending=False)

                fig_tempo_etapa = px.bar(
                    tempo_total_etapa, x="Etapa", y="Tempo (segundos)",
                    title="Tempo Total Aberto por Etapa", color="Etapa",
                    text=tempo_total_etapa["Tempo (segundos)"].apply(lambda x: hhmm_from_seconds(x)),
                )
                fig_tempo_etapa.update_layout(height=400, showlegend=False)
                fig_tempo_etapa.update_traces(textposition="auto")
                st.plotly_chart(fig_tempo_etapa, use_container_width=True)

                tempo_total_etapa["Tempo (HH:MM)"] = tempo_total_etapa["Tempo (segundos)"].apply(hhmm_from_seconds)
                st.dataframe(
                    tempo_total_etapa[["Etapa", "Tempo (HH:MM)"]],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("Sem dados de logs para exibir")
        else:
            st.info("Sem dados de logs para exibir")

        # =====================================================
        # MATRIZES DE AGENDAMENTOS POR CONSULTÓRIO
        # =====================================================
        st.markdown("---")
        st.markdown("### 📋 Matrizes de Análise")

        st.markdown("#### 1️⃣ Contagem de Pacientes por Consultório e Data")

        if not df_view.empty:
            df_pac = df_view.copy()
            df_pac["data_visita_str"] = df_pac["data_visita_dt"].dt.strftime("%d/%m/%Y")

            matriz_pacientes = df_pac.pivot_table(
                index="data_visita_str", columns="consultorio",
                values="id_paciente", aggfunc="count", fill_value=0,
            ).sort_index()
            matriz_pacientes["Total"] = matriz_pacientes.sum(axis=1)

            st.dataframe(matriz_pacientes, use_container_width=True, height=400)
            st.caption(f"Total de pacientes: {matriz_pacientes['Total'].sum():.0f}")
        else:
            st.info("Sem dados para exibir")

        st.markdown("---")
        st.markdown("#### 2️⃣ Contagem de Médicos Distintos por Consultório e Data")

        if not df_view.empty:
            df_med = df_view.copy()
            df_med["data_visita_str"] = df_med["data_visita_dt"].dt.strftime("%d/%m/%Y")

            matriz_medicos = df_med.pivot_table(
                index="data_visita_str", columns="consultorio",
                values="medico_responsavel", aggfunc="nunique", fill_value=0,
            ).sort_index()
            matriz_medicos["Total"] = matriz_medicos.sum(axis=1)

            st.dataframe(matriz_medicos, use_container_width=True, height=400)
            st.caption(f"Total de médicos distintos: {int(matriz_medicos['Total'].sum())}")
        else:
            st.info("Sem dados para exibir")

        # =====================================================
        # VISÃO DADOS — TABELA CUSTOMIZÁVEL
        # =====================================================
        st.markdown("---")
        st.subheader("📋 Visão Dados")
        st.caption("Selecione as colunas que deseja visualizar na tabela abaixo")

        df_visao = df_view.copy()
        df_visao["data_visita_fmt"] = df_visao["data_visita_dt"].dt.strftime("%d/%m/%Y")
        df_visao["data_cadastro_fmt"] = pd.to_datetime(df_visao["data_cadastro"], errors="coerce", utc=True).dt.tz_convert(None).dt.strftime("%d/%m/%Y %H:%M")
        _cad_naive = pd.to_datetime(df_visao["data_cadastro"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
        df_visao["antecedencia_dias"] = (df_visao["data_visita_dt"].dt.normalize() - _cad_naive).dt.days

        colunas_disponiveis = {
            "data_visita_fmt": "Data Visita",
            "nm_estudo": "Estudo",
            "id_paciente": "ID Participante",
            "nome_paciente": "Nome Participante",
            "desfecho_atendimento": "Desfecho Atendimento",
            "status_confirmacao": "Status Confirmação",
            "tipo_visita": "Tipo Visita",
            "visita": "Visita",
            "medico_responsavel": "Médico Responsável",
            "coordenacao": "Coordenação",
            "hora_chegada": "Hora Chegada",
            "hora_saida": "Hora Saída",
            "consultorio": "Consultório",
            "status_medico": "Status Médico",
            "status_enfermagem": "Status Enfermagem",
            "status_farmacia": "Status Farmácia",
            "status_espirometria": "Status Espirometria",
            "status_nutricionista": "Status Nutricionista",
            "jejum": "Jejum",
            "reembolso": "Reembolso",
            "valor_financeiro": "Valor Financeiro",
            "data_cadastro_fmt": "Data Cadastro",
            "antecedencia_dias": "Antecedência (dias)",
            "obs_visita": "Observações Visita",
        }

        colunas_disponiveis = {k: v for k, v in colunas_disponiveis.items() if k in df_visao.columns}

        colunas_padrao = ["data_visita_fmt", "nm_estudo", "id_paciente", "desfecho_atendimento"]
        colunas_padrao_existentes = [col for col in colunas_padrao if col in colunas_disponiveis]

        colunas_selecionadas_nomes = st.multiselect(
            "Colunas para exibir:",
            options=[colunas_disponiveis[k] for k in colunas_disponiveis.keys()],
            default=[colunas_disponiveis[k] for k in colunas_padrao_existentes],
            help="Selecione as colunas que deseja visualizar na tabela"
        )

        if colunas_selecionadas_nomes:
            nome_para_original = {v: k for k, v in colunas_disponiveis.items()}
            colunas_selecionadas_originais = [nome_para_original[nome] for nome in colunas_selecionadas_nomes]

            df_visao_filtrado = df_visao[colunas_selecionadas_originais].copy()
            df_visao_filtrado.rename(columns=colunas_disponiveis, inplace=True)

            gb = GridOptionsBuilder.from_dataframe(df_visao_filtrado)
            gb.configure_default_column(editable=False, groupable=True, filterable=True, sorteable=True)
            gb.configure_side_bar()

            AgGrid(
                df_visao_filtrado,
                gridOptions=gb.build(),
                update_mode=GridUpdateMode.NO_UPDATE,
                allow_unsafe_jscode=True,
                theme="streamlit",
                height=400,
            )

            col_download, col_info = st.columns([1, 3])
            with col_download:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                    df_visao_filtrado.to_excel(writer, index=False, sheet_name="Visão Dados")
                buffer.seek(0)

                st.download_button(
                    label="📥 Download Excel",
                    data=buffer,
                    file_name=f"visao_dados_{date.today().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )

            with col_info:
                st.caption(f"Total de {len(df_visao_filtrado)} registros | {len(colunas_selecionadas_nomes)} colunas selecionadas")
        else:
            st.warning("⚠️ Selecione pelo menos uma coluna para exibir")

        # =====================================================
        # RELATÓRIO PADRONIZADO + TEMPOS POR ETAPA
        # Reutiliza logs_all já buscado acima (sem segunda query)
        # =====================================================
        st.markdown("---")
        st.subheader("Relatório (padronizado) + tempos por etapa")

        df_logs_rel = pd.DataFrame(logs_all)

        if not df_logs_rel.empty:
            df_logs_rel.columns = [c.lower() for c in df_logs_rel.columns]
            df_logs_rel["ts"] = df_logs_rel["data_hora_etapa"].apply(parse_ts_utc)
            df_logs_rel = df_logs_rel.dropna(subset=["ts"])

            now_utc = pd.Timestamp(datetime.now(timezone.utc))
            df_logs_sorted = df_logs_rel.sort_values(["agendamento_id", "nome_etapa", "ts"])

            last_status = (
                df_logs_sorted.groupby(["agendamento_id", "nome_etapa"])["status_etapa"]
                .last()
                .reset_index()
                .rename(columns={"status_etapa": "ultimo_status"})
            )

            durations = []
            for (ag_id, etapa), grp in df_logs_sorted.groupby(["agendamento_id", "nome_etapa"]):
                grp = grp.reset_index(drop=True)
                total_sec = 0.0
                for i, row in grp.iterrows():
                    if row["status_etapa"] not in STATUS_INICIO:
                        continue
                    t_ini = ensure_utc(row["ts"])
                    t_fim = ensure_utc(grp.loc[i + 1, "ts"]) if i + 1 < len(grp) else now_utc
                    if t_ini is None or t_fim is None:
                        continue
                    delta = (t_fim - t_ini).total_seconds()
                    if delta > 0:
                        total_sec += delta
                durations.append({"agendamento_id": ag_id, "nome_etapa": etapa, "tempo_sec": total_sec})

            df_dur = pd.DataFrame(durations)
            df_stage = pd.merge(df_dur, last_status, on=["agendamento_id", "nome_etapa"], how="left")

            pivot_time = (
                df_stage.pivot_table(
                    index="agendamento_id", columns="nome_etapa",
                    values="tempo_sec", aggfunc="sum", fill_value=0.0,
                )
                .reindex(columns=ETAPAS_TEMPO, fill_value=0.0)
                .reset_index()
            )
            for etapa in ETAPAS_TEMPO:
                if etapa in pivot_time.columns:
                    pivot_time[f"Tempo {etapa.split('_', 1)[1].title()} (HH:MM)"] = pivot_time[etapa].apply(hhmm_from_seconds)
                    del pivot_time[etapa]

            pivot_last = (
                df_stage.pivot_table(
                    index="agendamento_id", columns="nome_etapa",
                    values="ultimo_status", aggfunc="last",
                )
                .reindex(columns=ETAPAS_TEMPO)
                .reset_index()
            )
            for etapa in ETAPAS_TEMPO:
                if etapa in pivot_last.columns:
                    pivot_last.rename(columns={etapa: f"Último {etapa.split('_', 1)[1].title()}"}, inplace=True)

            sum_sec = (
                df_stage.pivot_table(
                    index="agendamento_id", columns="nome_etapa",
                    values="tempo_sec", aggfunc="sum", fill_value=0.0,
                )
                .reindex(columns=ETAPAS_TEMPO, fill_value=0.0)
                .sum(axis=1)
                .reset_index(name="total_sec")
            )
            sum_sec["Total (HH:MM)"] = sum_sec["total_sec"].apply(hhmm_from_seconds)
            sum_sec = sum_sec.drop(columns=["total_sec"])
        else:
            ag_ids_list = list(ag_ids)
            pivot_time = pd.DataFrame({"agendamento_id": ag_ids_list})
            pivot_last = pd.DataFrame({"agendamento_id": ag_ids_list})
            sum_sec = pd.DataFrame({"agendamento_id": ag_ids_list, "Total (HH:MM)": "00:00"})

        rel_df = df_view.copy().reset_index(drop=True)
        rel_df["Data visita"] = pd.to_datetime(rel_df["data_visita"], errors="coerce").dt.strftime("%d/%m/%Y")
        rel_df["Hora consulta"] = rel_df["hora_consulta"]
        rel_df["Data cadastro"] = pd.to_datetime(rel_df["data_cadastro"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M:%S")
        rel_df["ID participante"] = rel_df["id_paciente"]
        rel_df["Nome participante"] = rel_df["nome_paciente"]
        rel_df["Estudo"] = rel_df["nm_estudo"]
        rel_df["Tipo visita"] = rel_df["tipo_visita"]
        rel_df["Médico responsável"] = rel_df["medico_responsavel"]
        rel_df["Status confirmação"] = rel_df["status_confirmacao"]
        rel_df["Coordenação"] = rel_df["coordenacao"]
        rel_df["Valor"] = rel_df["valor_financeiro"]
        rel_df["Reembolso"] = rel_df["reembolso"]
        rel_df["Desfecho atendimento"] = rel_df["desfecho_atendimento"]
        rel_df["Hora saída"] = pd.to_datetime(rel_df["hora_saida"], errors="coerce").dt.strftime("%H:%M:%S")
        _cad_naive_rel = pd.to_datetime(rel_df["data_cadastro"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
        rel_df["Antecedência (dias)"] = (rel_df["data_visita_dt"].dt.normalize() - _cad_naive_rel).dt.days

        base_cols = [
            "Data visita", "Hora consulta", "Data cadastro", "Antecedência (dias)",
            "ID participante", "Nome participante",
            "Estudo", "Tipo visita", "Médico responsável",
            "Status confirmação", "Coordenação", "Valor", "Reembolso",
            "Hora saída", "Desfecho atendimento",
        ]

        rel = rel_df.copy()
        rel["agendamento_id"] = rel_df["id"]

        if not pivot_time.empty:
            rel = rel.merge(pivot_time, on="agendamento_id", how="left")
        if not pivot_last.empty:
            rel = rel.merge(pivot_last, on="agendamento_id", how="left")
        if not sum_sec.empty:
            rel = rel.merge(sum_sec, on="agendamento_id", how="left")

        tempo_cols = [c for c in rel.columns if c.startswith("Tempo ")]
        ultimo_cols = [c for c in rel.columns if c.startswith("Último ")]
        ordered_cols = base_cols + tempo_cols + ultimo_cols + ["Total (HH:MM)"]
        ordered_cols = [c for c in ordered_cols if c in rel.columns]

        st.dataframe(rel[ordered_cols], use_container_width=True, hide_index=True)

        excel_buffer = BytesIO()
        rel[ordered_cols].to_excel(excel_buffer, index=False, sheet_name="Dados")
        excel_buffer.seek(0)
        st.download_button(
            "📥 Baixar XLSX do relatório (padronizado)",
            data=excel_buffer,
            file_name=f"relatorio_agendamentos_padronizado_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")
        import traceback
        st.code(traceback.format_exc())


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_agenda_relatorio()
