# ============================================================
# 📅 frontend/pages/farmacia_visitas.py
# Relatório de Visitas - Farmácia
# ============================================================
import streamlit as st
import pandas as pd
from datetime import date, datetime
from frontend.supabase_client import get_supabase_client
from frontend.components.feedback import feedback


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


def page_farmacia_visitas():
    """Página para relatório de visitas (agendamentos) - Matriz simplificada."""
    st.title("📅 Relatório de Visitas - Farmácia")
    
    try:
        supabase = get_supabase_client()
        
        # Busca estudos
        resp_estudos = supabase.table("tab_app_estudos").select("id_estudo, estudo").execute()
        df_estudos = pd.DataFrame(resp_estudos.data) if resp_estudos.data else pd.DataFrame()
        
        # IDs hardcoded para PRESENCIAL (129) e EXTRA (131)
        tipos_desejados = [129, 131]
        
        # Busca agendamentos
        resp_agendamentos = supabase.table("ag_agendamentos").select("*").execute()
        df_agendamentos = pd.DataFrame(resp_agendamentos.data) if resp_agendamentos.data else pd.DataFrame()
        
        if df_agendamentos.empty:
            st.warning("Nenhum agendamento registrado.")
            return
        
        # Normaliza colunas
        df_estudos.columns = [c.lower() for c in df_estudos.columns]
        df_agendamentos.columns = [c.lower() for c in df_agendamentos.columns]
        
        # Merge com estudos
        if not df_estudos.empty:
            df_agendamentos = df_agendamentos.merge(
                df_estudos,
                left_on="estudo_id",
                right_on="id_estudo",
                how="left",
                suffixes=("", "_est")
            ).rename(columns={"estudo": "nm_estudo"})
        
        # Converte datas
        df_agendamentos["data_visita_dt"] = pd.to_datetime(df_agendamentos["data_visita"], errors="coerce")
        df_agendamentos["Data Visita (BR)"] = df_agendamentos["data_visita_dt"].apply(fmt_date)
        
        # =====================================================
        # FILTROS
        # =====================================================
        st.markdown("### 🔍 Filtros")
        
        fc1, fc2, fc3 = st.columns([2, 1, 1])
        
        with fc1:
            estudos_unicos = sorted([x for x in df_agendamentos["nm_estudo"].unique() if x and x != ""])
            estudo_sel = st.selectbox(
                "Estudo",
                ["(Todos)"] + estudos_unicos,
                index=0
            )
        
        with fc2:
            dt_ini = st.date_input("Data (Início)")
        
        with fc3:
            dt_fim = st.date_input("Data (Fim)")
        
        # Aplicar filtros básicos
        df_view = df_agendamentos.copy()
        
        if estudo_sel != "(Todos)":
            df_view = df_view[df_view["nm_estudo"] == estudo_sel]
        
        if dt_ini and dt_fim:
            df_view = df_view[
                (df_view["data_visita_dt"] >= pd.to_datetime(dt_ini)) &
                (df_view["data_visita_dt"] <= pd.to_datetime(dt_fim))
            ]
        
        if df_view.empty:
            st.info("Nenhum agendamento encontrado com os filtros aplicados.")
            return
        
        # =====================================================
        # MATRIZ DE VISITAS (com filtro de tipo)
        # =====================================================
        st.markdown("---")
        st.markdown("### 📊 Matriz de Visitas")
        
        try:
            df_agrup = df_view.copy()
            
            # Filtra apenas PRESENCIAL (129) ou EXTRA (131)
            df_agrup = df_agrup[df_agrup["tipo_visita_id"].isin(tipos_desejados)]
            
            if df_agrup.empty:
                st.info("Nenhuma visita PRESENCIAL ou EXTRA encontrada com os filtros aplicados.")
                return
            
            # Garante colunas necessárias
            df_agrup["Data Visita (BR)"] = df_agrup["data_visita_dt"].apply(fmt_date)
            df_agrup["nm_estudo"] = df_agrup["nm_estudo"].fillna("(sem estudo)")
            df_agrup["visita"] = df_agrup["visita"].fillna("(sem visita)")
            
            # Agrupamento apenas pelos campos desejados
            agrupado = df_agrup.groupby([
                "Data Visita (BR)", "nm_estudo", "visita"
            ]).size().reset_index(name="quantidade_visita")
            
            # Ordenação
            agrupado = agrupado.sort_values([
                "Data Visita (BR)", "nm_estudo", "visita"
            ]).reset_index(drop=True)
            
            # Rename para exibição
            agrupado_display = agrupado.rename(columns={
                "Data Visita (BR)": "Data da Visita",
                "nm_estudo": "Estudo",
                "visita": "Visita",
                "quantidade_visita": "Quantidade Visita"
            })
            
            st.dataframe(
                agrupado_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Data da Visita": st.column_config.Column(width="small"),
                    "Estudo": st.column_config.Column(width="medium"),
                    "Visita": st.column_config.Column(width="large"),
                    "Quantidade Visita": st.column_config.Column(width="small")
                }
            )
            
            # Download CSV
            csv = agrupado_display.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 Baixar Matriz (CSV)",
                data=csv,
                file_name="visitas_matriz_farmacia.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        except Exception as e:
            feedback(f"❌ Erro ao gerar matriz: {str(e)}", "error", "⚠️")
    
    except Exception as e:
        feedback(f"❌ Erro ao carregar página: {str(e)}", "error", "⚠️")


# ============================================================
# ENTRADA DO STREAMLIT
# ============================================================
if __name__ == "__main__":
    page_farmacia_visitas()