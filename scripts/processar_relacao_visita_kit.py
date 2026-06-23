"""
Processa relacao_visita_kit.csv para importação na tabela tab_app_relacao_visita_kit.

Uso:
    python scripts/processar_relacao_visita_kit.py

Arquivos necessários na mesma pasta do script (ou ajuste os caminhos abaixo):
    - relacao_visita_kit.csv
    - lista_kits_estudo.csv
    - tab_app_estudos_rows.csv

Saída:
    - scripts/output_relacao_visita_kit.csv   → pronto para importar no Supabase
    - scripts/output_nao_mapeados.csv         → registros com estudo ou kit não encontrado
"""

import pandas as pd
import unicodedata
import re
from pathlib import Path

HERE = Path(__file__).parent

# ── Caminhos ──────────────────────────────────────────────────────────────────
RELACAO_CSV  = HERE / "relacao_visita_kit.csv"
KITS_CSV     = HERE / "lista_kits_estudo.csv"
ESTUDOS_CSV  = HERE / "tab_app_estudos_rows.csv"
OUT_OK       = HERE / "output_relacao_visita_kit.csv"
OUT_ERROS    = HERE / "output_nao_mapeados.csv"


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalizar(texto: str) -> str:
    """Remove acentos, lowercase, colapsa espaços."""
    if not isinstance(texto, str):
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower().strip()
    texto = re.sub(r"\s+", " ", texto)
    return texto


def consolidar_temperatura(ambiente, refrigerada, congelada) -> str | None:
    partes = []
    if str(ambiente).strip().upper() == "X":
        partes.append("Ambiente")
    if str(refrigerada).strip().upper() == "X":
        partes.append("Refrigerada")
    if str(congelada).strip().upper() == "X":
        partes.append("Congelada")
    return ", ".join(partes) if partes else None


def fix_mojibake(texto: str) -> str:
    """Corrige mojibake sequência a sequência (ex: Ã£→ã, Ã§→ç).

    Abordagem sequencial evita que uma sequência inválida (ex: ÃÃ) bloqueie
    a correção de outras sequências válidas na mesma string.
    """
    if not isinstance(texto, str):
        return texto
    # Tenta fix completo primeiro (mais rápido quando toda a string é mojibake puro)
    try:
        return texto.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    # Fix parcial: substitui cada par (alto-latin1 + byte-continuação) individualmente
    import re
    def _try(m):
        try:
            return m.group(0).encode("latin-1").decode("utf-8")
        except Exception:
            return m.group(0)
    # Caracteres U+00C0–U+00FF seguidos de U+0080–U+00BF são sequências UTF-8 de 2 bytes
    return re.sub(r"[\xc0-\xff][\x80-\xbf]", _try, texto)


