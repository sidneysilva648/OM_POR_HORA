"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ARQUIVO: main.py — orquestrador principal
AUTOR  : Sidney Albuquerque (BEMOL S/A)
DESCRIÇÃO:
    Ponto de entrada único da automação. Este é o arquivo que
    o Agendador de Tarefas do Windows deve chamar nos horários:
        09:30, 10:30, 11:30, 13:30, 14:30, 15:30, 16:30, 17:30

    Fluxo completo:
      1) Abre o SAP GUI e conecta à PRD-SSO [SAPPRD] (etapa 01).
      2) Executa a ZWM117 e lê os 3 indicadores (etapa 02).
      3) Grava no histórico do dia em JSON (etapa 03).
      4) Renderiza os 2 dashboards HTML em PNG (etapa 04):
            - cards/montagem_externa_<timestamp>.png
            - cards/administrativo_<timestamp>.png
      5) Envia cada PNG para o grupo correspondente (etapa 05).
      6) Registra log da execução.

USO:
    python main.py                       → fluxo completo
    python main.py --parcial 3           → força gravação na 3ª parcial
    python main.py --diagnostico         → dumpa o tree do SAP (debug)
    python main.py --skip-whatsapp       → só gera os dashboards
    python main.py --skip-card           → só grava no histórico
    python main.py --so-admin            → envia só pro admin
    python main.py --so-montagem         → envia só pro montagem
