# ============================================================
# 📦 backend/api/gemini_utils.py
# ============================================================
import importlib
import subprocess
import sys

# ============================================================
# 🧠 Instalação dinâmica (apenas se o pacote não existir)
# ============================================================
package_name = "google-generativeai"
if importlib.util.find_spec(package_name) is None:
    try:
        print(f"🔍 Pacote '{package_name}' não encontrado. Instalando automaticamente...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"✅ Pacote '{package_name}' instalado com sucesso.")
    except Exception as e:
        print(f"⚠️ Falha ao instalar '{package_name}': {e}")

# ============================================================
# 🔐 Import e configuração da API do Gemini
# ============================================================
try:
    import google.generativeai as genai
except ImportError:
    genai = None
    print("⚠️ Não foi possível importar 'google-generativeai'. Recurso de IA desativado.")


# ============================================================
# ⚙️ Chave de API (pode ser fixa ou via ambiente)
# ============================================================
API_KEY_GEMINI = "AIzaSyAKlVW4sPNO5ss05rpaEE8ulsnxnQPwPDA"

if genai:
    try:
        genai.configure(api_key=API_KEY_GEMINI)
    except Exception as e:
        print(f"⚠️ Erro ao configurar Gemini: {e}")


# ============================================================
# ✨ Função para gerar descrição com IA
# ============================================================
def gerar_descricao_relatorio(query_sql: str) -> str:
    """
    Usa o Gemini (Google Generative AI) para gerar uma descrição em português
    para o relatório, com base na query SQL informada.
    """
    if not genai:
        return "⚠️ O recurso de IA (Gemini) não está disponível neste ambiente."

    try:
        if not query_sql or not query_sql.strip():
            return "⚠️ Nenhuma query fornecida para gerar descrição."

        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"""
        Gere uma descrição curta e profissional em português para um relatório,
        com base na seguinte query SQL:

        {query_sql}

        A descrição deve:
        - Explicar de forma natural o que o relatório apresenta.
        - Mencionar o tipo de informação, agrupamento ou período, se aplicável.
        - Evitar termos técnicos de SQL.
        """

        response = model.generate_content(prompt)
        return response.text.strip() if response and response.text else "⚠️ Não foi possível gerar descrição."

    except Exception as e:
        return f"⚠️ Erro ao gerar descrição com Gemini: {e}"

