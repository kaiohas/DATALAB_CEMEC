# ============================================================
# 🔗 frontend/pages/agenda_usuarios_coordenacao.py
# Vínculo Usuário ↔ Coordenação
# ============================================================
import streamlit as st
import pandas as pd

from frontend.supabase_client import get_supabase_client, supabase_execute
from frontend.components.feedback import feedback


def parse_variaveis(valor_str: str) -> list:
    """Parse de valores a partir de uma string - removendo aspas e normalizando."""
    if not valor_str:
        return []

    valor_str = valor_str.strip('"').strip("'")

    if ";" in valor_str:
        valores = [v.strip() for v in valor_str.split(";") if v.strip()]
    elif "\n" in valor_str:
        valores = [v.strip() for v in valor_str.split("\n") if v.strip()]
    elif "," in valor_str:
        valores = [v.strip() for v in valor_str.split(",") if v.strip()]
    else:
        valores = [valor_str.strip()]

    return valores


# ============================================================
# CACHED DATA FETCHING — evita reconexões em reruns de widget
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
        df = df[df["nm_grupo"].str.startswith("agenda_", na=False)]
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
def _fetch_vinculos(_supabase):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_coordenacao")
        .select("*")
        .eq("sn_ativo", True)
        .order("id_usuario")
        .execute()
    )
    df = pd.DataFrame(resp.data) if resp.data else pd.DataFrame()
    if not df.empty:
        df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_vinculos_usuario(_supabase, usuario_id: int):
    resp = supabase_execute(
        lambda: _supabase.table("tab_app_usuario_coordenacao")
        .select("coordenacao")
        .eq("id_usuario", usuario_id)
        .eq("sn_ativo", True)
        .execute()
    )
    return [v["coordenacao"] for v in resp.data] if resp.data else []


def _invalidar_cache_vinculos():
    _fetch_vinculos.clear()
    _fetch_vinculos_usuario.clear()


def page_agenda_usuarios_coordenacao():
    """Página para vincular usuários às coordenações."""
    st.title("🔗 Vínculo Usuário ↔ Coordenação")

    try:
        supabase = get_supabase_client()

        # ✅ BUSCAR DADOS (cacheados)
        coordenacoes = _fetch_coordenacoes_var(supabase)
        df_grupos = _fetch_grupos(supabase)
        df_usuarios = _fetch_usuarios(supabase)

        if df_grupos.empty:
            st.warning("Nenhum grupo 'agenda_' encontrado no sistema.")
            st.stop()

        if df_usuarios.empty:
            st.warning("Nenhum usuário ativo encontrado.")
            st.stop()

        # =====================================================
        # FILTRO POR GRUPO
        # =====================================================
        st.markdown("### 🔍 Filtros")

        col1, col2 = st.columns(2)

        with col1:
            grupos_options = df_grupos["nm_grupo"].tolist()
            grupo_sel = st.selectbox(
                "Filtrar por Grupo",
                grupos_options,
                index=0,
                help="Selecione um grupo para filtrar usuários (apenas grupos 'agenda_')",
            )

        # ✅ BUSCAR USUÁRIOS DO GRUPO (cacheado — roda só quando grupo_sel muda)
        grupo_id = int(df_grupos[df_grupos["nm_grupo"] == grupo_sel].iloc[0]["id_grupo"])
        usuarios_grupo_ids = _fetch_usuarios_grupo(supabase, grupo_id)

        df_usuarios_filtrado = df_usuarios[df_usuarios["id_usuario"].isin(usuarios_grupo_ids)]

        st.markdown(f"**Usuários no grupo '{grupo_sel}':** {len(df_usuarios_filtrado)}")
        st.markdown("---")

        # =====================================================
        # ABAS
        # =====================================================
        aba_listar, aba_editar = st.tabs(["📋 Listar Vínculos", "✏️ Editar Vínculos"])

        # =====================================================
        # ABA 1: LISTAR VÍNCULOS
        # =====================================================
        with aba_listar:
            st.markdown("### 📋 Vínculos Existentes")

            # ✅ BUSCAR VÍNCULOS (cacheado)
            df_vinculos = _fetch_vinculos(supabase)

            if not df_vinculos.empty:
                df_vinculos = df_vinculos.merge(
                    df_usuarios_filtrado[["id_usuario", "nm_usuario"]],
                    left_on="id_usuario",
                    right_on="id_usuario",
                    how="inner",
                )

                df_display = df_vinculos[["id_usuario", "nm_usuario", "coordenacao", "sn_ativo", "dt_criacao"]].copy()
                df_display.columns = ["ID Usuário", "Usuário", "Coordenação", "Ativo", "Data Criação"]

                st.dataframe(df_display, use_container_width=True, hide_index=True)
                st.caption(f"Total de vínculos: {len(df_display)}")
            else:
                st.info("Nenhum vínculo encontrado para este grupo.")

        # =====================================================
        # ABA 2: EDITAR VÍNCULOS
        # =====================================================
        with aba_editar:
            st.markdown("### ✏️ Gerenciar Vínculos de um Usuário")

            if df_usuarios_filtrado.empty:
                st.warning("⚠️ Nenhum usuário encontrado neste grupo.")
            else:
                usuario_editar = st.selectbox(
                    "Selecione o Usuário",
                    df_usuarios_filtrado["nm_usuario"].tolist(),
                    help="Escolha um usuário para editar seus vínculos",
                    key="usuario_editar",
                )

                if usuario_editar:
                    usuario_id = int(
                        df_usuarios_filtrado[df_usuarios_filtrado["nm_usuario"] == usuario_editar].iloc[0]["id_usuario"]
                    )

                    # ✅ BUSCAR VÍNCULOS DO USUÁRIO (cacheado — roda só quando usuario muda)
                    coordenacoes_atuais = _fetch_vinculos_usuario(supabase, usuario_id)

                    st.markdown(f"**Usuário Selecionado:** {usuario_editar}")
                    st.markdown(f"**Coordenações Atuais:** {', '.join(coordenacoes_atuais) if coordenacoes_atuais else '(nenhuma)'}")

                    st.markdown("---")

                    with st.form(f"form_editar_vinculos_{usuario_id}"):
                        coordenacoes_novas = st.multiselect(
                            "Coordenações (selecione as que deseja manter/adicionar)",
                            coordenacoes,
                            default=coordenacoes_atuais,
                            help="Desselecione para remover vínculos",
                        )

                        if st.form_submit_button("💾 Atualizar Vínculos", use_container_width=True):
                            try:
                                supabase_execute(
                                    lambda: supabase.table("tab_app_usuario_coordenacao")
                                    .delete()
                                    .eq("id_usuario", usuario_id)
                                    .execute()
                                )

                                if coordenacoes_novas:
                                    for coordenacao in coordenacoes_novas:
                                        supabase_execute(
                                            lambda coordenacao=coordenacao: supabase.table("tab_app_usuario_coordenacao")
                                            .insert({
                                                "id_usuario": usuario_id,
                                                "coordenacao": coordenacao,
                                                "sn_ativo": True,
                                            })
                                            .execute()
                                        )

                                _invalidar_cache_vinculos()
                                feedback("✅ Vínculos atualizados com sucesso!", "success", "💾")
                                st.rerun()

                            except Exception as e:
                                feedback(f"❌ Erro ao atualizar vínculos: {str(e)}", "error", "⚠️")

    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_agenda_usuarios_coordenacao()
