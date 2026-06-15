# ============================================================
# ✅ frontend/pages/agenda_confirmacao.py
# Confirmação de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from frontend.supabase_client import get_supabase_client, supabase_execute, registrar_log_agendamento
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


# ============================================================
# CACHED DATA FETCHING — evita reconexões em reruns de filtro
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def _fetch_status_confirmacao(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_variaveis")
        .select("valor")
        .eq("uso", "status_confirmacao")
        .execute()
    )
    return parse_variaveis(resp.data[0]["valor"]) if resp.data else []


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_estudos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("id_estudo, estudo")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_agendamentos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_agendamentos")
        .select("*")
        .order("data_visita", desc=True)
        .limit(500)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


def _invalidar_cache():
    _fetch_agendamentos.clear()


def page_agenda_confirmacao():
    """Página para confirmação de agendamentos."""
    st.title("✅ Confirmação de Agendamentos")

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # ✅ BUSCAR VARIÁVEIS E ESTUDOS (cacheados)
        status_confirmacao_list = _fetch_status_confirmacao(supabase)
        df_estudos = _fetch_estudos(supabase)

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        fc1, fc2, fc3, fc4 = st.columns(4)

        with fc1:
            estudos_unicos = sorted([x for x in df_estudos["estudo"].unique() if x])
            estudo_sel = st.selectbox("Estudo", ["(Todos)"] + estudos_unicos, index=0)

        with fc2:
            dt_ini = st.date_input("Data (Início)", format="DD/MM/YYYY")

        with fc3:
            dt_fim = st.date_input("Data (Fim)", format="DD/MM/YYYY")

        with fc4:
            status_sel = st.selectbox(
                "Status Confirmação", ["(Todos)"] + status_confirmacao_list, index=0
            )

        # ✅ BUSCAR AGENDAMENTOS (cacheado 1 min)
        df_agendamentos = _fetch_agendamentos(supabase)

        if df_agendamentos.empty:
            st.warning("Nenhum agendamento encontrado.")
            st.stop()

        # Merge com estudos
        if not df_estudos.empty:
            df_agendamentos = df_agendamentos.merge(
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est")
            ).rename(columns={"estudo": "nm_estudo"})

        # Converte datas
        df_agendamentos["data_visita_dt"] = pd.to_datetime(df_agendamentos["data_visita"], errors="coerce")
        df_agendamentos["data_visita_br"] = df_agendamentos["data_visita_dt"].dt.strftime("%d/%m/%Y")

        # Aplicar filtros
        df_view = df_agendamentos.copy()

        if estudo_sel != "(Todos)":
            df_view = df_view[df_view["nm_estudo"] == estudo_sel]

        if dt_ini and dt_fim:
            df_view = df_view[
                (df_view["data_visita_dt"] >= pd.to_datetime(dt_ini)) &
                (df_view["data_visita_dt"] <= pd.to_datetime(dt_fim))
            ]

        if status_sel != "(Todos)":
            df_view = df_view[df_view["status_confirmacao"] == status_sel]

        if df_view.empty:
            st.info("Nenhum agendamento encontrado com os filtros aplicados.")
            st.session_state.pop("_conf_selected_id", None)
            st.stop()

        # =====================================================
        # TABELA COM AGGRID PARA SELEÇÃO
        # =====================================================
        st.markdown("---")
        st.markdown("### 📋 Clique na linha para editar")

        cols_display = [
            "id", "data_visita_br", "hora_consulta", "nm_estudo", "id_paciente", "nome_paciente",
            "tipo_visita", "visita", "medico_responsavel", "status_confirmacao"
        ]

        cols_existentes = [col for col in cols_display if col in df_view.columns]
        df_grid = df_view[cols_existentes].copy()
        df_grid.columns = [
            "ID", "Data", "Hora", "Estudo", "ID Paciente", "Paciente",
            "Tipo Visita", "Visita", "Médico", "Status"
        ][:len(cols_existentes)]

        gb = GridOptionsBuilder.from_dataframe(df_grid)
        gb.configure_selection(selection_mode="single", use_checkbox=False)
        gb.configure_column("ID", width=50)
        gb.configure_column("Data", width=80)
        gb.configure_column("Hora", width=70)
        gb.configure_column("Estudo", width=120)
        gb.configure_column("ID Paciente", width=90)
        gb.configure_column("Paciente", width=150)
        gb.configure_column("Tipo Visita", width=90)
        gb.configure_column("Visita", width=80)
        gb.configure_column("Médico", width=130)
        gb.configure_column("Status", width=120)

        grid_options = gb.build()

        grid_response = AgGrid(
            df_grid,
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            fit_columns_on_grid_load=False,
            height=400,
            theme="streamlit"
        )

        # =====================================================
        # PERSISTÊNCIA DA SELEÇÃO NO SESSION STATE
        # =====================================================
        selected_rows = grid_response["selected_rows"]
        if selected_rows is not None and len(selected_rows) > 0:
            st.session_state["_conf_selected_id"] = int(selected_rows.iloc[0]["ID"])

        selected_ag_id = st.session_state.get("_conf_selected_id")

        if selected_ag_id is not None and selected_ag_id not in df_view["id"].values:
            selected_ag_id = None
            st.session_state.pop("_conf_selected_id", None)

        # Exibe feedback de ação anterior (após rerun)
        if "_confirmacao_feedback" in st.session_state:
            msg, tipo = st.session_state.pop("_confirmacao_feedback")
            feedback(msg, tipo, "💾")

        # =====================================================
        # BLOCO DE CONFIRMAÇÃO
        # =====================================================
        if selected_ag_id is not None:
            df_view.columns = [c.lower() for c in df_view.columns]
            agendamento_data = df_view[df_view["id"] == selected_ag_id].iloc[0]
            agendamento_id = selected_ag_id

            st.markdown("---")

            col_titulo, col_limpar = st.columns([5, 1])
            with col_titulo:
                st.markdown("### ✏️ Atualizar Status de Confirmação")
            with col_limpar:
                if st.button("✖ Limpar seleção", use_container_width=True):
                    st.session_state.pop("_conf_selected_id", None)
                    st.rerun()

            st.markdown("#### 📌 Detalhes do Agendamento Selecionado")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.info(f"**Paciente:** {agendamento_data.get('nome_paciente', '—')}")
                st.info(f"**ID Paciente:** {agendamento_data.get('id_paciente', '—')}")

            with col2:
                st.info(f"**Data:** {agendamento_data.get('data_visita_br', '—')}")
                st.info(f"**Hora:** {agendamento_data.get('hora_consulta', '—')}")
                st.info(f"**Estudo:** {agendamento_data.get('nm_estudo', '—')}")

            with col3:
                st.info(f"**Tipo Visita:** {agendamento_data.get('tipo_visita', '—')}")
                st.info(f"**Médico:** {agendamento_data.get('medico_responsavel', '—')}")

            st.markdown("---")

            # Selectbox fora do form é intencional: permite renderização condicional
            # dos campos de reagendamento sem precisar submeter o form primeiro
            novo_status = st.selectbox(
                "Status de Confirmação",
                status_confirmacao_list,
                help="Selecione o novo status de confirmação",
                key=f"status_selector_{agendamento_id}",
            )

            nova_data_visita = None
            novo_horario = None

            if novo_status == "Reagendado":
                st.info("📅 Preencha a nova data e horário. Um novo agendamento será criado com os mesmos dados.")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    nova_data_visita = st.date_input(
                        "Nova Data da Visita", key=f"nova_data_{agendamento_id}", format="DD/MM/YYYY"
                    )
                with col_r2:
                    novo_horario = st.time_input(
                        "Novo Horário da Visita", key=f"novo_horario_{agendamento_id}", step=1800
                    )

            if st.button(
                "💾 Atualizar Status",
                use_container_width=True,
                key=f"btn_confirmar_{agendamento_id}",
                type="primary",
            ):
                if novo_status == "Reagendado" and not nova_data_visita:
                    feedback("⚠️ Informe a nova data para o reagendamento", "error", "⚠️")
                else:
                    try:
                        ag_id = agendamento_id
                        ns = novo_status
                        status_anterior = agendamento_data.get("status_confirmacao")
                        usuario_id_conf = st.session_state.get("id_usuario")

                        supabase_execute(
                            lambda: supabase.table("tab_app_agendamentos")
                            .update({"status_confirmacao": ns})
                            .eq("id", ag_id)
                            .execute()
                        )
                        registrar_log_agendamento(
                            supabase, ag_id, usuario_id_conf, usuario_logado,
                            "status_confirmacao", status_anterior, ns
                        )

                        if novo_status == "Reagendado":
                            resp_original = supabase_execute(
                                lambda: supabase.table("tab_app_agendamentos")
                                .select("*")
                                .eq("id", ag_id)
                                .execute()
                            )

                            if resp_original.data:
                                novo_ag = dict(resp_original.data[0])
                                novo_ag.pop("id", None)
                                novo_ag.pop("data_cadastro", None)
                                novo_ag["data_visita"] = str(nova_data_visita)
                                novo_ag["hora_consulta"] = novo_horario.strftime("%H:%M") if novo_horario else None
                                novo_ag["status_confirmacao"] = None

                                payload = novo_ag
                                resp_reag = supabase_execute(
                                    lambda: supabase.table("tab_app_agendamentos")
                                    .insert(payload)
                                    .execute()
                                )
                                novo_id_reag = resp_reag.data[0]["id"] if resp_reag.data else None
                                if novo_id_reag:
                                    registrar_log_agendamento(
                                        supabase, novo_id_reag, usuario_id_conf, usuario_logado,
                                        "reagendamento", str(agendamento_data.get("data_visita", "")), str(nova_data_visita)
                                    )

                            msg_ok = "✅ Status atualizado e novo agendamento criado com sucesso!"
                        else:
                            msg_ok = "✅ Status atualizado com sucesso!"

                        _invalidar_cache()
                        st.session_state["_confirmacao_feedback"] = (msg_ok, "success")
                        st.rerun()

                    except Exception as e:
                        feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")
        else:
            st.info("👆 Selecione um agendamento na tabela acima para editar o status de confirmação")

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_agenda_confirmacao()
