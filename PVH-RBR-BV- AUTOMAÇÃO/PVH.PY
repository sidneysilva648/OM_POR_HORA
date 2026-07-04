"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ARQUIVO: PVH.py — orquestrador da terceira automação (CENTRO 0016)
AUTOR  : Sidney Albuquerque (BEMOL S/A)

DESCRIÇÃO:
    Versão paralela da automação principal de OM POR HORA,
    mas filtrando pelo CENTRO DE TRABALHO 0016 (PVH — Porto Velho).

    META TOTAL DO DIA: 36 montagens.
    METAS PARCIAIS POR HORA (acumuladas):
       09:30 →  4   |  13:30 → 20
       10:30 →  8   |  14:30 → 24
       11:30 → 16   |  15:30 → 28
       (pula 12:30 — almoço)
                    |  16:30 → 32
                    |  17:50 → 36   ← fechamento do dia

    Fluxo:
      1) Reaproveita 01_abrir_sap.py da pasta pai para abrir SAP.
      2) Executa ZWM117 carregando variante via F17 + matrícula 21039.
      3) ALTERA o centro de trabalho para 0016 antes do F8 final.
      4) Lê os 3 indicadores (Sucesso/Insucesso/Iniciadas) na linha TOTAL.
      5) Grava em parciais_hoje_pvh.json (separado do principal).
      6) Renderiza cards/montagem_pvh.jpg (separado do principal).
      7) Envia no grupo configurado em GRUPO_PVH.

    NÃO conflita com a automação principal nem com a BV porque:
      - Usa a mesma pasta PVH-RBR-BV- AUTOMAÇÃO/ mas com arquivos
        próprios (parciais_hoje_pvh.json, execucoes_pvh.log,
        cards/montagem_pvh.*, templates/montagem_pvh.html)
      - Reaproveita só a SESSÃO Chrome WhatsApp (mesmo perfil)

USO:
    python PVH.py                    → fluxo completo
    python PVH.py --parcial 3        → força parcial 3
    python PVH.py --skip-whatsapp    → só gera o card
    python PVH.py --skip-card        → só grava no JSON
