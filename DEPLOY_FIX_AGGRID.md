# 🔧 Guia de Correção: AgGrid não exibindo no Render

## Problema
O AgGrid funciona em localhost mas não no Render (produção).

## Causas Comuns
1. **Python 3.13+ incompatível** - Versão muito nova sem suporte das bibliotecas
2. Versões incompatíveis do Streamlit e streamlit-aggrid
3. Falta de configuração do servidor
4. Problemas de cache/build

## ✅ Soluções Implementadas

### 1. runtime.txt E .python-version - Fixar versão do Python
```
runtime.txt:
3.11.9

.python-version:
3.11.9
```
**CRÍTICO:** Render precisa de ambos os arquivos para garantir Python 3.11!

### 2. requirements.txt - Versões Testadas e Compatíveis
```
streamlit==1.39.0
pandas==2.2.3
numpy==1.26.4
supabase==2.10.0
python-dotenv==1.0.1
streamlit-aggrid==1.0.5
plotly==5.24.1
openpyxl==3.1.5
```

**IMPORTANTE:** Estas versões funcionam com Python 3.11.x

### 3. Criar arquivo .streamlit/config.toml

Crie manualmente a pasta `.streamlit` na raiz do projeto e dentro dela crie o arquivo `config.toml`:

```toml
[server]
headless = true
enableCORS = false
enableXsrfProtection = false
port = 8501

[browser]
gatherUsageStats = false

[theme]
base = "light"
```

### 3. Procfile (já criado)
```
web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false --server.enableXsrfProtection=false
```

## 🔍 Diagnóstico Adicional

### Verificar logs do Render
No dashboard do Render, veja os logs de build e runtime. Procure por:
- Erros de importação do streamlit-aggrid
- Avisos sobre versões incompatíveis
- Erros JavaScript no browser console

### Testar versões compatíveis
Se o problema persistir, teste esta combinação:
```
streamlit==1.28.0
streamlit-aggrid==0.3.3
```

## 📋 Checklist de Deploy

- [ ] requirements.txt atualizado com versões fixadas
- [ ] Pasta .streamlit criada
- [ ] Arquivo .streamlit/config.toml criado
- [ ] Procfile criado/atualizado
- [ ] Commit e push para GitHub
- [ ] Rebuild no Render (Settings → Manual Deploy)
- [ ] Limpar cache do Render (Settings → Clear Build Cache)
- [ ] Verificar logs de build
- [ ] Testar no browser (F12 para ver console JavaScript)

## 🚨 Solução Alternativa: Usar st.dataframe ao invés de AgGrid

Se o AgGrid continuar não funcionando, você pode temporariamente usar:

```python
# Substitua AgGrid por st.dataframe com estilo
st.dataframe(
    df_grid,
    use_container_width=True,
    height=400,
    hide_index=True,
)
```

Ou use `st.data_editor` que é nativo do Streamlit (versão 1.23+):

```python
st.data_editor(
    df_grid,
    use_container_width=True,
    height=400,
    hide_index=True,
    disabled=True,  # Somente leitura
)
```

## 🎯 Comandos para Executar Localmente

```bash
# 1. Criar diretório .streamlit
mkdir .streamlit

# 2. Criar config.toml (Windows PowerShell)
New-Item -Path ".streamlit\config.toml" -ItemType File -Force

# 3. Popular config.toml (copiar conteúdo acima)

# 4. Reinstalar dependências
pip install -r requirements.txt --force-reinstall

# 5. Limpar cache do Streamlit
streamlit cache clear

# 6. Testar localmente
streamlit run app.py
```

## 📧 Próximos Passos

1. Crie manualmente `.streamlit/config.toml`
2. Faça commit e push
3. No Render:
   - Settings → Manual Deploy → Deploy latest commit
   - Settings → Clear Build Cache → Yes, clear cache
4. Monitore os logs
5. Teste no browser

Se ainda não funcionar, me avise e tentaremos outras abordagens!
