# ============================================================
# 📚 frontend/pages/dimensoes_tabs/aba_estudos.py
# Gestão de Estudos
# ============================================================
import streamlit as st
import pandas as pd
from frontend.supabase_client import get_supabase_client
from frontend.components.feedback import feedback


@st.cache_data(ttl=300)
def load_variaveis_por_uso():
    """Carrega variáveis agrupadas por uso para facilitar seleção."""
    try:
        supabase = get_supabase_client()
        response = supabase.table("tab_app_variaveis").select("uso, valor").execute()
        
        variaveis_dict = {}
        if response.data:
            for row in response.data:
                uso = row.get("uso")
                valor = row.get("valor")
                if uso and valor:
                    # Parse dos valores (suporta \n, vírgula, ponto-vírgula)
                    valores_list = parse_valores(valor)
                    variaveis_dict[uso] = valores_list
        
        return variaveis_dict
    except Exception as e:
        st.error(f"Erro ao carregar variáveis: {e}")
        return {}


def parse_valores(valor_str: str) -> list:
    """
    Parse de valores a partir de uma string.
    Suporta múltiplos separadores: \n, , ou ;
    """
    if not valor_str:
        return []
    
    # Trata diferentes separadores
    # Primeiro tenta \n (quebra de linha)
    if "\n" in valor_str:
        valores = [v.strip() for v in valor_str.split("\n") if v.strip()]
    # Depois tenta ; (ponto-vírgula)
    elif ";" in valor_str:
        valores = [v.strip() for v in valor_str.split(";") if v.strip()]
    # Depois tenta , (vírgula)
    elif "," in valor_str:
        valores = [v.strip() for v in valor_str.split(",") if v.strip()]
    # Se nenhum separador, retorna como item único
    else:
        valores = [valor_str.strip()]
    
    return valores


