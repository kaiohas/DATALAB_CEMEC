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


def _sel_idx(opts: list, val) -> int:
    return opts.index(val) if val in opts else 0


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
    # 👁️ VISUALIZAÇÃO
    # =====================================================
    st.markdown("### 👁️ Registros" + (" — Todos os Estudos" if ver_todos else " do Estudo"))

    fc_v, fc_k = st.columns(2)
    with fc_v:
        visita_opts_filtro = [TODOS] + variaveis.get("visita", [])
        visita_filtro = st.selectbox("Filtrar por Visita", visita_opts_filtro, key="rvk_filtro_visita")
    with fc_k:
        kits_catalogo = kits_opts if not ver_todos else sorted(set(kit_id_to_nome.values()))
        kit_opts_filtro = [TODOS] + kits_catalogo
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
            if ver_todos:
                estudo_id_to_nome = dict(zip(df_estudos["id_estudo"], df_estudos["estudo"]))
                df_view["estudo"] = df_view["id_estudo"].map(estudo_id_to_nome)
                df_view = df_view.sort_values(["estudo", "visita"])
                col_map = {
                    "estudo": "Estudo", "visita": "Visita", "kit": "Kit", "saldo": "Saldo (não vencido)",
                    "envio": "Envio", "temperatura": "Temperatura", "laboratorio": "Laboratório", "courier": "Courier",
                }
            else:
                col_map = {
                    "visita": "Visita", "kit": "Kit", "saldo": "Saldo (não vencido)",
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

    if ver_todos:
        st.caption("ℹ️ Selecione um estudo específico acima para criar ou editar registros.")
        return

    if not kits_opts:
        st.caption("⚠️ Este estudo não possui produtos do tipo 'Kit' cadastrados — o campo Kit ficará indisponível até existir um.")

    # =====================================================
    # ➕ CRIAR NOVO REGISTRO
    # =====================================================
    st.markdown("---")
    st.markdown("### ➕ Novo Registro")

    with st.form("form_novo_rvk"):
        visita = st.selectbox("Visita", [""] + variaveis.get("visita", []))
        kit_nome = st.selectbox("Kit", [""] + kits_opts)
        envio = st.selectbox("Envio", [""] + variaveis.get("opcoes_envio", []))
        temperatura = st.selectbox("Temperatura", [""] + variaveis.get("opcoes_temperatura", []))
        laboratorio = st.selectbox("Laboratório", [""] + variaveis.get("opcoes_laboratorio", []))
        courier = st.selectbox("Courier", [""] + variaveis.get("opcoes_courier", []))

        if st.form_submit_button("✅ Criar Registro", use_container_width=True):
            if not visita:
                st.error("⚠️ Visita é obrigatória")
            else:
                try:
                    supabase_execute(
                        lambda: supabase.table("tab_app_relacao_visita_kit")
                        .insert({
                            "id_estudo":   id_estudo,
                            "visita":      visita,
                            "kit_type":    kit_nome_to_id.get(kit_nome),
                            "envio":       envio or None,
                            "temperatura": temperatura or None,
                            "laboratorio": laboratorio or None,
                            "courier":     courier or None,
                        })
                        .execute()
                    )
                    _fetch_relacoes.clear()
                    feedback("✅ Registro criado com sucesso!", "success", "🎉")
                    st.rerun()
                except Exception as e:
                    feedback(f"❌ Erro ao criar registro: {e}", "error", "⚠️")

    # =====================================================
    # ✏️ EDITAR REGISTRO
    # =====================================================
    st.markdown("---")
    st.markdown("### ✏️ Editar Registro")

    if df_rel.empty:
        st.info("Nenhum registro para editar neste estudo.")
        return

    df_rel_idx = df_rel.reset_index(drop=True)

    def _label(row) -> str:
        kit_nome = kit_id_to_nome.get(int(row["kit_type"])) if pd.notna(row.get("kit_type")) else None
        base = row.get("visita") or "(sem visita)"
        return f"{base} — {kit_nome} (#{row['id']})" if kit_nome else f"{base} (#{row['id']})"

    labels = [_label(r) for _, r in df_rel_idx.iterrows()]
    label_sel = st.selectbox("Selecione um registro", labels, key="rvk_edit_sel")
    row = df_rel_idx.iloc[labels.index(label_sel)]

    with st.form(f"form_editar_rvk_{row['id']}"):
        opts_visita = [""] + variaveis.get("visita", [])
        visita_e = st.selectbox("Visita", opts_visita, index=_sel_idx(opts_visita, row.get("visita", "")))

        opts_kit = [""] + kits_opts
        kit_atual = kit_id_to_nome.get(int(row["kit_type"]), "") if pd.notna(row.get("kit_type")) else ""
        kit_e = st.selectbox("Kit", opts_kit, index=_sel_idx(opts_kit, kit_atual))

        opts_envio = [""] + variaveis.get("opcoes_envio", [])
        envio_e = st.selectbox("Envio", opts_envio, index=_sel_idx(opts_envio, row.get("envio", "")))

        opts_temp = [""] + variaveis.get("opcoes_temperatura", [])
        temperatura_e = st.selectbox("Temperatura", opts_temp, index=_sel_idx(opts_temp, row.get("temperatura", "")))

        opts_lab = [""] + variaveis.get("opcoes_laboratorio", [])
        laboratorio_e = st.selectbox("Laboratório", opts_lab, index=_sel_idx(opts_lab, row.get("laboratorio", "")))

        opts_courier = [""] + variaveis.get("opcoes_courier", [])
        courier_e = st.selectbox("Courier", opts_courier, index=_sel_idx(opts_courier, row.get("courier", "")))

        if st.form_submit_button("💾 Salvar Alterações", use_container_width=True):
            if not visita_e:
                st.error("⚠️ Visita é obrigatória")
            else:
                try:
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
                        .eq("id", int(row["id"]))
                        .execute()
                    )
                    _fetch_relacoes.clear()
                    feedback("✅ Registro atualizado!", "success", "💾")
                    st.rerun()
                except Exception as e:
                    feedback(f"❌ Erro ao atualizar: {e}", "error", "⚠️")
