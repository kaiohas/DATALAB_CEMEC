# ============================================================
# 🔗 frontend/pages/agenda_usuarios_coordenacao.py
# Vínculo Usuário ↔ Coordenação / Estudo
# ============================================================
import streamlit as st
import pandas as pd

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def parse_variaveis(valor_str: str) -> list:
    if not valor_str:
        return []
    valor_str = valor_str.strip('"').strip("'")
    if ";" in valor_str:
        return [v.strip() for v in valor_str.split(";") if v.strip()]
    elif "\n" in valor_str:
        return [v.strip() for v in valor_str.split("\n") if v.strip()]
    elif "," in valor_str:
        return [v.strip() for v in valor_str.split(",") if v.strip()]
    return [valor_str.strip()]


# ============================================================
# CACHED DATA FETCHING
# ============================================================

@st.cache_data(ttl=600, show_spinner=False)
def _fetch_coordenacoes_var(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_variaveis")
        .select("valor")
        .eq("uso", "coordenacao")
        .execute()
    )
    return parse_variaveis(resp.data[0]["valor"]) if resp.data else []


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_estudos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_estudos")
        .select("estudo")
        .order("estudo")
        .execute()
    )
    return sorted([r["estudo"] for r in resp.data if r.get("estudo")]) if resp.data else []


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_grupos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_grupos")
        .select("id_grupo, nm_grupo")
        .eq("sn_ativo", True)
        .order("nm_grupo")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_usuarios(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuarios")
        .select("id_usuario, nm_usuario, sn_ativo")
        .eq("sn_ativo", True)
        .order("nm_usuario")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_usuarios_grupo(_supabase, grupo_id: int):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_grupo")
        .select("id_usuario")
        .eq("id_grupo", grupo_id)
        .eq("sn_ativo", True)
        .execute()
    )
    return [u["id_usuario"] for u in resp.data] if resp.data else []


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_vinculos_tipo(_supabase, tipo: str):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_vinculo")
        .select("*")
        .eq("tipo", tipo)
        .eq("sn_ativo", True)
        .order("id_usuario")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_vinculos_usuario(_supabase, usuario_id: int, tipo: str):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_vinculo")
        .select("vinculo")
        .eq("id_usuario", usuario_id)
        .eq("tipo", tipo)
        .eq("sn_ativo", True)
        .execute()
    )
    return [v["vinculo"] for v in resp.data] if resp.data else []


def _invalidar_cache_vinculos():
    _fetch_vinculos_tipo.clear()
    _fetch_vinculos_usuario.clear()


# ============================================================
# BLOCO REUTILIZÁVEL: editar vínculos de um tipo
# ============================================================

def _render_aba_listar(supabase, tipo: str, label_vinculo: str, df_usuarios_filtrado: pd.DataFrame):
    st.markdown(f"### 📋 Vínculos de {label_vinculo}")
    df_vinculos = _fetch_vinculos_tipo(supabase, tipo)

    if not df_vinculos.empty and not df_usuarios_filtrado.empty:
        df_vinculos = df_vinculos.merge(
            df_usuarios_filtrado[["id_usuario", "nm_usuario"]],
            on="id_usuario",
            how="inner",
        )
        if not df_vinculos.empty:
            df_display = df_vinculos[["id_usuario", "nm_usuario", "vinculo", "sn_ativo", "dt_criacao"]].copy()
            df_display.columns = ["ID Usuário", "Usuário", label_vinculo, "Ativo", "Data Criação"]
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            st.caption(f"Total de vínculos: {len(df_display)}")
            return
    st.info(f"Nenhum vínculo de {label_vinculo.lower()} encontrado para este grupo.")


