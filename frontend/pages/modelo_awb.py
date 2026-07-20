# ============================================================
# ✈️ frontend/pages/modelo_awb.py
# Modelo de AWB (rastreio de envio de amostras)
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback

TABLE_MODELO = "tab_app_modelo_awb"


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


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_relacao_visita_kit(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_relacao_visita_kit")
        .select("id_estudo, visita, laboratorio, courier, temperatura")
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


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_opcoes_laboratorio(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_variaveis")
        .select("valor")
        .eq("uso", "opcoes_laboratorio")
        .execute()
    )
    return _parse_variaveis(resp.data[0]["valor"]) if resp.data else []


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_opcoes_desfecho_awb(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_variaveis")
        .select("valor")
        .eq("uso", "desfecho_awb")
        .execute()
    )
    return _parse_variaveis(resp.data[0]["valor"]) if resp.data else []


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_modelo_awb_existentes(_supabase, data_ini_str, data_fim_str):
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


def _invalidar_cache():
    _fetch_modelo_awb_existentes.clear()


# ============================================================
# PÁGINA
# ============================================================

def page_modelo_awb():
    st.title("✈️ Modelo de AWB")
    st.caption("Rastreio de envio de amostras (AWB) para as visitas agendadas.")

    try:
        _page_modelo_awb_body()
    except Exception as e:
        st.error(f"❌ Erro ao carregar página: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


def _page_modelo_awb_body():
    supabase = get_supabase_client()
    df_estudos      = _fetch_estudos(supabase)
    df_rvk          = _fetch_relacao_visita_kit(supabase)
    opcoes_lab      = _fetch_opcoes_laboratorio(supabase)
    opcoes_desfecho = _fetch_opcoes_desfecho_awb(supabase)

    if df_estudos.empty:
        st.warning("Nenhum estudo cadastrado.")
        return

    # =====================================================
    # FILTROS
    # =====================================================
    st.markdown("### 🔍 Filtros")
    fc1, fc2, fc3 = st.columns(3)

    with fc1:
        data_range_sel = st.date_input(
            "Data da Visita",
            value=(date.today(), date.today() + timedelta(days=15)),
            format="DD/MM/YYYY",
        )
    with fc2:
        estudos_opts = sorted(df_estudos["estudo"].dropna().unique().tolist())
        estudos_sel = st.multiselect("Estudo(s)", options=estudos_opts, default=[], placeholder="Todos")
    with fc3:
        lab_opts = sorted(opcoes_lab)
        lab_sel = st.multiselect("Laboratório", options=lab_opts, default=[], placeholder="Todos")

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
    # RESOLVER LAB/COURIER/TEMPERATURA POR VISITA,
    # DEPOIS AGRUPAR (DATA, ESTUDO, LAB, COURIER, TEMPERATURA)
    # =====================================================
    rvk_map = {}
    if not df_rvk.empty:
        for _, r in df_rvk.iterrows():
            chave = (r["id_estudo"], str(r["visita"]).strip())
            rvk_map[chave] = {
                "laboratorio": r.get("laboratorio") or None,
                "courier":     r.get("courier") or None,
                "temperatura": r.get("temperatura") or None,
            }

    def _resolver(row):
        info = rvk_map.get((row["estudo_id"], str(row["visita"]).strip()))
        if info is None:
            return pd.Series({"laboratorio": None, "courier": None, "temperatura": None})
        return pd.Series(info)

    resolvido = df_ag.apply(_resolver, axis=1)
    df_ag = pd.concat([df_ag, resolvido], axis=1)
    for campo in ["laboratorio", "courier", "temperatura"]:
        df_ag[campo] = df_ag[campo].fillna("")

    agrupado = (
        df_ag.groupby(
            ["data_visita", "estudo_id", "nm_estudo", "laboratorio", "courier", "temperatura"],
            dropna=False,
        )
        .size()
        .reset_index(name="_qtd")
    )

    if lab_sel:
        agrupado = agrupado[agrupado["laboratorio"].isin(lab_sel)]

    if agrupado.empty:
        st.info("Nenhum registro para os filtros selecionados.")
        return

    # =====================================================
    # PRÉ-PREENCHER COM O QUE JÁ FOI SALVO ANTES
    # =====================================================
    df_existentes = _fetch_modelo_awb_existentes(supabase, str(data_ini), str(data_fim))

    def _buscar_existente(row):
        if df_existentes.empty:
            return None
        cond = (
            (df_existentes["data_visita"] == str(row["data_visita"])) &
            (df_existentes["id_estudo"] == row["estudo_id"])
        )
        for campo in ["laboratorio", "courier", "temperatura"]:
            if row[campo]:
                cond &= (df_existentes[campo] == row[campo])
            else:
                cond &= df_existentes[campo].isna()
        match = df_existentes[cond]
        return match.iloc[0] if not match.empty else None

    awb_orig, desfecho_orig, obs_orig = [], [], []
    for _, row in agrupado.iterrows():
        existente = _buscar_existente(row)
        if existente is not None:
            awb_orig.append(existente.get("awb") or "")
            desfecho_orig.append(existente.get("desfecho") or "")
            obs_orig.append(existente.get("observacao") or "")
        else:
            awb_orig.append("")
            desfecho_orig.append("")
            obs_orig.append("")

    agrupado["_awb_original"]       = awb_orig
    agrupado["_desfecho_original"]  = desfecho_orig
    agrupado["_observacao_original"] = obs_orig
    agrupado["awb"]         = awb_orig
    agrupado["desfecho"]    = desfecho_orig
    agrupado["observacao"]  = obs_orig

    agrupado["_lab_sort"] = agrupado["laboratorio"].replace("", pd.NA)
    agrupado = agrupado.sort_values(
        ["data_visita", "nm_estudo", "_lab_sort"], na_position="last"
    ).drop(columns=["_lab_sort"]).reset_index(drop=True)
    agrupado["data_fmt"] = pd.to_datetime(agrupado["data_visita"]).dt.strftime("%d/%m/%Y")

    # =====================================================
    # MATRIZ EDITÁVEL
    # =====================================================
    st.markdown("---")
    st.markdown("### 📋 Matriz de AWB")
    st.caption(f"**Total:** {len(agrupado)} linha(s)")

    col_map = {
        "data_fmt":    "Data",
        "nm_estudo":   "Estudo",
        "laboratorio": "Laboratório",
        "courier":     "Courier",
        "temperatura": "Temperatura",
        "_qtd":        "Quantidade Visitas",
        "awb":         "AWB",
        "desfecho":    "Desfecho",
        "observacao":  "Observação",
    }
    df_editor = agrupado[list(col_map)].rename(columns=col_map)

    edited = st.data_editor(
        df_editor,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Data", "Estudo", "Laboratório", "Courier", "Temperatura", "Quantidade Visitas"],
        column_config={
            "Desfecho": st.column_config.SelectboxColumn(options=[""] + opcoes_desfecho),
        },
        key="editor_modelo_awb",
    )

    if st.button("💾 Gravar", type="primary", use_container_width=True):
        usuario_logado = st.session_state.get("usuario_logado", "desconhecido")
        erros = []
        alterados = 0

        for idx in agrupado.index:
            row = agrupado.loc[idx]
            novo_awb = (edited.loc[idx, "AWB"] or "").strip()
            novo_desfecho = edited.loc[idx, "Desfecho"] or ""
            nova_obs = (edited.loc[idx, "Observação"] or "").strip()

            if (
                novo_awb == (row["_awb_original"] or "") and
                novo_desfecho == (row["_desfecho_original"] or "") and
                nova_obs == (row["_observacao_original"] or "")
            ):
                continue

            rotulo = f"{row['nm_estudo']} / {row['laboratorio'] or '(sem laboratório)'} / {row['data_fmt']}"

            if not row["laboratorio"] and not row["courier"] and not row["temperatura"]:
                erros.append(f"{rotulo}: não é possível gravar sem Laboratório, Courier e Temperatura vinculados.")
                continue

            try:
                def _buscar():
                    q = (
                        supabase.table(TABLE_MODELO)
                        .select("id")
                        .eq("data_visita", str(row["data_visita"]))
                        .eq("id_estudo", int(row["estudo_id"]))
                    )
                    for campo in ["laboratorio", "courier", "temperatura"]:
                        valor = row[campo] or None
                        q = q.eq(campo, valor) if valor else q.is_(campo, "null")
                    return q.execute()

                existente_resp = supabase_execute(_buscar)

                payload = {
                    "data_visita":    str(row["data_visita"]),
                    "id_estudo":      int(row["estudo_id"]),
                    "laboratorio":    row["laboratorio"] or None,
                    "courier":        row["courier"] or None,
                    "temperatura":    row["temperatura"] or None,
                    "awb":            novo_awb or None,
                    "desfecho":       novo_desfecho or None,
                    "observacao":     nova_obs or None,
                    "responsavel":    usuario_logado,
                    "dt_atualizacao": pd.Timestamp.now(tz="UTC").isoformat(),
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
