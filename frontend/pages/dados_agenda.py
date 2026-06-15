# ============================================================
# 📋 frontend/pages/dados_agenda.py
# Dados - Agenda
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, timedelta

from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode
from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


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


def _add_business_days(start: date, days: int) -> date:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _calcular_prazo(data_visita_str, resolucao_dias, resolucao_modelo):
    if not data_visita_str:
        return None
    try:
        dv = date.fromisoformat(str(data_visita_str))
        d = int(resolucao_dias) if resolucao_dias else 5
        modelo = str(resolucao_modelo or "").lower().strip()
        if modelo == "úteis":
            return _add_business_days(dv, d)
        return dv + timedelta(days=d)
    except Exception:
        return None


def _farol(data_rev, data_transc) -> str:
    def has_val(v):
        return bool(v and str(v) not in ("", "None", "NaT", "nan", "NaN"))
    r, t = has_val(data_rev), has_val(data_transc)
    if r and t:
        return "🟢"
    if r or t:
        return "🟡"
    return "🔴"


def _fmt_date(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    try:
        return pd.to_datetime(v).strftime("%d/%m/%Y")
    except Exception:
        return ""


def _safe_date(v):
    if not v or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return pd.to_datetime(v).date()
    except Exception:
        return None


def _safe_float(v) -> float:
    try:
        f = float(v)
        return 0.0 if pd.isna(f) else f
    except Exception:
        return 0.0


def _sel_idx(opts: list, val) -> int:
    return opts.index(val) if val in opts else 0


# ============================================================
# CACHE FETCHERS
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def _fetch_estudos_vinculados(_supabase, usuario_id: int):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_vinculo")
        .select("vinculo")
        .eq("id_usuario", usuario_id)
        .eq("tipo", "estudo")
        .eq("sn_ativo", True)
        .execute()
    )
    return [r["vinculo"] for r in resp.data] if resp.data else []


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_estudos_info(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("id_estudo, estudo, resolucao_dias, resolucao_modelo")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_agendamentos(_supabase, ids_estudo: tuple, data_ini: str, data_fim: str):
    if not ids_estudo:
        return pd.DataFrame()
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_agendamentos")
        .select(
            "id, estudo_id, id_paciente, nome_paciente, visita, tipo_visita, "
            "data_visita, desfecho_atendimento, status_confirmacao, medico_responsavel"
        )
        .in_("estudo_id", list(ids_estudo))
        .gte("data_visita", data_ini)
        .lte("data_visita", data_fim)
        .order("data_visita", desc=False)
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_dados_agenda(_supabase, ids_agenda: tuple):
    if not ids_agenda:
        return pd.DataFrame()
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_dados_agenda")
        .select("*")
        .in_("id_agenda", list(ids_agenda))
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_usuarios(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuarios")
        .select("id_usuario, nm_usuario")
        .eq("sn_ativo", True)
        .order("nm_usuario")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_variaveis(_supabase):
    usos = ["revisado_coordenacao", "status_revisao", "status_transcricao", "visita_crio"]
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


# ============================================================
# AGGRID JS
# ============================================================

_DATE_CMP_JS = JsCode("""
function(a, b) {
    if (!a && !b) return 0; if (!a) return -1; if (!b) return 1;
    var pa = a.split('/'), pb = b.split('/');
    return new Date(pa[2], pa[1]-1, pa[0]) - new Date(pb[2], pb[1]-1, pb[0]);
}
""")


# ============================================================
# PÁGINA
# ============================================================

def page_dados_agenda():
    st.title("📋 Dados - Agenda")

    usuario_id = st.session_state.get("id_usuario")
    if not usuario_id:
        st.warning("⚠️ Sessão inválida. Faça login novamente.")
        return

    try:
        supabase = get_supabase_client()

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")
        fc1, fc2 = st.columns(2)
        with fc1:
            data_ini = st.date_input("Data início", value=date.today() - timedelta(days=10), format="DD/MM/YYYY")
        with fc2:
            data_fim = st.date_input("Data fim", value=date.today(), format="DD/MM/YYYY")

        if data_ini > data_fim:
            st.error("⚠️ Data início não pode ser maior que data fim.")
            return

        # =====================================================
        # CARREGAR DADOS
        # =====================================================
        nomes_estudos = _fetch_estudos_vinculados(supabase, usuario_id)
        if not nomes_estudos:
            st.info("ℹ️ Nenhum estudo vinculado ao seu usuário. Configure em Vínculo Usuário ↔ Estudo.")
            return

        df_estudos = _fetch_estudos_info(supabase)
        df_estudos_user = df_estudos[df_estudos["estudo"].isin(nomes_estudos)] if not df_estudos.empty else pd.DataFrame()
        if df_estudos_user.empty:
            st.warning("Nenhum estudo cadastrado correspondente ao vínculo.")
            return

        ids_estudo = tuple(df_estudos_user["id_estudo"].tolist())
        df_ags = _fetch_agendamentos(supabase, ids_estudo, str(data_ini), str(data_fim))
        if df_ags.empty:
            st.info("Nenhum agendamento encontrado para o período selecionado.")
            return

        fc3, fc4 = st.columns(2)
        with fc3:
            desfecho_opts = sorted([x for x in df_ags["desfecho_atendimento"].dropna().unique() if x])
            desfecho_sel = st.multiselect("Desfecho", options=desfecho_opts, default=[], placeholder="Todos")
        with fc4:
            confirmacao_opts = sorted([x for x in df_ags["status_confirmacao"].dropna().unique() if x])
            confirmacao_sel = st.multiselect("Confirmação", options=confirmacao_opts, default=[], placeholder="Todos")

        if desfecho_sel:
            df_ags = df_ags[df_ags["desfecho_atendimento"].isin(desfecho_sel)]
        if confirmacao_sel:
            df_ags = df_ags[df_ags["status_confirmacao"].isin(confirmacao_sel)]

        if df_ags.empty:
            st.info("Nenhum agendamento encontrado para os filtros selecionados.")
            return

        # Merge com info do estudo (prazo)
        df_ags = df_ags.merge(
            df_estudos_user[["id_estudo", "estudo", "resolucao_dias", "resolucao_modelo"]],
            left_on="estudo_id", right_on="id_estudo", how="left"
        )

        # Merge com dados já preenchidos
        ids_agenda = tuple(df_ags["id"].tolist())
        df_dados = _fetch_dados_agenda(supabase, ids_agenda)

        _dados_cols = [
            "id_agenda", "id", "data_rev", "data_transc", "id_responsavel",
            "revisado_coordenacao", "status_revisao", "tempo_gasto_revisao", "id_usuario_revisao",
            "status_transcricao", "tempo_gasto_transcricao", "id_usuario_transcricao",
            "status_visita_crio", "comentarios", "upload_check_list_tcle",
            "correto_tcle", "id_responsavel_double_check_tcle", "observacao",
        ]

        if not df_dados.empty:
            cols_disponíveis = [c for c in _dados_cols if c in df_dados.columns]
            df_ags = df_ags.merge(
                df_dados[cols_disponíveis].rename(columns={"id": "id_dado"}),
                left_on="id", right_on="id_agenda", how="left"
            )
        else:
            for col in [c for c in _dados_cols if c != "id_agenda"]:
                df_ags[col if col != "id" else "id_dado"] = None

        # Campos calculados
        df_ags["prazo_rev_tran"] = df_ags.apply(
            lambda r: _calcular_prazo(r.get("data_visita"), r.get("resolucao_dias"), r.get("resolucao_modelo")),
            axis=1,
        )
        df_ags["_farol"] = df_ags.apply(
            lambda r: _farol(r.get("data_rev"), r.get("data_transc")), axis=1
        )
        df_ags["data_visita_fmt"] = df_ags["data_visita"].apply(_fmt_date)
        df_ags["prazo_fmt"]       = df_ags["prazo_rev_tran"].apply(_fmt_date)

        # =====================================================
        # AGGRID
        # =====================================================
        col_map = {
            "estudo":               "Estudo",
            "id_paciente":          "ID Paciente",
            "nome_paciente":        "Nome Paciente",
            "visita":               "Visita",
            "data_visita_fmt":      "Data Visita",
            "desfecho_atendimento": "Desfecho",
            "status_confirmacao":   "Confirmação",
            "prazo_fmt":            "Prazo Rev/Tran",
            "medico_responsavel":   "Médico",
        }
        src_cols = ["_farol"] + [c for c in col_map if c in df_ags.columns]
        df_grid = df_ags[src_cols + ["id"]].copy()
        df_grid.rename(columns={k: v for k, v in col_map.items() if k in df_grid.columns}, inplace=True)

        gb = GridOptionsBuilder.from_dataframe(df_grid)
        gb.configure_column("id", hide=True)
        gb.configure_column("_farol", headerName="Farol", width=70,
                            pinned="left", suppressMenu=True, sortable=False, filter=False)
        gb.configure_column("Data Visita", comparator=_DATE_CMP_JS, type=["customComparator"])
        gb.configure_column("Prazo Rev/Tran", comparator=_DATE_CMP_JS, type=["customComparator"])
        gb.configure_default_column(resizable=True, sortable=True, filter=True, minWidth=100)
        gb.configure_selection("single", use_checkbox=False)
        gb.configure_grid_options(rowHeight=36)

        grid_resp = AgGrid(
            df_grid,
            gridOptions=gb.build(),
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            allow_unsafe_jscode=True,
            use_container_width=True,
            height=380,
        )

        sel = grid_resp.get("selected_rows")
        if sel is not None:
            sel_list = sel if isinstance(sel, list) else (
                sel.to_dict("records") if hasattr(sel, "to_dict") else []
            )
            if sel_list:
                st.session_state["_dados_agenda_sel_id"] = int(sel_list[0]["id"])

        # =====================================================
        # EXPANDER DE PREENCHIMENTO
        # =====================================================
        sel_id = st.session_state.get("_dados_agenda_sel_id")
        if not sel_id:
            st.caption("👆 Clique em uma linha para preencher os dados.")
            return

        rows_sel = df_ags[df_ags["id"] == sel_id]
        if rows_sel.empty:
            st.session_state.pop("_dados_agenda_sel_id", None)
            return

        row  = rows_sel.iloc[0]
        dado = {}
        if not df_dados.empty:
            r = df_dados[df_dados["id_agenda"] == sel_id]
            if not r.empty:
                dado = r.iloc[0].to_dict()

        df_usuarios = _fetch_usuarios(supabase)
        variaveis   = _fetch_variaveis(supabase)

        nm_usuarios = [""] + df_usuarios["nm_usuario"].tolist()

        def id_to_nome(uid):
            if not uid or (isinstance(uid, float) and pd.isna(uid)):
                return ""
            rows = df_usuarios[df_usuarios["id_usuario"] == int(uid)]
            return rows.iloc[0]["nm_usuario"] if not rows.empty else ""

        def nome_to_id(nm):
            if not nm:
                return None
            rows = df_usuarios[df_usuarios["nm_usuario"] == nm]
            return int(rows.iloc[0]["id_usuario"]) if not rows.empty else None

        # Botão fechar fora do expander
        if st.button("✕ Fechar", key="btn_fechar_expander"):
            st.session_state.pop("_dados_agenda_sel_id", None)
            st.rerun()

        titulo = (
            f"📝  {row.get('estudo', '')}  |  "
            f"Paciente {row.get('id_paciente', '')}  |  "
            f"{row.get('data_visita_fmt', '')}"
        )
        with st.expander(titulo, expanded=True):
            with st.form("form_dados_agenda"):
                c1, c2, c3 = st.columns(3)

                # ── Coluna 1: Revisão ──────────────────────
                with c1:
                    st.markdown("##### Revisão")
                    opts_rc = [""] + variaveis.get("revisado_coordenacao", [])
                    revisado_coord = st.selectbox(
                        "Revisado Coordenação", opts_rc,
                        index=_sel_idx(opts_rc, dado.get("revisado_coordenacao", ""))
                    )
                    data_rev = st.date_input(
                        "Data Revisão", value=_safe_date(dado.get("data_rev")), format="DD/MM/YYYY"
                    )
                    opts_sr = [""] + variaveis.get("status_revisao", [])
                    status_rev = st.selectbox(
                        "Status Revisão", opts_sr,
                        index=_sel_idx(opts_sr, dado.get("status_revisao", ""))
                    )
                    tempo_rev = st.number_input(
                        "Tempo gasto (h)", min_value=0.0, step=0.5,
                        value=_safe_float(dado.get("tempo_gasto_revisao")),
                        key="nr_tempo_rev"
                    )
                    quem_rev = st.selectbox(
                        "Quem fez revisão", nm_usuarios,
                        index=_sel_idx(nm_usuarios, id_to_nome(dado.get("id_usuario_revisao")))
                    )

                # ── Coluna 2: Transcrição ──────────────────
                with c2:
                    st.markdown("##### Transcrição")
                    data_transc = st.date_input(
                        "Data Transcrição", value=_safe_date(dado.get("data_transc")), format="DD/MM/YYYY"
                    )
                    opts_st = [""] + variaveis.get("status_transcricao", [])
                    status_transc = st.selectbox(
                        "Status Transcrição", opts_st,
                        index=_sel_idx(opts_st, dado.get("status_transcricao", ""))
                    )
                    tempo_transc = st.number_input(
                        "Tempo gasto (h)", min_value=0.0, step=0.5,
                        value=_safe_float(dado.get("tempo_gasto_transcricao")),
                        key="nr_tempo_transc"
                    )
                    quem_transc = st.selectbox(
                        "Quem fez transcrição", nm_usuarios,
                        index=_sel_idx(nm_usuarios, id_to_nome(dado.get("id_usuario_transcricao")))
                    )

                # ── Coluna 3: TCLE / CRIO ─────────────────
                with c3:
                    st.markdown("##### TCLE / CRIO")
                    opts_vc = [""] + variaveis.get("visita_crio", [])
                    status_crio = st.selectbox(
                        "Status Visita CRIO", opts_vc,
                        index=_sel_idx(opts_vc, dado.get("status_visita_crio", ""))
                    )
                    upload_tcle = st.checkbox(
                        "Upload Check List TCLE",
                        value=bool(dado.get("upload_check_list_tcle", False))
                    )
                    correto_tcle = st.checkbox(
                        "Correto TCLE",
                        value=bool(dado.get("correto_tcle", False))
                    )
                    double_check = st.selectbox(
                        "Resp. Double Check TCLE", nm_usuarios,
                        index=_sel_idx(
                            nm_usuarios,
                            id_to_nome(dado.get("id_responsavel_double_check_tcle"))
                        )
                    )

                st.markdown("---")
                comentarios = st.text_area(
                    "Comentários", value=dado.get("comentarios", "") or "", height=80
                )
                observacao = st.text_area(
                    "Observação", value=dado.get("observacao", "") or "", height=80
                )

                if st.form_submit_button("💾 Salvar", use_container_width=True, type="primary"):
                    payload = {
                        "id_agenda":                        sel_id,
                        "revisado_coordenacao":             revisado_coord or None,
                        "data_rev":                         str(data_rev) if data_rev else None,
                        "status_revisao":                   status_rev or None,
                        "tempo_gasto_revisao":              tempo_rev or None,
                        "id_usuario_revisao":               nome_to_id(quem_rev),
                        "data_transc":                      str(data_transc) if data_transc else None,
                        "status_transcricao":               status_transc or None,
                        "tempo_gasto_transcricao":          tempo_transc or None,
                        "id_usuario_transcricao":           nome_to_id(quem_transc),
                        "status_visita_crio":               status_crio or None,
                        "comentarios":                      comentarios or None,
                        "upload_check_list_tcle":           upload_tcle,
                        "correto_tcle":                     correto_tcle,
                        "id_responsavel_double_check_tcle": nome_to_id(double_check),
                        "observacao":                       observacao or None,
                    }
                    try:
                        if dado.get("id"):
                            payload["dt_atualizacao"] = pd.Timestamp.now(tz="UTC").isoformat()
                            supabase_execute(
                                lambda: supabase.table("tab_app_dados_agenda")
                                .update(payload)
                                .eq("id", int(dado["id"]))
                                .execute()
                            )
                        else:
                            payload["id_responsavel"] = usuario_id
                            supabase_execute(
                                lambda: supabase.table("tab_app_dados_agenda")
                                .insert(payload)
                                .execute()
                            )
                        _fetch_dados_agenda.clear()
                        feedback("✅ Dados salvos com sucesso!", "success", "💾")
                        st.rerun()
                    except Exception as e:
                        feedback(f"❌ Erro ao salvar: {e}", "error", "⚠️")

    except Exception as e:
        st.error(f"❌ Erro ao carregar página: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
