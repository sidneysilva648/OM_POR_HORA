"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ETAPA  : 03 — Gravar indicadores na planilha
AUTOR  : Sidney Albuquerque (BEMOL S/A)
DESCRIÇÃO:
    Recebe os indicadores extraídos da ZWM117 e grava nas
    colunas C (Sucesso), D (Insucesso) e E (Iniciadas) da
    LINHA correspondente à parcial atual.

    Estrutura confirmada da planilha (Planilha1):
       Linha 5  → 1ª parcial (09:30)
       Linha 6  → 2ª parcial (10:30)
       Linha 7  → 3ª parcial (12:30)
       Linha 8  → 4ª parcial (13:40)
       Linha 9  → 5ª parcial (14:30)
       Linha 10 → 6ª parcial (15:30)
       Linha 11 → 7ª parcial (16:35)
       Linha 12 → 8ª parcial (17:30)
==============================================================
"""

from datetime import datetime, time
from pathlib import Path
import sys
import shutil
import time as _time

from openpyxl import load_workbook

# ============================================================
# CONFIGURAÇÕES
# ============================================================

PLANILHA = Path(
    r"C:\Users\21039\OneDrive - BEMOL S A\automacao"
    r"\OM POR HORA\OM_POR_HORA - AUTOMAÇÃO.xlsx"
)
ABA = "Planilha1"

COLUNA_SUCESSO   = "C"
COLUNA_INSUCESSO = "D"
COLUNA_INICIADAS = "E"

# Mapa parcial → (linha, hora de referência)
PARCIAIS = [
    (1, 5,  time(9,  30)),
    (2, 6,  time(10, 30)),
    (3, 7,  time(12, 30)),
    (4, 8,  time(13, 40)),
    (5, 9,  time(14, 30)),
    (6, 10, time(15, 30)),
    (7, 11, time(16, 35)),
    (8, 12, time(17, 30)),
]

# ============================================================
# FUNÇÕES
# ============================================================

def fechar_planilha_no_excel() -> bool:
    """
    Se a planilha estiver aberta no Excel, salva e fecha aquele workbook
    para liberar o arquivo. Retorna True se conseguiu fechar.
    """
    try:
        import win32com.client
        import pythoncom
    except ImportError:
        return False

    fechou = False
    alvo = str(PLANILHA).lower()

    # Tenta achar instâncias do Excel já abertas
    try:
        pythoncom.CoInitialize()
        try:
            excel = win32com.client.GetActiveObject("Excel.Application")
        except Exception:
            return False  # Excel não está rodando — nada a fechar

        for wb in list(excel.Workbooks):
            try:
                fullname = (wb.FullName or "").lower()
            except Exception:
                continue
            if fullname == alvo or Path(fullname).name == PLANILHA.name:
                try:
                    print(f"[INFO] Fechando '{wb.Name}' aberta no Excel...")
                    wb.Save()
                    wb.Close(SaveChanges=False)
                    fechou = True
                except Exception as e:
                    print(f"[AVISO] Não consegui fechar o workbook: {e}")
        # Se o Excel ficou sem workbooks abertos, encerra a aplicação
        try:
            if excel.Workbooks.Count == 0:
                excel.Quit()
        except Exception:
            pass
    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    if fechou:
        # Dá um instante para o Windows liberar o lock do arquivo
        _time.sleep(1.0)
    return fechou


def detectar_parcial(agora: datetime | None = None) -> tuple[int, int]:
    """
    Retorna (numero_parcial, linha_excel) com base no horário atual.
    Escolhe a parcial mais próxima (e <= agora) dentro de uma janela
    de tolerância. Se for muito antes da 1ª, usa a 1ª. Se depois da 8ª,
    usa a 8ª.
    """
    if agora is None:
        agora = datetime.now()
    hora_atual = agora.time()

    # Maior parcial cujo horário já passou
    escolhida = PARCIAIS[0]
    for n, linha, hora_ref in PARCIAIS:
        if hora_atual >= hora_ref:
            escolhida = (n, linha, hora_ref)

    n, linha, _ = escolhida
    return n, linha


def gravar(indicadores: dict, parcial: int | None = None) -> tuple[int, int]:
    """
    Grava os 3 indicadores na linha correspondente.

    Args:
        indicadores: {'sucesso': int, 'insucesso': int, 'iniciadas': int}
        parcial    : Número 1-8. Se None, detecta pelo horário atual.

    Returns:
        (parcial, linha) realmente gravadas.
    """
    if not PLANILHA.exists():
        raise FileNotFoundError(f"Planilha não encontrada: {PLANILHA}")

    # Determina a parcial / linha
    if parcial is None:
        parcial, linha = detectar_parcial()
    else:
        encontrada = next((p for p in PARCIAIS if p[0] == parcial), None)
        if not encontrada:
            raise ValueError(f"Parcial inválida: {parcial} (use 1-8).")
        _, linha, _ = encontrada

    print(f"[INFO] Gravando na parcial {parcial} (linha {linha}) da '{ABA}'...")

    # Se a planilha estiver aberta no Excel, fecha para liberar o arquivo
    fechar_planilha_no_excel()

    # Backup defensivo antes de salvar
    backup = PLANILHA.with_suffix(".bak.xlsx")
    try:
        shutil.copy2(PLANILHA, backup)
    except PermissionError:
        print("[AVISO] Backup falhou (arquivo ainda em uso). Seguindo mesmo assim.")
    except Exception as e:
        print(f"[AVISO] Falha ao criar backup ({e}) — seguindo mesmo assim.")

    # Retry para vencer locks transitórios do Windows/OneDrive
    ultima_excecao = None
    for tentativa in range(1, 6):
        try:
            wb = load_workbook(PLANILHA)
            if ABA not in wb.sheetnames:
                raise ValueError(f"Aba '{ABA}' não encontrada na planilha.")
            ws = wb[ABA]

            ws[f"{COLUNA_SUCESSO}{linha}"]   = int(indicadores.get("sucesso", 0))
            ws[f"{COLUNA_INSUCESSO}{linha}"] = int(indicadores.get("insucesso", 0))
            ws[f"{COLUNA_INICIADAS}{linha}"] = int(indicadores.get("iniciadas", 0))

            wb.save(PLANILHA)
            wb.close()

            print(f"[OK] Gravado: C{linha}={indicadores.get('sucesso',0)} "
                  f"D{linha}={indicadores.get('insucesso',0)} "
                  f"E{linha}={indicadores.get('iniciadas',0)}")
            return parcial, linha

        except PermissionError as e:
            ultima_excecao = e
            print(f"[AVISO] Tentativa {tentativa}/5 — arquivo bloqueado. "
                  f"Tentando fechar Excel e aguardar...")
            fechar_planilha_no_excel()
            _time.sleep(2 * tentativa)  # backoff progressivo

    # Esgotou as tentativas
    raise PermissionError(
        f"Não foi possível gravar em '{PLANILHA.name}' — o arquivo continua "
        f"em uso. Feche o Excel e tente novamente.\n"
        f"Erro original: {ultima_excecao}"
    )


# ============================================================
# EXECUÇÃO MANUAL (para testes)
# ============================================================

if __name__ == "__main__":
    # Exemplo de uso manual para testar a gravação sem rodar o SAP:
    #   python 03_gravar_planilha.py 1 100 5 12
    # → grava parcial 1: sucesso=100, insucesso=5, iniciadas=12
    if len(sys.argv) == 5:
        p = int(sys.argv[1])
        ind = {
            "sucesso":   int(sys.argv[2]),
            "insucesso": int(sys.argv[3]),
            "iniciadas": int(sys.argv[4]),
        }
        gravar(ind, parcial=p)
    else:
        # Apenas mostra qual parcial seria gravada agora
        p, l = detectar_parcial()
        print(f"Parcial detectada para agora: {p}ª (linha {l})")
        print("Para gravar manualmente: "
              "python 03_gravar_planilha.py <parcial> <sucesso> <insucesso> <iniciadas>")