def aba_estudos(usuario_logado: str):
    st.subheader("📚 Gestão de Estudos")

    try:
        supabase = get_supabase_client()
        
        # Busca todos os estudos
        response = supabase.table("tab_app_estudos").select("*").order("estudo").execute()
        df_estudos = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        
    except Exception as e:
        feedback(f"❌ Erro ao carregar estudos: {e}", "error", "⚠️")
        return

    # Carrega variáveis disponíveis
    variaveis = load_variaveis_por_uso()

    # =====================================================
    # 👁️ VISUALIZAÇÃO
    # =====================================================
    st.markdown("### 👁️ Estudos Cadastrados")
    
    if not df_estudos.empty:
        df_estudos.columns = [c.lower() for c in df_estudos.columns]
        
        # Adiciona coluna de status
        df_display = df_estudos.copy()
        df_display["status"] = df_display["sn_ativo"].apply(lambda x: "🟢 Ativo" if x else "🔴 Inativo")
        
        st.dataframe(
            df_display[["estudo", "cod_estudo", "centro", "coordenacao", "disciplina", "coordenador", "status"]],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhum estudo cadastrado ainda.")

    # =====================================================
    # ➕ CRIAR NOVO ESTUDO
    # =====================================================
    st.markdown("---")
    st.markdown("### ➕ Criar Novo Estudo")
    
    with st.form("form_novo_estudo"):
        col1, col2 = st.columns(2)
        
        with col1:
            estudo = st.text_input(
                "Nome do Estudo (único)",
                placeholder="ex: Estudo ABC 2024",
                help="Identificador único do estudo"
            )
            cod_estudo = st.text_input(
                "Código do Estudo",
                placeholder="ex: ESTUDO-001"
            )
        
        with col2:
            # Centro - com parse correto
            centro_valores = variaveis.get("centro", [])
            centro = st.selectbox(
                "Centro",
                [""] + centro_valores if centro_valores else [""],
                help="Valor vem da variável 'centro'"
            )
            
            # Disciplina - com parse correto
            disciplina_valores = variaveis.get("disciplina", [])
            disciplina = st.selectbox(
                "Disciplina",
                [""] + disciplina_valores if disciplina_valores else [""],
                help="Valor vem da variável 'disciplina'"
            )
        
        col3, col4 = st.columns(2)
        
        with col3:
            id_centro = st.text_input("ID Centro")
            
            # Coordenação - com parse correto
            coordenacao_valores = variaveis.get("coordenacao", [])
            coordenacao = st.selectbox(
                "Coordenação",
                [""] + coordenacao_valores if coordenacao_valores else [""],
                help="Valor vem da variável 'coordenacao'"
            )
        
        with col4:
            coordenador = st.text_input("Coordenador")
            pi = st.text_input("PI (Pesquisador Principal)")
        
        col5, col6 = st.columns(2)
        
        with col5:
            # Patrocinador - com parse correto
            patrocinador_valores = variaveis.get("patrocinador", [])
            patrocinador = st.selectbox(
                "Patrocinador",
                [""] + patrocinador_valores if patrocinador_valores else [""],
                help="Valor vem da variável 'patrocinador'"
            )
            
            # Entrada Dados Modelo - com parse correto
            entrada_modelo_valores = variaveis.get("entrada_dados_modelo", [])
            entrada_dados_modelo = st.selectbox(
                "Entrada Dados Modelo",
                [""] + entrada_modelo_valores if entrada_modelo_valores else [""],
                help="Valor vem da variável 'entrada_dados_modelo'"
            )
        
        with col6:
            entrada_dados_dias = st.text_input("Entrada Dados Dias")
            
            # Resolução Modelo - com parse correto
            resolucao_modelo_valores = variaveis.get("resolucao_modelo", [])
            resolucao_modelo = st.selectbox(
                "Resolução Modelo",
                [""] + resolucao_modelo_valores if resolucao_modelo_valores else [""],
                help="Valor vem da variável 'resolucao_modelo'"
            )
        
        resolucao_dias = st.text_input("Resolução Dias")
        
        if st.form_submit_button("✅ Criar Estudo", use_container_width=True):
            if not estudo:
                st.error("⚠️ Nome do estudo é obrigatório")
            else:
                try:
                    supabase = get_supabase_client()
                    
                    # Verifica se estudo já existe
                    existing = supabase.table("tab_app_estudos").select("id_estudo").eq("estudo", estudo).execute()
                    if existing.data:
                        st.error("❌ Este estudo já existe")
                        return
                    
                    # Cria novo estudo
                    supabase.table("tab_app_estudos").insert({
                        "estudo": estudo,
                        "cod_estudo": cod_estudo if cod_estudo else None,
                        "centro": centro if centro else None,
                        "id_centro": id_centro if id_centro else None,
                        "disciplina": disciplina if disciplina else None,
                        "coordenacao": coordenacao if coordenacao else None,
                        "coordenador": coordenador if coordenador else None,
                        "pi": pi if pi else None,
                        "patrocinador": patrocinador if patrocinador else None,
                        "entrada_dados_modelo": entrada_dados_modelo if entrada_dados_modelo else None,
                        "entrada_dados_dias": entrada_dados_dias if entrada_dados_dias else None,
                        "resolucao_modelo": resolucao_modelo if resolucao_modelo else None,
                        "resolucao_dias": resolucao_dias if resolucao_dias else None,
                        "sn_ativo": True
                    }).execute()
                    
                    feedback(f"✅ Estudo '{estudo}' criado com sucesso!", "success", "🎉")
                    st.rerun()
                    
                except Exception as e:
                    feedback(f"❌ Erro ao criar estudo: {e}", "error", "⚠️")

    # =====================================================
    # ✏️ EDITAR ESTUDO
    # =====================================================
    st.markdown("---")
    st.markdown("### ✏️ Editar Estudo")
    
    if not df_estudos.empty:
        df_estudos.columns = [c.lower() for c in df_estudos.columns]
        estudo_sel = st.selectbox("Selecione um estudo", df_estudos["estudo"].tolist())
        
        if estudo_sel:
            estudo_data = df_estudos[df_estudos["estudo"] == estudo_sel].iloc[0]
            
            with st.form(f"form_editar_{estudo_sel}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    novo_cod = st.text_input("Código do Estudo", value=estudo_data.get("cod_estudo", ""))
                    novo_centro = st.text_input("Centro", value=estudo_data.get("centro", ""))
                    novo_disciplina = st.text_input("Disciplina", value=estudo_data.get("disciplina", ""))
                
                with col2:
                    novo_coordenacao = st.text_input("Coordenação", value=estudo_data.get("coordenacao", ""))
                    novo_coordenador = st.text_input("Coordenador", value=estudo_data.get("coordenador", ""))
                    novo_pi = st.text_input("PI", value=estudo_data.get("pi", ""))
                
                col3, col4 = st.columns(2)
                
                with col3:
                    novo_patrocinador = st.text_input("Patrocinador", value=estudo_data.get("patrocinador", ""))
                    novo_entrada_modelo = st.text_input("Entrada Dados Modelo", value=estudo_data.get("entrada_dados_modelo", ""))
                
                with col4:
                    novo_entrada_dias = st.text_input("Entrada Dados Dias", value=estudo_data.get("entrada_dados_dias", ""))
                    novo_resolucao_modelo = st.text_input("Resolução Modelo", value=estudo_data.get("resolucao_modelo", ""))
                
                novo_resolucao_dias = st.text_input("Resolução Dias", value=estudo_data.get("resolucao_dias", ""))
                novo_status = st.checkbox("Ativo", value=bool(estudo_data.get("sn_ativo", True)))
                
                if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
                    try:
                        supabase = get_supabase_client()
                        supabase.table("tab_app_estudos").update({
                            "cod_estudo": novo_cod if novo_cod else None,
                            "centro": novo_centro if novo_centro else None,
                            "disciplina": novo_disciplina if novo_disciplina else None,
                            "coordenacao": novo_coordenacao if novo_coordenacao else None,
                            "coordenador": novo_coordenador if novo_coordenador else None,
                            "pi": novo_pi if novo_pi else None,
                            "patrocinador": novo_patrocinador if novo_patrocinador else None,
                            "entrada_dados_modelo": novo_entrada_modelo if novo_entrada_modelo else None,
                            "entrada_dados_dias": novo_entrada_dias if novo_entrada_dias else None,
                            "resolucao_modelo": novo_resolucao_modelo if novo_resolucao_modelo else None,
                            "resolucao_dias": novo_resolucao_dias if novo_resolucao_dias else None,
                            "sn_ativo": novo_status
                        }).eq("estudo", estudo_sel).execute()
                        
                        feedback(f"✅ Estudo '{estudo_sel}' atualizado!", "success", "💾")
                        st.rerun()
                        
                    except Exception as e:
                        feedback(f"❌ Erro ao atualizar: {e}", "error", "⚠️")