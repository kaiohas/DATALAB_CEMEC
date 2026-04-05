# 🔧 Guia de Correção: AgGrid não exibindo no Render

## Problema
O AgGrid funciona em localhost mas não no Render (produção).

## Causas Comuns
1. Versões incompatíveis do Streamlit e streamlit-aggrid
2. Falta de configuração do servidor
3. Problemas de cache/build

## ✅ Soluções Implementadas

### 1. requirements.txt - Versões Fixadas
```
streamlit==1.32.0
pandas==2.1.4
numpy==1.26.3
supabase==2.3.4
python-dotenv==1.0.1
streamlit-aggrid==0.3.4.post3
plotly==5.18.0
openpyxl>=3.0.0
```

**IMPORTANTE:** Se ainda não funcionar, tente estas versões alternativas:
```
streamlit==1.31.0
streamlit-aggrid==0.3.4
```

### 2. Criar arquivo .streamlit/config.toml

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
