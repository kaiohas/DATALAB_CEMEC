# ============================================================
# 📜 frontend/pages/farmacia_lancamentos.py
# Lançamentos Realizados - Farmácia
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


def safe_date_value(value, fallback: date | None = None) -> date | None:
    """
    Converte value para date, sem retornar NaT.
    - Se não conseguir converter, retorna fallback (default: None)
    """
    if value in (None, "", "N/A"):
        return fallback
    try:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()

        dt = pd.to_datetime(value, errors="coerce")
        if pd.isna(dt):
            return fallback
        # dt pode ser Timestamp
        return dt.date()
    except Exception:
        return fallback


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


def page_farmacia_lancamentos():
    """Página para visualização e gerenciamento de lançamentos."""
    st.title("📜 Lançamentos Realizados - Farmácia")

    # ✅ Aviso pós-rerun (editar/deletar)
    if st.session_state.get("_farmacia_lanc_save_ok"):
        msg = st.session_state.get("_farmacia_lanc_save_msg") or "✅ Alteração realizada com sucesso!"
        when = st.session_state.get("_farmacia_lanc_save_when")

        try:
            st.toast(msg, icon="✅")
        except Exception:
            st.success(msg)

        if when:
            st.caption(f"Última ação: {when}")

        st.session_state.pop("_farmacia_lanc_save_ok", None)
        st.session_state.pop("_farmacia_lanc_save_msg", None)
        st.session_state.pop("_farmacia_lanc_save_when", None)

    try:
        supabase = get_supabase_client()

        # Busca movimentações
        resp_movs = supabase_execute(lambda: supabase.table(TABLE_MOVS).select("*").execute())
        df_movs = pd.DataFrame(resp_movs.data) if resp_movs.data else pd.DataFrame()

        if df_movs.empty:
            st.warning("Nenhum lançamento registrado.")
            return

        # Busca estudos
        resp_estudos = supabase_execute(
            lambda: supabase.table("tab_app_estudos").select("id_estudo, estudo").execute()
        )
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()

        # Busca produtos
        resp_produtos = supabase_execute(
            lambda: supabase.table("produtos").select("id, nome, tipo_produto").execute()
        )
        df_produtos = pd.DataFrame(resp_produtos.data) if resp_produtos.data else pd.DataFrame()

        # Variáveis para select
        resp_localizacao = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "localizacao").execute()
        )
        resp_tipo_acao = supabase_execute(
            lambda: supabase.table("tab_app_variaveis").select("valor").eq("uso", "tipo_de_acao").execute()
        )

        localizacoes = []
        if resp_localizacao.data and resp_localizacao.data[0].get("valor"):
            localizacoes = parse_variaveis(resp_localizacao.data[0]["valor"])

        tipos_acao = []
        if resp_tipo_acao.data and resp_tipo_acao.data[0].get("valor"):
            tipos_acao = parse_variaveis(resp_tipo_acao.data[0]["valor"])

        # Normaliza colunas
        df_movs.columns = [c.lower() for c in df_movs.columns]
        if not df_estudos.empty:
            df_estudos.columns = [c.lower() for c in df_estudos.columns]
        if not df_produtos.empty:
            df_produtos.columns = [c.lower() for c in df_produtos.columns]

        # Merges
        if not df_estudos.empty and "estudo_id" in df_movs.columns:
            df_movs = df_movs.merge(
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est"),
            ).rename(columns={"estudo": "nm_estudo"})

        if not df_produtos.empty and "produto_id" in df_movs.columns:
            df_movs = df_movs.merge(
                df_produtos,
                left_on="produto_id",
                right_on="id",
                how="left",
                suffixes=("", "_prod"),
            ).rename(columns={"nome": "nm_produto"})

        # Datas para filtro/exibição (blindado contra NaT)
        df_movs["data_dt"] = pd.to_datetime(df_movs.get("data"), errors="coerce")
        df_movs["data_brl"] = df_movs["data_dt"].apply(fmt_date)

        # validade é varchar no schema, então nem sempre é data -> blindar
        df_movs["validade_dt"] = pd.to_datetime(df_movs.get("validade"), errors="coerce")
        df_movs["validade_brl"] = df_movs["validade_dt"].apply(fmt_date)

        # Normaliza valores vazios
        for col in ["nm_estudo", "nm_produto", "validade_brl", "lote", "tipo_transacao", "tipo_produto"]:
            if col in df_movs.columns:
                df_movs[col] = df_movs[col].fillna("")

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            filtro_estudo = st.multiselect(
                "Estudo",
                sorted([x for x in df_movs.get("nm_estudo", pd.Series(dtype=str)).unique() if x]),
            )

        with c2:
            filtro_produto = st.multiselect(
                "Produto",
                sorted([x for x in df_movs.get("nm_produto", pd.Series(dtype=str)).unique() if x]),
            )

        with c3:
            filtro_tipo_transacao = st.multiselect(
                "Tipo de Transação",
                sorted([x for x in df_movs.get("tipo_transacao", pd.Series(dtype=str)).unique() if x]),
            )

        with c4:
            aplicar_periodo = st.checkbox("Filtrar por período?", value=False)

        df_view = df_movs.copy()

        if filtro_estudo and "nm_estudo" in df_view.columns:
            df_view = df_view[df_view["nm_estudo"].isin(filtro_estudo)]
        if filtro_produto and "nm_produto" in df_view.columns:
            df_view = df_view[df_view["nm_produto"].isin(filtro_produto)]
        if filtro_tipo_transacao and "tipo_transacao" in df_view.columns:
            df_view = df_view[df_view["tipo_transacao"].isin(filtro_tipo_transacao)]

        if aplicar_periodo:
            min_dt = df_view["data_dt"].min()
            max_dt = df_view["data_dt"].max()

            c5, c6 = st.columns(2)
            with c5:
                dt_ini = st.date_input(
                    "Data (Início)",
                    value=(min_dt.date() if pd.notna(min_dt) else date.today()),
                )
            with c6:
                dt_fim = st.date_input(
                    "Data (Fim)",
                    value=(max_dt.date() if pd.notna(max_dt) else date.today()),
                )

            df_view = df_view[
                (df_view["data_dt"] >= pd.to_datetime(dt_ini)) &
                (df_view["data_dt"] <= pd.to_datetime(dt_fim))
            ]

        if df_view.empty:
            st.info("Nenhum lançamento encontrado com os filtros atuais.")
            return

        # =====================================================
        # VISUALIZAÇÃO
        # =====================================================
        st.markdown("### 📋 Lançamentos")

        cols_order = [
            "id", "data_brl", "tipo_transacao", "nm_estudo", "nm_produto",
            "tipo_produto", "quantidade", "validade_brl", "lote", "nota",
            "tipo_acao", "consideracoes", "responsavel", "localizacao",
        ]
        cols_order = [c for c in cols_order if c in df_view.columns]

        df_show = df_view[cols_order].rename(columns={
            "id": "ID",
            "data_brl": "Data",
            "tipo_transacao": "Tipo",
            "nm_estudo": "Estudo",
            "nm_produto": "Produto",
            "tipo_produto": "Tipo de Produto",
            "quantidade": "Quantidade",
            "validade_brl": "Validade",
            "lote": "Lote",
            "nota": "Nota",
            "tipo_acao": "Tipo Ação",
            "consideracoes": "Considerações",
            "responsavel": "Responsável",
            "localizacao": "Localização",
        })

        st.dataframe(df_show, use_container_width=True, hide_index=True)

        excel_buffer = BytesIO()
        df_show.to_excel(excel_buffer, index=False, sheet_name="Dados")
        excel_buffer.seek(0)
        st.download_button(
            "📥 Baixar XLSX",
            data=excel_buffer,
            file_name="lancamentos_farmacia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        # =====================================================
        # BLOCO DE EDIÇÃO (DROP DOWN)
        # =====================================================
        st.markdown("---")
        st.markdown("### ✏️ Editar Lançamento")

        df_view.columns = [c.lower() for c in df_view.columns]

        opcoes = [
            f"[{int(r['id'])}] {r.get('nm_produto','')} ({r.get('data_brl','')})"
            for _, r in df_view.iterrows()
        ]
        sel_rotulo = st.selectbox("Selecione o lançamento para editar", opcoes)
        lancamento_id = int(sel_rotulo.split("]")[0].replace("[", ""))

        registro = df_movs[df_movs["id"] == lancamento_id].iloc[0]

        with st.expander("Dados do Lançamento", expanded=False):
            # defaults seguros
            data_edit_default = safe_date_value(registro.get("data"), fallback=date.today())

            validade_atual_str = (registro.get("validade") or "")
            validade_atual_date = safe_date_value(validade_atual_str, fallback=None)

            lote_atual = registro.get("lote") or ""
            nota_atual = registro.get("nota") or ""
            consideracoes_atual = registro.get("consideracoes") or ""

            tipo_transacao_atual = registro.get("tipo_transacao") or "Entrada"
            if tipo_transacao_atual not in ["Entrada", "Saída"]:
                tipo_transacao_atual = "Entrada"

            tipo_acao_atual = registro.get("tipo_acao") or ""
            localizacao_atual = registro.get("localizacao") or ""

            tipo_acao_opts = [""] + tipos_acao if tipos_acao else [""]
            localizacao_opts = [""] + localizacoes if localizacoes else [""]

            idx_tipo_acao = tipo_acao_opts.index(tipo_acao_atual) if tipo_acao_atual in tipo_acao_opts else 0
            idx_localizacao = localizacao_opts.index(localizacao_atual) if localizacao_atual in localizacao_opts else 0

            with st.form(f"form_edicao_{lancamento_id}"):
                col1, col2, col3 = st.columns(3)

                with col1:
                    data_edit = st.date_input("Data", value=data_edit_default)
                with col2:
                    tipo_transacao = st.selectbox(
                        "Tipo de Transação",
                        ["Entrada", "Saída"],
                        index=["Entrada", "Saída"].index(tipo_transacao_atual),
                    )
                with col3:
                    quantidade = st.number_input(
                        "Quantidade",
                        min_value=1,
                        value=int(registro.get("quantidade") or 1),
                        step=1,
                    )

                st.caption(
                    f"Produto: **{registro.get('nm_produto','—')}** "
                    f"({registro.get('nm_estudo','—')})"
                )

                c4, c5 = st.columns(2)
                with c4:
                    sem_validade = st.checkbox("Sem validade", value=(validade_atual_date is None))
                    if sem_validade:
                        validade_edit = None
                    else:
                        validade_edit = st.date_input(
                            "Validade",
                            value=(validade_atual_date or date.today()),
                        )
                with c5:
                    lote = st.text_input("Lote", value=lote_atual)

                nota = st.text_input("Nota Fiscal", value=nota_atual)

                c6, c7 = st.columns(2)
                with c6:
                    tipo_acao = st.selectbox("Tipo de Ação", tipo_acao_opts, index=idx_tipo_acao)
                with c7:
                    localizacao = st.selectbox("Localização", localizacao_opts, index=idx_localizacao)

                consideracoes = st.text_area("Considerações", value=consideracoes_atual)

                st.text_input("Responsável (não editável)", registro.get("responsavel", ""), disabled=True)

                submit = st.form_submit_button("Salvar Alterações")

                if submit:
                    try:
                        payload_update = {
                            "data": str(data_edit),
                            "tipo_transacao": tipo_transacao,
                            "quantidade": int(quantidade),
                            "validade": (str(validade_edit) if validade_edit else None),
                            "lote": lote if lote else None,
                            "nota": nota if nota else None,
                            "tipo_acao": tipo_acao if tipo_acao else None,
                            "consideracoes": consideracoes if consideracoes else None,
                            "localizacao": localizacao if localizacao else None,
                        }

                        supabase_execute(
                            lambda: supabase.table(TABLE_MOVS)
                            .update(payload_update)
                            .eq("id", lancamento_id)
                            .execute()
                        )

                        st.session_state["_farmacia_lanc_save_ok"] = True
                        st.session_state["_farmacia_lanc_save_msg"] = "✅ Lançamento atualizado com sucesso!"
                        st.session_state["_farmacia_lanc_save_when"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                        feedback("✅ Lançamento atualizado com sucesso!", "success", "💾")
                        st.rerun()

                    except Exception as e:
                        feedback(f"❌ Erro ao atualizar: {str(e)}", "error", "⚠️")

        # =====================================================
        # BLOCO DE DELEÇÃO
        # =====================================================
        st.markdown("---")
        st.markdown("### 🗑️ Deletar Lançamento")

        if st.button("❌ Deletar Lançamento", use_container_width=True):
            try:
                supabase_execute(lambda: supabase.table(TABLE_MOVS).delete().eq("id", lancamento_id).execute())

                st.session_state["_farmacia_lanc_save_ok"] = True
                st.session_state["_farmacia_lanc_save_msg"] = "✅ Lançamento deletado com sucesso!"
                st.session_state["_farmacia_lanc_save_when"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

                feedback("✅ Lançamento deletado com sucesso!", "success", "🗑️")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro ao deletar: {str(e)}", "error", "⚠️")

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_farmacia_lancamentos()