"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ETAPA  : 03 — Gravar histórico do dia (JSON)
AUTOR  : Sidney Albuquerque (BEMOL S/A)
DESCRIÇÃO:
    Substitui o antigo 03_gravar_planilha.py.
    Agora os dados não vão pra um Excel — vão pra um JSON
    local que serve de "estado do dia". Esse JSON é lido pelos
    templates HTML para renderizar os dashboards.

    Formato do JSON (parciais_hoje.json):
    {
        "data": "2026-05-15",
        "atualizado_em": "2026-05-15T14:30:00",
        "meta_total_dia": 385,
        "parciais": [
            {"n": 1, "hora": "09:30", "meta": 48,
             "sucesso": null, "insucesso": null, "iniciadas": null},
            ...
        ]
    }

    A cada execução, a parcial correspondente ao horário atual
    (ou forçada via parâmetro) é preenchida. Se o JSON for de
    OUTRO DIA, ele é resetado.
==============================================================
"""

import json
from datetime import datetime, date, time as dtime
from pathlib import Path
from typing import Optional

# ============================================================
# CONFIGURAÇÕES
# ============================================================

HERE = Path(__file__).parent
HISTORICO_JSON = HERE / "parciais_hoje.json"

# Estrutura padrão das 8 parciais do dia.
# Horários e metas conforme o dashboard atual.
# Aplicado de SEGUNDA a SEXTA (weekday() 0-4)
# Meta total: 300 (recalculada proporcionalmente)
PARCIAIS_PADRAO_SEG_SEX = [
    {"n": 1, "hora": "09:30", "meta": 38},
    {"n": 2, "hora": "10:30", "meta": 76},
    {"n": 3, "hora": "11:30", "meta": 114},
    {"n": 4, "hora": "13:30", "meta": 152},
    {"n": 5, "hora": "14:30", "meta": 190},
    {"n": 6, "hora": "15:30", "meta": 228},
    {"n": 7, "hora": "16:30", "meta": 266},
    {"n": 8, "hora": "17:30", "meta": 300},
]

# Metas específicas do SÁBADO (weekday() == 5).
# Meta total: 350 (igual à Seg-Sex)
PARCIAIS_PADRAO_SABADO = [
    {"n": 1, "hora": "09:30", "meta": 44},
    {"n": 2, "hora": "10:30", "meta": 88},
    {"n": 3, "hora": "11:30", "meta": 131},
    {"n": 4, "hora": "13:30", "meta": 175},
    {"n": 5, "hora": "14:30", "meta": 219},
    {"n": 6, "hora": "15:30", "meta": 263},
    {"n": 7, "hora": "16:30", "meta": 306},
    {"n": 8, "hora": "17:30", "meta": 350},
]


def _parciais_para_hoje(agora: datetime = None):
    """
    Escolhe a lista de parciais conforme o dia da semana.
    weekday(): 0=Seg, 1=Ter, 2=Qua, 3=Qui, 4=Sex, 5=Sáb, 6=Dom
    """
    if agora is None:
        agora = datetime.now()
    if agora.weekday() == 5:  # sábado
        return PARCIAIS_PADRAO_SABADO
    return PARCIAIS_PADRAO_SEG_SEX


# Compatibilidade com código antigo que importa PARCIAIS_PADRAO direto
# (resolve conforme o dia da semana no momento do import)
PARCIAIS_PADRAO = _parciais_para_hoje()


# ============================================================
# FUNÇÕES
# ============================================================

def _parcial_atual_por_horario(agora: datetime = None) -> int:
    """
    Retorna o número da parcial (1..8) baseado no horário atual.

    Lógica:
      1) Se o horário atual estiver dentro de ±JANELA_MIN minutos de
         algum parcial cadastrado, SNAP para esse parcial (escolhe o
         mais próximo).
      2) Caso contrário, retorna o último parcial cuja hora já passou.

    Por que essa lógica?
      Permite agendar no Windows Task Scheduler um pouco ANTES da
      hora cheia (ex.: 10:20 pra parcial das 10:30) e ainda assim
      ela grava no lugar certo. Isso também tolera atrasos pequenos
      do agendador (rodar 10:35 conta como 10:30).

    Exemplos com JANELA_MIN = 15:
      10:20 → parcial 2 (10:30, dentro de -10min)
      10:35 → parcial 2 (10:30, dentro de +5min)
      10:00 → parcial 1 (09:30 já passou; 10:30 está a -30min, fora da janela)
      14:50 → parcial 5 (14:30 já passou; 15:30 está a -40min, fora da janela)
    """
    if agora is None:
        agora = datetime.now()

    JANELA_MIN = 15
    minutos_agora = agora.hour * 60 + agora.minute

    melhor_dist = JANELA_MIN + 1
    melhor_parcial = None
    ultimo_passado = 1

    parciais_do_dia = _parciais_para_hoje(agora)
    for p in parciais_do_dia:
        h, m = map(int, p["hora"].split(":"))
        minutos_parcial = h * 60 + m
        dist = abs(minutos_agora - minutos_parcial)

        # Snap pelo mais próximo dentro da janela
        if dist <= JANELA_MIN and dist < melhor_dist:
            melhor_dist = dist
            melhor_parcial = p["n"]

        # Fallback: último parcial cuja hora já passou
        if minutos_agora >= minutos_parcial:
            ultimo_passado = p["n"]

    return melhor_parcial if melhor_parcial is not None else ultimo_passado


def _vazio_para_hoje(hoje_iso: str) -> dict:
    """Estrutura inicial do JSON para o dia."""
    parciais_do_dia = _parciais_para_hoje()
    parciais = []
    for p in parciais_do_dia:
        parciais.append({
            **p,
            "sucesso":   None,
            "insucesso": None,
            "iniciadas": None,
        })
    return {
        "data": hoje_iso,
        "atualizado_em": None,
        "meta_total_dia": parciais_do_dia[-1]["meta"],
        "parciais": parciais,
    }


def carregar_historico() -> dict:
    """Carrega o JSON do dia; cria/reseta se for outro dia."""
    hoje_iso = date.today().isoformat()
    if HISTORICO_JSON.exists():
        try:
            dados = json.loads(HISTORICO_JSON.read_text(encoding="utf-8"))
            if dados.get("data") == hoje_iso:
                return dados
            print(f"[INFO] Histórico era de {dados.get('data')} → resetando para {hoje_iso}.")
        except Exception as e:
            print(f"[AVISO] JSON corrompido ({e}) — recriando.")
    return _vazio_para_hoje(hoje_iso)


def salvar_historico(dados: dict) -> None:
    HISTORICO_JSON.write_text(
        json.dumps(dados, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def gravar(
    indicadores: dict,
    parcial: Optional[int] = None,
) -> tuple[int, dict]:
    """
    Atualiza a parcial atual no JSON do dia.

    Args:
        indicadores: {'sucesso': int, 'insucesso': int, 'iniciadas': int}
        parcial    : número 1..8 (None = detecta pelo horário atual)

    Returns:
        (parcial_gravada, dict_historico_completo)
    """
    dados = carregar_historico()

    if parcial is None:
        parcial = _parcial_atual_por_horario()

    if not 1 <= parcial <= 8:
        raise ValueError(f"Parcial inválida: {parcial} (use 1..8).")

    print(f"[INFO] Gravando parcial {parcial} no histórico do dia...")

    # Atualiza a parcial correspondente
    for p in dados["parciais"]:
        if p["n"] == parcial:
            p["sucesso"]   = int(indicadores.get("sucesso", 0))
            p["insucesso"] = int(indicadores.get("insucesso", 0))
            p["iniciadas"] = int(indicadores.get("iniciadas", 0))
            break

    dados["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_historico(dados)

    print(f"[OK] Parcial {parcial} → Sucesso={indicadores.get('sucesso')} "
          f"Insucesso={indicadores.get('insucesso')} "
          f"Iniciadas={indicadores.get('iniciadas')}")
    return parcial, dados


# ============================================================
# Compat com main.py antigo
# ============================================================
# Função-alias para não quebrar o main.py atual enquanto migramos.
# Retorna (parcial, linha=parcial) — "linha" não faz mais sentido,
# mas a tupla mantém compatibilidade.
def gravar_compat(indicadores, parcial=None):
    p, _dados = gravar(indicadores, parcial=parcial)
    return p, p


# ============================================================
# EXECUÇÃO MANUAL
# ============================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 5:
        p = int(sys.argv[1])
        ind = {
            "sucesso":   int(sys.argv[2]),
            "insucesso": int(sys.argv[3]),
            "iniciadas": int(sys.argv[4]),
        }
        gravar(ind, parcial=p)
    else:
        p_now = _parcial_atual_por_horario()
        print(f"Parcial detectada agora: {p_now}ª")
        print("Uso manual: python 03_gravar_historico.py <parcial> <sucesso> <insucesso> <iniciadas>")
