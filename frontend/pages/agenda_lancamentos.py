# ============================================================
# 📝 frontend/pages/agenda_lancamentos.py
# Lançamento de Agendamentos
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date
from frontend.supabase_client import get_supabase_client
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


def calc_programacao(data_cad: date, data_visita: date) -> str:
    """Calcula tipo de programação baseado nas datas."""
    if not (data_cad and data_visita):
        return None
    
    delta = (data_visita - data_cad).days
    
    if delta < 1:
        return "Não Programada"
    elif delta <= 7:
        return "Extraordinário"
    elif delta <= 15:
        return "Incluída"
    else:
        return "Programada"


def page_agenda_lancamentos():
    """Página para lançamento de novos agendamentos."""
    st.title("📝 Lançamento de Agendamentos")
    
    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")
        
        # ✅ BUSCAR ID DO USUÁRIO NO BANCO
        resp_usuario = supabase.table("tab_app_usuarios").select("id_usuario").eq("nm_usuario", usuario_logado.lower().strip()).execute()
        
        if not resp_usuario.data:
            st.error("❌ Usuário não encontrado no sistema")
            st.stop()
        
        usuario_id = resp_usuario.data[0]["id_usuario"]
        
        # Busca dados das variáveis
        resp_estudos = supabase.table("tab_app_estudos").select("id_estudo, estudo, coordenacao").execute()
        resp_tipo_visita = supabase.table("tab_app_variaveis").select("valor").eq("uso", "tipo_visita").execute()
        resp_medico = supabase.table("tab_app_variaveis").select("valor").eq("uso", "medico_responsavel").execute()
        resp_consultorio = supabase.table("tab_app_variaveis").select("valor").eq("uso", "consultorio").execute()
        resp_jejum = supabase.table("tab_app_variaveis").select("valor").eq("uso", "jejum").execute()
        resp_reembolso = supabase.table("tab_app_variaveis").select("valor").eq("uso", "reembolso").execute()
        resp_visita = supabase.table("tab_app_variaveis").select("valor").eq("uso", "visita").execute()
        
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_estudos.columns = [c.lower() for c in df_estudos.columns]
        
        # Parse variáveis
        tipos_visita = parse_variaveis(resp_tipo_visita.data[0]["valor"]) if resp_tipo_visita.data else []
        medicos = parse_variaveis(resp_medico.data[0]["valor"]) if resp_medico.data else []
        consultorios = parse_variaveis(resp_consultorio.data[0]["valor"]) if resp_consultorio.data else []
        jejuns = parse_variaveis(resp_jejum.data[0]["valor"]) if resp_jejum.data else []
        reembolsos = parse_variaveis(resp_reembolso.data[0]["valor"]) if resp_reembolso.data else []
        visitas = parse_variaveis(resp_visita.data[0]["valor"]) if resp_visita.data else []
        
        # =====================================================
        # FORMULÁRIO DE CADASTRO
        # =====================================================
        st.markdown("### ➕ Cadastrar Novo Agendamento")
        
        with st.form("form_novo_agendamento"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                data_visita = st.date_input(
                    "Data da Visita",
                    value=date.today(),
                    help="Data agendada para a visita"
                )
            
            with col2:
                hora_consulta = st.time_input(
                    "Hora da Consulta",
                    help="Horário da consulta"
                )
            
            with col3:
                estudo_options = [f"[{int(row['id_estudo'])}] {row['estudo']}" for _, row in df_estudos.iterrows()] if not df_estudos.empty else []
                estudo_sel_label = st.selectbox(
                    "Estudo",
                    estudo_options if estudo_options else [""],
                    help="Selecione o estudo"
                )
                
                # Extrai informações do estudo selecionado
                estudo_id = None
                coordenacao_estudo = None
                if estudo_sel_label and "[" in estudo_sel_label:
                    estudo_id_str = estudo_sel_label.split("]")[0].replace("[", "")
                    estudo_id = int(estudo_id_str)
                    estudo_row = df_estudos[df_estudos["id_estudo"] == estudo_id]
                    if not estudo_row.empty:
                        coordenacao_estudo = estudo_row.iloc[0].get("coordenacao")
            
            # ✅ REMOVIDO: Exibição de coordenação do estudo
            
            # Dados do paciente
            col4, col5 = st.columns(2)
            
            with col4:
                id_paciente = st.text_input(
                    "ID Paciente",
                    placeholder="ex: P001",
                    help="Identificador único do paciente"
                )
            
            with col5:
                nome_paciente = st.text_input(
                    "Nome do Paciente",
                    placeholder="ex: João Silva",
                    help="Nome completo do paciente"
                )
            
            # Informações clínicas
            col6, col7, col8 = st.columns(3)
            
            with col6:
                tipo_visita_sel = st.selectbox(
                    "Tipo de Visita",
                    [""] + tipos_visita if tipos_visita else [""],
                    help="Tipo de visita (presencial, remota, etc)",
                    key="tipo_visita"
                )
            
            with col7:
                visita_sel = st.selectbox(
                    "Visita",
                    [""] + visitas if visitas else [""],
                    help="Qual visita é esta (V.1, V.2, etc)",
                    key="visita"
                )
            
            with col8:
                medico_sel = st.selectbox(
                    "Médico Responsável",
                    [""] + medicos if medicos else [""],
                    help="Médico responsável pelo agendamento",
                    key="medico"
                )
            
            # Mais informações
            col9, col10, col11 = st.columns(3)
            
            with col9:
                consultorio_sel = st.selectbox(
                    "Consultório",
                    [""] + consultorios if consultorios else [""],
                    help="Consultório onde será realizado",
                    key="consultorio"
                )
            
            with col10:
                jejum_sel = st.selectbox(
                    "Jejum",
                    [""] + jejuns if jejuns else [""],
                    help="Status de jejum do paciente",
                    key="jejum"
                )
            
            with col11:
                reembolso_sel = st.selectbox(
                    "Reembolso",
                    [""] + reembolsos if reembolsos else [""],
                    help="Tipo de reembolso",
                    key="reembolso"
                )
            
            # Campos adicionais
            col12, col13 = st.columns(2)
            
            with col12:
                valor_financeiro = st.number_input(
                    "Valor Financeiro",
                    min_value=0.0,
                    step=0.01,
                    help="Valor financeiro do agendamento"
                )
            
            with col13:
                horario_uber = st.time_input(
                    "Horário Uber",
                    help="Horário programado para Uber (opcional)"
                )
            
            # Observações
            obs_visita = st.text_area(
                "Observações da Visita",
                placeholder="Anotações sobre a visita",
                height=80
            )
            
            obs_coleta = st.text_area(
                "Observações da Coleta",
                placeholder="Anotações sobre coleta",
                height=80
            )
            
            if st.form_submit_button("✅ Cadastrar Agendamento", use_container_width=True):
                if not (data_visita and estudo_id and id_paciente and nome_paciente):
                    st.error("⚠️ Data da Visita, Estudo, ID e Nome do Paciente são obrigatórios")
                else:
                    try:
                        # Calcula programação
                        programacao = calc_programacao(date.today(), data_visita)
                        
                        # Monta payload
                        payload = {
                            "data_visita": str(data_visita),
                            "hora_consulta": str(hora_consulta) if hora_consulta else None,
                            "estudo_id": estudo_id,
                            "id_paciente": id_paciente,
                            "nome_paciente": nome_paciente,
                            "tipo_visita": tipo_visita_sel if tipo_visita_sel else None,
                            "visita": visita_sel if visita_sel else None,
                            "medico_responsavel": medico_sel if medico_sel else None,
                            "consultorio": consultorio_sel if consultorio_sel else None,
                            "jejum": jejum_sel if jejum_sel else None,
                            "reembolso": reembolso_sel if reembolso_sel else None,
                            "coordenacao": coordenacao_estudo,
                            "valor_financeiro": float(valor_financeiro) if valor_financeiro > 0 else None,
                            "horario_uber": str(horario_uber) if horario_uber else None,
                            "obs_visita": obs_visita.strip() if obs_visita else None,
                            "obs_coleta": obs_coleta.strip() if obs_coleta else None,
                            "responsavel_agendamento_id": usuario_id,
                            "responsavel_agendamento_nome": usuario_logado,
                            "programacao": programacao,
                            "status_confirmacao": None
                        }
                        
                        supabase.table("tab_app_agendamentos").insert(payload).execute()
                        
                        feedback("✅ Agendamento cadastrado com sucesso!", "success", "🎉")
                        st.rerun()
                        
                    except Exception as e:
                        feedback(f"❌ Erro ao cadastrar: {str(e)}", "error", "⚠️")
        
        # =====================================================
        # VISUALIZAÇÃO DE AGENDAMENTOS
        # =====================================================
        st.markdown("---")
        st.markdown("### 👁️ Agendamentos Cadastrados")
        
        try:
            resp_agendamentos = supabase.table("tab_app_agendamentos").select("*").order("data_visita", desc=True).limit(100).execute()
            df_agendamentos = pd.DataFrame(resp_agendamentos.data) if resp_agendamentos.data else pd.DataFrame()
            
            if not df_agendamentos.empty:
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
                
                # Seleciona colunas para exibição
                cols_display = [
                    "data_visita", "nm_estudo", "id_paciente", "nome_paciente",
                    "tipo_visita", "visita", "medico_responsavel", "consultorio",
                    "status_confirmacao"
                ]
                
                # Verifica quais colunas existem
                cols_existentes = [col for col in cols_display if col in df_agendamentos.columns]
                
                df_display = df_agendamentos[cols_existentes].copy()
                df_display.columns = [
                    "Data Visita", "Estudo", "ID Paciente", "Nome Paciente",
                    "Tipo Visita", "Visita", "Médico", "Consultório", "Status Confirmação"
                ][:len(cols_existentes)]
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download CSV
                csv = df_display.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 Baixar CSV",
                    data=csv,
                    file_name="agendamentos.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("Nenhum agendamento cadastrado ainda.")
        
        except Exception as e:
            feedback(f"❌ Erro ao carregar agendamentos: {str(e)}", "error", "⚠️")
    
    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_agenda_lancamentos()