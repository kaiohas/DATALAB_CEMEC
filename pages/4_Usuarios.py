import streamlit as st
import pandas as pd
from supabase_client import client
from auth import require_roles, hash_password

# st-aggrid imports
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="Usuários | Agenda Unificada", page_icon="👥", layout="wide")
require_roles(["gerencia"])

st.title("👥 Gerenciamento de Usuários")

# ==================== FUNÇÕES AUXILIARES ====================
def listar_usuarios():
    resp = client.table("ag_users").select("*").order("username").execute()
    return resp.data or []

def listar_usuarios_agenda():
    """Retorna apenas usuários com perfil 'agenda' ativos."""
    resp = client.table("ag_users").select("id, username").eq("role", "agenda").eq("is_active", True).order("username").execute()
    return resp.data or []

def listar_vinculos_usuario_gestao(gestao_user_id: int):
    """Retorna lista de IDs dos usuários agenda vinculados a um usuário gestão."""
    resp = client.table("ag_user_links").select("agenda_user_id").eq("gestao_user_id", gestao_user_id).execute()
    return [row["agenda_user_id"] for row in (resp.data or [])]

def atualizar_vinculos_usuario_gestao(gestao_user_id: int, agenda_user_ids: list):
    """Atualiza vínculos: remove todos existentes e cria novos."""
    # Remove vínculos antigos
    client.table("ag_user_links").delete().eq("gestao_user_id", gestao_user_id).execute()
    
    # Cria novos vínculos
    if agenda_user_ids:
        rows = [{"gestao_user_id": gestao_user_id, "agenda_user_id": aid} for aid in agenda_user_ids]
        client.table("ag_user_links").insert(rows).execute()

def contar_vinculos_por_usuario():
    """Retorna dict {gestao_user_id: quantidade_de_vinculos}."""
    resp = client.table("ag_user_links").select("gestao_user_id").execute()
    vinculos_count = {}
    for row in (resp.data or []):
        gid = row["gestao_user_id"]
        vinculos_count[gid] = vinculos_count.get(gid, 0) + 1
    return vinculos_count

# ==================== ABAS ====================
aba_lista, aba_novo, aba_editar, aba_vinculos = st.tabs(["Listar", "Novo Usuário", "Editar", "Vínculos Gestão"])

