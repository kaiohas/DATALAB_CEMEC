# ============================================================
# 📊 frontend/pages/dados_relatorio.py
# Relatórios de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, datetime, timezone
from io import BytesIO

from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from frontend.supabase_client import get_supabase_client, supabase_execute


# ============================================================
# HELPERS (mesmo padrão de agenda_relatorio)
# ============================================================

def _parse_ts_utc(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    ts = pd.to_datetime(val, errors="coerce", utc=True)
    return None if pd.isna(ts) else ts


def _ensure_utc(ts):
    if ts is None:
        return None
    if not isinstance(ts, pd.Timestamp):
        ts = pd.to_datetime(ts, errors="coerce")
    if ts is None or pd.isna(ts):
        return None
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _hhmm(total_seconds: float) -> str:
    if pd.isna(total_seconds) or total_seconds is None:
        return "00:00"
    s = int(total_seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"


_STATUS_INICIO = {"Atendendo", "Em atendimento"}
_ETAPAS_TEMPO  = [
    "status_medico", "status_enfermagem", "status_espirometria",
    "status_farmacia", "status_nutricionista",
]

_DATE_CMP_JS = JsCode("""
function(a, b) {
    function p(d) {
        if (!d) return null;
        var x = d.split('/');
        return new Date(parseInt(x[2]), parseInt(x[1])-1, parseInt(x[0]));
    }
    var da = p(a), db = p(b);
    if (!da && !db) return 0;
    if (!da) return -1;
    if (!db) return 1;
    return da < db ? -1 : da > db ? 1 : 0;
}
""")


# ============================================================
# CACHED FETCHERS
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def _fetch_estudos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos").select("id_estudo, estudo").execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_agendamentos(_supabase, data_visita_str):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_agendamentos")
        .select("*")
        .eq("data_visita", data_visita_str)
        .order("id", desc=False)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_log_agendamentos(_supabase, agendamento_id):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_log_agendamentos")
        .select("*")
        .eq("agendamento_id", agendamento_id)
        .order("data_alteracao", desc=False)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_log_etapas(_supabase, ag_ids: tuple):
    if not ag_ids:
        return []
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_log_etapas")
        .select("agendamento_id, nome_etapa, status_etapa, data_hora_etapa")
        .in_("agendamento_id", list(ag_ids))
        .execute()
    )
    return resp.data if resp.data else []


# ============================================================
# PÁGINA
# ============================================================

