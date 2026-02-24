# ============================================================
# 📊 frontend/pages/agenda_relatorio.py
# Relatório e Estatísticas de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta, datetime, timezone

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


def page_agenda_relatorio():
    """Página de relatórios e estatísticas."""
    st.title("📊 Relatório de Agendamentos")

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # =====================================================
        # BUSCAR DADOS
        # =====================================================
        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos")
            .select("id_estudo, estudo, disciplina, coordenacao")
            .execute()
        )
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_estudos.columns = [c.lower() for c in df_estudos.columns]

        resp_agendamentos = supabase_execute(
            lambda: supabase.table("tab_app_agendamentos").select("*").limit(1000).execute()
        )
        df_agendamentos = pd.DataFrame(resp_agendamentos.data) if resp_agendamentos.data else pd.DataFrame()

        if df_agendamentos.empty:
            st.warning("Nenhum agendamento encontrado.")
            st.stop()

        df_agendamentos.columns = [c.lower() for c in df_agendamentos.columns]

        # ✅ CORRIGIDO: Usar "estudo" em vez de "nm_estudo"
        if not df_estudos.empty:
            df_agendamentos = df_agendamentos.merge(
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est"),
            ).rename(columns={"estudo": "nm_estudo"})

        # Converte datas
        df_agendamentos["data_visita_dt"] = pd.to_datetime(df_agendamentos["data_visita"], errors="coerce")
        df_agendamentos["data_cadastro_dt"] = pd.to_datetime(df_agendamentos["data_cadastro"], errors="coerce")

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)

        # Filtro 1: Estudo
        with fc1:
            estudos_unicos = sorted([x for x in df_estudos["estudo"].dropna().unique() if x])
            estudo_sel = st.selectbox(
                "Estudo",
                ["(Todos)"] + estudos_unicos,
                index=0,
            )

        # ✅ Filtro 2: Disciplina (amarrada ao estudo)
        with fc2:
            if estudo_sel != "(Todos)":
                disciplinas_estudo = sorted(
                    [x for x in df_estudos[df_estudos["estudo"] == estudo_sel]["disciplina"].dropna().unique() if x]
                )
            else:
                disciplinas_estudo = sorted([x for x in df_estudos["disciplina"].dropna().unique() if x])

            disciplina_sel = st.selectbox(
                "Disciplina",
                ["(Todas)"] + disciplinas_estudo,
                index=0,
            )

        # Filtro 3: Status Confirmação
        with fc3:
            status_unicos = sorted([x for x in df_agendamentos["status_confirmacao"].dropna().unique() if x])
            status_sel = st.selectbox(
                "Status Confirmação",
                ["(Todos)"] + status_unicos,
                index=0,
            )

        # ✅ Filtro 4: Coordenação
        with fc4:
            coordenacoes_unicas = sorted([x for x in df_agendamentos["coordenacao"].dropna().unique() if x])
            coordenacao_sel = st.selectbox(
                "Coordenação",
                ["(Todas)"] + coordenacoes_unicas,
                index=0,
            )

        # Filtros 5 e 6: Data
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

        # Gráfico 1: Agendamentos por Status
        with col1:
            if not df_view.empty:
                df_status = df_view["status_confirmacao"].fillna("Sem Status").value_counts().reset_index()
                df_status.columns = ["Status", "Quantidade"]

                fig_status = px.bar(
                    df_status,
                    x="Status",
                    y="Quantidade",
                    title="Agendamentos por Status de Confirmação",
                    color="Status",
                    text="Quantidade",
                )
                fig_status.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_status, use_container_width=True)
            else:
                st.info("Sem dados para exibir")

        # Gráfico 2: Agendamentos por Estudo
        with col2:
            if not df_view.empty:
                df_estudo = df_view["nm_estudo"].fillna("Sem Estudo").value_counts().reset_index()
                df_estudo.columns = ["Estudo", "Quantidade"]

                fig_estudo = px.pie(
                    df_estudo,
                    values="Quantidade",
                    names="Estudo",
                    title="Distribuição de Agendamentos por Estudo",
                )
                fig_estudo.update_layout(height=400)
                st.plotly_chart(fig_estudo, use_container_width=True)

        # Gráfico 3: Agendamentos ao Longo do Tempo
        col3, col4 = st.columns(2)

        with col3:
            if not df_view.empty and not df_view["data_visita_dt"].isnull().all():
                df_timeline = df_view.groupby(df_view["data_visita_dt"].dt.date).size().reset_index(name="Quantidade")
                df_timeline.columns = ["Data", "Quantidade"]

                fig_timeline = px.line(
                    df_timeline,
                    x="Data",
                    y="Quantidade",
                    title="Agendamentos ao Longo do Tempo",
                    markers=True,
                )
                fig_timeline.update_layout(height=400)
                st.plotly_chart(fig_timeline, use_container_width=True)
            else:
                st.info("Sem dados para exibir")

        # Gráfico 4: Top Médicos
        with col4:
            if not df_view.empty and not df_view["medico_responsavel"].isnull().all():
                df_medicos = df_view["medico_responsavel"].value_counts().head(10).reset_index()
                df_medicos.columns = ["Médico", "Quantidade"]

                fig_medicos = go.Figure(
                    data=[
                        go.Bar(
                            y=df_medicos["Médico"],
                            x=df_medicos["Quantidade"],
                            orientation="h",
                            text=df_medicos["Quantidade"],
                            textposition="auto",
                        )
                    ]
                )
                fig_medicos.update_layout(
                    title="Top 10 Médicos com Mais Agendamentos",
                    height=400,
                    yaxis={"categoryorder": "total ascending"},
                )
                st.plotly_chart(fig_medicos, use_container_width=True)
            else:
                st.info("Sem dados para exibir")

        # =====================================================
        # ✅ GRÁFICO DE TEMPO POR ETAPA
        # =====================================================
        st.markdown("---")
        st.markdown("### ⏱️ Tempo por Etapa")

        ETAPAS_MAPA = {
            "status_medico": "Tempo Médico",
            "status_enfermagem": "Tempo Enfermagem",
            "status_espirometria": "Tempo Espirometria",
            "status_nutricionista": "Tempo Nutricionista",
            "status_farmacia": "Tempo Farmácia",
        }
        STATUS_INICIO = {"Atendendo", "Em atendimento"}

        # Busca logs de agendamentos
        ag_ids = df_view["id"].tolist()

        resp_logs = supabase_execute(
            lambda: supabase.table("tab_app_log_etapas")
            .select("agendamento_id, nome_etapa, status_etapa, data_hora_etapa")
            .in_("agendamento_id", ag_ids)
            .execute()
        )

        logs_all = resp_logs.data if resp_logs.data else []

        if logs_all:
            df_logs = pd.DataFrame(logs_all)
            df_logs.columns = [c.lower() for c in df_logs.columns]
            df_logs["ts"] = df_logs["data_hora_etapa"].apply(parse_ts_utc)
            df_logs = df_logs.dropna(subset=["ts"])

            if not df_logs.empty:
                now_utc = pd.Timestamp(datetime.now(timezone.utc))
                df_logs_sorted = df_logs.sort_values(["agendamento_id", "nome_etapa", "ts"])

                # Cálculo de durações por etapa
                durations = []
                for (ag_id, etapa), grp in df_logs_sorted.groupby(["agendamento_id", "nome_etapa"]):
                    grp = grp.reset_index(drop=True)
                    total_sec = 0.0
                    for i, row in grp.iterrows():
                        if row["status_etapa"] not in STATUS_INICIO:
                            continue
                        t_ini = ensure_utc(row["ts"])
                        if i + 1 < len(grp):
                            t_fim = ensure_utc(grp.loc[i + 1, "ts"])
                        else:
                            t_fim = now_utc
                        if t_ini is None or t_fim is None:
                            continue
                        delta = (t_fim - t_ini).total_seconds()
                        if delta > 0:
                            total_sec += delta
                    durations.append({"nome_etapa": etapa, "tempo_sec": total_sec})

                # Agregar tempos por etapa (soma total)
                df_tempo_etapa = pd.DataFrame(durations)
                tempo_total_etapa = df_tempo_etapa.groupby("nome_etapa")["tempo_sec"].sum().reset_index()
                tempo_total_etapa.columns = ["Etapa", "Tempo (segundos)"]
                tempo_total_etapa["Etapa"] = tempo_total_etapa["Etapa"].map(ETAPAS_MAPA).fillna(tempo_total_etapa["Etapa"])
                tempo_total_etapa = tempo_total_etapa.sort_values("Tempo (segundos)", ascending=False)

                # ✅ Gráfico de barras com tempo por etapa
                fig_tempo_etapa = px.bar(
                    tempo_total_etapa,
                    x="Etapa",
                    y="Tempo (segundos)",
                    title="Tempo Total Aberto por Etapa",
                    color="Etapa",
                    text=tempo_total_etapa["Tempo (segundos)"].apply(lambda x: hhmm_from_seconds(x)),
                )
                fig_tempo_etapa.update_layout(
                    height=400,
                    showlegend=False,
                    xaxis_title="Etapa",
                    yaxis_title="Tempo (segundos)",
                )
                fig_tempo_etapa.update_traces(textposition="auto")
                st.plotly_chart(fig_tempo_etapa, use_container_width=True)

                # Resumo em tabela
                tempo_total_etapa["Tempo (HH:MM)"] = tempo_total_etapa["Tempo (segundos)"].apply(hhmm_from_seconds)
                st.dataframe(
                    tempo_total_etapa[["Etapa", "Tempo (HH:MM)"]],
                    use_container_width=True,
                    hide_index=True,
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

        # Matriz 1: Contagem de Pacientes por Consultório e Data
        st.markdown("#### 1️⃣ Contagem de Pacientes por Consultório e Data")

        if not df_view.empty:
            df_pacientes_consultorio = df_view.copy()
            df_pacientes_consultorio["data_visita_str"] = df_pacientes_consultorio["data_visita_dt"].dt.strftime("%d/%m/%Y")

            matriz_pacientes = df_pacientes_consultorio.pivot_table(
                index="data_visita_str",
                columns="consultorio",
                values="id_paciente",
                aggfunc="count",
                fill_value=0,
            ).sort_index()

            matriz_pacientes["Total"] = matriz_pacientes.sum(axis=1)

            st.dataframe(
                matriz_pacientes,
                use_container_width=True,
                height=400,
            )

            st.caption(f"Total de pacientes: {matriz_pacientes['Total'].sum():.0f}")
        else:
            st.info("Sem dados para exibir")

        # Matriz 2: Contagem de Médicos Distintos por Consultório e Data
        st.markdown("---")
        st.markdown("#### 2️⃣ Contagem de Médicos Distintos por Consultório e Data")

        if not df_view.empty:
            df_medicos_consultorio = df_view.copy()
            df_medicos_consultorio["data_visita_str"] = df_medicos_consultorio["data_visita_dt"].dt.strftime("%d/%m/%Y")

            matriz_medicos = df_medicos_consultorio.pivot_table(
                index="data_visita_str",
                columns="consultorio",
                values="medico_responsavel",
                aggfunc="nunique",
                fill_value=0,
            ).sort_index()

            matriz_medicos["Total"] = matriz_medicos.sum(axis=1)

            st.dataframe(
                matriz_medicos,
                use_container_width=True,
                height=400,
            )

            st.caption(f"Total de médicos distintos: {int(matriz_medicos['Total'].sum())}")
        else:
            st.info("Sem dados para exibir")

        # =====================================================
        # ABA DE RELATÓRIO DETALHADO COM TEMPOS
        # =====================================================
        st.markdown("---")
        st.subheader("Relatório (padronizado) + tempos por etapa")

        ETAPAS_TEMPO = [
            "status_medico",
            "status_enfermagem",
            "status_espirometria",
            "status_farmacia",
            "status_nutricionista",
        ]

        # Busca logs de agendamentos
        ag_ids = df_view["id"].tolist()

        resp_logs = supabase_execute(
            lambda: supabase.table("tab_app_log_etapas")
            .select("agendamento_id, nome_etapa, status_etapa, data_hora_etapa")
            .in_("agendamento_id", ag_ids)
            .execute()
        )

        logs_all = resp_logs.data if resp_logs.data else []

        # ========== Processamento de Logs ==========
        df_logs = pd.DataFrame(logs_all)

        if not df_logs.empty:
            df_logs.columns = [c.lower() for c in df_logs.columns]
            df_logs["ts"] = df_logs["data_hora_etapa"].apply(parse_ts_utc)
            df_logs = df_logs.dropna(subset=["ts"])

            now_utc = pd.Timestamp(datetime.now(timezone.utc))
            df_logs_sorted = df_logs.sort_values(["agendamento_id", "nome_etapa", "ts"])

            # Último status por etapa
            last_status = (
                df_logs_sorted.groupby(["agendamento_id", "nome_etapa"])["status_etapa"]
                .last()
                .reset_index()
                .rename(columns={"status_etapa": "ultimo_status"})
            )

            # Cálculo de durações
            durations = []
            for (ag_id, etapa), grp in df_logs_sorted.groupby(["agendamento_id", "nome_etapa"]):
                grp = grp.reset_index(drop=True)
                total_sec = 0.0
                for i, row in grp.iterrows():
                    if row["status_etapa"] not in STATUS_INICIO:
                        continue
                    t_ini = ensure_utc(row["ts"])
                    if i + 1 < len(grp):
                        t_fim = ensure_utc(grp.loc[i + 1, "ts"])
                    else:
                        t_fim = now_utc
                    if t_ini is None or t_fim is None:
                        continue
                    delta = (t_fim - t_ini).total_seconds()
                    if delta > 0:
                        total_sec += delta
                durations.append({"agendamento_id": ag_id, "nome_etapa": etapa, "tempo_sec": total_sec})

            df_dur = pd.DataFrame(durations)
            df_stage = pd.merge(df_dur, last_status, on=["agendamento_id", "nome_etapa"], how="left")

            # Tabela de tempos (HH:MM)
            pivot_time = (
                df_stage.pivot_table(
                    index="agendamento_id",
                    columns="nome_etapa",
                    values="tempo_sec",
                    aggfunc="sum",
                    fill_value=0.0,
                )
                .reindex(columns=ETAPAS_TEMPO, fill_value=0.0)
                .reset_index()
            )
            for etapa in ETAPAS_TEMPO:
                if etapa in pivot_time.columns:
                    pivot_time[f"Tempo {etapa.split('_', 1)[1].title()} (HH:MM)"] = pivot_time[etapa].apply(hhmm_from_seconds)
                    del pivot_time[etapa]

            # Último status por etapa
            pivot_last = (
                df_stage.pivot_table(
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
                    pivot_last.rename(columns={etapa: f"Último {etapa.split('_', 1)[1].title()}"}, inplace=True)

            # Total geral HH:MM
            sum_sec = (
                df_stage.pivot_table(
                    index="agendamento_id",
                    columns="nome_etapa",
                    values="tempo_sec",
                    aggfunc="sum",
                    fill_value=0.0,
                )
                .reindex(columns=ETAPAS_TEMPO, fill_value=0.0)
                .sum(axis=1)
                .reset_index(name="total_sec")
            )
            sum_sec["Total (HH:MM)"] = sum_sec["total_sec"].apply(hhmm_from_seconds)
            sum_sec = sum_sec.drop(columns=["total_sec"])
        else:
            pivot_time = pd.DataFrame({"agendamento_id": ag_ids})
            pivot_last = pd.DataFrame({"agendamento_id": ag_ids})
            sum_sec = pd.DataFrame({"agendamento_id": ag_ids, "Total (HH:MM)": "00:00"})

        # ========== Montagem do Relatório ==========
        rel_df = df_view.copy()
        rel_df = rel_df.reset_index(drop=True)

        # Formatações
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

        # Colunas de saída
        base_cols = [
            "Data visita", "Hora consulta", "Data cadastro",
            "ID participante", "Nome participante",
            "Estudo", "Tipo visita", "Médico responsável",
            "Status confirmação", "Coordenação", "Valor", "Reembolso",
            "Hora saída", "Desfecho atendimento",
        ]

        # ✅ MERGE CORRIGIDO
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

        # Download CSV
        csv = rel[ordered_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 Baixar CSV do relatório (padronizado)",
            data=csv,
            file_name=f"relatorio_agendamentos_padronizado_{date.today()}.csv",
            mime="text/csv",
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