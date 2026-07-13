# ============================================================
# 💊 frontend/pages/modelo_kits.py
# Modelo de Dispensação de Kits
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback

TABLE_MOVS   = "tab_app_farmacia_movimentacoes"
TABLE_MODELO = "tab_app_modelo_kits"


# ============================================================
# HELPERS
# ============================================================

def _parse_variaveis(valor_str: str) -> list:
    if not valor_str:
        return []
    valor_str = valor_str.strip('"').strip("'")
    for sep in [";", "\n", ","]:
        if sep in valor_str:
            return [v.strip() for v in valor_str.split(sep) if v.strip()]
    return [valor_str.strip()]


# ============================================================
# CACHE FETCHERS
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def _fetch_estudos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("id_estudo, estudo")
        .order("estudo")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_kits_catalogo(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("produtos")
        .select("id, nome, estudo_id")
        .eq("tipo_produto", "Kit")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_relacao_visita_kit(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_relacao_visita_kit")
        .select("id_estudo, visita, kit_type")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_agendamentos_range(_supabase, data_ini_str, data_fim_str):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_agendamentos")
        .select("id, data_visita, estudo_id, visita")
        .gte("data_visita", data_ini_str)
        .lte("data_visita", data_fim_str)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_saldo_lotes(_supabase, ids_produto: tuple) -> pd.DataFrame:
    """Saldo por produto+lote+validade, considerando só lotes não vencidos com saldo > 0."""
    cols = ["produto_id", "lote", "validade", "saldo"]
    if not ids_produto:
        return pd.DataFrame(columns=cols)
    resp = supabase_execute(
        lambda: _supabase.table(TABLE_MOVS)
        .select("produto_id, tipo_transacao, quantidade, validade, lote")
        .in_("produto_id", list(ids_produto))
        .execute()
    )
    if not resp.data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(resp.data)
    df.columns = [c.lower() for c in df.columns]

    validade_dt = pd.to_datetime(df["validade"], errors="coerce")
    nao_vencido = validade_dt.isna() | (validade_dt.dt.date >= date.today())
    df = df[nao_vencido].copy()
    df["lote"] = df["lote"].fillna("")
    df["validade"] = df["validade"].fillna("")

    quantidade = pd.to_numeric(df["quantidade"], errors="coerce").fillna(0)
    sinal = df["tipo_transacao"].map({"Entrada": 1, "Saída": -1}).fillna(0)
    df["qtd_sinal"] = quantidade * sinal

    agrupado = (
        df.groupby(["produto_id", "lote", "validade"], dropna=False)["qtd_sinal"]
        .sum()
        .reset_index()
        .rename(columns={"qtd_sinal": "saldo"})
    )
    agrupado["saldo"] = agrupado["saldo"].astype(int)
    return agrupado[agrupado["saldo"] > 0].reset_index(drop=True)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_modelo_kits_existentes(_supabase, data_ini_str, data_fim_str):
    resp = supabase_execute(
        lambda: _supabase.table(TABLE_MODELO)
        .select("*")
        .gte("data_visita", data_ini_str)
        .lte("data_visita", data_fim_str)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_opcoes_desfecho(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_variaveis")
        .select("valor")
        .eq("uso", "opcoes_desfecho")
        .execute()
    )
    return _parse_variaveis(resp.data[0]["valor"]) if resp.data else []


def _invalidar_cache():
    _fetch_modelo_kits_existentes.clear()
    _fetch_saldo_lotes.clear()


# ============================================================
# PÁGINA
# ============================================================

def page_modelo_kits():
    st.title("💊 Modelo de Kits")
    st.caption("Planejamento e dispensação de kits para as visitas agendadas.")

    try:
        _page_modelo_kits_body()
    except Exception as e:
        st.error(f"❌ Erro ao carregar página: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


def _page_modelo_kits_body():
    supabase = get_supabase_client()
    df_estudos       = _fetch_estudos(supabase)
    df_kits_catalogo = _fetch_kits_catalogo(supabase)
    df_rvk           = _fetch_relacao_visita_kit(supabase)
    opcoes_desfecho  = _fetch_opcoes_desfecho(supabase)

    if df_estudos.empty:
        st.warning("Nenhum estudo cadastrado.")
        return

    # =====================================================
    # FILTROS
    # =====================================================
    st.markdown("### 🔍 Filtros")
    fc1, fc2, fc3, fc4 = st.columns(4)

    with fc1:
        data_range_sel = st.date_input(
            "Data da Visita",
            value=(date.today(), date.today() + timedelta(days=7)),
            format="DD/MM/YYYY",
        )
    with fc2:
        estudos_opts = sorted(df_estudos["estudo"].dropna().unique().tolist())
        estudos_sel = st.multiselect("Estudo(s)", options=estudos_opts, default=[], placeholder="Todos")
    with fc3:
        kits_opts = sorted(df_kits_catalogo["nome"].dropna().unique().tolist()) if not df_kits_catalogo.empty else []
        kits_sel = st.multiselect("Kit Type", options=kits_opts, default=[], placeholder="Todos")
    with fc4:
        V_TODOS, V_COM, V_SEM = "(Todos)", "Com Kit vinculado", "Sem Kit vinculado"
        vinculo_sel = st.selectbox("Vínculo de Kit", [V_TODOS, V_COM, V_SEM])

    if isinstance(data_range_sel, (list, tuple)) and len(data_range_sel) == 2:
        data_ini, data_fim = data_range_sel
    else:
        data_ini = data_fim = data_range_sel[0] if isinstance(data_range_sel, (list, tuple)) else data_range_sel
    if data_ini > data_fim:
        data_ini, data_fim = data_fim, data_ini

    # =====================================================
    # AGENDAMENTOS NO RANGE
    # =====================================================
    df_ag = _fetch_agendamentos_range(supabase, str(data_ini), str(data_fim))
    if df_ag.empty:
        st.info("Nenhum agendamento encontrado no período selecionado.")
        return

    estudo_id_to_nome = dict(zip(df_estudos["id_estudo"], df_estudos["estudo"]))
    df_ag["nm_estudo"] = df_ag["estudo_id"].map(estudo_id_to_nome)
    df_ag = df_ag[df_ag["nm_estudo"].notna()]

    if estudos_sel:
        df_ag = df_ag[df_ag["nm_estudo"].isin(estudos_sel)]

    if df_ag.empty:
        st.info("Nenhum agendamento encontrado para os filtros selecionados.")
        return

    # =====================================================
    # RESOLVER KIT POR VISITA, DEPOIS AGRUPAR (DATA, ESTUDO, KIT) -> QUANTIDADE VISITAS
    # =====================================================
    # Passo 1: conta por (data, estudo, visita) - nível granular, necessário
    # pra resolver o kit_type de cada visita individualmente.
    contagem_visita = (
        df_ag.groupby(["data_visita", "estudo_id", "nm_estudo", "visita"], dropna=False)
        .size()
        .reset_index(name="qtd")
    )

    rvk_map = {}
    if not df_rvk.empty:
        for _, r in df_rvk.iterrows():
            if pd.notna(r.get("kit_type")):
                rvk_map[(r["id_estudo"], str(r["visita"]).strip())] = int(r["kit_type"])

    contagem_visita["kit_type"] = contagem_visita.apply(
        lambda r: rvk_map.get((r["estudo_id"], str(r["visita"]).strip())), axis=1
    )

    # Passo 2: re-agrupa por (data, estudo, kit) somando as visitas — visitas
    # diferentes que resolvem pro mesmo kit (ou que ficam todas sem kit) viram 1 linha só.
    agrupado = (
        contagem_visita.groupby(["data_visita", "estudo_id", "nm_estudo", "kit_type"], dropna=False)["qtd"]
        .sum()
        .reset_index(name="quantidade_visitas")
    )

    kit_id_to_nome = (
        dict(zip(df_kits_catalogo["id"], df_kits_catalogo["nome"])) if not df_kits_catalogo.empty else {}
    )

    # =====================================================
    # EXPANDIR POR LOTE/VALIDADE (só kits resolvidos)
    # =====================================================
    ids_kits_resolvidos = tuple(int(k) for k in agrupado["kit_type"].dropna().unique())
    df_saldo = _fetch_saldo_lotes(supabase, ids_kits_resolvidos)

    linhas = []
    for _, row in agrupado.iterrows():
        base = {
            "data_visita":        row["data_visita"],
            "id_estudo":          int(row["estudo_id"]),
            "nm_estudo":          row["nm_estudo"],
            "quantidade_visitas": int(row["quantidade_visitas"]),
        }
        kit_type = row["kit_type"]
        if pd.isna(kit_type):
            linhas.append({
                **base, "kit_type": None, "kit_nome": None, "validade": None, "lote": None,
                "quantidade_estoque": None, "kit_resolvido": False,
            })
            continue

        kit_type = int(kit_type)
        lotes = df_saldo[df_saldo["produto_id"] == kit_type] if not df_saldo.empty else pd.DataFrame()
        if lotes.empty:
            linhas.append({
                **base, "kit_type": kit_type, "kit_nome": kit_id_to_nome.get(kit_type),
                "validade": None, "lote": None, "quantidade_estoque": 0, "kit_resolvido": True,
            })
        else:
            for _, lote_row in lotes.iterrows():
                linhas.append({
                    **base,
                    "kit_type":            kit_type,
                    "kit_nome":            kit_id_to_nome.get(kit_type),
                    "validade":            lote_row["validade"] or None,
                    "lote":                lote_row["lote"] or None,
                    "quantidade_estoque":  int(lote_row["saldo"]),
                    "kit_resolvido":       True,
                })

    df_matriz = pd.DataFrame(linhas)
    if df_matriz.empty:
        st.info("Nenhum registro para os filtros selecionados.")
        return

    if kits_sel:
        df_matriz = df_matriz[df_matriz["kit_nome"].isin(kits_sel)]
    if vinculo_sel == V_COM:
        df_matriz = df_matriz[df_matriz["kit_resolvido"]]
    elif vinculo_sel == V_SEM:
        df_matriz = df_matriz[~df_matriz["kit_resolvido"]]

    if df_matriz.empty:
        st.info("Nenhum registro para os filtros selecionados.")
        return

    # =====================================================
    # PRÉ-PREENCHER COM O QUE JÁ FOI SALVO ANTES
    # =====================================================
    df_existentes = _fetch_modelo_kits_existentes(supabase, str(data_ini), str(data_fim))

    def _buscar_existente(row):
        if df_existentes.empty:
            return None
        cond = (
            (df_existentes["data_visita"] == str(row["data_visita"])) &
            (df_existentes["id_estudo"] == row["id_estudo"])
        )
        if row["kit_type"] is not None:
            cond &= (df_existentes["kit_type"] == row["kit_type"])
        else:
            cond &= df_existentes["kit_type"].isna()
        if row["validade"]:
            cond &= (df_existentes["validade"] == row["validade"])
        else:
            cond &= df_existentes["validade"].isna()
        if row["lote"]:
            cond &= (df_existentes["lote"] == row["lote"])
        else:
            cond &= (df_existentes["lote"].isna() | (df_existentes["lote"] == ""))
        match = df_existentes[cond]
        return match.iloc[0] if not match.empty else None

    dispensado_originais, desfecho_originais = [], []
    for _, row in df_matriz.iterrows():
        existente = _buscar_existente(row)
        if existente is not None:
            dispensado_originais.append(int(existente.get("dispensado") or 0))
            desfecho_originais.append(existente.get("desfecho") or "")
        else:
            dispensado_originais.append(0)
            desfecho_originais.append("")

    df_matriz["_dispensado_original"] = dispensado_originais
    df_matriz["_desfecho_original"]   = desfecho_originais
    df_matriz["dispensado"] = dispensado_originais
    df_matriz["desfecho"]   = desfecho_originais

    df_matriz = df_matriz.sort_values(
        ["data_visita", "nm_estudo", "kit_nome"], na_position="last"
    ).reset_index(drop=True)
    df_matriz["data_fmt"] = pd.to_datetime(df_matriz["data_visita"]).dt.strftime("%d/%m/%Y")

    # =====================================================
    # MATRIZ EDITÁVEL
    # =====================================================
    st.markdown("---")
    st.markdown("### 📋 Matriz de Dispensação")
    st.caption(f"**Total:** {len(df_matriz)} linha(s)")

    col_map = {
        "data_fmt":            "Data",
        "nm_estudo":           "Estudo",
        "kit_nome":            "Kit Type",
        "validade":            "Validade",
        "lote":                "Lote",
        "quantidade_visitas":  "Quantidade Visitas",
        "quantidade_estoque":  "Quantidade Estoque",
        "dispensado":          "Dispensado",
        "desfecho":            "Desfecho",
    }
    df_editor = df_matriz[list(col_map)].rename(columns=col_map)

    edited = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=[
            "Data", "Estudo", "Kit Type", "Validade", "Lote",
            "Quantidade Visitas", "Quantidade Estoque",
        ],
        column_config={
            "Dispensado": st.column_config.NumberColumn(min_value=0, step=1),
            "Desfecho": st.column_config.SelectboxColumn(options=[""] + opcoes_desfecho),
        },
        key="editor_modelo_kits",
    )

    if st.button("💾 Gravar", type="primary", use_container_width=True):
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")
        erros = []
        alterados = 0

        for idx in df_matriz.index:
            row = df_matriz.loc[idx]
            novo_dispensado = int(edited.loc[idx, "Dispensado"] or 0)
            novo_desfecho = edited.loc[idx, "Desfecho"] or ""
            dispensado_original = int(row["_dispensado_original"] or 0)
            desfecho_original = row["_desfecho_original"] or ""

            if novo_dispensado == dispensado_original and novo_desfecho == desfecho_original:
                continue

            rotulo = f"{row['nm_estudo']} / {row['kit_nome'] or '(sem kit)'} / {row['data_fmt']}"

            if novo_dispensado > 0 and not row["kit_resolvido"]:
                erros.append(f"{rotulo}: não é possível dispensar sem Kit Type vinculado.")
                continue

            delta = novo_dispensado - dispensado_original
            if delta > 0:
                estoque = row["quantidade_estoque"]
                if pd.isna(estoque) or delta > estoque:
                    disponivel = 0 if pd.isna(estoque) else int(estoque)
                    erros.append(f"{rotulo}: quer adicionar {delta} un., mas só há {disponivel} em estoque.")
                    continue

            kit_type_row = None if pd.isna(row["kit_type"]) else int(row["kit_type"])
            validade_row = row["validade"] or None
            lote_row     = row["lote"] or None

            try:
                def _buscar():
                    q = (
                        supabase.table(TABLE_MODELO)
                        .select("id")
                        .eq("data_visita", str(row["data_visita"]))
                        .eq("id_estudo", int(row["id_estudo"]))
                    )
                    q = q.eq("kit_type", kit_type_row) if kit_type_row is not None else q.is_("kit_type", "null")
                    q = q.eq("validade", validade_row) if validade_row else q.is_("validade", "null")
                    q = q.eq("lote", lote_row) if lote_row else q.is_("lote", "null")
                    return q.execute()

                existente_resp = supabase_execute(_buscar)

                payload = {
                    "data_visita":        str(row["data_visita"]),
                    "id_estudo":          int(row["id_estudo"]),
                    "kit_type":           kit_type_row,
                    "validade":           validade_row,
                    "lote":               lote_row,
                    "quantidade_visitas": int(row["quantidade_visitas"]),
                    "dispensado":         novo_dispensado,
                    "desfecho":           novo_desfecho or None,
                    "responsavel":        usuario_logado,
                    "dt_atualizacao":     pd.Timestamp.now(tz="UTC").isoformat(),
                }

                if existente_resp.data:
                    reg_id = existente_resp.data[0]["id"]
                    supabase_execute(
                        lambda: supabase.table(TABLE_MODELO).update(payload).eq("id", reg_id).execute()
                    )
                else:
                    supabase_execute(
                        lambda: supabase.table(TABLE_MODELO).insert(payload).execute()
                    )

                if delta != 0 and kit_type_row is not None:
                    supabase_execute(
                        lambda: supabase.table(TABLE_MOVS).insert({
                            "data":           str(date.today()),
                            "tipo_transacao": "Saída" if delta > 0 else "Entrada",
                            "estudo_id":      int(row["id_estudo"]),
                            "produto_id":     kit_type_row,
                            "tipo_produto":   "Kit",
                            "quantidade":     abs(delta),
                            "validade":       validade_row,
                            "lote":           lote_row,
                            "nota":           None,
                            "tipo_acao":      "Distribuição enfermagem",
                            "consideracoes":  None,
                            "responsavel":    usuario_logado,
                            "localizacao":    "Enfermagem",
                        }).execute()
                    )

                alterados += 1
            except Exception as e:
                erros.append(f"{rotulo}: {e}")

        _invalidar_cache()

        if alterados:
            feedback(f"✅ {alterados} registro(s) gravado(s) com sucesso!", "success", "💾")
        for e in erros:
            st.error(f"⚠️ {e}")
        if alterados and not erros:
            st.rerun()
