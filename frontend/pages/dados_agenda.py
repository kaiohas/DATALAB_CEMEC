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
        if not resolucao_dias:
            return _add_business_days(dv, 5)
        d = int(resolucao_dias)
        modelo = str(resolucao_modelo or "").lower().strip()
        if modelo == "úteis":
            return _add_business_days(dv, d)
        return dv + timedelta(days=d)
    except Exception:
        return None


def _status_atuacao(desfecho, status_revisao, status_transcricao) -> str:
    if str(desfecho or "").strip() != "Finalizado":
        return "N/A"
    def preenchido(v):
        return bool(v and str(v).strip() not in ("", "None", "nan", "NaN"))
    rev = preenchido(status_revisao)
    tran = preenchido(status_transcricao)
    if rev and tran:
        return "Concluído"
    if rev or tran:
        return "Em andamento"
    return "Pendente"


def _farol(prazo_rev_tran, desfecho) -> str:
    if str(desfecho or "").strip() != "Finalizado":
        return "⚪"
    if prazo_rev_tran is None:
        return "⚪"
    prazo = prazo_rev_tran if isinstance(prazo_rev_tran, date) else _safe_date(prazo_rev_tran)
    if prazo is None:
        return "⚪"
    today = date.today()
    if prazo < today:
        return "🔴"
    if prazo <= today + timedelta(days=3):
        return "🟡"
    return "🟢"


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

@st.cache_data(ttl=600, show_spinner=False)
def _fetch_estudos_info(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("id_estudo, estudo, disciplina, resolucao_dias, resolucao_modelo")
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


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_usuarios_dados(_supabase):
    resp_grupo = supabase_execute(
        lambda: _supabase.table("tab_app_grupos")
        .select("id_grupo")
        .ilike("nm_grupo", "Dados")
        .eq("sn_ativo", True)
        .execute()
    )
    if not resp_grupo.data:
        return pd.DataFrame()
    grupo_id = resp_grupo.data[0]["id_grupo"]
    resp_ug = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_grupo")
        .select("id_usuario")
        .eq("id_grupo", grupo_id)
        .eq("sn_ativo", True)
        .execute()
    )
    if not resp_ug.data:
        return pd.DataFrame()
    ids_usuarios = [u["id_usuario"] for u in resp_ug.data]
    resp_u = supabase_execute(
        lambda: _supabase.table("tab_app_usuarios")
        .select("id_usuario, nm_usuario")
        .in_("id_usuario", ids_usuarios)
        .eq("sn_ativo", True)
        .order("nm_usuario")
        .execute()
    )
    df = pd.DataFrame(resp_u.data) if resp_u.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_variaveis(_supabase):
    usos = ["revisado_coordenacao", "status_revisao", "status_transcricao", "visita_crio", "status_indice"]
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

def _qp_date(val: str | None, default: date) -> date:
    try:
        return date.fromisoformat(val) if val else default
    except Exception:
        return default


def _qp_list(val: str | None) -> list:
    return [x for x in val.split(",") if x.strip()] if val else []


