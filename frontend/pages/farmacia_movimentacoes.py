# ============================================================
# 📝 frontend/pages/farmacia_movimentacoes.py
# Registro de Movimentações - Farmácia
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


TABLE_MOVS = "tab_app_farmacia_movimentacoes"


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


def obter_saldo(estudo_id: int, produto_id: int, validade, lote) -> int:
    """
    Calcula o saldo atual de um produto considerando entradas e saídas.

    validade: date|datetime|str|None
    lote: str|None
    """
    try:
        supabase = get_supabase_client()

        query = supabase.table(TABLE_MOVS).select("tipo_transacao, quantidade")

        if estudo_id:
            query = query.eq("estudo_id", estudo_id)
        if produto_id:
            query = query.eq("produto_id", produto_id)

        if validade:
            query = query.eq("validade", str(validade))
        if lote:
            query = query.eq("lote", lote)

        resp = supabase_execute(lambda: query.execute())
        movs = resp.data or []

        entradas = sum(int(m.get("quantidade") or 0) for m in movs if m.get("tipo_transacao") == "Entrada")
        saidas = sum(int(m.get("quantidade") or 0) for m in movs if m.get("tipo_transacao") == "Saída")

        return entradas - saidas

    except Exception as e:
        st.error(f"Erro ao calcular saldo: {str(e)}")
        return 0


