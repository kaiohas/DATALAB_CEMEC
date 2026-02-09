# ============================================================
# test_login.py
# Testa função de login
# ============================================================
import hashlib
from frontend.components.login import hash_password, verificar_senha

# Teste 1: Hash de senha
print("🔐 Teste 1: Hash de senha...")
senha = "admin123"
hash_resultado = hash_password(senha)
print(f"Senha: {senha}")
print(f"Hash: {hash_resultado}")

# Teste 2: Verificar senha
print("\n🔐 Teste 2: Verificar senha...")
correto = verificar_senha("admin123", hash_resultado)
incorreto = verificar_senha("senha_errada", hash_resultado)

print(f"admin123 correto? {correto} (esperado: True)")
print(f"senha_errada correto? {incorreto} (esperado: False)")

if correto and not incorreto:
    print("\n✅ Sistema de hash funcionando!")
else:
    print("\n❌ Erro no sistema de hash")