==============================================================
"""

import sys
import traceback
import importlib.util
from datetime import datetime
from pathlib import Path 
import json


HERE = Path(__file__).parent
LOG_FILE = HERE / "execucoes.log"


# ============================================================
# META DIÁRIA
# ============================================================
# Meta de montagens concluídas com sucesso para o dia (Seg–Sex).
# O mesmo valor deve estar em 03_gravar_historico.py → PARCIAIS_PADRAO_SEG_SEX.
META_DIA = 350

# ============================================================
# LEGENDAS DO WHATSAPP
# ============================================================
# Cada parcial (1..8) tem seu próprio cabeçalho identificando a hora.
# Depois do cabeçalho, é anexado o RODAPÉ FIXO (mesmo nas 8 parciais).
# Edite aqui pra mudar o texto.
# Suporta emojis nativos (use Win+. pra abrir o painel de emoji).
# ============================================================

# Cabeçalho variável conforme a parcial — grupo Montagem Externa Bemol
LEGENDAS_MONTAGEM_POR_PARCIAL = {
    1: "09:30 - Primeira parcial do dia !!",
    2: "10:30 - Segunda parcial do dia",
    3: "11:30 - Terceira parcial do dia",
    4: "13:30 - Quarta parcial do dia",
    5: "14:30 - Quinta parcial do dia",
    6: "15:30 - Sexta parcial do dia",
    7: "16:30 - Sétima parcial do dia",
    8: "17:30 - Última parcial do dia !",
}

# Rodapé fixo (vai junto em TODAS as 8 parciais do grupo Montagem Externa)
RODAPE_MONTAGEM = (
    "Tenham um ótimo dia de trabalho!"
)

# Cabeçalho variável conforme a parcial — grupo LogRev - Montagem - Adms
# (Sem rodapé — só o identificador da parcial)
LEGENDAS_ADMIN_POR_PARCIAL = {
    1: "09:30 - Primeira parcial do dia !!",
    2: "10:30 - Segunda parcial do dia",
    3: "11:30 - Terceira parcial do dia",
    4: "13:30 - Quarta parcial do dia",
    5: "14:30 - Quinta parcial do dia",
    6: "15:30 - Sexta parcial do dia",
    7: "16:30 - Sétima parcial do dia",
    8: "17:30 - Última parcial do dia !",
}


def _montar_legenda_montagem(parcial: int) -> str:
    """Junta o cabeçalho da parcial com o rodapé fixo (grupo Montagem)."""
    cabecalho = LEGENDAS_MONTAGEM_POR_PARCIAL.get(parcial, f"Parcial {parcial}")
    return f"{cabecalho}\n\n{RODAPE_MONTAGEM}"


def _montar_legenda_admin(parcial: int) -> str:
    """Retorna apenas o cabeçalho da parcial (grupo Administrativo, sem rodapé)."""
    return LEGENDAS_ADMIN_POR_PARCIAL.get(parcial, f"Parcial {parcial}")


def _carregar(nome: str, arquivo: str):
    spec = importlib.util.spec_from_file_location(nome, HERE / arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _registrar_log(linha: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {linha}\n")


def main() -> int:
    # ----- Parse de argumentos -----
    diagnostico    = "--diagnostico" in sys.argv or "-d" in sys.argv
    skip_whatsapp  = "--skip-whatsapp" in sys.argv
    skip_card      = "--skip-card" in sys.argv
    so_admin       = "--so-admin" in sys.argv
    so_montagem    = "--so-montagem" in sys.argv
    parcial_forcada = None
    if "--parcial" in sys.argv:
        idx = sys.argv.index("--parcial")
        try:
            parcial_forcada = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("[ERRO] --parcial precisa de um número de 1 a 8.")
            return 2

    print("=" * 60)
    print(f"OM_por_HORA — execução em {datetime.now():%d/%m/%Y %H:%M:%S}")
    print("=" * 60)

    try:
        # ----- Carrega módulos -----
        zwm117   = _carregar("zwm117",   "02_executar_zwm117.py")
        gravar   = _carregar("gravar",   "03_gravar_historico.py")
        card_mod = _carregar("card",     "04_gerar_card.py")
        wpp_mod  = _carregar("wpp",      "05_enviar_whatsapp.py")

        # ----- ETAPAS 01 + 02: abrir SAP e ler indicadores -----
        indicadores = zwm117.executar(diagnostico=diagnostico)

        # ----- ETAPA 03: gravar no histórico (JSON) -----
        parcial, historico = gravar.gravar(indicadores, parcial=parcial_forcada)

        msg = (
            f"PARCIAL {parcial} gravada | "
            f"Sucesso={indicadores['sucesso']} "
            f"Insucesso={indicadores['insucesso']} "
            f"Iniciadas={indicadores['iniciadas']}"
        )
        print("\n[OK]", msg)
        _registrar_log("OK   | " + msg)

        # ----- ETAPA 04: gerar dashboards -----
        if skip_card:
            print("[INFO] --skip-card → não gerando dashboards.")
            return 0

        print("\n--- Gerando dashboards ---")
        paths = card_mod.gerar_todos()
        _registrar_log(f"CARD | montagem={paths['montagem'].name} admin={paths['admin'].name}")

        # ----- ETAPA 05: enviar nos grupos -----
        if skip_whatsapp:
            print("[INFO] --skip-whatsapp → dashboards gerados, mas não enviados.")
            return 0

        # Monta legendas baseadas na parcial atual:
        #   - Montagem: cabeçalho variável + rodapé fixo
        #   - Admin:    apenas o cabeçalho variável (sem rodapé)
        legenda_montagem = _montar_legenda_montagem(parcial)
        legenda_admin    = _montar_legenda_admin(parcial)

        envios = {}
        if not so_admin:
            envios[wpp_mod.GRUPO_MONTAGEM_EXTERNA] = (paths["montagem"], legenda_montagem)
        if not so_montagem:
            envios[wpp_mod.GRUPO_ADMINISTRATIVO]   = (paths["admin"],    legenda_admin)

        resultados = wpp_mod.enviar_dashboards(envios)
        for grupo, status in resultados.items():
            marca = "OK " if status is True else "ERR"
            _registrar_log(f"WPP  | {marca} {grupo} {'' if status is True else str(status)}")
        return 0

    except Exception as e:
        erro = f"FALHA: {type(e).__name__}: {e}"
        print("\n[ERRO]", erro)
        traceback.print_exc()
        _registrar_log("ERR  | " + erro)
        return 1


if __name__ == "__main__":
    sys.exit(main())

    

    
       