def page_farmacia_movimentacoes():
    """Página para registro de movimentações (entrada/saída)."""
    st.title("📝 Registro de Movimentações - Farmácia")

    # ✅ Mostra confirmação de gravação após rerun (igual agenda_gestao)
    if st.session_state.get("_farmacia_mov_save_ok"):
        msg = st.session_state.get("_farmacia_mov_save_msg") or "✅ Movimentação registrada com sucesso!"
        when = st.session_state.get("_farmacia_mov_save_when")

        try:
            st.toast(msg, icon="✅")
        except Exception:
            st.success(msg)

        if when:
            st.caption(f"Última gravação: {when}")

        st.session_state.pop("_farmacia_mov_save_ok", None)
        st.session_state.pop("_farmacia_mov_save_msg", None)
        st.session_state.pop("_farmacia_mov_save_when", None)

    try:
        supabase = get_supabase_client()
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")

        # =====================================================
        # CARREGAR DIMENSÕES
        # =====================================================
        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos").select("id_estudo, estudo").order("estudo").execute()
        )
        resp_produtos = supabase_execute(
            lambda: supabase.table("produtos").select("id, nome, estudo_id, tipo_produto").order("nome").execute()
        )
        resp_localizacao = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "localizacao").execute()
        )
        resp_tipo_acao = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "tipo_de_acao").execute()
        )

        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        df_produtos = pd.DataFrame(resp_produtos.data) if resp_produtos.data else pd.DataFrame()

        if not df_estudos.empty:
            df_estudos.columns = [c.lower() for c in df_estudos.columns]
        if not df_produtos.empty:
            df_produtos.columns = [c.lower() for c in df_produtos.columns]

        localizacoes = []
        if resp_localizacao.data and resp_localizacao.data[0].get("valor"):
            localizacoes = parse_variaveis(resp_localizacao.data[0]["valor"])

        tipos_acao = []
        if resp_tipo_acao.data and resp_tipo_acao.data[0].get("valor"):
            tipos_acao = parse_variaveis(resp_tipo_acao.data[0]["valor"])

        # =====================================================
        # FORM (SEM st.form): dependências ao vivo (Estudo -> Produto)
        # =====================================================
        st.markdown("### 📋 Registrar Nova Movimentação")

        col1, col2 = st.columns(2)

        with col1:
            tipo_transacao = st.selectbox(
                "Tipo de Transação",
                ["Entrada", "Saída"],
                key="tipo_transacao",
            )

            estudo_sel = st.selectbox(
                "Estudo",
                df_estudos["estudo"].tolist() if not df_estudos.empty else [],
                key="estudo_sel",
            )
            estudo_id = None
            if estudo_sel and not df_estudos.empty:
                estudo_id = int(df_estudos.loc[df_estudos["estudo"] == estudo_sel, "id_estudo"].values[0])

        with col2:
            data_acao = date.today()
            st.info(f"Data da Ação: **{fmt_date(data_acao)}**")

            quantidade = st.number_input(
                "Quantidade",
                min_value=1,
                step=1,
                key="quantidade",
            )

        # Produtos filtrados pelo estudo
        df_produtos_filtrados = df_produtos.copy()
        if (estudo_id is not None) and (not df_produtos_filtrados.empty) and ("estudo_id" in df_produtos_filtrados.columns):
            df_produtos_filtrados = df_produtos_filtrados[df_produtos_filtrados["estudo_id"] == estudo_id]

        produto_sel = st.selectbox(
            "Produto",
            df_produtos_filtrados["nome"].tolist() if not df_produtos_filtrados.empty else [],
            key="produto_sel",
        )

        produto_id = None
        tipo_produto = ""
        if produto_sel and not df_produtos_filtrados.empty:
            row_prod = df_produtos_filtrados[df_produtos_filtrados["nome"] == produto_sel].iloc[0]
            produto_id = int(row_prod["id"])
            tipo_produto = str(row_prod.get("tipo_produto") or "")

        st.markdown(f"**Tipo de Produto:** {tipo_produto if tipo_produto else '-'}")

        # Campos dependentes
        validade = None
        lote = None

        if tipo_transacao == "Entrada":
            cva, cvb = st.columns([1, 2])
            with cva:
                sem_validade = st.checkbox(
                    "Sem validade",
                    value=True,
                    help="Desmarque para informar uma data de validade.",
                    key="sem_validade",
                )
            with cvb:
                if sem_validade:
                    validade = None
                else:
                    validade = st.date_input("Validade", value=date.today(), key="validade_entrada")

            lote = st.text_input("Lote", key="lote_entrada")

        else:
            resp_base = supabase_execute(
                lambda: supabase.table(TABLE_MOVS).select("validade, lote, estudo_id, produto_id").execute()
            )
            df_base = pd.DataFrame(resp_base.data) if resp_base.data else pd.DataFrame()

            if not df_base.empty:
                df_base.columns = [c.lower() for c in df_base.columns]

                if (estudo_id is not None) and ("estudo_id" in df_base.columns):
                    df_base = df_base[df_base["estudo_id"] == estudo_id]
                else:
                    df_base = df_base.iloc[0:0]

                if (produto_id is not None) and ("produto_id" in df_base.columns):
                    df_base = df_base[df_base["produto_id"] == produto_id]
                else:
                    df_base = df_base.iloc[0:0]

            if not df_base.empty and "validade" in df_base.columns:
                vdates = pd.to_datetime(df_base["validade"], errors="coerce").dt.date.dropna().drop_duplicates().sort_values().tolist()
            else:
                vdates = []

            validade_labels = ["Sem validade"] + [fmt_date(d) for d in vdates]
            validade_map = {"Sem validade": None}
            validade_map.update({fmt_date(d): d for d in vdates})

            validade_label = st.selectbox("Validade", validade_labels, key="validade_saida_label")
            validade = validade_map.get(validade_label)

            if not df_base.empty and "lote" in df_base.columns:
                lotes = df_base["lote"].dropna().drop_duplicates().sort_values().astype(str).tolist()
            else:
                lotes = []

            lote_sel = st.selectbox("Lote", ["—"] + lotes, key="lote_saida_sel")
            lote = None if lote_sel == "—" else lote_sel

            if (estudo_id is not None) and (produto_id is not None):
                saldo_preview = obter_saldo(estudo_id, produto_id, validade, lote)
                st.caption(
                    f"Saldo disponível para **{produto_sel or '—'}** | "
                    f"**Validade:** {fmt_date(validade)} | **Lote:** {lote or '—'} → "
                    f"**{int(saldo_preview)}**"
                )

        nota = st.text_input("Nota Fiscal", key="nota")
        tipo_acao_sel = st.selectbox(
            "Tipo de Ação",
            [""] + tipos_acao if tipos_acao else [""],
            key="tipo_acao_sel",
        )
        consideracoes = st.text_area("Considerações", key="consideracoes")
        localizacao = st.selectbox(
            "Localização",
            [""] + localizacoes if localizacoes else [""],
            key="localizacao_sel",
        )

        st.caption(f"Responsável: **{usuario_logado}**")

        # ---------------------------
        # SALVAR
        # ---------------------------
        if st.button("Salvar Movimentação", type="primary", use_container_width=True):
            if (estudo_id is None) or (produto_id is None):
                st.error("Selecione **Estudo** e **Produto**.")
                st.stop()

            if tipo_transacao == "Saída":
                saldo_atual = obter_saldo(estudo_id, produto_id, validade, lote)
                if quantidade > (saldo_atual or 0):
                    st.error(
                        f"Não foi possível registrar a saída: quantidade informada (**{int(quantidade)}**) "
                        f"excede o saldo disponível (**{int(saldo_atual or 0)}**)\n\n"
                        f"**Produto:** {produto_sel or '—'} | **Validade:** {fmt_date(validade)} | **Lote:** {lote or '—'}"
                    )
                    st.stop()

            payload = {
                "data": data_acao.isoformat(),  # coluna é DATE
                "tipo_transacao": tipo_transacao,
                "estudo_id": estudo_id,
                "produto_id": produto_id,
                "tipo_produto": tipo_produto if tipo_produto else None,
                "quantidade": int(quantidade),
                "validade": str(validade) if validade else None,
                "lote": lote if lote else None,
                "nota": nota if nota else None,
                "tipo_acao": tipo_acao_sel if tipo_acao_sel else None,
                "consideracoes": consideracoes if consideracoes else None,
                "responsavel": usuario_logado,
                "localizacao": localizacao if localizacao else None,
            }

            try:
                supabase_execute(lambda: supabase.table(TABLE_MOVS).insert(payload).execute())

                # ✅ sinaliza sucesso para aparecer após rerun
                st.session_state["_farmacia_mov_save_ok"] = True
                st.session_state["_farmacia_mov_save_msg"] = "✅ Movimentação registrada com sucesso!"
                st.session_state["_farmacia_mov_save_when"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                feedback("✅ Movimentação registrada com sucesso!", "success", "🎉")
                st.rerun()
            except Exception as e:
                feedback(f"❌ Erro ao salvar movimentação: {e}", "error", "⚠️")

        # =====================================================
        # HISTÓRICO
        # =====================================================
        st.markdown("---")
        st.markdown("### 📜 Histórico de Movimentações")

        try:
            resp_movs = supabase_execute(
                lambda: supabase.table(TABLE_MOVS).select("*").order("data", desc=True).limit(100).execute()
            )
            df_movs = pd.DataFrame(resp_movs.data) if resp_movs.data else pd.DataFrame()

            if not df_movs.empty:
                df_movs.columns = [c.lower() for c in df_movs.columns]

                if not df_estudos.empty:
                    df_movs = df_movs.merge(
                        df_estudos,
                        left_on="estudo_id",
                        right_on="id_estudo",
                        how="left",
                        suffixes=("", "_est"),
                    ).rename(columns={"estudo": "nm_estudo"})

                if not df_produtos.empty:
                    df_movs = df_movs.merge(
                        df_produtos,
                        left_on="produto_id",
                        right_on="id",
                        how="left",
                        suffixes=("", "_prod"),
                    ).rename(columns={"nome": "nm_produto"})

                if "data" in df_movs.columns:
                    df_movs["data_dt"] = pd.to_datetime(df_movs["data"], errors="coerce")
                    df_movs["Data (BR)"] = df_movs["data_dt"].apply(fmt_date)

                if "validade" in df_movs.columns:
                    df_movs["validade_dt"] = pd.to_datetime(df_movs["validade"], errors="coerce")
                    df_movs["Validade (BR)"] = df_movs["validade_dt"].apply(fmt_date)

                cols_display = [
                    "id", "Data (BR)", "tipo_transacao", "nm_estudo", "nm_produto",
                    "tipo_produto", "quantidade", "Validade (BR)", "lote",
                    "tipo_acao", "responsavel", "localizacao",
                ]
                cols_display = [c for c in cols_display if c in df_movs.columns]

                df_display = df_movs[cols_display].copy()
                df_display.columns = [
                    "ID", "Data", "Tipo", "Estudo", "Produto",
                    "Tipo Produto", "Quantidade", "Validade", "Lote",
                    "Tipo Ação", "Responsável", "Localização",
                ][: len(cols_display)]

                st.dataframe(df_display, use_container_width=True, hide_index=True)

                excel_buffer = BytesIO()
                df_display.to_excel(excel_buffer, index=False, sheet_name="Dados")
                excel_buffer.seek(0)
                st.download_button(
                    "📥 Baixar Histórico (XLSX)",
                    data=excel_buffer,
                    file_name="movimentacoes_farmacia.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
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