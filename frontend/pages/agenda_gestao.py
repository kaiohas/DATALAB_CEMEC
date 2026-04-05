# ============================================================
# 🧭 frontend/pages/agenda_gestao.py
# Gestão de Agendamentos
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


def page_agenda_gestao():
    """Página de gestão de agendamentos."""
    st.title("🧭 Gestão de Agendamentos")

    # ✅ Mostra confirmação de gravação após rerun
    if st.session_state.get("_agenda_gestao_save_ok"):
        ag_id = st.session_state.get("_agenda_gestao_save_agendamento_id")
        when = st.session_state.get("_agenda_gestao_save_when")

        # toast (se disponível) + fallback
        try:
            st.toast(f"✅ Alterações gravadas com sucesso (Agendamento {ag_id})", icon="✅")
        except Exception:
            st.success(f"✅ Alterações gravadas com sucesso (Agendamento {ag_id})")

        if when:
            st.caption(f"Última gravação: {when}")

        # limpa para não repetir
        st.session_state.pop("_agenda_gestao_save_ok", None)
        st.session_state.pop("_agenda_gestao_save_agendamento_id", None)
        st.session_state.pop("_agenda_gestao_save_when", None)

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # ✅ BUSCAR ID DO USUÁRIO NO BANCO
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
        # BUSCAR VARIÁVEIS DOS DEPARTAMENTOS
        # =====================================================
        resp_status_medico = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "status_medico").execute()
        )
        resp_status_enfermagem = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "status_enfermagem").execute()
        )
        resp_status_farmacia = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "status_farmacia").execute()
        )
        resp_status_espirometria = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "status_espirometria").execute()
        )
        resp_status_nutricionista = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "status_nutricionista").execute()
        )
        resp_desfecho = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "desfecho_atendimento").execute()
        )

        status_medico_list = parse_variaveis(resp_status_medico.data[0]["valor"]) if resp_status_medico.data else []
        status_enfermagem_list = parse_variaveis(resp_status_enfermagem.data[0]["valor"]) if resp_status_enfermagem.data else []
        status_farmacia_list = parse_variaveis(resp_status_farmacia.data[0]["valor"]) if resp_status_farmacia.data else []
        status_espirometria_list = parse_variaveis(resp_status_espirometria.data[0]["valor"]) if resp_status_espirometria.data else []
        status_nutricionista_list = parse_variaveis(resp_status_nutricionista.data[0]["valor"]) if resp_status_nutricionista.data else []
        desfecho_list = parse_variaveis(resp_desfecho.data[0]["valor"]) if resp_desfecho.data else []

        # =====================================================
        # BUSCAR ESTUDOS
        # =====================================================
        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos").select("id_estudo, estudo, coordenacao").execute()
        )
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        if not df_estudos.empty:
            df_estudos.columns = [c.lower() for c in df_estudos.columns]

        # =====================================================
        # BUSCAR AGENDAMENTOS (SEM FILTRO DE CONFIRMADO)
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

        fc1, fc2, fc3, fc4 = st.columns(4)

        with fc1:
            estudos_vinculados = sorted([x for x in df_view.get("nm_estudo", pd.Series(dtype=str)).unique() if x])
            estudo_sel = st.selectbox("Estudo", ["(Todos)"] + estudos_vinculados, index=0)

        with fc2:
            status_unicos = sorted([x for x in df_view.get("status_confirmacao", pd.Series(dtype=str)).dropna().unique() if x])
            status_sel = st.selectbox("Status Confirmação", ["(Todos)"] + status_unicos, index=0)

        with fc3:
            dt_ini = st.date_input("Data (Início)")

        with fc4:
            dt_fim = st.date_input("Data (Fim)")

        # Aplicar filtros adicionais
        if estudo_sel != "(Todos)" and "nm_estudo" in df_view.columns:
            df_view = df_view[df_view["nm_estudo"] == estudo_sel]

        if status_sel != "(Todos)" and "status_confirmacao" in df_view.columns:
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
        st.markdown("### 📋 Clique na linha para atualizar status dos departamentos")

        cols_display = [
            "id", "data_visita_br", "nm_estudo", "id_paciente", "nome_paciente",
            "hora_chegada", "tipo_visita", "visita", "medico_responsavel", "status_confirmacao"
        ]

        cols_rename = {
            "id": "ID",
            "data_visita_br": "Data",
            "nm_estudo": "Estudo",
            "id_paciente": "ID Paciente",
            "nome_paciente": "Paciente",
            "hora_chegada": "Hora Chegada",
            "tipo_visita": "Tipo Visita",
            "visita": "Visita",
            "medico_responsavel": "Médico",
            "status_confirmacao": "Status",
        }
        cols_existentes = [col for col in cols_display if col in df_view.columns]
        if not cols_existentes:
            cols_existentes = [c for c in df_view.columns if c not in ("data_visita_dt", "data_visita")]
            cols_rename = {}
        df_grid = df_view[cols_existentes].copy()
        df_grid.rename(columns=cols_rename, inplace=True)

        # =====================================================
        # CONFIGURAR AGGRID
        # =====================================================
        gb = GridOptionsBuilder.from_dataframe(df_grid)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_selection(selection_mode="single", use_checkbox=False)

        # Configurar colunas
        if "ID" in df_grid.columns:
            gb.configure_column("ID", width=50)
        if "Data" in df_grid.columns:
            gb.configure_column("Data", width=80)
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
        if "Médico" in df_grid.columns:
            gb.configure_column("Médico", width=130)
        if "Status" in df_grid.columns:
            gb.configure_column("Status", width=150)

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
            theme="light",
        )

        selected_rows = grid_response["selected_rows"]

        # =====================================================
        # BLOCO DE ATUALIZAÇÃO DE STATUS (baseado na seleção)
        # =====================================================
        if selected_rows is not None and len(selected_rows) > 0:
            selected_row = selected_rows.iloc[0]
            agendamento_id = int(selected_row["ID"])

            # Busca o agendamento completo
            agendamento_data = df_view[df_view["id"] == agendamento_id].iloc[0]

            st.markdown("---")
            st.markdown("### ✏️ Atualizar Status dos Departamentos")

            # Exibir detalhes do agendamento selecionado
            st.markdown("#### 📌 Detalhes do Agendamento Selecionado")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.info(f"**Paciente:** {agendamento_data.get('nome_paciente', '—')}")
                st.info(f"**ID Paciente:** {agendamento_data.get('id_paciente', '—')}")
                st.info(f"**Status:** {agendamento_data.get('status_confirmacao', '—')}")

            with col2:
                st.info(f"**Data:** {agendamento_data.get('data_visita_br', '—')}")
                st.info(f"**Estudo:** {agendamento_data.get('nm_estudo', '—')}")
                st.info(f"**Tipo Visita:** {agendamento_data.get('tipo_visita', '—')}")

            with col3:
                st.info(f"**Médico:** {agendamento_data.get('medico_responsavel', '—')}")
                st.info(f"**Consultório:** {agendamento_data.get('consultorio', '—')}")

            # ✅ EXIBIR obs_visita E obs_coleta (SOMENTE LEITURA)
            st.markdown("#### 📝 Observações")

            col_obs1, col_obs2 = st.columns(2)

            with col_obs1:
                obs_visita = agendamento_data.get("obs_visita") or "—"
                st.info(f"**Obs. Visita:**\n{obs_visita}")

            with col_obs2:
                obs_coleta = agendamento_data.get("obs_coleta") or "—"
                st.info(f"**Obs. Coleta:**\n{obs_coleta}")

            st.markdown("---")

            # ✅ OBTER VALORES ATUAIS DOS STATUS
            status_medico_atual = agendamento_data.get("status_medico") or ""
            status_enfermagem_atual = agendamento_data.get("status_enfermagem") or ""
            status_farmacia_atual = agendamento_data.get("status_farmacia") or ""
            status_espirometria_atual = agendamento_data.get("status_espirometria") or ""
            status_nutricionista_atual = agendamento_data.get("status_nutricionista") or ""
            hora_chegada_atual = agendamento_data.get("hora_chegada") or ""
            hora_saida_atual = agendamento_data.get("hora_saida") or ""
            desfecho_atual = agendamento_data.get("desfecho_atendimento") or ""
            valor_uber_atual = agendamento_data.get("valor_uber") or ""

            # Formulário para atualizar status
            with st.form(f"form_status_{agendamento_id}"):
                st.markdown("#### 🏥 Status dos Departamentos")

                # ✅ PRIMEIRO: Hora chegada e Valor Uber
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
                    st.write("")

                # ✅ DEPOIS: status na ordem pedida
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

                # ✅ HORA SAÍDA E DESFECHO
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
                    )

                st.markdown("---")

                if st.form_submit_button("💾 Atualizar Status", use_container_width=True):
                    payload = {}
                    logs_para_inserir = []

                    timestamp_agora = datetime.now(timezone.utc).isoformat()

                    # ✅ Hora chegada (time)
                    if hora_chegada:
                        novo_hora_chegada = hora_chegada.isoformat()
                        if novo_hora_chegada != (hora_chegada_atual or ""):
                            payload["hora_chegada"] = novo_hora_chegada
                    else:
                        # Permite limpar
                        if hora_chegada_atual:
                            payload["hora_chegada"] = None

                    # ✅ LÓGICA: Se status foi alterado, registra no log
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

                    # CAMPOS ADICIONAIS
                    if hora_saida:
                        payload["hora_saida"] = hora_saida.isoformat()
                    else:
                        # Permite limpar
                        if hora_saida_atual:
                            payload["hora_saida"] = None

                    if desfecho:
                        payload["desfecho_atendimento"] = desfecho

                    # ✅ VALOR UBER
                    if valor_uber != valor_uber_atual:
                        payload["valor_uber"] = valor_uber if valor_uber else None

                    if payload:
                        try:
                            # 1️⃣ Atualiza agendamento
                            supabase_execute(
                                lambda: supabase.table("tab_app_agendamentos")
                                .update(payload)
                                .eq("id", agendamento_id)
                                .execute()
                            )

                            # 2️⃣ Insere logs das mudanças
                            for log in logs_para_inserir:
                                supabase_execute(
                                    lambda log=log: supabase.table("tab_app_log_etapas").insert(log).execute()
                                )

                            # ✅ sinaliza sucesso para aparecer após rerun
                            st.session_state["_agenda_gestao_save_ok"] = True
                            st.session_state["_agenda_gestao_save_agendamento_id"] = agendamento_id
                            st.session_state["_agenda_gestao_save_when"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                            feedback("✅ Status atualizado e logs registrados com sucesso!", "success", "💾")
                            st.rerun()

                        except Exception as e:
                            feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")
                    else:
                        st.warning("⚠️ Nenhuma alteração detectada")

            # =====================================================
            # 📜 TABELA DE LOG DE ETAPAS
            # =====================================================
            st.markdown("---")
            st.markdown("### 📜 Histórico de Etapas")

            resp_logs = supabase_execute(
                lambda: supabase.table("tab_app_log_etapas")
                .select("*")
                .eq("agendamento_id", agendamento_id)
                .order("data_hora_etapa", desc=True)
                .execute()
            )
            df_logs = pd.DataFrame(resp_logs.data) if resp_logs.data else pd.DataFrame()

            if not df_logs.empty:
                df_logs.columns = [c.lower() for c in df_logs.columns]
                df_logs["data_hora_etapa"] = pd.to_datetime(df_logs["data_hora_etapa"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M:%S")

                df_logs_display = df_logs[["nome_etapa", "status_etapa", "data_hora_etapa", "usuario_nome"]].copy()
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