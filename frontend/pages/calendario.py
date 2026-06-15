# ============================================================
# 📅 frontend/pages/calendario.py
# Calendário de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO

from frontend.supabase_client import get_supabase_client, supabase_execute


def _parse_variaveis(valor_str: str) -> list:
    if not valor_str:
        return []
    valor_str = valor_str.strip('"').strip("'")
    if ";" in valor_str:
        return [v.strip() for v in valor_str.split(";") if v.strip()]
    if "\n" in valor_str:
        return [v.strip() for v in valor_str.split("\n") if v.strip()]
    if "," in valor_str:
        return [v.strip() for v in valor_str.split(",") if v.strip()]
    return [valor_str.strip()]


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_estudos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("id_estudo, estudo, coordenacao")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_medicos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_variaveis")
        .select("valor")
        .eq("uso", "medico_responsavel")
        .execute()
    )
    return _parse_variaveis(resp.data[0]["valor"]) if resp.data else []


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_calendario(_supabase, data_str):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_agendamentos")
        .select(
            "id, hora_consulta, estudo_id, id_paciente, "
            "tipo_visita, visita, medico_responsavel, consultorio, coordenacao"
        )
        .eq("data_visita", data_str)
        .order("hora_consulta", desc=False)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


def page_calendario():
    st.title("📅 Calendário")

    try:
        supabase = get_supabase_client()

        df_estudos = _fetch_estudos(supabase)
        medicos    = _fetch_medicos(supabase)

        coordenacoes_lista = sorted([
            x for x in df_estudos["coordenacao"].dropna().unique() if x
        ]) if not df_estudos.empty else []

        estudos_lista = sorted([
            x for x in df_estudos["estudo"].dropna().unique() if x
        ]) if not df_estudos.empty else []

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        fc1, fc2 = st.columns(2)
        fc3, fc4 = st.columns(2)

        with fc1:
            data_sel = st.date_input("Data", value=date.today(), format="DD/MM/YYYY")

        with fc2:
            coordenacao_sel = st.selectbox(
                "Coordenação",
                ["(Todas)"] + coordenacoes_lista,
            )

        with fc3:
            estudos_filtrados = estudos_lista
            if coordenacao_sel != "(Todas)" and not df_estudos.empty:
                estudos_filtrados = sorted([
                    x for x in df_estudos[df_estudos["coordenacao"] == coordenacao_sel]["estudo"].dropna().unique()
                    if x
                ])
            estudos_sel = st.multiselect(
                "Estudo(s)",
                options=estudos_filtrados,
                default=[],
                placeholder="Todos",
            )

        with fc4:
            medico_sel = st.multiselect(
                "Médico(s)",
                options=medicos,
                default=[],
                placeholder="Todos",
            )

        st.markdown("")
        buscar = st.button("🔍 Buscar", use_container_width=True, type="primary")

        # =====================================================
        # BUSCA E RESULTADO
        # =====================================================
        if buscar:
            df_raw = _fetch_calendario(supabase, str(data_sel))

            if not df_raw.empty and not df_estudos.empty:
                df_raw = df_raw.merge(
                    df_estudos[["id_estudo", "estudo"]],
                    left_on="estudo_id", right_on="id_estudo", how="left",
                )
            elif not df_raw.empty:
                df_raw["estudo"] = ""

            if coordenacao_sel != "(Todas)" and not df_raw.empty:
                df_raw = df_raw[df_raw["coordenacao"] == coordenacao_sel]

            if estudos_sel and not df_raw.empty:
                df_raw = df_raw[df_raw["estudo"].isin(estudos_sel)]

            if medico_sel and not df_raw.empty:
                df_raw = df_raw[df_raw["medico_responsavel"].isin(medico_sel)]

            st.session_state["_calendario_df"]   = df_raw
            st.session_state["_calendario_data"] = data_sel

        # =====================================================
        # EXIBIÇÃO DA TABELA
        # =====================================================
        if "_calendario_df" in st.session_state:
            df = st.session_state["_calendario_df"]
            data_ref = st.session_state.get("_calendario_data", data_sel)

            st.markdown("---")
            st.subheader(f"Agenda — {data_ref.strftime('%d/%m/%Y')}")

            if df.empty:
                st.info("Nenhum agendamento encontrado para os filtros selecionados.")
            else:
                cols_map = {
                    "hora_consulta":      "Horário",
                    "estudo":             "Estudo",
                    "id_paciente":        "ID Paciente",
                    "tipo_visita":        "Tipo de Visita",
                    "visita":             "Visita",
                    "medico_responsavel": "Médico",
                    "consultorio":        "Consultório",
                }
                cols_src = [c for c in cols_map if c in df.columns]
                df_grid  = df[cols_src].copy()
                df_grid.rename(columns=cols_map, inplace=True)

                st.dataframe(df_grid, use_container_width=True, hide_index=True)

                col_caption, col_dl = st.columns([4, 1])
                with col_caption:
                    st.caption(f"Total: {len(df_grid)} agendamento(s)")
                with col_dl:
                    buf = BytesIO()
                    with pd.ExcelWriter(buf, engine="openpyxl") as w:
                        df_grid.to_excel(w, index=False, sheet_name="Calendário")
                    buf.seek(0)
                    st.download_button(
                        "📥 Excel",
                        data=buf,
                        file_name=f"calendario_{data_ref}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    except Exception as e:
        st.error(f"❌ Erro ao carregar página: {str(e)}")
