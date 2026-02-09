# ============================================================
# test_connection.py
# Testa conexão com Supabase
# ============================================================
import os
from dotenv import load_dotenv
from frontend.supabase_client import get_supabase_client

load_dotenv()

print("🔍 Testando conexão com Supabase...")

try:
    supabase = get_supabase_client()
    print("✅ Cliente Supabase criado com sucesso")
    
    # Teste 1: Listar usuários
    print("\n📋 Teste 1: Buscando usuários...")
    response = supabase.table("tab_app_usuarios").select("*").execute()
    print(f"✅ Encontrados {len(response.data)} usuários")
    for user in response.data:
        print(f"   - {user['nm_usuario']} ({user['ds_email']})")
    
    # Teste 2: Listar grupos
    print("\n📋 Teste 2: Buscando grupos...")
    response = supabase.table("tab_app_grupos").select("*").execute()
    print(f"✅ Encontrados {len(response.data)} grupos")
    for grupo in response.data:
        print(f"   - {grupo['nm_grupo']}")
    
    # Teste 3: Listar páginas
    print("\n📋 Teste 3: Buscando páginas...")
    response = supabase.table("tab_app_paginas").select("*").execute()
    print(f"✅ Encontradas {len(response.data)} páginas")
    for pagina in response.data:
        print(f"   - {pagina['nm_pagina']}")
    
    # Teste 4: Menu do admin
    print("\n📋 Teste 4: Buscando menu do admin...")
    response = supabase.table("tab_app_menu_app").select("*").eq("nm_usuario", "admin").execute()
    print(f"✅ Encontradas {len(response.data)} páginas no menu")
    for menu in response.data:
        print(f"   - {menu['ds_label']}")
    
    print("\n" + "="*50)
    print("✅ TODOS OS TESTES PASSARAM!")
    print("="*50)
    
except Exception as e:
    print(f"\n❌ ERRO: {str(e)}")
    import traceback
    traceback.print_exc()