def _render_aba_editar(supabase, tipo: str, label_vinculo: str, opcoes: list, df_usuarios_filtrado: pd.DataFrame):
    st.markdown(f"### ✏️ Gerenciar Vínculos de {label_vinculo}")

    if df_usuarios_filtrado.empty:
        st.warning("⚠️ Nenhum usuário encontrado neste grupo.")
        return

    usuario_editar = st.selectbox(
        "Selecione o Usuário",
        df_usuarios_filtrado["nm_usuario"].tolist(),
        key=f"usuario_editar_{tipo}",
    )

    if not usuario_editar:
        return

    usuario_id = int(
        df_usuarios_filtrado[df_usuarios_filtrado["nm_usuario"] == usuario_editar].iloc[0]["id_usuario"]
    )

    vinculos_atuais = _fetch_vinculos_usuario(supabase, usuario_id, tipo)

    st.markdown(f"**Usuário:** {usuario_editar}")
    st.markdown(f"**{label_vinculo}s atuais:** {', '.join(vinculos_atuais) if vinculos_atuais else '(nenhum)'}")
    st.markdown("---")

    with st.form(f"form_editar_vinculos_{tipo}_{usuario_id}"):
        vinculos_novos = st.multiselect(
            f"{label_vinculo}s (selecione os que deseja manter/adicionar)",
            opcoes,
            default=vinculos_atuais,
        )

        if st.form_submit_button("💾 Atualizar Vínculos", use_container_width=True):
            try:
                supabase_execute(
                    lambda: supabase.table("tab_app_usuario_vinculo")
                    .delete()
                    .eq("id_usuario", usuario_id)
                    .eq("tipo", tipo)
                    .execute()
                )

                for val in vinculos_novos:
                    v = val
                    supabase_execute(
                        lambda v=v: supabase.table("tab_app_usuario_vinculo")
                        .insert({
                            "id_usuario": usuario_id,
                            "vinculo": v,
                            "tipo": tipo,
                            "sn_ativo": True,
                        })
                        .execute()
                    )

                _invalidar_cache_vinculos()
                feedback("✅ Vínculos atualizados com sucesso!", "success", "💾")
                st.rerun()

            except Exception as e:
                feedback(f"❌ Erro ao atualizar vínculos: {str(e)}", "error", "⚠️")


# ============================================================
# PÁGINA PRINCIPAL
# ============================================================

def page_agenda_usuarios_coordenacao():
    st.title("🔗 Vínculo Usuário ↔ Coordenação / Estudo")

    try:
        supabase = get_supabase_client()

        coordenacoes  = _fetch_coordenacoes_var(supabase)
        estudos       = _fetch_estudos(supabase)
        df_grupos     = _fetch_grupos(supabase)
        df_usuarios   = _fetch_usuarios(supabase)

        if df_grupos.empty:
            st.warning("Nenhum grupo encontrado no sistema.")
            st.stop()

        if df_usuarios.empty:
            st.warning("Nenhum usuário ativo encontrado.")
            st.stop()

        # =====================================================
        # FILTRO POR GRUPO
        # =====================================================
        st.markdown("### 🔍 Filtros")

        grupo_sel = st.selectbox(
            "Filtrar por Grupo",
            df_grupos["nm_grupo"].tolist(),
        )

        grupo_id = int(df_grupos[df_grupos["nm_grupo"] == grupo_sel].iloc[0]["id_grupo"])
        usuarios_grupo_ids = _fetch_usuarios_grupo(supabase, grupo_id)
        df_usuarios_filtrado = df_usuarios[df_usuarios["id_usuario"].isin(usuarios_grupo_ids)]

        st.markdown(f"**Usuários no grupo '{grupo_sel}':** {len(df_usuarios_filtrado)}")
        st.markdown("---")

        # =====================================================
        # ABAS
        # =====================================================
        aba_listar, aba_coord, aba_estudo = st.tabs([
            "📋 Listar Vínculos",
            "🏢 Vínculo Coordenação",
            "🔬 Vínculo Estudo",
        ])

        with aba_listar:
            col1, col2 = st.columns(2)
            with col1:
                _render_aba_listar(supabase, "coordenacao", "Coordenação", df_usuarios_filtrado)
            with col2:
                _render_aba_listar(supabase, "estudo", "Estudo", df_usuarios_filtrado)

        with aba_coord:
            _render_aba_editar(supabase, "coordenacao", "Coordenação", coordenacoes, df_usuarios_filtrado)

        with aba_estudo:
            _render_aba_editar(supabase, "estudo", "Estudo", estudos, df_usuarios_filtrado)

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


if __name__ == "__main__":
    page_agenda_usuarios_coordenacao()
