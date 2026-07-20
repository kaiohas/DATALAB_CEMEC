# ============================================================
# 🚚 frontend/pages/relacao_visita_kit.py
# Relação Visita x Kit (por Estudo)
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback

TABLE_MOVS = "tab_app_farmacia_movimentacoes"


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
def _fetch_variaveis(_supabase):
    usos = ["visita", "opcoes_envio", "opcoes_temperatura", "opcoes_laboratorio", "opcoes_courier"]
    result = {}
    for uso in usos:
        resp = supabase_execute(
            lambda uso=uso: _supabase.table("tab_app_variaveis")
            .select("valor")
            .eq("uso", uso)
            .execute()
        )
        result[uso] = _parse_variaveis(resp.data[0]["valor"]) if resp.data else []
    return result


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_kits(_supabase, id_estudo: int):
    resp = supabase_execute(
        lambda: _supabase.table("produtos")
        .select("id, nome")
        .eq("estudo_id", id_estudo)
        .eq("tipo_produto", "Kit")
        .order("nome")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_relacoes(_supabase, id_estudo: int):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_relacao_visita_kit")
        .select("*")
        .eq("id_estudo", id_estudo)
        .order("visita")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_relacoes_todas(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_relacao_visita_kit")
        .select("*")
        .order("id_estudo")
        .order("visita")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_todos_kits(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("produtos")
        .select("id, nome")
        .eq("tipo_produto", "Kit")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_saldo_kits(_supabase, ids_produto: tuple) -> dict:
    """Saldo (Entradas - Saídas) por produto, considerando só lotes não vencidos.

    Produtos sem nenhuma movimentação na farmácia ficam de fora do dict (célula
    vazia na tabela); produtos com movimentação mas saldo não-vencido nulo
    (ex: todos os lotes vencidos) entram com valor 0.
    """
    if not ids_produto:
        return {}
    resp = supabase_execute(
        lambda: _supabase.table(TABLE_MOVS)
        .select("produto_id, tipo_transacao, quantidade, validade")
        .in_("produto_id", list(ids_produto))
        .execute()
    )
    if not resp.data:
        return {}
    df = pd.DataFrame(resp.data)
    df.columns = [c.lower() for c in df.columns]
    produtos_com_mov = set(int(p) for p in df["produto_id"].dropna().unique())

    validade_dt = pd.to_datetime(df["validade"], errors="coerce")
    nao_vencido = validade_dt.isna() | (validade_dt.dt.date >= date.today())
    df_valido = df[nao_vencido]

    quantidade = pd.to_numeric(df_valido["quantidade"], errors="coerce").fillna(0)
    sinal = df_valido["tipo_transacao"].map({"Entrada": 1, "Saída": -1}).fillna(0)
    qtd_sinal = quantidade * sinal

    saldo = qtd_sinal.groupby(df_valido["produto_id"]).sum()
    saldo_dict = {int(k): int(v) for k, v in saldo.items()}
    return {pid: saldo_dict.get(pid, 0) for pid in produtos_com_mov}


# ============================================================
# PÁGINA
# ============================================================

def page_relacao_visita_kit():
    st.title("🚚 Relação Visita x Kit")
    st.caption("Associação entre visita, kit e dados de envio/logística, por estudo.")

    try:
        supabase = get_supabase_client()
        df_estudos = _fetch_estudos(supabase)
    except Exception as e:
        feedback(f"❌ Erro ao carregar estudos: {e}", "error", "⚠️")
        return

    if df_estudos.empty:
        st.warning("Nenhum estudo cadastrado.")
        return

    # =====================================================
    # SELEÇÃO DE ESTUDO (contexto para toda a página)
    # =====================================================
    TODOS = "(Todos)"
    estudos_opts = [TODOS] + df_estudos["estudo"].tolist()
    estudo_sel = st.selectbox("Estudo", estudos_opts, key="rvk_estudo")
    ver_todos = estudo_sel == TODOS
    id_estudo = None if ver_todos else int(df_estudos[df_estudos["estudo"] == estudo_sel].iloc[0]["id_estudo"])

    try:
        variaveis = _fetch_variaveis(supabase)
        if ver_todos:
            df_kits = pd.DataFrame()
            df_rel = _fetch_relacoes_todas(supabase)
        else:
            df_kits = _fetch_kits(supabase, id_estudo)
            df_rel = _fetch_relacoes(supabase, id_estudo)
    except Exception as e:
        feedback(f"❌ Erro ao carregar dados de apoio: {e}", "error", "⚠️")
        return

    kit_nome_to_id = {row["nome"]: int(row["id"]) for _, row in df_kits.iterrows()} if not df_kits.empty else {}
    kits_opts = list(kit_nome_to_id.keys())

    if ver_todos:
        df_todos_kits = _fetch_todos_kits(supabase)
        kit_id_to_nome = {int(r["id"]): r["nome"] for _, r in df_todos_kits.iterrows()} if not df_todos_kits.empty else {}
    else:
        kit_id_to_nome = {v: k for k, v in kit_nome_to_id.items()}

    # =====================================================
    # 👁️ VISUALIZAÇÃO (Todos os Estudos) — somente leitura
    # =====================================================
    if ver_todos:
        st.markdown("### 👁️ Registros — Todos os Estudos")

        fc_v, fc_k = st.columns(2)
        with fc_v:
            visita_opts_filtro = [TODOS] + variaveis.get("visita", [])
            visita_filtro = st.selectbox("Filtrar por Visita", visita_opts_filtro, key="rvk_filtro_visita")
        with fc_k:
            kit_opts_filtro = [TODOS] + sorted(set(kit_id_to_nome.values()))
            kit_filtro = st.selectbox("Filtrar por Kit", kit_opts_filtro, key="rvk_filtro_kit")

        if not df_rel.empty:
            df_view = df_rel.copy()
            df_view["kit"] = df_view["kit_type"].apply(
                lambda k: kit_id_to_nome.get(int(k), f"(kit #{int(k)})") if pd.notna(k) else ""
            )
            ids_produto_view = tuple(int(k) for k in df_view["kit_type"].dropna().unique())
            try:
                saldo_map = _fetch_saldo_kits(supabase, ids_produto_view)
            except Exception as e:
                feedback(f"❌ Erro ao carregar saldo da farmácia: {e}", "error", "⚠️")
                saldo_map = {}
            df_view["saldo"] = df_view["kit_type"].apply(
                lambda k: saldo_map.get(int(k)) if pd.notna(k) else None
            )

            if visita_filtro != TODOS:
                df_view = df_view[df_view["visita"] == visita_filtro]
            if kit_filtro != TODOS:
                df_view = df_view[df_view["kit"] == kit_filtro]

            if not df_view.empty:
                estudo_id_to_nome = dict(zip(df_estudos["id_estudo"], df_estudos["estudo"]))
                df_view["estudo"] = df_view["id_estudo"].map(estudo_id_to_nome)
                df_view = df_view.sort_values(["estudo", "visita"])
                col_map = {
                    "estudo": "Estudo", "visita": "Visita", "kit": "Kit", "saldo": "Saldo (não vencido)",
                    "envio": "Envio", "temperatura": "Temperatura", "laboratorio": "Laboratório", "courier": "Courier",
                }
                st.dataframe(
                    df_view[list(col_map)].rename(columns=col_map),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption("💊 Saldo (não vencido) = entradas − saídas na farmácia para aquele kit, somando só lotes sem validade vencida.")
            else:
                st.info("Nenhum registro encontrado para os filtros selecionados.")
        else:
            st.info("Nenhum registro encontrado.")

        st.caption("ℹ️ Selecione um estudo específico acima para criar, editar ou apagar registros.")
        return

    # =====================================================
    # 📋 MATRIZ EDITÁVEL (Estudo específico) — criar, editar e apagar
    # =====================================================
    st.markdown("### 📋 Registros do Estudo")

    fc_v, fc_k = st.columns(2)
    with fc_v:
        visita_opts_filtro = [TODOS] + variaveis.get("visita", [])
        visita_filtro = st.selectbox("Filtrar por Visita", visita_opts_filtro, key="rvk_filtro_visita")
    with fc_k:
        kit_opts_filtro = [TODOS] + kits_opts
        kit_filtro = st.selectbox("Filtrar por Kit", kit_opts_filtro, key="rvk_filtro_kit")

    if not kits_opts:
        st.caption("⚠️ Este estudo não possui produtos do tipo 'Kit' cadastrados — o campo Kit ficará indisponível até existir um.")

    df_rel_idx = df_rel.reset_index(drop=True)
    df_view = df_rel_idx.copy()

    if not df_view.empty:
        df_view["kit"] = df_view["kit_type"].apply(
            lambda k: kit_id_to_nome.get(int(k), f"(kit #{int(k)})") if pd.notna(k) else ""
        )
        ids_produto_view = tuple(int(k) for k in df_view["kit_type"].dropna().unique())
        try:
            saldo_map = _fetch_saldo_kits(supabase, ids_produto_view)
        except Exception as e:
            feedback(f"❌ Erro ao carregar saldo da farmácia: {e}", "error", "⚠️")
            saldo_map = {}
        df_view["saldo"] = df_view["kit_type"].apply(
            lambda k: saldo_map.get(int(k)) if pd.notna(k) else None
        )
    else:
        df_view = pd.DataFrame(columns=[
            "id", "id_estudo", "visita", "kit_type", "envio",
            "temperatura", "laboratorio", "courier", "kit", "saldo",
        ])

    df_filtrado = df_view.copy()
    if visita_filtro != TODOS:
        df_filtrado = df_filtrado[df_filtrado["visita"] == visita_filtro]
    if kit_filtro != TODOS:
        df_filtrado = df_filtrado[df_filtrado["kit"] == kit_filtro]

    # guarda o índice original (em df_rel_idx) pra conseguir achar o "id" real
    # no banco depois, já que o data_editor só devolve posições 0..N-1 do que foi exibido.
    df_filtrado = df_filtrado.reset_index().rename(columns={"index": "_orig_idx"})

    col_map = {
        "visita": "Visita", "kit": "Kit", "envio": "Envio", "temperatura": "Temperatura",
        "laboratorio": "Laboratório", "courier": "Courier", "saldo": "Saldo (não vencido)",
    }
    df_editor = df_filtrado[list(col_map)].rename(columns=col_map)

    edited = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        disabled=["Saldo (não vencido)"],
        column_config={
            "Visita":      st.column_config.SelectboxColumn(options=[""] + variaveis.get("visita", []), required=True),
            "Kit":         st.column_config.SelectboxColumn(options=[""] + kits_opts),
            "Envio":       st.column_config.SelectboxColumn(options=[""] + variaveis.get("opcoes_envio", [])),
            "Temperatura": st.column_config.SelectboxColumn(options=[""] + variaveis.get("opcoes_temperatura", [])),
            "Laboratório": st.column_config.SelectboxColumn(options=[""] + variaveis.get("opcoes_laboratorio", [])),
            "Courier":     st.column_config.SelectboxColumn(options=[""] + variaveis.get("opcoes_courier", [])),
        },
        key="editor_rvk",
    )
    st.caption(
        "💊 Saldo (não vencido) = entradas − saídas na farmácia para aquele kit, somando só lotes sem validade vencida. "
        "Use o \"+\" no fim da tabela pra adicionar um registro novo, ou selecione uma linha pra apagar."
    )

    if st.button("💾 Gravar", type="primary", use_container_width=True):
        estado = st.session_state.get("editor_rvk", {})
        edited_rows = estado.get("edited_rows", {})
        added_rows = estado.get("added_rows", [])
        deleted_rows = estado.get("deleted_rows", [])

        erros = []
        alterados = 0

        # ── Exclusões ──────────────────────────────────
        for pos in deleted_rows:
            try:
                orig_idx = int(df_filtrado.iloc[pos]["_orig_idx"])
                reg_id = int(df_rel_idx.loc[orig_idx, "id"])
                supabase_execute(
                    lambda reg_id=reg_id: supabase.table("tab_app_relacao_visita_kit")
                    .delete().eq("id", reg_id).execute()
                )
                alterados += 1
            except Exception as e:
                erros.append(f"Erro ao apagar linha: {e}")

        # ── Edições ────────────────────────────────────
        for pos, mudancas in edited_rows.items():
            try:
                orig_idx = int(df_filtrado.iloc[pos]["_orig_idx"])
                reg_id = int(df_rel_idx.loc[orig_idx, "id"])

                visita_e = mudancas.get("Visita", df_editor.loc[pos, "Visita"])
                if not visita_e:
                    erros.append(f"Linha #{reg_id}: Visita é obrigatória — alteração não gravada.")
                    continue
                kit_e         = mudancas.get("Kit", df_editor.loc[pos, "Kit"])
                envio_e       = mudancas.get("Envio", df_editor.loc[pos, "Envio"])
                temperatura_e = mudancas.get("Temperatura", df_editor.loc[pos, "Temperatura"])
                laboratorio_e = mudancas.get("Laboratório", df_editor.loc[pos, "Laboratório"])
                courier_e     = mudancas.get("Courier", df_editor.loc[pos, "Courier"])

                supabase_execute(
                    lambda: supabase.table("tab_app_relacao_visita_kit")
                    .update({
                        "visita":      visita_e,
                        "kit_type":    kit_nome_to_id.get(kit_e),
                        "envio":       envio_e or None,
                        "temperatura": temperatura_e or None,
                        "laboratorio": laboratorio_e or None,
                        "courier":     courier_e or None,
                    })
                    .eq("id", reg_id)
                    .execute()
                )
                alterados += 1
            except Exception as e:
                erros.append(f"Erro ao atualizar linha: {e}")

        # ── Novos registros ────────────────────────────
        for nova in added_rows:
            visita_n = nova.get("Visita") or ""
            if not visita_n:
                continue  # linha em branco adicionada sem preencher — ignora silenciosamente
            try:
                kit_n = nova.get("Kit") or ""
                supabase_execute(
                    lambda: supabase.table("tab_app_relacao_visita_kit")
                    .insert({
                        "id_estudo":   id_estudo,
                        "visita":      visita_n,
                        "kit_type":    kit_nome_to_id.get(kit_n),
                        "envio":       nova.get("Envio") or None,
                        "temperatura": nova.get("Temperatura") or None,
                        "laboratorio": nova.get("Laboratório") or None,
                        "courier":     nova.get("Courier") or None,
                    })
                    .execute()
                )
                alterados += 1
            except Exception as e:
                erros.append(f"Erro ao criar registro (Visita={visita_n}): {e}")

        if alterados:
            _fetch_relacoes.clear()
            feedback(f"✅ {alterados} alteração(ões) gravada(s) com sucesso!", "success", "💾")
        for e in erros:
            st.error(f"⚠️ {e}")
        if alterados and not erros:
            st.rerun()
