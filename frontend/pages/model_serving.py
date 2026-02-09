import streamlit as st
import pandas as pd
import numpy as np
import time

def page_model_serving():
    st.title("🤖 Previsão de Risco de Cliente")
    idade = st.slider("Idade", 18, 100, 35)
    saldo = st.number_input("Saldo (R$)", min_value=0, value=50000, step=1000)
    produtos = st.slider("Produtos", 1, 5, 1)
    if st.button("Obter Previsão"):
        with st.spinner("Consultando modelo..."):
            time.sleep(1.2)
            base_prob = (idade / 100) * 0.1 + (produtos / 5) * 0.2 + (0.1 if saldo < 100000 else -0.1)
            prob = min(1, max(0, base_prob + np.random.rand() * 0.1))
        st.success(f"Probabilidade de churn: {prob*100:.1f}%")
