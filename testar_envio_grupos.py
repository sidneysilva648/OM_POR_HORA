"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ARQUIVO: testar_envio_grupos.py — TESTE de envio (isolado)
AUTOR  : Sidney Albuquerque (BEMOL S/A)

DESCRIÇÃO:
    Pega os PNGs JÁ SALVOS em cards/ e envia pros grupos do
    WhatsApp. Serve apenas para verificar visualmente o
    TAMANHO e FORMATO da imagem no grupo.

    O QUE ESTE SCRIPT FAZ:
      ✅ Envia o PNG existente pros grupos via enviar_dashboards
      ✅ Reaproveita a sessão do WhatsApp Web já logada

    O QUE ESTE SCRIPT NÃO FAZ:
      ❌ NÃO abre o SAP
      ❌ NÃO roda a ZWM117
      ❌ NÃO mexe no parciais_hoje.json
      ❌ NÃO regenera os PNGs

USO:
    python testar_envio_grupos.py                → envia pros 2 grupos
    python testar_envio_grupos.py --so-montagem  → só Montagem Externa Bemol
    python testar_envio_grupos.py --so-admin     → só LogRev - Montagem - Adms
==============================================================
"""

import sys
import importlib.util
from pathlib import Path

HERE = Path(__file__).parent
PASTA_CARDS = HERE / "cards"

# JPGs gerados pela etapa 04 (formato que o WhatsApp trata como foto, não sticker)
# Se ainda existir só PNG na pasta, o script avisa pra rodar 04_gerar_card.py.
PNG_MONTAGEM = PASTA_CARDS / "montagem_externa.jpg"
PNG_ADMIN    = PASTA_CARDS / "administrativo.jpg"

# Legenda de teste (curta e clara, só pra identificar)
LEGENDA_TESTE_MONTAGEM = "🧪 TESTE — verificando tamanho da imagem"
LEGENDA_TESTE_ADMIN    = "🧪 TESTE — verificando tamanho da imagem"


def main() -> int:
    # ----- Carrega o módulo de WhatsApp (sem rodar nada de SAP) -----
    spec = importlib.util.spec_from_file_location(
        "wpp", HERE / "05_enviar_whatsapp.py"
    )
    wpp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wpp)

    # ----- Parse flags -----
    so_montagem = "--so-montagem" in sys.argv
    so_admin    = "--so-admin"    in sys.argv

    # ----- Verifica que os PNGs existem -----
    if not PNG_MONTAGEM.exists():
        print(f"[ERRO] PNG não encontrado: {PNG_MONTAGEM}")
        print("        Rode antes: python 04_gerar_card.py")
        return 1
    if not PNG_ADMIN.exists():
        print(f"[ERRO] PNG não encontrado: {PNG_ADMIN}")
        print("        Rode antes: python 04_gerar_card.py")
        return 1

    # ----- Mostra info dos arquivos -----
    print("=" * 60)
    print(" TESTE de envio — usando PNGs já salvos em cards/")
    print("=" * 60)
    print()
    print(f"  Montagem  : {PNG_MONTAGEM.name}  "
          f"({PNG_MONTAGEM.stat().st_size // 1024} KB)")
    print(f"  Admin     : {PNG_ADMIN.name}  "
          f"({PNG_ADMIN.stat().st_size // 1024} KB)")
    print()

    # ----- Monta o dict de envios -----
    envios = {}
    if not so_admin:
        envios[wpp.GRUPO_MONTAGEM_EXTERNA] = (PNG_MONTAGEM, LEGENDA_TESTE_MONTAGEM)
    if not so_montagem:
        envios[wpp.GRUPO_ADMINISTRATIVO]   = (PNG_ADMIN,    LEGENDA_TESTE_ADMIN)

    if not envios:
        print("[ERRO] Você passou ambos --so-montagem e --so-admin (sobra nenhum)?")
        return 2

    # ----- Envia -----
    resultados = wpp.enviar_dashboards(envios)

    # ----- Mostra resumo -----
    print()
    print("=" * 60)
    print(" RESULTADO")
    print("=" * 60)
    for grupo, status in resultados.items():
        if status is True:
            print(f"  [OK]  {grupo}")
        else:
            print(f"  [ERR] {grupo}: {status}")
    print()
    print("Agora confere no celular como chegou:")
    print("  - É FOTO normal? (toque na imagem abre em tela cheia com zoom)")
    print("  - É STICKER? (imagem pequena, sem legenda visível)")
    print()

    # Retorna sucesso se TODOS deram ok
    return 0 if all(v is True for v in resultados.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