# ==================== ABA: LISTAR ====================
with aba_lista:
    st.subheader("Usuários cadastrados")
    usuarios = listar_usuarios()
    if usuarios:
        df = pd.DataFrame(usuarios)
        df = df[["id", "username", "role", "is_active"]]
        df.columns = ["ID", "Usuário", "Perfil", "Ativo"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum usuário cadastrado.")

# ==================== ABA: NOVO USUÁRIO ====================
with aba_novo:
    st.subheader("Cadastrar novo usuário")
    with st.form("frm_novo_usuario", clear_on_submit=True):
        username_new = st.text_input("Nome de usuário")
        password_new = st.text_input("Senha", type="password")
        role_new = st.selectbox("Perfil", options=["agenda", "gestao", "gerencia"])
        is_active_new = st.checkbox("Usuário ativo", value=True)
        submitted = st.form_submit_button("Cadastrar", type="primary")
    
    if submitted:
        if not username_new.strip() or not password_new.strip():
            st.warning("Preencha usuário e senha.")
        else:
            # Verifica se já existe
            existing = client.table("ag_users").select("id").eq("username", username_new.strip()).execute().data
            if existing:
                st.error("Nome de usuário já existe.")
            else:
                password_hash = hash_password(password_new)
                payload = {
                    "username": username_new.strip(),
                    "password_hash": password_hash,
                    "role": role_new,
                    "is_active": is_active_new,
                }
                client.table("ag_users").insert(payload).execute()
                st.success(f"Usuário '{username_new}' cadastrado com sucesso.")
                st.rerun()

# ==================== ABA: EDITAR ====================
with aba_editar:
    st.subheader("Editar usuário existente")
    usuarios_edit = listar_usuarios()
    if not usuarios_edit:
        st.info("Nenhum usuário para editar.")
    else:
        options_edit = {f"{u['username']} (ID: {u['id']})": u for u in usuarios_edit}
        selected_key = st.selectbox("Selecione o usuário", list(options_edit.keys()), key="sel_edit_user")
        user_edit = options_edit[selected_key]
        
        with st.form("frm_edit_usuario"):
            username_edit = st.text_input("Nome de usuário", value=user_edit["username"])
            password_edit = st.text_input("Nova senha (deixe em branco para não alterar)", type="password")
            role_edit = st.selectbox("Perfil", options=["agenda", "gestao", "gerencia"], index=["agenda", "gestao", "gerencia"].index(user_edit["role"]))
            is_active_edit = st.checkbox("Usuário ativo", value=user_edit["is_active"])
            submitted_edit = st.form_submit_button("Salvar alterações", type="primary")
        
        if submitted_edit:
            payload_edit = {
                "username": username_edit.strip(),
                "role": role_edit,
                "is_active": is_active_edit,
            }
            if password_edit.strip():
                payload_edit["password_hash"] = hash_password(password_edit)
            
            client.table("ag_users").update(payload_edit).eq("id", user_edit["id"]).execute()
            st.success("Usuário atualizado.")
            st.rerun()
        
        st.divider()
        st.error("⚠️ Ação perigosa: Excluir usuário")
        if st.button("Excluir este usuário", type="secondary", key="btn_del_user"):
            # Remove vínculos relacionados
            client.table("ag_user_links").delete().eq("gestao_user_id", user_edit["id"]).execute()
            client.table("ag_user_links").delete().eq("agenda_user_id", user_edit["id"]).execute()
            # Remove usuário
            client.table("ag_users").delete().eq("id", user_edit["id"]).execute()
            st.success("Usuário excluído.")
            st.rerun()

# ==================== ABA: VÍNCULOS GESTÃO ====================
with aba_vinculos:
    st.subheader("Gerenciar vínculos: Gestão → Agenda")
    st.markdown("""
    Aqui você define quais usuários **agenda** cada usuário **gestão** pode visualizar.
    Um usuário gestão pode ter **múltiplos** vínculos.
    """)
    
    # Busca TODOS os usuários (não só gestão, para exibir na tabela)
    todos_usuarios = listar_usuarios()
    
    if not todos_usuarios:
        st.info("Nenhum usuário cadastrado.")
    else:
        # Conta vínculos por usuário gestão
        vinculos_count = contar_vinculos_por_usuario()
        
        # Monta DataFrame para exibição
        df_usuarios = pd.DataFrame(todos_usuarios)
        
        # Adiciona coluna de vínculos (apenas para perfil 'gestao')
        df_usuarios["Vínculos"] = df_usuarios.apply(
            lambda row: vinculos_count.get(row["id"], 0) if row["role"] == "gestao" else "-",
            axis=1
        )
        
        # Renomeia colunas para exibição
        df_usuarios["Usuário"] = df_usuarios["username"]
        df_usuarios["Perfil"] = df_usuarios["role"]
        df_usuarios["Ativo"] = df_usuarios["is_active"].apply(lambda x: "Sim" if x else "Não")
        
        # Seleciona colunas para exibição na tabela
        cols_show_vinculos = ["Usuário", "Perfil", "Ativo", "Vínculos"]
        
        st.markdown("### Selecione um usuário GESTÃO para gerenciar vínculos")
        st.markdown("Clique em uma linha da tabela para selecionar (apenas usuários com perfil **gestão** podem ter vínculos).")
        
        # Configurações do AgGrid
        gb_vinculos = GridOptionsBuilder.from_dataframe(df_usuarios[cols_show_vinculos + ["id"]])
        gb_vinculos.configure_default_column(enableValue=True, editable=False, resizable=True, filter=True, sortable=True)
        gb_vinculos.configure_column("id", header_name="user_id", hide=True)
        gb_vinculos.configure_selection(selection_mode="single", use_checkbox=False)
        gridOptions_vinculos = gb_vinculos.build()
        
        grid_response_vinculos = AgGrid(
            df_usuarios[cols_show_vinculos + ["id", "role"]],
            gridOptions=gridOptions_vinculos,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            allow_unsafe_jscode=True,
            theme="alpine",
            fit_columns_on_grid_load=True,
            enable_enterprise_modules=False,
            key="grid_vinculos"
        )
        
        selected_rows_vinculos = grid_response_vinculos.get("selected_rows", None)
        
        user_gestao_sel = None
        if selected_rows_vinculos is None:
            # Sem seleção explícita: tenta usar o primeiro usuário gestão disponível
            usuarios_gestao_default = [u for u in todos_usuarios if u["role"] == "gestao"]
            if usuarios_gestao_default:
                user_gestao_sel = usuarios_gestao_default[0]
        else:
            try:
                if isinstance(selected_rows_vinculos, list):
                    if len(selected_rows_vinculos) > 0:
                        selected_id_vinc = selected_rows_vinculos[0].get("id")
                        if selected_id_vinc is not None:
                            selected_id_vinc = int(selected_id_vinc)
                            user_gestao_sel = next((u for u in todos_usuarios if u["id"] == selected_id_vinc), None)
                elif isinstance(selected_rows_vinculos, pd.DataFrame):
                    if len(selected_rows_vinculos) > 0:
                        selected_id_vinc = selected_rows_vinculos.iloc[0].get("id")
                        if pd.notna(selected_id_vinc):
                            selected_id_vinc = int(selected_id_vinc)
                            user_gestao_sel = next((u for u in todos_usuarios if u["id"] == selected_id_vinc), None)
                else:
                    try:
                        if len(selected_rows_vinculos) > 0:
                            first = selected_rows_vinculos[0]
                            if isinstance(first, dict):
                                selected_id_vinc = first.get("id")
                                selected_id_vinc = int(selected_id_vinc)
                                user_gestao_sel = next((u for u in todos_usuarios if u["id"] == selected_id_vinc), None)
                    except Exception:
                        user_gestao_sel = None
            except Exception:
                user_gestao_sel = None
        
        if user_gestao_sel is None:
            # Fallback: primeiro usuário gestão
            usuarios_gestao_fallback = [u for u in todos_usuarios if u["role"] == "gestao"]
            if usuarios_gestao_fallback:
                user_gestao_sel = usuarios_gestao_fallback[0]
        
        if user_gestao_sel is None or user_gestao_sel["role"] != "gestao":
            st.warning("Selecione um usuário com perfil **gestão** para gerenciar vínculos. Apenas usuários gestão podem ter vínculos configurados.")
        else:
            st.divider()
            st.markdown(f"### Editando vínculos de: **{user_gestao_sel['username']}** (ID: {user_gestao_sel['id']})")
            
            # Busca usuários agenda disponíveis
            usuarios_agenda_disponiveis = listar_usuarios_agenda()
            
            if not usuarios_agenda_disponiveis:
                st.warning("Nenhum usuário com perfil 'agenda' ativo disponível para vincular.")
            else:
                # Busca vínculos atuais
                vinculos_atuais = listar_vinculos_usuario_gestao(user_gestao_sel["id"])
                
                st.markdown(f"**Vínculos atuais:** {len(vinculos_atuais)} usuário(s) agenda")
                
                # Multiselect com usuários agenda
                opcoes_agenda = {u["id"]: u["username"] for u in usuarios_agenda_disponiveis}
                
                vinculos_selecionados = st.multiselect(
                    "Selecione os usuários AGENDA que este usuário gestão pode visualizar",
                    options=list(opcoes_agenda.keys()),
                    default=vinculos_atuais,
                    format_func=lambda x: opcoes_agenda[x],
                    key=f"multi_agenda_vinculos_{user_gestao_sel['id']}"  # Key única por usuário
                )
                
                if st.button("Salvar vínculos", type="primary", use_container_width=True):
                    atualizar_vinculos_usuario_gestao(user_gestao_sel["id"], vinculos_selecionados)
                    st.success(f"Vínculos atualizados! {user_gestao_sel['username']} agora visualiza {len(vinculos_selecionados)} usuário(s) agenda.")
                    st.rerun()