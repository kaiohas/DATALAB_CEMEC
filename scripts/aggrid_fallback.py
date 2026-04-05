"""
Script para adicionar fallback ao AgGrid em caso de falha.
Adicione esta função no início de agenda_gestao.py e agenda_relatorio.py
"""

def render_grid_with_fallback(df, gridOptions, height=400, use_aggrid=True):
    """
    Renderiza grid com AgGrid ou fallback para st.dataframe se AgGrid falhar.
    
    Args:
        df: DataFrame para exibir
        gridOptions: Opções do GridOptionsBuilder
        height: Altura do grid
        use_aggrid: Se True, tenta usar AgGrid primeiro
    
    Returns:
        dict com selected_rows (lista de dicts selecionados)
    """
    import streamlit as st
    
    if use_aggrid:
        try:
            from st_aggrid import AgGrid, GridUpdateMode
            
            grid_response = AgGrid(
                df,
                gridOptions=gridOptions,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=False,
                height=height,
                theme="streamlit",
                allow_unsafe_jscode=True,
            )
            return grid_response
        except Exception as e:
            st.warning(f"⚠️ AgGrid não disponível. Usando visualização alternativa. Erro: {str(e)}")
            use_aggrid = False
    
    if not use_aggrid:
        # Fallback para st.dataframe com seleção manual
        st.dataframe(
            df,
            use_container_width=True,
            height=height,
            hide_index=True,
        )
        
        # Permitir seleção manual via selectbox
        if len(df) > 0:
            id_col = df.columns[0]  # Primeira coluna (geralmente ID)
            selected_id = st.selectbox(
                "Selecione um registro para editar:",
                options=df[id_col].tolist(),
                key="manual_selection"
            )
            
            if selected_id:
                selected_row = df[df[id_col] == selected_id].to_dict('records')
                return {"selected_rows": selected_row}
        
        return {"selected_rows": []}


# Exemplo de uso no código existente:

# ANTES:
"""
grid_response = AgGrid(
    df_grid,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.SELECTION_CHANGED,
    fit_columns_on_grid_load=False,
    height=400,
    theme="streamlit",
    allow_unsafe_jscode=True,
)
"""

# DEPOIS:
"""
grid_response = render_grid_with_fallback(
    df_grid,
    grid_options,
    height=400,
    use_aggrid=True  # Mude para False para forçar fallback
)
"""
