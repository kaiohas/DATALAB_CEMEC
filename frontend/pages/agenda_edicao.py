# ============================================================
# ✏️ frontend/pages/agenda_edicao.py
# Edição e Deleção de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
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


def page_agenda_edicao():
    """Página para editar e deletar agendamentos."""
    st.title("✏️ Edição e Deleção de Agendamentos")

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # =====================================================
        # BUSCAR ID DO USUÁRIO NO BANCO
        # =====================================================
        resp_usuario = supabase_execute(
            lambda: supabase.table("tab_app_usuarios")
            .select("id_usuario")
            .eq("nm_usuario", usuario_logado.lower().strip())
            .execute()
        )

        if not resp_usuario.data:
            st.error("❌ Usuário não encontrado no sistema")
            st.stop()

        usuario_id = resp_usuario.data[0]["id_usuario"]

        # =====================================================
        # BUSCAR COORDENAÇÕES DO USUÁRIO
        # =====================================================
        resp_coordenacoes = supabase_execute(
            lambda: supabase.table("tab_app_usuario_coordenacao")
            .select("coordenacao")
            .eq("id_usuario", usuario_id)
            .eq("sn_ativo", True)
            .execute()
        )
        coordenacoes_usuario = [c["coordenacao"] for c in resp_coordenacoes.data] if resp_coordenacoes.data else []

        if not coordenacoes_usuario:
            st.warning("⚠️ Você não está vinculado a nenhuma coordenação. Solicite à gerência.")
            st.stop()

        st.caption(f"👤 Coordenações: {', '.join(coordenacoes_usuario)}")

        # =====================================================
        # BUSCAR VARIÁVEIS (EXATAMENTE COMO NA PÁGINA DE LANÇAMENTO)
        # =====================================================
        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos")
            .select("id_estudo, estudo, coordenacao")
            .execute()
        )
        resp_tipo_visita = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "tipo_visita").execute()
        )
        resp_medico = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "medico_responsavel").execute()
        )
        resp_consultorio = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "consultorio").execute()
        )
        resp_jejum = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "jejum").execute()
        )
        resp_reembolso = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "reembolso").execute()
        )
        resp_visita = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "visita").execute()
        )

        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_estudos.columns = [c.lower() for c in df_estudos.columns]

        # Parse variáveis (EXATAMENTE COMO NA PÁGINA DE LANÇAMENTO)
        tipos_visita = parse_variaveis(resp_tipo_visita.data[0]["valor"]) if resp_tipo_visita.data else []
        medicos = parse_variaveis(resp_medico.data[0]["valor"]) if resp_medico.data else []
        consultorios = parse_variaveis(resp_consultorio.data[0]["valor"]) if resp_consultorio.data else []
        jejuns = parse_variaveis(resp_jejum.data[0]["valor"]) if resp_jejum.data else []
        reembolsos = parse_variaveis(resp_reembolso.data[0]["valor"]) if resp_reembolso.data else []
        visitas = parse_variaveis(resp_visita.data[0]["valor"]) if resp_visita.data else []

        # ✅ BUSCAR USUÁRIOS PARA RESPONSÁVEL
        resp_usuarios = supabase_execute(
            lambda: supabase.table("tab_app_usuarios")
            .select("nm_usuario")
            .eq("sn_ativo", True)
            .execute()
        )
        usuarios_list = [u["nm_usuario"] for u in resp_usuarios.data] if resp_usuarios.data else []
        usuarios_list = sorted(usuarios_list)

        # =====================================================
        # BUSCAR AGENDAMENTOS
        # =====================================================
        resp_agendamentos = supabase_execute(
            lambda: supabase.table("tab_app_agendamentos")
            .select("*")
            .order("data_visita", desc=False)
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

        # =====================================================
        # FILTRAR POR COORDENAÇÃO DO USUÁRIO
        # =====================================================
        df_view = df_agendamentos[df_agendamentos["coordenacao"].isin(coordenacoes_usuario)].copy()

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        fc1, fc2, fc3, fc4 = st.columns(4)

        with fc1:
            estudos_vinculados = sorted([x for x in df_view["nm_estudo"].unique() if x])
            estudo_sel = st.selectbox(
                "Estudo",
                ["(Todos)"] + estudos_vinculados,
                index=0
            )

        with fc2:
            status_unicos = sorted([x for x in df_view["status_confirmacao"].dropna().unique() if x])
            status_sel = st.selectbox(
                "Status Confirmação",
                ["(Todos)"] + status_unicos,
                index=0
            )

        with fc3:
            dt_ini = st.date_input("Data (Início)")

        with fc4:
            dt_fim = st.date_input("Data (Fim)")

        # Aplicar filtros
        if estudo_sel != "(Todos)":
            df_view = df_view[df_view["nm_estudo"] == estudo_sel]

        if status_sel != "(Todos)":
            df_view = df_view[df_view["status_confirmacao"] == status_sel]

        if dt_ini and dt_fim:
            df_view = df_view[
                (df_view["data_visita_dt"] >= pd.to_datetime(dt_ini)) &
                (df_view["data_visita_dt"] <= pd.to_datetime(dt_fim))
            ]

        if df_view.empty:
            st.warning("⚠️ Nenhum agendamento encontrado para sua coordenação com os filtros aplicados.")
            st.stop()

        st.success(f"✅ {len(df_view)} agendamento(s) encontrado(s)")

        # =====================================================
        # TABELA COM AGGRID PARA SELEÇÃO
        # =====================================================
        st.markdown("---")
        st.markdown("### 📋 Clique na linha para editar ou deletar")

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
        gb.configure_column("Status", width=100)

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
        # BLOCO DE EDIÇÃO/DELEÇÃO
        # =====================================================
        if selected_rows is not None and len(selected_rows) > 0:
            selected_row = selected_rows.iloc[0]
            agendamento_id = int(selected_row["ID"])

            # Busca o agendamento completo
            df_view.columns = [c.lower() for c in df_view.columns]
            agendamento_data = df_view[df_view["id"] == agendamento_id].iloc[0]

            st.markdown("---")
            st.markdown("### ✏️ Editar Agendamento")

            # Exibir detalhes
            st.markdown("#### 📌 Detalhes do Agendamento Selecionado")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.info(f"**Paciente:** {agendamento_data.get('nome_paciente', '—')}")
                st.info(f"**ID Paciente:** {agendamento_data.get('id_paciente', '—')}")

            with col2:
                st.info(f"**Data:** {agendamento_data.get('data_visita_br', '—')}")
                st.info(f"**Estudo:** {agendamento_data.get('nm_estudo', '—')}")

            with col3:
                st.info(f"**Status Confirmação:** {agendamento_data.get('status_confirmacao', '—')}")

            st.markdown("---")

            # Obter valores atuais
            id_paciente_atual = agendamento_data.get("id_paciente") or ""
            nome_paciente_atual = agendamento_data.get("nome_paciente") or ""
            data_visita_atual = agendamento_data.get("data_visita") or ""
            hora_consulta_atual = agendamento_data.get("hora_consulta") or ""
            tipo_visita_atual = agendamento_data.get("tipo_visita") or ""
            visita_atual = agendamento_data.get("visita") or ""
            medico_atual = agendamento_data.get("medico_responsavel") or ""
            consultorio_atual = agendamento_data.get("consultorio") or ""
            jejum_atual = agendamento_data.get("jejum") or ""
            reembolso_atual = agendamento_data.get("reembolso") or ""
            valor_atual = agendamento_data.get("valor_financeiro") or ""
            responsavel_agendamento_atual = agendamento_data.get("responsavel_agendamento_nome") or ""
            horario_uber_atual = agendamento_data.get("horario_uber") or ""

            # Formulário de edição
            with st.form(f"form_edicao_{agendamento_id}"):
                st.markdown("#### 📝 Campos Editáveis")

                col1, col2, col3 = st.columns(3)

                with col1:
                    id_paciente_novo = st.text_input(
                        "ID Paciente",
                        value=id_paciente_atual,
                        key=f"id_paciente_{agendamento_id}"
                    )

                    nome_paciente_novo = st.text_input(
                        "Nome Paciente",
                        value=nome_paciente_atual,
                        key=f"nome_paciente_{agendamento_id}"
                    )

                    data_visita_nova = st.date_input(
                        "Data da Visita",
                        value=pd.to_datetime(data_visita_atual, errors="coerce") if data_visita_atual else None,
                        key=f"data_visita_{agendamento_id}"
                    )

                with col2:
                    hora_consulta_nova = st.time_input(
                        "Hora Consulta",
                        value=pd.to_datetime(hora_consulta_atual, errors="coerce").time() if hora_consulta_atual else None,
                        key=f"hora_consulta_{agendamento_id}"
                    )

                    # ✅ TIPO DE VISITA - USANDO PADRÃO DE LANÇAMENTO
                    tipo_visita_novo = st.selectbox(
                        "Tipo de Visita",
                        [""] + tipos_visita if tipos_visita else [""],
                        index=(tipos_visita.index(tipo_visita_atual) + 1) if tipo_visita_atual in tipos_visita else 0,
                        key=f"tipo_visita_{agendamento_id}"
                    )

                    # ✅ VISITA - USANDO PADRÃO DE LANÇAMENTO (com uso = "visita")
                    visita_nova = st.selectbox(
                        "Visita",
                        [""] + visitas if visitas else [""],
                        index=(visitas.index(visita_atual) + 1) if visita_atual in visitas else 0,
                        key=f"visita_{agendamento_id}"
                    )

                with col3:
                    # ✅ MÉDICO - USANDO PADRÃO DE LANÇAMENTO
                    medico_novo = st.selectbox(
                        "Médico Responsável",
                        [""] + medicos if medicos else [""],
                        index=(medicos.index(medico_atual) + 1) if medico_atual in medicos else 0,
                        key=f"medico_{agendamento_id}"
                    )

                    # ✅ CONSULTÓRIO - USANDO PADRÃO DE LANÇAMENTO
                    consultorio_novo = st.selectbox(
                        "Consultório",
                        [""] + consultorios if consultorios else [""],
                        index=(consultorios.index(consultorio_atual) + 1) if consultorio_atual in consultorios else 0,
                        key=f"consultorio_{agendamento_id}"
                    )

                    # ✅ JEJUM - USANDO PADRÃO DE LANÇAMENTO
                    jejum_novo = st.selectbox(
                        "Jejum",
                        [""] + jejuns if jejuns else [""],
                        index=(jejuns.index(jejum_atual) + 1) if jejum_atual in jejuns else 0,
                        key=f"jejum_{agendamento_id}"
                    )

                # Próxima linha
                col4, col5, col6 = st.columns(3)

                with col4:
                    # ✅ REEMBOLSO - USANDO PADRÃO DE LANÇAMENTO
                    reembolso_novo = st.selectbox(
                        "Reembolso",
                        [""] + reembolsos if reembolsos else [""],
                        index=(reembolsos.index(reembolso_atual) + 1) if reembolso_atual in reembolsos else 0,
                        key=f"reembolso_{agendamento_id}"
                    )

                    valor_novo = st.text_input(
                        "Valor Financeiro",
                        value=str(valor_atual),
                        key=f"valor_{agendamento_id}"
                    )

                with col5:
                    # ✅ RESPONSÁVEL - SELETOR DE USUÁRIOS
                    responsavel_novo = st.selectbox(
                        "Responsável Agendamento",
                        [""] + usuarios_list if usuarios_list else [""],
                        index=(usuarios_list.index(responsavel_agendamento_atual) + 1) if responsavel_agendamento_atual in usuarios_list else 0,
                        key=f"responsavel_{agendamento_id}"
                    )

                with col6:
                    horario_uber_novo = st.time_input(
                        "Horário Uber",
                        value=pd.to_datetime(horario_uber_atual, errors="coerce").time() if horario_uber_atual else None,
                        key=f"horario_uber_{agendamento_id}"
                    )

                st.markdown("---")

                col_salvar, col_deletar = st.columns(2)

                with col_salvar:
                    if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                        # Monta payload com alterações
                        payload = {}

                        if id_paciente_novo != id_paciente_atual:
                            payload["id_paciente"] = id_paciente_novo

                        if nome_paciente_novo != nome_paciente_atual:
                            payload["nome_paciente"] = nome_paciente_novo

                        if data_visita_nova and str(data_visita_nova) != str(data_visita_atual).split()[0]:
                            payload["data_visita"] = str(data_visita_nova)

                        if hora_consulta_nova and str(hora_consulta_nova) != str(hora_consulta_atual):
                            payload["hora_consulta"] = str(hora_consulta_nova)

                        if tipo_visita_novo and tipo_visita_novo != tipo_visita_atual:
                            payload["tipo_visita"] = tipo_visita_novo

                        if visita_nova and visita_nova != visita_atual:
                            payload["visita"] = visita_nova

                        if medico_novo and medico_novo != medico_atual:
                            payload["medico_responsavel"] = medico_novo

                        if consultorio_novo and consultorio_novo != consultorio_atual:
                            payload["consultorio"] = consultorio_novo

                        if jejum_novo and jejum_novo != jejum_atual:
                            payload["jejum"] = jejum_novo

                        if reembolso_novo and reembolso_novo != reembolso_atual:
                            payload["reembolso"] = reembolso_novo

                        if valor_novo != str(valor_atual):
                            try:
                                payload["valor_financeiro"] = float(valor_novo) if valor_novo else None
                            except Exception:
                                st.error("❌ Valor financeiro deve ser um número")
                                st.stop()

                        if responsavel_novo and responsavel_novo != responsavel_agendamento_atual:
                            payload["responsavel_agendamento_nome"] = responsavel_novo

                        if horario_uber_novo and str(horario_uber_novo) != str(horario_uber_atual):
                            payload["horario_uber"] = str(horario_uber_novo)

                        if payload:
                            try:
                                supabase_execute(
                                    lambda: supabase.table("tab_app_agendamentos")
                                    .update(payload)
                                    .eq("id", agendamento_id)
                                    .execute()
                                )
                                feedback("✅ Agendamento atualizado com sucesso!", "success", "💾")
                                st.rerun()
                            except Exception as e:
                                feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")
                        else:
                            st.warning("⚠️ Nenhuma alteração detectada")

                with col_deletar:
                    if st.form_submit_button("🗑️ Deletar Agendamento", use_container_width=True, type="secondary"):
                        st.session_state[f"confirmar_delecao_{agendamento_id}"] = True

            # =====================================================
            # CONFIRMAÇÃO DE DELEÇÃO
            # =====================================================
            if st.session_state.get(f"confirmar_delecao_{agendamento_id}", False):
                st.markdown("---")
                st.warning("⚠️ ATENÇÃO: Esta ação não pode ser desfeita!")

                col_conf, col_cancel = st.columns(2)

                with col_conf:
                    if st.button(
                        "✅ CONFIRMAR DELEÇÃO",
                        type="primary",
                        use_container_width=True,
                        key=f"btn_conf_del_{agendamento_id}",
                    ):
                        try:
                            # Delete logs primeiro (por causa da constraint)
                            supabase_execute(
                                lambda: supabase.table("tab_app_log_etapas")
                                .delete()
                                .eq("agendamento_id", agendamento_id)
                                .execute()
                            )

                            # Depois delete o agendamento
                            supabase_execute(
                                lambda: supabase.table("tab_app_agendamentos")
                                .delete()
                                .eq("id", agendamento_id)
                                .execute()
                            )

                            feedback("✅ Agendamento deletado com sucesso!", "success", "🗑️")
                            st.session_state[f"confirmar_delecao_{agendamento_id}"] = False
                            st.rerun()
                        except Exception as e:
                            feedback(f"❌ Erro ao deletar: {str(e)}", "error", "⚠️")

                with col_cancel:
                    if st.button("❌ Cancelar", use_container_width=True, key=f"btn_cancel_del_{agendamento_id}"):
                        st.session_state[f"confirmar_delecao_{agendamento_id}"] = False
                        st.rerun()

        else:
            st.info("👆 Selecione um agendamento na tabela acima para editar ou deletar")

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")
        import traceback
        st.code(traceback.format_exc())


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_agenda_edicao()