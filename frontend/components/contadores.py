# ============================================================
# 🔢 frontend/components/contadores.py
# Contadores de agendamentos (total + por coordenação)
# ============================================================
import streamlit as st
import pandas as pd


def render_contadores_agenda(df: pd.DataFrame, col_coordenacao: str = "coordenacao", max_por_linha: int = 5):
    """Exibe um card com o total de agendamentos e um card por coordenação."""
    total = len(df)

    if col_coordenacao in df.columns and total:
        por_coord = (
            df[col_coordenacao]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace("", "(Sem coordenação)")
            .value_counts()
            .sort_index()
        )
    else:
        por_coord = pd.Series(dtype=int)

    cards = [("📊 Total de agendas", total)] + [(f"🧭 {coord}", int(qtd)) for coord, qtd in por_coord.items()]

    with st.container(border=True):
        for i in range(0, len(cards), max_por_linha):
            linha = cards[i:i + max_por_linha]
            cols = st.columns(max_por_linha)
            for col, (rotulo, valor) in zip(cols, linha):
                col.metric(rotulo, valor)
