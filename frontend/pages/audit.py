import streamlit as st

def page_audit():
    st.title("🔒 Logs de Auditoria e Segurança")
    logs = [
        "2025-09-30 10:30:15 | ADMIN | Alteração de permissão no schema financeiro",
        "2025-09-30 10:25:40 | ANALYST | Query executada com sucesso (2.1s)",
        "2025-09-30 10:15:01 | DEVELOPER | Job ETL-Transform iniciado",
    ]
    for log in logs:
        st.text(log)
