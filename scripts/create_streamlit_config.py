import os

# Criar diretório .streamlit na raiz do projeto (não na pasta scripts)
project_root = os.path.dirname(os.path.dirname(__file__))
streamlit_dir = os.path.join(project_root, '.streamlit')
os.makedirs(streamlit_dir, exist_ok=True)

# Criar config.toml com tema claro
config_path = os.path.join(streamlit_dir, 'config.toml')
config_content = """[theme]
base="light"
primaryColor="#0068C9"
backgroundColor="#FFFFFF"
secondaryBackgroundColor="#F0F2F6"
textColor="#262730"
font="sans serif"

[server]
headless = true
enableCORS = false
enableXsrfProtection = false
port = 8501

[browser]
gatherUsageStats = false
"""

with open(config_path, 'w') as f:
    f.write(config_content)

print(f"✅ Arquivo de configuração criado em: {config_path}")
print(f"📁 Diretório: {streamlit_dir}")
print("\n🎨 Tema configurado: LIGHT (sempre claro)")
print("🩺 Para adicionar ícone, configure page_icon='🩺' no app.py")

