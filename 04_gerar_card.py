"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ETAPA  : 04 — Gerar dashboards (HTML → PNG)
AUTOR  : Sidney Albuquerque (BEMOL S/A)
DESCRIÇÃO:
    Renderiza os dois templates HTML (montagem_externa.html e
    administrativo.html) em Chrome headless e tira screenshot
    do elemento principal (#dash-root), gerando dois PNGs:
        cards/montagem_externa_YYYYMMDD_HHMMSS.png
        cards/administrativo_YYYYMMDD_HHMMSS.png

    Lê os dados do parciais_hoje.json (etapa 03).
==============================================================
"""

import sys
import json
import time
import base64
import importlib.util
from datetime import datetime, time as dtime
from pathlib import Path

# ============================================================
# CONFIGURAÇÕES
# ============================================================

HERE = Path(__file__).parent
PASTA_CARDS = HERE / "cards"
PASTA_CARDS.mkdir(exist_ok=True)

PASTA_TEMPLATES = HERE / "templates"
TEMPLATE_MONTAGEM = PASTA_TEMPLATES / "montagem_externa.html"
TEMPLATE_ADMIN     = PASTA_TEMPLATES / "administrativo.html"

LOGO_BEMOL = HERE / "bemol.png"

HISTORICO_JSON = HERE / "parciais_hoje.json"


def _logo_base64() -> str:
    """Lê bemol.png e devolve como data URI base64 — pronto pra usar no src=...
    Embarcar o logo no próprio HTML evita problemas de caminho quando o
    Chrome carrega o arquivo via file:// e simplifica deployment.
    """
    if not LOGO_BEMOL.exists():
        print(f"[AVISO] {LOGO_BEMOL.name} não encontrado — logo ficará vazio.")
        return ""
    try:
        b64 = base64.b64encode(LOGO_BEMOL.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        print(f"[AVISO] Falha ao codificar logo: {e}")
        return ""

# ============================================================
# FORMATAÇÃO DE DATA
# ============================================================

DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira",
    "quinta-feira", "sexta-feira", "sábado", "domingo",
]
MESES = [
    "", "janeiro", "fevereiro", "março", "abril", "maio",
    "junho", "julho", "agosto", "setembro", "outubro",
    "novembro", "dezembro",
]

def _formatar_data(d: datetime) -> str:
    return f"{DIAS_SEMANA[d.weekday()]}, {d.day} de {MESES[d.month]} de {d.year}"


# ============================================================
# CARREGA E PREPARA DADOS PARA OS TEMPLATES
# ============================================================

def _carregar_historico() -> dict:
    if not HISTORICO_JSON.exists():
        raise FileNotFoundError(
            f"Histórico não encontrado: {HISTORICO_JSON}\n"
            "Rode a etapa 03 antes de gerar os dashboards."
        )
    return json.loads(HISTORICO_JSON.read_text(encoding="utf-8"))


def _calcular_kpis(historico: dict) -> dict:
    """Soma cumulativa atual e derivados para o dashboard administrativo."""
    parciais_preenchidas = [
        p for p in historico["parciais"]
        if p.get("sucesso") is not None
    ]
    if not parciais_preenchidas:
        ultima = {"sucesso": 0, "insucesso": 0, "iniciadas": 0}
    else:
        ultima = parciais_preenchidas[-1]

    sucesso   = ultima.get("sucesso")   or 0
    insucesso = ultima.get("insucesso") or 0
    iniciadas = ultima.get("iniciadas") or 0
    total_processado = sucesso + insucesso + iniciadas
    meta_dia = historico["meta_total_dia"]

    def pct(v, total):
        return round((v / total) * 100, 1) if total else 0.0

    pct_sucesso   = pct(sucesso,   total_processado)
    pct_insucesso = pct(insucesso, total_processado)
    pct_iniciadas = pct(iniciadas, total_processado)
    pct_meta      = pct(sucesso,   meta_dia)
    taxa_sucesso  = pct(sucesso,   (sucesso + insucesso))

    # Ritmo: comparado à meta da última parcial preenchida
    if parciais_preenchidas:
        meta_parcial = parciais_preenchidas[-1]["meta"]
        if sucesso >= meta_parcial:
            ritmo = "BOM"
        elif sucesso >= meta_parcial * 0.8:
            ritmo = "ATENÇÃO"
        else:
            ritmo = "ABAIXO"
    else:
        ritmo = "—"

    return {
        "sucesso": sucesso,
        "insucesso": insucesso,
        "iniciadas": iniciadas,
        "meta_dia": meta_dia,
        "pct_sucesso":   pct_sucesso,
        "pct_insucesso": pct_insucesso,
        "pct_iniciadas": pct_iniciadas,
        "pct_meta":      pct_meta,
        "taxa_sucesso_pct": taxa_sucesso,
        "ritmo": ritmo,
    }


def _proxima_parcial_str(historico: dict) -> str:
    for p in historico["parciais"]:
        if p.get("sucesso") is None:
            return p["hora"]
    return "—"


def _preparar_dados_montagem(historico: dict) -> dict:
    return {"parciais": historico["parciais"]}


def _preparar_dados_admin(historico: dict) -> dict:
    return {
        "parciais": historico["parciais"],
        "kpi": _calcular_kpis(historico),
    }


# ============================================================
# RENDERIZAÇÃO HTML → PNG
# ============================================================

def _carregar_chrome_helpers():
    """Carrega _criar_driver de 05_enviar_whatsapp.py para reaproveitar."""
    spec = importlib.util.spec_from_file_location(
        "wpp", HERE / "05_enviar_whatsapp.py"
    )
    wpp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wpp)
    return wpp


def _renderizar(template_path: Path, dados: dict, data_str: str,
                hora_str: str, extras: dict, saida_nome: str,
                element_id: str = "dash-root",
                largura: int = 900, altura: int = 1200) -> Path:
    """
    Renderiza um template HTML em Chrome headless e tira screenshot
    do elemento `element_id`. Retorna o caminho do PNG.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service

    # Lê o template e faz substituições básicas (placeholders)
    html = template_path.read_text(encoding="utf-8")
    html = html.replace("{{LOGO_BASE64}}", _logo_base64())
    html = html.replace("{{DATA}}", data_str)
    html = html.replace("{{HORA}}", hora_str)
    html = html.replace("{{DADOS_JSON}}", json.dumps(dados, ensure_ascii=False))
    for chave, valor in extras.items():
        html = html.replace("{{" + chave + "}}", str(valor))

    # Salva HTML temporário (mesmo nome — sobrescreve a cada execução).
    # Esse HTML é só "vivo" durante o screenshot, depois pode até ser apagado.
    html_render = PASTA_CARDS / f"_{saida_nome}.html"
    html_render.write_text(html, encoding="utf-8")

    # Sobe um Chrome HEADLESS local para tirar screenshot
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--hide-scrollbars")
    options.add_argument(f"--window-size={largura},{altura}")
    # Renderizar em 2x de resolucao — PNG sai mais nítido e grande, evita
    # o WhatsApp tratar como sticker.
    options.add_argument("--force-device-scale-factor=2")
    options.add_argument("--high-dpi-support=1")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    try:
        from webdriver_manager.chrome import ChromeDriverManager
        servico = Service(ChromeDriverManager().install(), log_output=None)
        driver = webdriver.Chrome(service=servico, options=options)
    except ImportError:
        driver = webdriver.Chrome(options=options)

    try:
        driver.get(html_render.as_uri())
        # Espera o JavaScript terminar (linhas da tabela / Chart.js / plugin datalabels)
        inicio = time.time()
        while time.time() - inicio < 12:
            try:
                pronto = driver.execute_script("return document.readyState === 'complete' && (window.__dashReady === undefined || window.__dashReady === true);")
                if pronto:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        # Pequena margem extra para Chart.js + datalabels terminarem de pintar
        time.sleep(1.2)

        # Localiza o elemento principal
        try:
            elemento = driver.find_element(By.ID, element_id)
        except Exception:
            elemento = driver.find_element(By.TAG_NAME, "body")

        # Nome fixo — sobrescreve a cada execução.
        # 1) Selenium só sabe salvar PNG; salva temporariamente.
        png_path = PASTA_CARDS / f"{saida_nome}.png"
        elemento.screenshot(str(png_path))

        # 2) Converte PNG → JPG.
        # IMPORTANTE: WhatsApp Business trata PNG como sticker em vários
        # casos (mesmo com imagem grande / não-quadrada). Já JPG NUNCA é
        # tratado como sticker — é sempre foto. Por isso enviamos JPG.
        try:
            from PIL import Image
            jpg_path = PASTA_CARDS / f"{saida_nome}.jpg"
            img = Image.open(png_path)
            if img.mode in ("RGBA", "LA"):
                # Achata pra branco caso tenha transparência
                fundo = Image.new("RGB", img.size, (255, 255, 255))
                fundo.paste(img, mask=img.split()[-1])
                img = fundo
            else:
                img = img.convert("RGB")
            img.save(jpg_path, "JPEG", quality=92, optimize=True, progressive=True)
            print(f"[OK] {saida_nome} → {jpg_path.name}  "
                  f"({img.size[0]}x{img.size[1]}, "
                  f"{jpg_path.stat().st_size // 1024} KB)")
            return jpg_path
        except Exception as e:
            print(f"[AVISO] Falha ao converter pra JPG ({e}). Usando PNG.")
            return png_path
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ============================================================
# FUNÇÕES PÚBLICAS
# ============================================================

def gerar_montagem_externa(historico: dict = None) -> Path:
    if historico is None:
        historico = _carregar_historico()
    dados = _preparar_dados_montagem(historico)
    agora = datetime.now()
    return _renderizar(
        template_path=TEMPLATE_MONTAGEM,
        dados=dados,
        data_str=_formatar_data(agora),
        hora_str=agora.strftime("%H:%M"),
        extras={},
        saida_nome="montagem_externa",
        # Landscape (mais largo que alto) — WhatsApp trata como foto normal,
        # não como sticker. Com device-scale=2, PNG sai em ~2360x1680.
        largura=1180, altura=840,
    )


def gerar_administrativo(historico: dict = None) -> Path:
    if historico is None:
        historico = _carregar_historico()
    dados = _preparar_dados_admin(historico)
    kpi = dados["kpi"]
    agora = datetime.now()
    extras = {
        "SUCESSO":          kpi["sucesso"],
        "INSUCESSO":        kpi["insucesso"],
        "INICIADAS":        kpi["iniciadas"],
        "META_DIA":         kpi["meta_dia"],
        "SUCESSO_PCT":      kpi["pct_sucesso"],
        "INSUCESSO_PCT":    kpi["pct_insucesso"],
        "INICIADAS_PCT":    kpi["pct_iniciadas"],
        "PCT_META":         kpi["pct_meta"],
        "PROXIMA":          _proxima_parcial_str(historico),
    }
    return _renderizar(
        template_path=TEMPLATE_ADMIN,
        dados=dados,
        data_str=_formatar_data(agora),
        hora_str=agora.strftime("%H:%M"),
        extras=extras,
        saida_nome="administrativo",
        # Portrait (mais alto que largo) — WhatsApp trata como foto normal.
        # Com device-scale=2, PNG sai em ~2160x3200.
        largura=1080, altura=1600,
    )


def _limpar_arquivos_antigos() -> int:
    """
    Remove arquivos com timestamp na pasta cards/.
    Mantém apenas os arquivos com nome FIXO:
       - administrativo.png
       - montagem_externa.png
       - _administrativo.html
       - _montagem_externa.html

    Retorna a quantidade de arquivos removidos.
    """
    if not PASTA_CARDS.exists():
        return 0

    nomes_fixos = {
        # JPG é o formato final enviado pro WhatsApp (não vira sticker)
        "administrativo.jpg",
        "montagem_externa.jpg",
        # PNG é gerado pelo Selenium como passo intermediário antes do JPG
        "administrativo.png",
        "montagem_externa.png",
        # HTML temporário renderizado pelo Chrome
        "_administrativo.html",
        "_montagem_externa.html",
    }

    removidos = 0
    for arq in PASTA_CARDS.iterdir():
        if not arq.is_file():
            continue
        if arq.name in nomes_fixos:
            continue
        # Remove qualquer outro arquivo (timestampados antigos, etc.)
        try:
            arq.unlink()
            removidos += 1
        except Exception as e:
            print(f"[AVISO] Não consegui remover {arq.name}: {e}")

    if removidos > 0:
        print(f"[OK] Limpeza: {removidos} arquivos antigos removidos da pasta cards/")
    return removidos


def gerar_todos() -> dict:
    """Gera ambos dashboards. Retorna {'montagem': Path, 'admin': Path}."""
    _limpar_arquivos_antigos()         # mantém só os arquivos fixos
    historico = _carregar_historico()
    return {
        "montagem": gerar_montagem_externa(historico),
        "admin":    gerar_administrativo(historico),
    }


# ===== Compat: main.py antigo chamava `capturar_planilha(parcial=...)` =====
def capturar_planilha(parcial=None):
    """Alias de compatibilidade. Gera AMBOS os dashboards e retorna o de montagem."""
    paths = gerar_todos()
    return paths["montagem"]


def gerar_card(*args, **kwargs):
    return capturar_planilha()


# ============================================================
# TESTE
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Gerando dashboards a partir do histórico de hoje...")
    print("=" * 60)
    paths = gerar_todos()
    print()
    print(f"  MONTAGEM_EXTERNA: {paths['montagem']}")
    print(f"  ADMINISTRATIVO  : {paths['admin']}")
    print()
    print("Abra ambos PNGs e compare com seus templates.")