==============================================================
"""

import sys
import json
import time
import base64
import traceback
import importlib.util
from datetime import datetime, time as dtime, date
from pathlib import Path

# ============================================================
# CONFIGURAÇÕES
# ============================================================

HERE = Path(__file__).parent                          # PVH-RBR-BV- AUTOMAÇÃO/
PASTA_PAI = HERE.parent                                # OM POR HORA/
LOG_FILE = HERE / "execucoes_pvh.log"
HISTORICO_JSON = HERE / "parciais_hoje_pvh.json"
PASTA_CARDS = HERE / "cards"
PASTA_CARDS.mkdir(exist_ok=True)
PASTA_TEMPLATES = HERE / "templates"
TEMPLATE_PVH = PASTA_TEMPLATES / "montagem_pvh.html"
LOGO_BEMOL = PASTA_PAI / "bemol.png"

# ----- SAP -----
MATRICULA = "21039"
CENTRO_DE_TRABALHO = "0016"   # ← centro PVH (Porto Velho)
TREE_ID = "wnd[0]/shellcont/shell/shellcont[1]/shell[1]"

# ⚠️ ID do campo "Centro" na tela da ZWM117 (após carregar a variante).
# Não tenho 100% de certeza do ID — coloquei opções comuns no SAP.
# Quando você rodar o gravador de scripts do SAP alterando o centro,
# me manda o trecho — eu ajusto o ID exato.
# Os candidatos mais prováveis (em ordem):
CAMPO_CENTRO_CANDIDATOS = [
    "wnd[0]/usr/ctxtP_WERKS",
    "wnd[0]/usr/ctxtPLANT-LOW",
    "wnd[0]/usr/ctxtS_WERKS-LOW",
    "wnd[0]/usr/ctxtWERKS-LOW",
    "wnd[0]/usr/ctxtCENTRO",
    "wnd[0]/usr/ctxtP_CENTRO",
]

# ----- Parciais (específicas do PVH — centro 0016) -----
# Horários e metas conforme tabela enviada pelo Sidney (2026-06-20):
#   - 12:30 NÃO existe (almoço — pula direto pra 13:30)
#   - 17:50 é o fechamento (diferente do BV que fecha 17:30)
#   - META TOTAL DO DIA = 36 montagens
PARCIAIS_PADRAO = [
    {"n": 1, "hora": "09:35", "meta":  4},
    {"n": 2, "hora": "10:35", "meta":  8},
    {"n": 3, "hora": "11:35", "meta": 16},
    {"n": 4, "hora": "13:35", "meta": 20},
    {"n": 5, "hora": "14:35", "meta": 24},
    {"n": 6, "hora": "15:35", "meta": 28},
    {"n": 7, "hora": "16:35", "meta": 32},
    {"n": 8, "hora": "17:35", "meta": 36},
]

# ----- WhatsApp -----
# Nome EXATO confirmado pelo Sidney em 2026-06-20 (via print do WhatsApp).
GRUPO_PVH = "Montagens_CD PVH"

LEGENDAS_PVH_POR_PARCIAL = {
    1: "09:35 - Primeira parcial do dia !!",
    2: "10:35 - Segunda parcial do dia",
    3: "11:35 - Terceira parcial do dia",
    4: "13:35 - Quarta parcial do dia",
    5: "14:35 - Quinta parcial do dia",
    6: "15:35 - Sexta parcial do dia",
    7: "16:35 - Sétima parcial do dia",
    8: "17:35 - Última parcial do dia !",
}
# Grupo PVH recebe APENAS o cabeçalho da parcial (sem rodapé).
# Se quiser adicionar rodapé um dia, é só preencher esta constante
# e o `_legenda_pvh` junta automaticamente.
RODAPE_PVH = ""


# ============================================================
# UTILITÁRIOS
# ============================================================

def _carregar_da_pasta_pai(nome: str, arquivo: str):
    """Carrega um módulo .py da pasta pai (OM POR HORA/)."""
    spec = importlib.util.spec_from_file_location(nome, PASTA_PAI / arquivo)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _registrar_log(linha: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {linha}\n")


def _formatar_data(d: datetime) -> str:
    dias = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado", "domingo"]
    meses = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    return f"{dias[d.weekday()]}, {d.day} de {meses[d.month]} de {d.year}"


def _logo_base64() -> str:
    if not LOGO_BEMOL.exists():
        return ""
    try:
        b64 = base64.b64encode(LOGO_BEMOL.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return ""


# ============================================================
# HISTÓRICO JSON (próprio, separado do OM POR HORA)
# ============================================================

def _vazio_para_hoje(hoje_iso: str) -> dict:
    parciais = [{**p, "sucesso": None, "insucesso": None, "iniciadas": None}
                for p in PARCIAIS_PADRAO]
    return {
        "data": hoje_iso,
        "atualizado_em": None,
        "meta_total_dia": PARCIAIS_PADRAO[-1]["meta"],
        "centro": CENTRO_DE_TRABALHO,
        "parciais": parciais,
    }


def carregar_historico() -> dict:
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
        json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")


def _parcial_atual_por_horario(agora: datetime = None) -> int:
    """Detecta parcial pelo horário atual com janela ±15min."""
    if agora is None:
        agora = datetime.now()
    JANELA_MIN = 15
    minutos_agora = agora.hour * 60 + agora.minute
    melhor_dist = JANELA_MIN + 1
    melhor_parcial = None
    ultimo_passado = 1
    for p in PARCIAIS_PADRAO:
        h, m = map(int, p["hora"].split(":"))
        minutos_p = h * 60 + m
        dist = abs(minutos_agora - minutos_p)
        if dist <= JANELA_MIN and dist < melhor_dist:
            melhor_dist = dist
            melhor_parcial = p["n"]
        if minutos_agora >= minutos_p:
            ultimo_passado = p["n"]
    return melhor_parcial if melhor_parcial is not None else ultimo_passado


def gravar_historico(indicadores: dict, parcial: int = None) -> tuple:
    dados = carregar_historico()
    if parcial is None:
        parcial = _parcial_atual_por_horario()
    if not 1 <= parcial <= 8:
        raise ValueError(f"Parcial inválida: {parcial} (1..8)")
    for p in dados["parciais"]:
        if p["n"] == parcial:
            p["sucesso"]   = int(indicadores.get("sucesso", 0))
            p["insucesso"] = int(indicadores.get("insucesso", 0))
            p["iniciadas"] = int(indicadores.get("iniciadas", 0))
            break
    dados["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    salvar_historico(dados)
    print(f"[OK] Parcial {parcial} (PVH) → Sucesso={indicadores.get('sucesso')} "
          f"Insucesso={indicadores.get('insucesso')} Iniciadas={indicadores.get('iniciadas')}")
    return parcial, dados


# ============================================================
# SAP: ZWM117 com centro 0077
# ============================================================

def _alterar_centro_de_trabalho(session, centro: str) -> bool:
    """
    Tenta alterar o campo 'Centro de Trabalho' na tela atual do SAP.

    Estratégia em 2 etapas:
      1) Tenta os IDs candidatos conhecidos (CAMPO_CENTRO_CANDIDATOS).
      2) Se nenhum funcionar, faz VARREDURA na árvore de UI atual:
         lista todos os elementos editáveis (tipo GuiCTextField/GuiTextField)
         e tenta os que têm WERKS / PLANT / CENTRO / TRABALHO no nome.

    Retorna True se conseguiu setar, False se nem a varredura achou.
    Imprime tudo no terminal para diagnóstico.
    """
    # ----- 1) Tenta IDs candidatos -----
    for campo_id in CAMPO_CENTRO_CANDIDATOS:
        try:
            campo = session.findById(campo_id)
            campo.text = centro
            print(f"[OK] Centro setado em '{campo_id}' = {centro}")
            return True
        except Exception:
            continue

    print("[INFO] Nenhum candidato pré-cadastrado funcionou.")
    print("[INFO] Varrendo todos os campos da tela...")

    # ----- 2) Varredura: lista TODOS os campos da tela atual -----
    encontrados = []
    def _varrer(elemento, caminho=""):
        """Recursão pra listar a árvore de UI."""
        try:
            nome = elemento.Name
            tipo = elemento.Type           # ex.: GuiCTextField, GuiTextField
            id_ = elemento.Id
            txt = ""
            try:
                txt = elemento.Text or ""
            except Exception:
                pass
            # Só interessa campos editáveis
            if tipo in ("GuiCTextField", "GuiTextField"):
                encontrados.append({"id": id_, "name": nome, "type": tipo, "text": txt})
        except Exception:
            return
        # Recurso filhos
        try:
            count = elemento.Children.Count
            for i in range(count):
                _varrer(elemento.Children.ElementAt(i), caminho)
        except Exception:
            return

    try:
        _varrer(session.findById("wnd[0]/usr"))
    except Exception as e:
        print(f"[AVISO] Falha na varredura: {e}")
        return False

    print(f"[DIAG] Campos editáveis encontrados: {len(encontrados)}")
    for c in encontrados:
        print(f"   - id='{c['id']}'  name='{c['name']}'  type='{c['type']}'  text='{c['text']}'")

    # Procura nomes que parecem ser "Centro" / "WERKS" / "PLANT"
    palavras_chave = ["WERKS", "PLANT", "CENTRO", "TRABALHO", "CTRTRAB"]
    for c in encontrados:
        nome_up = (c["name"] or "").upper()
        if any(p in nome_up for p in palavras_chave):
            try:
                campo = session.findById(c["id"])
                campo.text = centro
                print(f"[OK] Centro setado via varredura em '{c['id']}' (name='{c['name']}') = {centro}")
                return True
            except Exception as e:
                print(f"[AVISO] Falhou setar '{c['id']}': {e}")
                continue

    # Última tentativa: campo cujo TEXTO ATUAL é "0005" (centro antigo)
    for c in encontrados:
        if (c["text"] or "").strip() == "0005":
            try:
                campo = session.findById(c["id"])
                campo.text = centro
                print(f"[OK] Centro setado por valor atual '0005' em '{c['id']}' = {centro}")
                return True
            except Exception:
                continue

    return False


def executar_zwm117_pvh(diagnostico: bool = False) -> dict:
    """Abre SAP, executa ZWM117 com centro 0077, retorna os indicadores."""
    abrir_sap = _carregar_da_pasta_pai("abrir_sap", "01_abrir_sap.py")
    zwm117 = _carregar_da_pasta_pai("zwm117", "02_executar_zwm117.py")

    # obter_sessao_segura cobre 3 casos numa chamada so:
    #  1) SAP fechado          → abre SAP Logon automaticamente
    #  2) Sessao em timeout    → relogga via SSO (sessao morre apos 30-60min)
    #  3) Usuario usando SAP   → cria sessao paralela (nao interrompe usuario)
    session = abrir_sap.obter_sessao_segura()

    # ----- ETAPA 1: ir até ZWM117 e carregar variante (igual à automação principal) -----
    print("[INFO] Maximizando janela principal...")
    session.findById("wnd[0]").maximize()
    print("[INFO] Indo para a transação ZWM117...")
    session.findById("wnd[0]/tbar[0]/okcd").text = "/nzwm117"
    session.findById("wnd[0]").sendVKey(0)
    time.sleep(1.0)

    print(f"[INFO] Abrindo seletor de variante (F17)...")
    session.findById("wnd[0]/tbar[1]/btn[17]").press()
    time.sleep(0.5)
    print(f"[INFO] Preenchendo matrícula {MATRICULA} em ENAME-LOW...")
    session.findById("wnd[1]/usr/txtENAME-LOW").text = MATRICULA
    session.findById("wnd[1]/tbar[0]/btn[8]").press()
    time.sleep(1.0)
    try:
        if session.ActiveWindow.Name == "wnd[1]":
            session.findById("wnd[1]").sendVKey(0)
            time.sleep(0.5)
    except Exception:
        pass

    # ----- ETAPA 2: definir período (hoje) -----
    hoje = datetime.now().strftime("%d.%m.%Y")
    print(f"[INFO] Definindo período: {hoje} a {hoje}")
    session.findById("wnd[0]/usr/ctxtSO_DATA-LOW").text = hoje
    session.findById("wnd[0]/usr/ctxtSO_DATA-HIGH").text = hoje

    # ----- ETAPA 3: ALTERAR O CENTRO DE TRABALHO PARA 0077 -----
    print(f"[INFO] Alterando centro de trabalho para {CENTRO_DE_TRABALHO}...")
    centro_setado = _alterar_centro_de_trabalho(session, CENTRO_DE_TRABALHO)
    if not centro_setado:
        print(f"[AVISO] Não consegui setar o centro automaticamente.")
        print(f"        Continuando com o centro padrão da variante...")

    # ----- ETAPA 4: executar (F8) -----
    print("[INFO] Executando relatório (F8)...")
    session.findById("wnd[0]/tbar[1]/btn[8]").press()

    # ----- ETAPA 5: aguarda o tree de resultado -----
    inicio = time.time()
    carregou = False
    while time.time() - inicio < 60:
        try:
            session.findById(TREE_ID)
            time.sleep(2)
            carregou = True
            break
        except Exception:
            time.sleep(1)
    if not carregou:
        raise TimeoutError("Tela de resultado não apareceu.")

    print("[OK] Resultado carregado. Lendo indicadores...")

    # ----- ETAPA 6: lê indicadores reusando lógica do zwm117 do pai -----
    indicadores = zwm117.ler_indicadores(session)
    print(f"\n[OK] PVH (centro {CENTRO_DE_TRABALHO}) — "
          f"Sucesso={indicadores['sucesso']} "
          f"Insucesso={indicadores['insucesso']} "
          f"Iniciadas={indicadores['iniciadas']}")
    return indicadores


# ============================================================
# GERAÇÃO DO CARD (próprio, não conflita)
# ============================================================

def gerar_card_pvh(historico: dict = None) -> Path:
    """Renderiza o template HTML do PVH em JPG."""
    if historico is None:
        historico = carregar_historico()

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service

    # Substitui placeholders no template
    html = TEMPLATE_PVH.read_text(encoding="utf-8")
    html = html.replace("{{LOGO_BASE64}}", _logo_base64())
    html = html.replace("{{DATA}}", _formatar_data(datetime.now()))
    html = html.replace("{{DADOS_JSON}}",
                        json.dumps({"parciais": historico["parciais"]}, ensure_ascii=False))

    # Limpa arquivos antigos (preserva os 3 finais do PVH + os do BV)
    NOMES_FIXOS = {
        "montagem_pvh.jpg", "montagem_pvh.png", "_montagem_pvh.html",
        "montagem_bv.jpg",  "montagem_bv.png",  "_montagem_bv.html",
    }
    for arq in PASTA_CARDS.iterdir():
        if arq.is_file() and arq.name not in NOMES_FIXOS:
            try: arq.unlink()
            except Exception: pass

    # Salva HTML temporário
    html_path = PASTA_CARDS / "_montagem_pvh.html"
    html_path.write_text(html, encoding="utf-8")

    # Renderiza no Chrome headless
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--window-size=1180,840")
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
        driver.get(html_path.as_uri())
        # Espera JS terminar
        inicio = time.time()
        while time.time() - inicio < 10:
            try:
                pronto = driver.execute_script(
                    "return document.readyState === 'complete' && (window.__dashReady === undefined || window.__dashReady === true);")
                if pronto: break
            except Exception: pass
            time.sleep(0.2)
        time.sleep(1.0)

        try:
            elemento = driver.find_element(By.ID, "dash-root")
        except Exception:
            elemento = driver.find_element(By.TAG_NAME, "body")

        png_path = PASTA_CARDS / "montagem_pvh.png"
        elemento.screenshot(str(png_path))

        # Converte para JPG (não vira sticker no WhatsApp)
        from PIL import Image
        jpg_path = PASTA_CARDS / "montagem_pvh.jpg"
        img = Image.open(png_path)
        if img.mode in ("RGBA", "LA"):
            fundo = Image.new("RGB", img.size, (255, 255, 255))
            fundo.paste(img, mask=img.split()[-1])
            img = fundo
        else:
            img = img.convert("RGB")
        img.save(jpg_path, "JPEG", quality=92, optimize=True, progressive=True)
        print(f"[OK] Card PVH gerado: {jpg_path.name} ({img.size[0]}x{img.size[1]})")
        return jpg_path
    finally:
        try: driver.quit()
        except Exception: pass


# ============================================================
# ENVIO WHATSAPP (reusa o módulo do pai)
# ============================================================

def _legenda_pvh(parcial: int) -> str:
    """Monta a legenda do PVH: cabeçalho da parcial + rodapé (se houver)."""
    cab = LEGENDAS_PVH_POR_PARCIAL.get(parcial, f"Parcial {parcial}")
    if RODAPE_PVH:
        return f"{cab}\n\n{RODAPE_PVH}"
    return cab


def enviar_no_grupo(caminho_jpg: Path, parcial: int) -> bool:
    """Envia o card PVH pelo grupo configurado, reusando o módulo de WhatsApp do pai."""
    wpp = _carregar_da_pasta_pai("wpp", "05_enviar_whatsapp.py")
    legenda = _legenda_pvh(parcial)
    envios = {GRUPO_PVH: (caminho_jpg, legenda)}
    resultados = wpp.enviar_dashboards(envios)
    return all(v is True for v in resultados.values())


# ============================================================
# MAIN
# ============================================================

def main() -> int:
    diagnostico   = "--diagnostico" in sys.argv or "-d" in sys.argv
    skip_whatsapp = "--skip-whatsapp" in sys.argv
    skip_card     = "--skip-card" in sys.argv
    parcial_forc  = None
    if "--parcial" in sys.argv:
        try:
            parcial_forc = int(sys.argv[sys.argv.index("--parcial") + 1])
        except (IndexError, ValueError):
            print("[ERRO] --parcial precisa de número 1-8.")
            return 2

    print("=" * 60)
    print(f"PVH (Centro {CENTRO_DE_TRABALHO}) — execução em "
          f"{datetime.now():%d/%m/%Y %H:%M:%S}")
    print("=" * 60)

    try:
        # 1+2) SAP + ZWM117 com centro 0077 — com retry para sessao expirada/zumbi
        MAX_TENTATIVAS = 2
        indicadores = None
        ultimo_erro = None
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                indicadores = executar_zwm117_pvh(diagnostico=diagnostico)
                break
            except Exception as e:
                ultimo_erro = e
                msg = str(e).lower()
                sinais_de_falha_sap = [
                    "control could not be found", "object", "session",
                    "rpc", "connection", "the rpc server",
                    "unspecified error", "exceção", "exception",
                    "<unknown>", "parent", "disconectado", "disconnected"
                ]
                parece_sessao_morta = any(s in msg for s in sinais_de_falha_sap)

                if tentativa < MAX_TENTATIVAS and parece_sessao_morta:
                    print(f"\n[AVISO] Tentativa {tentativa} falhou: {e}")
                    print("        Fechando conexoes SAP zumbis e tentando novamente...\n")
                    # Forca fechar TODAS as conexoes SAP pra comecar do zero
                    try:
                        import win32com.client as _w32
                        sap_gui = _w32.GetObject("SAPGUI")
                        app = sap_gui.GetScriptingEngine
                        for i in range(app.Connections.Count - 1, -1, -1):
                            try:
                                app.Children(i).CloseConnection()
                            except Exception:
                                pass
                    except Exception:
                        pass
                    time.sleep(3.0)  # da tempo do SAP processar o fechamento
                    continue
                else:
                    # Esgotou tentativas OU erro nao parece ser de sessao
                    raise

        if indicadores is None:
            raise RuntimeError(f"executar_zwm117_pvh falhou apos {MAX_TENTATIVAS} tentativas. Ultimo erro: {ultimo_erro}")

        # 3) Grava no histórico próprio
        parcial, historico = gravar_historico(indicadores, parcial=parcial_forc)
        _registrar_log(
            f"OK   | PARCIAL {parcial} (PVH) | "
            f"Sucesso={indicadores['sucesso']} "
            f"Insucesso={indicadores['insucesso']} "
            f"Iniciadas={indicadores['iniciadas']}"
        )

        # 4) Gera card próprio
        if skip_card:
            print("[INFO] --skip-card → não gerando card.")
            return 0
        time.sleep(1.2)
        caminho = gerar_card_pvh(historico)
        _registrar_log(f"CARD | {caminho.name}")

        # 5) Envia no WhatsApp
        if skip_whatsapp:
            print("[INFO] --skip-whatsapp → card gerado, sem envio.")
            return 0

        ok = enviar_no_grupo(caminho, parcial)
        _registrar_log(f"WPP  | {'OK ' if ok else 'ERR'} {GRUPO_PVH}")
        return 0

    except Exception as e:
        erro = f"FALHA: {type(e).__name__}: {e}"
        print("\n[ERRO]", erro)
        traceback.print_exc()
        _registrar_log("ERR  | " + erro)
        return 1


if __name__ == "__main__":
    sys.exit(main())


