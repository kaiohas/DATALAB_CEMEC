import os

# Criar diretório .streamlit se não existir
streamlit_dir = os.path.join(os.path.dirname(__file__), '.streamlit')
os.makedirs(streamlit_dir, exist_ok=True)

# Criar config.toml
config_path = os.path.join(streamlit_dir, 'config.toml')
config_content = """[server]
headless = true
enableCORS = false
enableXsrfProtection = false
port = 8501

[browser]
gatherUsageStats = false

[theme]
base = "light"
"""

with open(config_path, 'w') as f:
    f.write(config_content)

print(f"Arquivo de configuração criado em: {config_path}")