def page_dados_agenda():
    st.title("📋 Dados - Agenda")

    usuario_id = st.session_state.get("id_usuario")
    if not usuario_id:
        st.warning("⚠️ Sessão inválida. Faça login novamente.")
        return

    try:
        supabase = get_supabase_client()

        df_estudos = _fetch_estudos_info(supabase)
        if df_estudos.empty:
            st.warning("Nenhum estudo cadastrado.")
            return

        # ── Ler filtros persistidos na URL ────────────────────
        _p = st.query_params
        _hoje = date.today()
        _p_ini      = _qp_date(_p.get("di"),   _hoje - timedelta(days=10))
        _p_fim      = _qp_date(_p.get("df"),   _hoje)
        _p_disc     = _p.get("disc", "(Todas)")
        _p_estudo   = _qp_list(_p.get("est",  ""))
        _p_desfecho = _qp_list(_p.get("des",  ""))
        _p_conf     = _qp_list(_p.get("conf", ""))
        _p_prazo_i  = _qp_date(_p.get("pi"),   None) if _p.get("pi") else None
        _p_prazo_f  = _qp_date(_p.get("pf"),   None) if _p.get("pf") else None
        _p_farol    = _qp_list(_p.get("far",  ""))

        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")
        fc1, fc2, fc3, fc4 = st.columns(4)
        with fc1:
            data_ini = st.date_input("Data início", value=_p_ini, format="DD/MM/YYYY")
        with fc2:
            data_fim = st.date_input("Data fim", value=_p_fim, format="DD/MM/YYYY")
        with fc3:
            disciplinas_opts = sorted([x for x in df_estudos["disciplina"].dropna().unique() if x])
            disc_opts_full = ["(Todas)"] + disciplinas_opts
            disciplina_sel = st.selectbox(
                "Disciplina", disc_opts_full,
                index=disc_opts_full.index(_p_disc) if _p_disc in disc_opts_full else 0
            )
        with fc4:
            estudos_disp = sorted([x for x in df_estudos["estudo"].dropna().unique() if x])
            estudo_sel = st.multiselect(
                "Estudo", options=estudos_disp,
                default=[e for e in _p_estudo if e in estudos_disp],
                placeholder="Todos"
            )

        if data_ini > data_fim:
            st.error("⚠️ Data início não pode ser maior que data fim.")
            return

        # =====================================================
        # CARREGAR DADOS
        # =====================================================
        if disciplina_sel != "(Todas)":
            df_estudos_filtrado = df_estudos[df_estudos["disciplina"] == disciplina_sel]
        else:
            df_estudos_filtrado = df_estudos

        if estudo_sel:
            df_estudos_filtrado = df_estudos_filtrado[df_estudos_filtrado["estudo"].isin(estudo_sel)]

        ids_estudo = tuple(df_estudos_filtrado["id_estudo"].tolist())
        df_ags = _fetch_agendamentos(supabase, ids_estudo, str(data_ini), str(data_fim))
        if df_ags.empty:
            st.info("Nenhum agendamento encontrado para o período selecionado.")
            return

        fc5, fc6, fc7, fc8, fc9 = st.columns(5)
        with fc5:
            desfecho_opts = sorted([x for x in df_ags["desfecho_atendimento"].dropna().unique() if x])
            desfecho_sel = st.multiselect(
                "Desfecho", options=desfecho_opts,
                default=[d for d in _p_desfecho if d in desfecho_opts],
                placeholder="Todos"
            )
        with fc6:
            confirmacao_opts = sorted([x for x in df_ags["status_confirmacao"].dropna().unique() if x])
            confirmacao_sel = st.multiselect(
                "Confirmação", options=confirmacao_opts,
                default=[c for c in _p_conf if c in confirmacao_opts],
                placeholder="Todos"
            )
        with fc7:
            prazo_ini = st.date_input("Prazo Rev/Tran (início)", value=_p_prazo_i, format="DD/MM/YYYY")
        with fc8:
            prazo_fim = st.date_input("Prazo Rev/Tran (fim)", value=_p_prazo_f, format="DD/MM/YYYY")
        with fc9:
            farol_opts = ["🟢 Verde", "🟡 Amarelo", "🔴 Vermelho", "⚪ Cinza"]
            farol_sel = st.multiselect(
                "Farol", options=farol_opts,
                default=[f for f in _p_farol if f in farol_opts],
                placeholder="Todos"
            )

        # ── Persistir filtros na URL (sem triggerar rerun) ───
        st.query_params.update({
            "di":   str(data_ini),
            "df":   str(data_fim),
            "disc": disciplina_sel,
            "est":  ",".join(estudo_sel),
            "des":  ",".join(desfecho_sel),
            "conf": ",".join(confirmacao_sel),
            "pi":   str(prazo_ini) if prazo_ini else "",
            "pf":   str(prazo_fim) if prazo_fim else "",
            "far":  ",".join(farol_sel),
        })

        if desfecho_sel:
            df_ags = df_ags[df_ags["desfecho_atendimento"].isin(desfecho_sel)]
        if confirmacao_sel:
            df_ags = df_ags[df_ags["status_confirmacao"].isin(confirmacao_sel)]

        if df_ags.empty:
            st.info("Nenhum agendamento encontrado para os filtros selecionados.")
            return

        # Merge com info do estudo (prazo)
        df_ags = df_ags.merge(
            df_estudos_filtrado[["id_estudo", "estudo", "resolucao_dias", "resolucao_modelo"]],
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
            "correto_tcle", "id_responsavel_double_check_tcle", "observacao", "indice",
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
            lambda r: _farol(r.get("prazo_rev_tran"), r.get("desfecho_atendimento")), axis=1
        )

        if farol_sel:
            _farol_map = {"🟢 Verde": "🟢", "🟡 Amarelo": "🟡", "🔴 Vermelho": "🔴", "⚪ Cinza": "⚪"}
            farol_emojis = [_farol_map[f] for f in farol_sel]
            df_ags = df_ags[df_ags["_farol"].isin(farol_emojis)]

        if prazo_ini:
            df_ags = df_ags[df_ags["prazo_rev_tran"].apply(
                lambda v: v is not None and (v if isinstance(v, date) else _safe_date(v)) >= prazo_ini
            )]
        if prazo_fim:
            df_ags = df_ags[df_ags["prazo_rev_tran"].apply(
                lambda v: v is not None and (v if isinstance(v, date) else _safe_date(v)) <= prazo_fim
            )]

        df_ags["data_visita_fmt"] = df_ags["data_visita"].apply(_fmt_date)
        df_ags["prazo_fmt"]       = df_ags["prazo_rev_tran"].apply(_fmt_date)
        df_ags["status_atuacao"]  = df_ags.apply(
            lambda r: _status_atuacao(r.get("desfecho_atendimento"), r.get("status_revisao"), r.get("status_transcricao")),
            axis=1,
        )

        # =====================================================
        # AGGRID
        # =====================================================
        col_map = {
            "status_atuacao":       "Status Atuação",
            "prazo_fmt":            "Prazo Rev/Tran",
            "estudo":               "Estudo",
            "id_paciente":          "ID Paciente",
            "nome_paciente":        "Nome Paciente",
            "visita":               "Visita",
            "data_visita_fmt":      "Data Visita",
            "desfecho_atendimento": "Desfecho",
            "status_confirmacao":   "Confirmação",
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

        df_usuarios       = _fetch_usuarios(supabase)
        df_usuarios_dados = _fetch_usuarios_dados(supabase)
        variaveis         = _fetch_variaveis(supabase)

        nm_usuarios       = [""] + df_usuarios["nm_usuario"].tolist()
        nm_usuarios_dados = [""] + (df_usuarios_dados["nm_usuario"].tolist() if not df_usuarios_dados.empty else [])

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
                        "Quem fez revisão", nm_usuarios_dados,
                        index=_sel_idx(nm_usuarios_dados, id_to_nome(dado.get("id_usuario_revisao")))
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
                        "Quem fez transcrição", nm_usuarios_dados,
                        index=_sel_idx(nm_usuarios_dados, id_to_nome(dado.get("id_usuario_transcricao")))
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
                    opts_idx = [""] + variaveis.get("status_indice", [])
                    indice = st.selectbox(
                        "Índice", opts_idx,
                        index=_sel_idx(opts_idx, dado.get("indice", ""))
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
                        "indice":                           indice or None,
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
