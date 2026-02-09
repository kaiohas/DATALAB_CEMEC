# ============================================================
# 📝 frontend/pages/farmacia_movimentacoes.py
# Registro de Movimentações - Farmácia
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, datetime
from frontend.supabase_client import get_supabase_client
from frontend.components.feedback import feedback


def fmt_date(d) -> str:
    """Formata date/datetime/str para dd/mm/aaaa."""
    if d in (None, "", "N/A"):
        return "—"
    try:
        if isinstance(d, (date, datetime)):
            return d.strftime("%d/%m/%Y")
        dt = pd.to_datetime(d, errors="coerce")
        if pd.isna(dt):
            return str(d)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def obter_saldo(estudo_id: int, produto_id: int, validade: str, lote: str) -> int:
    """Calcula o saldo atual de um produto considerando entradas e saídas."""
    try:
        supabase = get_supabase_client()
        
        query = supabase.table("movimentacoes").select("tipo_transacao, quantidade")
        
        if estudo_id:
            query = query.eq("estudo_id", estudo_id)
        if produto_id:
            query = query.eq("produto_id", produto_id)
        if validade:
            query = query.eq("validade", validade)
        if lote:
            query = query.eq("lote", lote)
        
        resp = query.execute()
        movs = resp.data or []
        
        entradas = sum(m.get("quantidade", 0) for m in movs if m.get("tipo_transacao") == "Entrada")
        saidas = sum(m.get("quantidade", 0) for m in movs if m.get("tipo_transacao") == "Saída")
        
        return entradas - saidas
    
    except Exception as e:
        st.error(f"Erro ao calcular saldo: {str(e)}")
        return 0


def parse_variaveis(valor_str: str) -> list:
    """Parse de valores a partir de uma string."""
    if not valor_str:
        return []
    
    if "\n" in valor_str:
        valores = [v.strip() for v in valor_str.split("\n") if v.strip()]
    elif ";" in valor_str:
        valores = [v.strip() for v in valor_str.split(";") if v.strip()]
    elif "," in valor_str:
        valores = [v.strip() for v in valor_str.split(",") if v.strip()]
    else:
        valores = [valor_str.strip()]
    
    return valores


