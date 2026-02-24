# ============================================================
# ✅ frontend/pages/agenda_confirmacao.py
# Confirmação de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def parse_variaveis(valor_str: str) -> list:
    """Parse de valores a partir de uma string - removendo aspas e normalizando."""
    if not valor_str:
        return []

    # Remove aspas no início e fim
    valor_str = valor_str.strip('"').strip("'")

    # Tenta split com diferentes delimitadores
    if ";" in valor_str:
        valores = [v.strip() for v in valor_str.split(";") if v.strip()]
    elif "\n" in valor_str:
        valores = [v.strip() for v in valor_str.split("\n") if v.strip()]
    elif "," in valor_str:
        valores = [v.strip() for v in valor_str.split(",") if v.strip()]
    else:
        valores = [valor_str.strip()]

    return valores


def page_agenda_confirmacao():
    """Página para confirmação de agendamentos."""
    st.title("✅ Confirmação de Agendamentos")

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # Busca variáveis de status de confirmação
        resp_status_confirmacao = supabase_execute(
            lambda: supabase.table("tab_app_variaveis")
            .select("valor")
            .eq("uso", "status_confirmacao")
            .execute()
        )
        status_confirmacao_list = (
            parse_variaveis(resp_status_confirmacao.data[0]["valor"])
            if resp_status_confirmacao.data
            else []
        )

        # Busca estudos
        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos")
            .select("id_estudo, estudo")
            .execute()
        )
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_estudos.columns = [c.lower() for c in df_estudos.columns]

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        fc1, fc2, fc3, fc4 = st.columns(4)

        with fc1:
            estudos_unicos = sorted([x for x in df_estudos["estudo"].unique() if x])
            estudo_sel = st.selectbox(
                "Estudo",
                ["(Todos)"] + estudos_unicos,
                index=0
            )

        with fc2:
            dt_ini = st.date_input("Data (Início)")

        with fc3:
            dt_fim = st.date_input("Data (Fim)")

        with fc4:
            status_sel = st.selectbox(
                "Status Confirmação",
                ["(Todos)"] + status_confirmacao_list,
                index=0
            )

        # Busca agendamentos
        resp_agendamentos = supabase_execute(
            lambda: supabase.table("tab_app_agendamentos")
            .select("*")
            .order("data_visita", desc=True)
            .limit(500)
            .execute()
        )
        df_agendamentos = pd.DataFrame(resp_agendamentos.data) if resp_agendamentos.data else pd.DataFrame()

        if df_agendamentos.empty:
            st.warning("Nenhum agendamento encontrado.")
            st.stop()

        df_agendamentos.columns = [c.lower() for c in df_agendamentos.columns]

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
            st.stop()

        # =====================================================
        # TABELA COM AGGRID PARA SELEÇÃO
        # =====================================================
        st.markdown("---")
        st.markdown("### 📋 Clique na linha para editar")

        # Seleciona colunas para exibição
        cols_display = [
            "id", "data_visita_br", "nm_estudo", "id_paciente", "nome_paciente",
            "tipo_visita", "visita", "medico_responsavel", "status_confirmacao"
        ]

        cols_existentes = [col for col in cols_display if col in df_view.columns]
        df_grid = df_view[cols_existentes].copy()
        df_grid.columns = [
            "ID", "Data", "Estudo", "ID Paciente", "Paciente",
            "Tipo Visita", "Visita", "Médico", "Status"
        ][:len(cols_existentes)]

        # Configurar AgGrid
        gb = GridOptionsBuilder.from_dataframe(df_grid)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_selection(selection_mode="single", use_checkbox=False)
        gb.configure_column("ID", width=50)
        gb.configure_column("Data", width=80)
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
            theme="light"
        )

        selected_rows = grid_response["selected_rows"]

        # =====================================================
        # BLOCO DE CONFIRMAÇÃO (baseado na seleção)
        # =====================================================
        if selected_rows is not None and len(selected_rows) > 0:
            selected_row = selected_rows.iloc[0]
            agendamento_id = int(selected_row["ID"])

            # Busca o agendamento completo
            df_view.columns = [c.lower() for c in df_view.columns]
            agendamento_data = df_view[df_view["id"] == agendamento_id].iloc[0]

            st.markdown("---")
            st.markdown("### ✏️ Atualizar Status de Confirmação")

            # Exibir detalhes do agendamento selecionado
            st.markdown("#### 📌 Detalhes do Agendamento Selecionado")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.info(f"**Paciente:** {agendamento_data.get('nome_paciente', '—')}")
                st.info(f"**ID Paciente:** {agendamento_data.get('id_paciente', '—')}")

            with col2:
                st.info(f"**Data:** {agendamento_data.get('data_visita_br', '—')}")
                st.info(f"**Estudo:** {agendamento_data.get('nm_estudo', '—')}")

            with col3:
                st.info(f"**Tipo Visita:** {agendamento_data.get('tipo_visita', '—')}")
                st.info(f"**Médico:** {agendamento_data.get('medico_responsavel', '—')}")

            st.markdown("---")

            # Formulário para atualizar status
            with st.form(f"form_confirmar_{agendamento_id}"):
                novo_status = st.selectbox(
                    "Status de Confirmação",
                    status_confirmacao_list,
                    help="Selecione o novo status de confirmação",
                    key=f"status_selector_{agendamento_id}"
                )

                if st.form_submit_button("💾 Atualizar Status", use_container_width=True):
                    try:
                        supabase_execute(
                            lambda: supabase.table("tab_app_agendamentos")
                            .update({"status_confirmacao": novo_status})
                            .eq("id", agendamento_id)
                            .execute()
                        )

                        feedback("✅ Status atualizado com sucesso!", "success", "💾")
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