def limpar_texto(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = fix_mojibake(str(v).strip())
    return s if s else None


# ── Carga ─────────────────────────────────────────────────────────────────────

df_relacao = pd.read_csv(
    RELACAO_CSV,
    sep=";",
    encoding="utf-8-sig",
    dtype=str,
    skip_blank_lines=True,
)

# Remove a primeira coluna vazia (índice extra no CSV)
df_relacao.columns = [c.strip() for c in df_relacao.columns]
if df_relacao.columns[0] in ("", "Unnamed: 0"):
    df_relacao = df_relacao.iloc[:, 1:]

# Remove linhas completamente vazias
df_relacao.dropna(how="all", inplace=True)
df_relacao = df_relacao[df_relacao["ESTUDO"].notna() & (df_relacao["ESTUDO"].str.strip() != "")]
df_relacao.reset_index(drop=True, inplace=True)

df_estudos = pd.read_csv(ESTUDOS_CSV, dtype=str)
df_estudos.columns = [c.lower().strip() for c in df_estudos.columns]

df_kits = pd.read_csv(KITS_CSV, dtype=str)
df_kits.columns = [c.lower().strip() for c in df_kits.columns]
df_kits["estudo_id"] = df_kits["estudo_id"].str.strip()
df_kits["id"]        = df_kits["id"].str.strip()

# ── Índices de busca ──────────────────────────────────────────────────────────

# Estudo: norm_nome → id_estudo
estudo_idx: dict[str, str] = {}
for _, row in df_estudos.iterrows():
    estudo_idx[normalizar(row["estudo"])] = row["id_estudo"].strip()

# Kits: (norm_nome, estudo_id) → id produto  |  norm_nome → id produto (fallback)
kit_idx_full: dict[tuple, str] = {}
kit_idx_nome: dict[str, str]   = {}
for _, row in df_kits.iterrows():
    chave = (normalizar(row["nome"]), row["estudo_id"].strip())
    kit_idx_full[chave] = row["id"].strip()
    if normalizar(row["nome"]) not in kit_idx_nome:
        kit_idx_nome[normalizar(row["nome"])] = row["id"].strip()


def buscar_kit(nome_kit: str, id_estudo: str) -> str | None:
    if not nome_kit:
        return None
    n = normalizar(nome_kit)
    # 1) Exato com estudo
    if (n, id_estudo) in kit_idx_full:
        return kit_idx_full[(n, id_estudo)]
    # 2) Exato sem estudo
    if n in kit_idx_nome:
        return kit_idx_nome[n]
    # 3) Contém — kit do banco contém o nome do CSV (e mesmo estudo)
    for (kit_n, est_id), kid in kit_idx_full.items():
        if est_id == id_estudo and n and n in kit_n:
            return kid
    # 4) Contém — inverso
    for (kit_n, est_id), kid in kit_idx_full.items():
        if est_id == id_estudo and kit_n and kit_n in n:
            return kid
    return None


# ── Processamento ─────────────────────────────────────────────────────────────

rows_ok     = []
rows_erros  = []

for _, row in df_relacao.iterrows():
    estudo_raw  = limpar_texto(row.get("ESTUDO"))
    visita      = limpar_texto(row.get("VISITA"))
    kit_raw     = limpar_texto(row.get("KIT TYPE"))
    envio       = limpar_texto(row.get("ENVIO"))
    laboratorio = limpar_texto(row.get("LABORATORIO"))
    courier     = limpar_texto(row.get("COURIER"))

    temperatura = consolidar_temperatura(
        row.get("AMBIENTE", ""),
        row.get("REFRIGERADA", ""),
        row.get("CONGELADA", ""),
    )

    # Mapear estudo
    id_estudo = estudo_idx.get(normalizar(estudo_raw or ""))
    if not id_estudo:
        rows_erros.append({
            "motivo": "estudo_nao_encontrado",
            "estudo": estudo_raw,
            "visita": visita,
            "kit_type_raw": kit_raw,
        })
        continue

    # Mapear kit
    kit_id   = buscar_kit(kit_raw, id_estudo) if kit_raw else None
    kit_warn = (kit_raw is not None) and (kit_id is None)

    rows_ok.append({
        "id_estudo":   id_estudo,
        "visita":      visita,
        "kit_type":    kit_id,
        "envio":       envio,
        "temperatura": temperatura,
        "laboratorio": laboratorio,
        "courier":     courier,
        # colunas de diagnóstico (remover antes de importar se preferir)
        "_estudo_raw": estudo_raw,
        "_kit_raw":    kit_raw,
        "_kit_warn":   "kit_nao_encontrado" if kit_warn else "",
    })

# ── Saída ─────────────────────────────────────────────────────────────────────

df_ok = pd.DataFrame(rows_ok)
df_err = pd.DataFrame(rows_erros)

# CSV de importação (sem colunas de diagnóstico)
cols_import = ["id_estudo", "visita", "kit_type", "envio", "temperatura", "laboratorio", "courier"]
df_ok[cols_import].to_csv(OUT_OK, index=False, encoding="utf-8-sig")

# CSV de diagnóstico completo (com avisos de kit)
df_ok.to_csv(HERE / "output_diagnostico.csv", index=False, encoding="utf-8-sig")

# CSV de erros de estudo não encontrado
df_err.to_csv(OUT_ERROS, index=False, encoding="utf-8-sig")

# ── Relatório ─────────────────────────────────────────────────────────────────

total        = len(df_relacao)
ok           = len(df_ok)
erros_estudo = len(df_err)
kit_warns    = df_ok["_kit_warn"].eq("kit_nao_encontrado").sum() if not df_ok.empty else 0
kit_ok       = ok - kit_warns

print(f"\n{'='*55}")
print(f"  RELATÓRIO DE PROCESSAMENTO")
print(f"{'='*55}")
print(f"  Linhas lidas:              {total}")
print(f"  ✅ Mapeadas (estudo OK):   {ok}")
print(f"     ├─ kit mapeado:         {kit_ok}")
print(f"     └─ kit NÃO mapeado:    {kit_warns}  (kit_type ficará NULL)")
print(f"  ❌ Estudo não encontrado:  {erros_estudo}")
print(f"{'='*55}")
print(f"\nArquivos gerados em: {HERE}")
print(f"  output_relacao_visita_kit.csv  → importar no Supabase")
print(f"  output_diagnostico.csv         → revisar avisos de kit")
print(f"  output_nao_mapeados.csv        → estudos não encontrados")

if erros_estudo > 0:
    print(f"\n  Estudos não encontrados:")
    for e in df_err["estudo"].unique():
        print(f"    - {e}")

if kit_warns > 0:
    print(f"\n  Kits não mapeados (amostra):")
    sample = df_ok[df_ok["_kit_warn"] != ""][["_estudo_raw", "_kit_raw"]].drop_duplicates().head(15)
    for _, r in sample.iterrows():
        print(f"    [{r['_estudo_raw']}]  {r['_kit_raw']}")
