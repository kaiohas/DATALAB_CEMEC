# ============================================================
# 🌈 Componente de Feedback Visual — Data Hub
# ============================================================
import streamlit as st

def feedback(message: str, status: str = "success", icon: str = "💬"):
    """
    Exibe uma mensagem de feedback moderna tipo pop-up (toast animado).
    
    Parâmetros:
        message (str): Texto da mensagem
        status (str): 'success', 'error', 'warning', 'info'
        icon (str): Emoji ou ícone opcional
    """
    color = {
        "success": "#16a34a",  # verde
        "error": "#dc2626",    # vermelho
        "warning": "#f59e0b",  # laranja
        "info": "#2563eb",     # azul
    }.get(status, "#16a34a")

    st.markdown(f"""
        <div style="
            position: fixed;
            bottom: 24px;
            right: 24px;
            background-color: {color};
            color: white;
            padding: 14px 24px;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            font-size: 15px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: fadeIn 0.3s ease-out;
            z-index: 9999;
        ">
            <span>{icon}</span> {message}
        </div>

        <style>
        @keyframes fadeIn {{
            from {{opacity: 0; transform: translateY(15px);}}
            to {{opacity: 1; transform: translateY(0);}}
        }}
        </style>
    """, unsafe_allow_html=True)