def page_dados_relatorio():
    st.title("📊 Relatórios")

    try:
        supabase = get_supabase_client()

        df_estudos   = _fetch_estudos(supabase)
        estudos_lista = (
            sorted(df_estudos["estudo"].dropna().unique().tolist())
            if not df_estudos.empty else []
        )

        # =====================================================
        # FILTROS GLOBAIS
        # =====================================================
        st.markdown("### 🔍 Filtros")
        fc1, fc2 = st.columns(2)

        with fc1:
            data_visita_sel = st.date_input("Data da Visita", value=date.today())
        with fc2:
            estudos_sel = st.multiselect("Estudo(s)", options=estudos_lista, default=[], placeholder="Todos")

        # =====================================================
        # PREPARAR df_view
        # =====================================================
        df_ag = _fetch_agendamentos(supabase, str(data_visita_sel))

        if not df_ag.empty and not df_estudos.empty:
            df_ag = df_ag.merge(
                df_estudos[["id_estudo", "estudo"]],
                left_on="estudo_id", right_on="id_estudo", how="left",
            )
        elif not df_ag.empty:
            df_ag["estudo"] = ""

        if estudos_sel and not df_ag.empty:
            df_ag = df_ag[df_ag["estudo"].isin(estudos_sel)]

        if not df_ag.empty:
            df_ag = df_ag.rename(columns={"estudo": "nm_estudo"})
            df_ag["data_visita_dt"]  = pd.to_datetime(df_ag["data_visita"],  errors="coerce")
            df_ag["data_cadastro_dt"] = pd.to_datetime(df_ag["data_cadastro"], errors="coerce")

        df_view = df_ag.copy()

        if df_view.empty:
            st.info("Nenhum agendamento encontrado para os filtros selecionados.")
            st.session_state.pop("_log_selected_ag_id", None)
            st.stop()

        st.caption(
            f"📅 {data_visita_sel.strftime('%d/%m/%Y')} — "
            f"{len(df_view)} agendamento(s) encontrado(s)"
        )
        st.markdown("---")

        # =====================================================
        # BLOCO 1 — VISÃO DE LOG
        # =====================================================
        with st.expander("📋 Visão de Log", expanded=True):

            st.subheader("Agendamentos")
            st.caption("Clique em uma linha para ver o histórico de alterações")

            _cad_naive = (
                pd.to_datetime(df_view["data_cadastro"], errors="coerce", utc=True)
                .dt.tz_convert(None).dt.normalize()
            )
            df_view["data_visita_fmt"]   = df_view["data_visita_dt"].dt.strftime("%d/%m/%Y")
            df_view["data_cadastro_fmt"] = (
                pd.to_datetime(df_view["data_cadastro"], errors="coerce", utc=True)
                .dt.tz_convert(None).dt.strftime("%d/%m/%Y %H:%M")
            )
            df_view["antecedencia_dias"] = (
                df_view["data_visita_dt"].dt.normalize() - _cad_naive
            ).dt.days

            cols_ordered = [
                ("data_visita_fmt",      "Data Visita"),
                ("data_cadastro_fmt",    "Data Criação"),
                ("id_paciente",          "ID Paciente"),
                ("nome_paciente",        "Paciente"),
                ("tipo_visita",          "Tipo Visita"),
                ("visita",               "Visita"),
                ("desfecho_atendimento", "Desfecho Atendimento"),
                ("antecedencia_dias",    "Antecedência (dias)"),
                ("id",                   "ID"),
            ]
            cols_src    = [c for c, _ in cols_ordered if c in df_view.columns]
            cols_rename = {c: n for c, n in cols_ordered if c in df_view.columns}
            df_grid1 = df_view[cols_src].copy()
            df_grid1.rename(columns=cols_rename, inplace=True)

            gb1 = GridOptionsBuilder.from_dataframe(df_grid1)
            gb1.configure_selection(selection_mode="single", use_checkbox=False)
            gb1.configure_default_column(filterable=True, sortable=True)
            gb1.configure_column("Data Visita",          width=105, comparator=_DATE_CMP_JS)
            gb1.configure_column("Data Criação",         width=130)
            gb1.configure_column("ID Paciente",          width=95)
            gb1.configure_column("Paciente",             width=170)
            gb1.configure_column("Tipo Visita",          width=105)
            gb1.configure_column("Visita",               width=80)
            gb1.configure_column("Desfecho Atendimento", width=160)
            gb1.configure_column("Antecedência (dias)",  width=135)
            gb1.configure_column("ID",                   width=65)

            grid_resp1 = AgGrid(
                df_grid1,
                gridOptions=gb1.build(),
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                height=300,
                theme="streamlit",
                allow_unsafe_jscode=True,
                key="aggrid_log",
            )

            sel1 = grid_resp1["selected_rows"]
            if sel1 is not None and len(sel1) > 0:
                st.session_state["_log_selected_ag_id"] = int(sel1.iloc[0]["ID"])

            selected_ag_id = st.session_state.get("_log_selected_ag_id")
            if selected_ag_id is not None and selected_ag_id not in df_view["id"].values:
                selected_ag_id = None
                st.session_state.pop("_log_selected_ag_id", None)

            col_c1, col_d1 = st.columns([4, 1])
            with col_c1:
                st.caption(f"Total: {len(df_grid1)} agendamento(s)")
            with col_d1:
                buf1 = BytesIO()
                with pd.ExcelWriter(buf1, engine="openpyxl") as w:
                    df_grid1.to_excel(w, index=False, sheet_name="Agendamentos")
                buf1.seek(0)
                st.download_button(
                    "📥 Excel", data=buf1,
                    file_name=f"agendamentos_{data_visita_sel}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="dl_agendamentos",
                )

            st.markdown("---")

            if selected_ag_id:
                row_sel = df_view[df_view["id"] == selected_ag_id]
                nome_p  = row_sel["nome_paciente"].values[0] if not row_sel.empty else str(selected_ag_id)
                est_p   = row_sel["nm_estudo"].values[0]     if not row_sel.empty and "nm_estudo" in row_sel.columns else ""

                st.subheader(f"Histórico de Alterações — {nome_p}")
                if est_p:
                    st.caption(f"Estudo: {est_p}  |  ID Agendamento: {selected_ag_id}")

                col_ref, _ = st.columns([1, 5])
                with col_ref:
                    if st.button("🔄 Atualizar log", key="btn_refresh_log"):
                        _fetch_log_agendamentos.clear()
                        st.rerun()

                df_log = _fetch_log_agendamentos(supabase, selected_ag_id)

                if df_log.empty:
                    st.info("Nenhuma alteração registrada para este agendamento.")
                else:
                    if "data_alteracao" in df_log.columns:
                        df_log["data_alteracao"] = (
                            pd.to_datetime(df_log["data_alteracao"], errors="coerce", utc=True)
                            .dt.tz_convert("America/Sao_Paulo")
                            .dt.strftime("%d/%m/%Y %H:%M:%S")
                        )

                    cols_log_map = {
                        "id":                    "ID Log",
                        "data_alteracao":        "Data/Hora",
                        "usuario_alteracao_nome":"Usuário",
                        "campo_alterado":        "Campo",
                        "valor_antigo":          "Valor Antigo",
                        "valor_novo":            "Valor Novo",
                    }
                    df_grid2 = df_log[[k for k in cols_log_map if k in df_log.columns]].copy()
                    df_grid2.rename(columns=cols_log_map, inplace=True)

                    fl1, fl2 = st.columns(2)
                    with fl1:
                        filtrar_data_log = st.checkbox("Filtrar por data da alteração", key="chk_log_data")
                        if filtrar_data_log:
                            data_log_sel = st.date_input("Data da alteração", value=date.today(), key="date_log_filter")
                        else:
                            data_log_sel = None
                    with fl2:
                        campos_unicos = ["(Todos)"] + sorted(df_grid2["Campo"].dropna().unique().tolist()) \
                            if "Campo" in df_grid2.columns else ["(Todos)"]
                        campo_sel = st.selectbox("Campo alterado", campos_unicos, key="sel_log_campo")

                    if filtrar_data_log and data_log_sel and "Data/Hora" in df_grid2.columns:
                        df_grid2 = df_grid2[
                            df_grid2["Data/Hora"].str.startswith(data_log_sel.strftime("%d/%m/%Y"), na=False)
                        ]
                    if campo_sel != "(Todos)" and "Campo" in df_grid2.columns:
                        df_grid2 = df_grid2[df_grid2["Campo"] == campo_sel]

                    st.dataframe(df_grid2, use_container_width=True, hide_index=True)

                    col_c2, col_d2 = st.columns([4, 1])
                    with col_c2:
                        st.caption(f"Total: {len(df_grid2)} registro(s) de alteração")
                    with col_d2:
                        buf2 = BytesIO()
                        with pd.ExcelWriter(buf2, engine="openpyxl") as w:
                            df_grid2.to_excel(w, index=False, sheet_name="Log Alterações")
                        buf2.seek(0)
                        st.download_button(
                            "📥 Excel", data=buf2,
                            file_name=f"log_{selected_ag_id}_{date.today()}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_log",
                        )
            else:
                st.info("👆 Selecione um agendamento na tabela acima para ver o histórico de alterações.")

        # =====================================================
        # BLOCO 2 — RELATÓRIO PERSONALIZADO
        # =====================================================
        with st.expander("📄 Relatório Personalizado"):
            df_visao = df_view.copy()
            _cad_vp  = (
                pd.to_datetime(df_visao["data_cadastro"], errors="coerce", utc=True)
                .dt.tz_convert(None).dt.normalize()
            )
            df_visao["data_visita_fmt"]   = df_visao["data_visita_dt"].dt.strftime("%d/%m/%Y")
            df_visao["data_cadastro_fmt"] = (
                pd.to_datetime(df_visao["data_cadastro"], errors="coerce", utc=True)
                .dt.tz_convert(None).dt.strftime("%d/%m/%Y %H:%M")
            )
            df_visao["antecedencia_dias"] = (
                df_visao["data_visita_dt"].dt.normalize() - _cad_vp
            ).dt.days

            colunas_disponiveis = {
                "data_visita_fmt":      "Data Visita",
                "nm_estudo":            "Estudo",
                "id_paciente":          "ID Participante",
                "nome_paciente":        "Nome Participante",
                "desfecho_atendimento": "Desfecho Atendimento",
                "status_confirmacao":   "Status Confirmação",
                "tipo_visita":          "Tipo Visita",
                "visita":               "Visita",
                "medico_responsavel":   "Médico Responsável",
                "coordenacao":          "Coordenação",
                "hora_chegada":         "Hora Chegada",
                "hora_saida":           "Hora Saída",
                "consultorio":          "Consultório",
                "status_medico":        "Status Médico",
                "status_enfermagem":    "Status Enfermagem",
                "status_farmacia":      "Status Farmácia",
                "status_espirometria":  "Status Espirometria",
                "status_nutricionista": "Status Nutricionista",
                "jejum":                "Jejum",
                "reembolso":            "Reembolso",
                "valor_financeiro":     "Valor Financeiro",
                "data_cadastro_fmt":    "Data Cadastro",
                "antecedencia_dias":    "Antecedência (dias)",
                "obs_visita":           "Observações Visita",
            }
            colunas_disponiveis = {k: v for k, v in colunas_disponiveis.items() if k in df_visao.columns}

            padrao = ["data_visita_fmt", "nm_estudo", "id_paciente", "desfecho_atendimento"]
            padrao_existentes = [c for c in padrao if c in colunas_disponiveis]

            colunas_sel = st.multiselect(
                "Colunas para exibir:",
                options=[colunas_disponiveis[k] for k in colunas_disponiveis],
                default=[colunas_disponiveis[k] for k in padrao_existentes],
                key="ms_colunas_personalizado",
            )

            if colunas_sel:
                n2o = {v: k for k, v in colunas_disponiveis.items()}
                df_vp = df_visao[[n2o[n] for n in colunas_sel]].copy()
                df_vp.rename(columns=colunas_disponiveis, inplace=True)

                gb_vp = GridOptionsBuilder.from_dataframe(df_vp)
                gb_vp.configure_default_column(editable=False, groupable=True, filterable=True, sorteable=True)
                gb_vp.configure_side_bar()
                if "Data Visita" in df_vp.columns:
                    gb_vp.configure_column("Data Visita", comparator=_DATE_CMP_JS)

                AgGrid(
                    df_vp,
                    gridOptions=gb_vp.build(),
                    update_mode=GridUpdateMode.NO_UPDATE,
                    allow_unsafe_jscode=True,
                    theme="streamlit",
                    height=400,
                    key="aggrid_personalizado",
                )

                col_d_vp, col_i_vp = st.columns([1, 3])
                with col_d_vp:
                    buf_vp = BytesIO()
                    with pd.ExcelWriter(buf_vp, engine="openpyxl") as w:
                        df_vp.to_excel(w, index=False, sheet_name="Relatório Personalizado")
                    buf_vp.seek(0)
                    st.download_button(
                        "📥 Download Excel", data=buf_vp,
                        file_name=f"relatorio_personalizado_{data_visita_sel}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="dl_personalizado",
                    )
                with col_i_vp:
                    st.caption(f"Total de {len(df_vp)} registros | {len(colunas_sel)} colunas selecionadas")
            else:
                st.warning("⚠️ Selecione pelo menos uma coluna para exibir")

        # =====================================================
        # BLOCO 3 — VISÃO COM DESFECHOS
        # =====================================================
        with st.expander("⏱️ Visão com Desfechos"):
            ag_ids   = tuple(df_view["id"].tolist())
            logs_all = _fetch_log_etapas(supabase, ag_ids)

            df_logs_rel = pd.DataFrame(logs_all)

            if not df_logs_rel.empty:
                df_logs_rel.columns = [c.lower() for c in df_logs_rel.columns]
                df_logs_rel["ts"]   = df_logs_rel["data_hora_etapa"].apply(_parse_ts_utc)
                df_logs_rel         = df_logs_rel.dropna(subset=["ts"])

                now_utc      = pd.Timestamp(datetime.now(timezone.utc))
                df_ls        = df_logs_rel.sort_values(["agendamento_id", "nome_etapa", "ts"])

                last_status = (
                    df_ls.groupby(["agendamento_id", "nome_etapa"])["status_etapa"]
                    .last().reset_index()
                    .rename(columns={"status_etapa": "ultimo_status"})
                )

                durations = []
                for (ag_id, etapa), grp in df_ls.groupby(["agendamento_id", "nome_etapa"]):
                    grp       = grp.reset_index(drop=True)
                    total_sec = 0.0
                    for i, row in grp.iterrows():
                        if row["status_etapa"] not in _STATUS_INICIO:
                            continue
                        t_ini  = _ensure_utc(row["ts"])
                        t_fim  = _ensure_utc(grp.loc[i + 1, "ts"]) if i + 1 < len(grp) else now_utc
                        if t_ini is None or t_fim is None:
                            continue
                        delta = (t_fim - t_ini).total_seconds()
                        if delta > 0:
                            total_sec += delta
                    durations.append({"agendamento_id": ag_id, "nome_etapa": etapa, "tempo_sec": total_sec})

                df_dur   = pd.DataFrame(durations)
                df_stage = pd.merge(df_dur, last_status, on=["agendamento_id", "nome_etapa"], how="left")

                pivot_time = (
                    df_stage.pivot_table(
                        index="agendamento_id", columns="nome_etapa",
                        values="tempo_sec", aggfunc="sum", fill_value=0.0,
                    )
                    .reindex(columns=_ETAPAS_TEMPO, fill_value=0.0)
                    .reset_index()
                )
                for etapa in _ETAPAS_TEMPO:
                    if etapa in pivot_time.columns:
                        pivot_time[f"Tempo {etapa.split('_', 1)[1].title()} (HH:MM)"] = pivot_time[etapa].apply(_hhmm)
                        del pivot_time[etapa]

                pivot_last = (
                    df_stage.pivot_table(
                        index="agendamento_id", columns="nome_etapa",
                        values="ultimo_status", aggfunc="last",
                    )
                    .reindex(columns=_ETAPAS_TEMPO)
                    .reset_index()
                )
                for etapa in _ETAPAS_TEMPO:
                    if etapa in pivot_last.columns:
                        pivot_last.rename(columns={etapa: f"Último {etapa.split('_', 1)[1].title()}"}, inplace=True)

                sum_sec = (
                    df_stage.pivot_table(
                        index="agendamento_id", columns="nome_etapa",
                        values="tempo_sec", aggfunc="sum", fill_value=0.0,
                    )
                    .reindex(columns=_ETAPAS_TEMPO, fill_value=0.0)
                    .sum(axis=1)
                    .reset_index(name="total_sec")
                )
                sum_sec["Total (HH:MM)"] = sum_sec["total_sec"].apply(_hhmm)
                sum_sec = sum_sec.drop(columns=["total_sec"])
            else:
                ag_ids_list = list(ag_ids)
                pivot_time  = pd.DataFrame({"agendamento_id": ag_ids_list})
                pivot_last  = pd.DataFrame({"agendamento_id": ag_ids_list})
                sum_sec     = pd.DataFrame({"agendamento_id": ag_ids_list, "Total (HH:MM)": "00:00"})

            rel_df = df_view.copy().reset_index(drop=True)
            rel_df["Data visita"]          = rel_df["data_visita_dt"].dt.strftime("%d/%m/%Y")
            rel_df["Hora consulta"]        = rel_df.get("hora_consulta")
            rel_df["Data cadastro"]        = pd.to_datetime(rel_df["data_cadastro"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M:%S")
            rel_df["ID participante"]      = rel_df["id_paciente"]
            rel_df["Nome participante"]    = rel_df["nome_paciente"]
            rel_df["Estudo"]               = rel_df.get("nm_estudo")
            rel_df["Tipo visita"]          = rel_df.get("tipo_visita")
            rel_df["Médico responsável"]   = rel_df.get("medico_responsavel")
            rel_df["Status confirmação"]   = rel_df.get("status_confirmacao")
            rel_df["Coordenação"]          = rel_df.get("coordenacao")
            rel_df["Valor"]                = rel_df.get("valor_financeiro")
            rel_df["Reembolso"]            = rel_df.get("reembolso")
            rel_df["Desfecho atendimento"] = rel_df.get("desfecho_atendimento")
            if "hora_saida" in rel_df.columns:
                rel_df["Hora saída"] = pd.to_datetime(rel_df["hora_saida"], errors="coerce").dt.strftime("%H:%M:%S")
            else:
                rel_df["Hora saída"] = None
            _cad_naive_rel = (
                pd.to_datetime(rel_df["data_cadastro"], errors="coerce", utc=True)
                .dt.tz_convert(None).dt.normalize()
            )
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

            tempo_cols   = [c for c in rel.columns if c.startswith("Tempo ")]
            ultimo_cols  = [c for c in rel.columns if c.startswith("Último ")]
            ordered_cols = base_cols + tempo_cols + ultimo_cols + ["Total (HH:MM)"]
            ordered_cols = [c for c in ordered_cols if c in rel.columns]

            st.dataframe(rel[ordered_cols], use_container_width=True, hide_index=True)

            buf_des = BytesIO()
            rel[ordered_cols].to_excel(buf_des, index=False, sheet_name="Visão com Desfechos")
            buf_des.seek(0)
            st.download_button(
                "📥 Download Excel", data=buf_des,
                file_name=f"visao_desfechos_{data_visita_sel}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_desfechos",
                use_container_width=True,
            )

    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