def page_farmacia_movimentacoes():
    """Página para registro de movimentações (entrada/saída)."""
    st.title("📝 Registro de Movimentações - Farmácia")
    
    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")
        
        # Busca dados
        resp_estudos = supabase.table("tab_app_estudos").select("id_estudo, estudo").execute()
        resp_produtos = supabase.table("produtos").select("id, nome, estudo_id, tipo_produto").execute()
        resp_localizacao = supabase.table("tab_app_variaveis").select("valor").eq("uso", "localizacao").execute()
        resp_tipo_acao = supabase.table("tab_app_variaveis").select("valor").eq("uso", "tipo_de_acao").execute()
        
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_produtos = pd.DataFrame(resp_produtos.data) if resp_produtos.data else pd.DataFrame()
        
        # Normaliza colunas
        df_estudos.columns = [c.lower() for c in df_estudos.columns]
        df_produtos.columns = [c.lower() for c in df_produtos.columns]
        
        # Parse variáveis
        localizacoes = []
        if resp_localizacao.data and resp_localizacao.data[0].get("valor"):
            localizacoes = parse_variaveis(resp_localizacao.data[0]["valor"])
        
        tipos_acao = []
        if resp_tipo_acao.data and resp_tipo_acao.data[0].get("valor"):
            tipos_acao = parse_variaveis(resp_tipo_acao.data[0]["valor"])
        
        # =====================================================
        # FORMULÁRIO DE MOVIMENTAÇÃO
        # =====================================================
        st.markdown("### 📋 Registrar Nova Movimentação")
        
        with st.form("form_movimentacao"):
            col1, col2 = st.columns(2)
            
            with col1:
                tipo_transacao = st.selectbox(
                    "Tipo de Transação",
                    ["Entrada", "Saída"],
                    help="Selecione se é entrada ou saída de produto"
                )
            
            with col2:
                st.info(f"Data da Movimentação: **{fmt_date(date.today())}**")
            
            # Seleção de estudo
            estudo_sel = st.selectbox(
                "Estudo",
                df_estudos["estudo"].tolist() if not df_estudos.empty else [],
                help="Selecione o estudo"
            )
            
            estudo_id = None
            if estudo_sel and not df_estudos.empty:
                estudo_id = int(df_estudos[df_estudos["estudo"] == estudo_sel].iloc[0]["id_estudo"])
            
            # Filtra produtos pelo estudo
            df_produtos_filtrados = df_produtos.copy()
            if estudo_id:
                df_produtos_filtrados = df_produtos_filtrados[df_produtos_filtrados["estudo_id"] == estudo_id]
            
            produto_sel = st.selectbox(
                "Produto",
                df_produtos_filtrados["nome"].tolist() if not df_produtos_filtrados.empty else [],
                help="Selecione o produto"
            )
            
            produto_id = None
            if produto_sel and not df_produtos_filtrados.empty:
                produto_id = int(df_produtos_filtrados[df_produtos_filtrados["nome"] == produto_sel].iloc[0]["id"])
            
            # Detalhes da movimentação
            col3, col4 = st.columns(2)
            
            with col3:
                quantidade = st.number_input(
                    "Quantidade",
                    min_value=1,
                    step=1,
                    help="Quantidade a registrar"
                )
            
            with col4:
                validade = st.date_input(
                    "Data de Validade",
                    value=date.today(),
                    help="Data de validade do produto"
                )
            
            col5, col6 = st.columns(2)
            
            with col5:
                lote = st.text_input(
                    "Lote",
                    placeholder="ex: 123456",
                    help="Número do lote (opcional)"
                )
            
            with col6:
                localizacao = st.selectbox(
                    "Localização",
                    [""] + localizacoes if localizacoes else [""],
                    help="Onde o produto está armazenado"
                )
            
            tipo_acao = st.selectbox(
                "Tipo de Ação",
                [""] + tipos_acao if tipos_acao else [""],
                help="Tipo de ação realizada"
            )
            
            col7, col8 = st.columns(2)
            
            with col7:
                nota = st.text_input(
                    "Nota",
                    placeholder="Observações adicionais",
                    help="Anotações sobre a movimentação"
                )
            
            with col8:
                consideracoes = st.text_input(
                    "Considerações",
                    placeholder="Outras observações",
                    help="Considerações adicionais"
                )
            
            if st.form_submit_button("✅ Registrar Movimentação", use_container_width=True):
                if not estudo_sel or not produto_sel or not quantidade:
                    st.error("⚠️ Estudo, Produto e Quantidade são obrigatórios")
                else:
                    try:
                        # Validação para saída
                        if tipo_transacao == "Saída":
                            saldo_atual = obter_saldo(estudo_id, produto_id, str(validade), lote)
                            if quantidade > saldo_atual:
                                st.error(
                                    f"❌ Quantidade informada ({quantidade}) excede o saldo disponível ({saldo_atual})\n\n"
                                    f"**Produto:** {produto_sel} | **Validade:** {fmt_date(validade)} | **Lote:** {lote or '—'}"
                                )
                                st.stop()
                        
                        # Insere movimentação
                        payload = {
                            "data": str(date.today()),
                            "tipo_transacao": tipo_transacao,
                            "estudo_id": estudo_id,
                            "produto_id": produto_id,
                            "quantidade": int(quantidade),
                            "validade": str(validade),
                            "lote": lote if lote else None,
                            "nota": nota if nota else None,
                            "tipo_acao": tipo_acao if tipo_acao else None,
                            "consideracoes": consideracoes if consideracoes else None,
                            "responsavel": usuario_logado,
                            "localizacao": localizacao if localizacao else None
                        }
                        
                        supabase.table("movimentacoes").insert(payload).execute()
                        
                        feedback(
                            f"✅ Movimentação de {tipo_transacao.lower()} registrada com sucesso!",
                            "success",
                            "🎉"
                        )
                        st.rerun()
                        
                    except Exception as e:
                        feedback(f"❌ Erro ao registrar: {str(e)}", "error", "⚠️")
        
        # =====================================================
        # HISTÓRICO DE MOVIMENTAÇÕES
        # =====================================================
        st.markdown("---")
        st.markdown("### 📜 Histórico de Movimentações")
        
        try:
            resp_movs = supabase.table("movimentacoes").select("*").order("data", desc=True).limit(100).execute()
            df_movs = pd.DataFrame(resp_movs.data) if resp_movs.data else pd.DataFrame()
            
            if not df_movs.empty:
                df_movs.columns = [c.lower() for c in df_movs.columns]
                
                # Merge com estudos
                if not df_estudos.empty:
                    df_movs = df_movs.merge(
                        df_estudos,
                        left_on="estudo_id",
                        right_on="id_estudo",
                        how="left",
                        suffixes=("", "_est")
                    ).rename(columns={"estudo": "nm_estudo"})
                
                # Merge com produtos
                if not df_produtos.empty:
                    df_movs = df_movs.merge(
                        df_produtos,
                        left_on="produto_id",
                        right_on="id",
                        how="left",
                        suffixes=("", "_prod")
                    ).rename(columns={"nome": "nm_produto"})
                
                # Formata datas
                df_movs["data_dt"] = pd.to_datetime(df_movs["data"], errors="coerce")
                df_movs["Data (BR)"] = df_movs["data_dt"].apply(fmt_date)
                
                df_movs["validade_dt"] = pd.to_datetime(df_movs["validade"], errors="coerce")
                df_movs["Validade (BR)"] = df_movs["validade_dt"].apply(fmt_date)
                
                # Seleciona colunas para exibição
                cols_display = ["id", "Data (BR)", "tipo_transacao", "nm_estudo", "nm_produto", 
                               "quantidade", "Validade (BR)", "lote", "tipo_acao", "responsavel", "localizacao"]
                
                df_display = df_movs[cols_display].copy()
                df_display.columns = ["ID", "Data", "Tipo", "Estudo", "Produto", "Quantidade", "Validade", "Lote", "Tipo Ação", "Responsável", "Localização"]
                
                st.dataframe(
                    df_display,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Download CSV
                csv = df_display.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 Baixar Histórico (CSV)",
                    data=csv,
                    file_name="movimentacoes_farmacia.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.info("Nenhuma movimentação registrada ainda.")
        
        except Exception as e:
            feedback(f"❌ Erro ao carregar histórico: {str(e)}", "error", "⚠️")
    
    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_farmacia_movimentacoes()