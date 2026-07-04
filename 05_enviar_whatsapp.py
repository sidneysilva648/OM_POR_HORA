"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ETAPA  : 05 — Enviar card no WhatsApp Web
AUTOR  : Sidney Albuquerque (BEMOL S/A)
DESCRIÇÃO:
    Envia uma imagem (gerada na etapa 04) para um grupo do
    WhatsApp via web.whatsapp.com automatizado com Selenium.

    Usa um PERFIL PERSISTENTE do Chrome (user-data-dir), o que
    significa que VOCÊ ESCANEIA O QR CODE UMA ÚNICA VEZ — nas
    execuções seguintes a sessão já estará logada.

PRIMEIRA EXECUÇÃO (manual, fora do agendador):
    1) python 05_enviar_whatsapp.py --primeiro-uso
       → abre o Chrome, escaneia o QR code, fecha o navegador.
    2) Edite a variável GRUPO_DESTINO abaixo com o nome EXATO
       do grupo (exatamente como aparece no WhatsApp Web).

DEPENDÊNCIAS:
    pip install selenium webdriver-manager
==============================================================
"""

import sys
import time
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime


def _wpp_debug(msg: str) -> None:
    """
    Grava uma linha de DEBUG em execucoes.log. Usado pra rastrear se o envio
    foi por CLIPBOARD (foto) ou FILE INPUT (pode virar sticker). Como o script
    roda via Task Scheduler, prints comuns somem — por isso gravamos em arquivo.
    """
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_path = Path(__file__).parent / "execucoes.log"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] WPP-DBG  | {msg}\n")
    except Exception:
        pass

# ============================================================
# CONFIGURAÇÕES — AJUSTE AQUI
# ============================================================

# Nome EXATO dos grupos no WhatsApp (case-sensitive, com espaços
# e acentos idênticos ao que aparece na barra lateral).
# Ambos dentro da comunidade "Comunidade Bemol 2 - Notícias".
#   - PNG.MONTAGEM_EXTERNA   → grupo dos montadores (visualização simples)
#   - PNG.ADMINISTRATIVO     → grupo gerencial (KPIs + gráfico + semáforos)
GRUPO_MONTAGEM_EXTERNA = "Montagem Externa Bemol"
GRUPO_ADMINISTRATIVO   = "LogRev - Montagem - Adms"

# Compatibilidade com código antigo
GRUPO_DESTINO = GRUPO_MONTAGEM_EXTERNA

# Pasta onde a sessão do WhatsApp Web fica salva (login persistente).
# IMPORTANTE: o Chrome NÃO lida bem com user-data-dir contendo espaços
# ou caracteres especiais (e a pasta do projeto está no OneDrive "BEMOL S A"
# com vários espaços). Por isso o perfil mora em:
#   C:\Users\<user>\.whatsapp_om_profile
# Caminho sem espaços, fora do OneDrive (também evita sync conflitos).
HERE = Path(__file__).parent
PERFIL_CHROME = Path.home() / ".whatsapp_om_profile"
PERFIL_CHROME.mkdir(exist_ok=True)

# Timeouts (segundos)
TIMEOUT_LOGIN     = 120    # tempo para escanear QR code
TIMEOUT_ELEMENTO  = 30
TIMEOUT_ENVIO     = 60

# ============================================================
# FUNÇÕES
# ============================================================

def _verificar_chrome_aberto():
    """Avisa se o Chrome normal está rodando — pode conflitar com o perfil."""
    try:
        import psutil
        for proc in psutil.process_iter(["name"]):
            nome = (proc.info.get("name") or "").lower()
            if nome == "chrome.exe":
                print("[AVISO] O Chrome normal está aberto. Se der erro de "
                      "perfil em uso, feche-o e tente novamente.")
                return
    except Exception:
        pass


def _criar_driver(visivel: bool = False):
    """
    Cria o webdriver do Chrome usando o perfil persistente.

    Args:
        visivel: Se True, a janela do Chrome aparece normalmente.
                 Se False (default), a janela fica posicionada FORA
                 da tela (Top/Left = -32000) — Selenium e WhatsApp
                 funcionam, mas o usuário nem vê a janela.
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    _verificar_chrome_aberto()

    options = Options()

    # ----- Perfil persistente (sem espaços no caminho) -----
    options.add_argument(f"--user-data-dir={PERFIL_CHROME}")

    # ----- Flags de estabilidade no Windows -----
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--window-size=1280,900")

    # IMPORTANTE: impede o Chrome de "dormir" quando a janela está
    # minimizada / fora da tela / oculta. Sem essas flags o WhatsApp
    # Web entra em modo background throttling e elementos não renderizam.
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-features=CalculateNativeWinOcclusion")

    # Reduz o ruído de logs do ChromeDriver no terminal
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)

    # webdriver-manager baixa o ChromeDriver compatível com o Chrome instalado
    try:
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        servico = Service(
            ChromeDriverManager().install(),
            log_output=None,
        )
        driver = webdriver.Chrome(service=servico, options=options)
    except ImportError:
        # Fallback: assume que chromedriver está no PATH
        driver = webdriver.Chrome(options=options)

    # ----- Modo "discreto": posicionar a janela FORA da tela -----
    # Histórico:
    #   - minimize_window() = Chrome throttle, search box não renderiza
    #   - position(-32000,-32000) = WhatsApp Web não renderiza canvas
    #   - position(5000, 5000)   = funciona; fora da tela em monitores
    #                                  comuns (até 4K = 3840), Chrome
    #                                  considera a janela "ativa".
    # Combinado com as flags --disable-renderer-backgrounding, o
    # WhatsApp Web renderiza tudo normalmente.
    if not visivel:
        try:
            driver.set_window_size(1280, 900)
            driver.set_window_position(5000, 5000)
        except Exception as e:
            print(f"[AVISO] Não consegui posicionar a janela: {e}")
    else:
        # Modo VISIVEL: força a janela a aparecer maximizada e na frente
        # (caso contrario o Chrome pode abrir em segundo plano)
        try:
            driver.set_window_position(0, 0)
            driver.set_window_size(1280, 900)
            driver.maximize_window()
            # Traz a janela do Chrome pra frente usando win32 (Windows)
            try:
                import win32gui
                import win32con
                # Pega o handle da janela do Chrome pelo titulo
                def _trazer_pra_frente(hwnd, _):
                    titulo = win32gui.GetWindowText(hwnd)
                    if "WhatsApp" in titulo or "Chrome" in titulo:
                        try:
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                        except Exception:
                            pass
                win32gui.EnumWindows(_trazer_pra_frente, None)
            except Exception:
                pass
        except Exception as e:
            print(f"[AVISO] Não consegui maximizar a janela: {e}")

    driver.set_page_load_timeout(60)
    return driver


def _detectar_qr_code(driver) -> bool:
    """Detecta se a tela está mostrando o QR code (sessão expirou).

    Seletores deliberadamente PRECISOS — só elementos exclusivos da
    tela de QR. Evita falsos positivos com elementos `data-ref` que
    aparecem em outras telas do WhatsApp Web.
    """
    from selenium.webdriver.common.by import By
    seletores_qr = [
        # O canvas com o QR tem aria-label específico
        "//canvas[contains(@aria-label,'Scan me')]",
        "//canvas[contains(@aria-label,'Escan')]",
        # Texto característico da tela de login (PT e EN)
        "//*[contains(text(),'Conectar um aparelho')]",
        "//*[contains(text(),'Connect a device')]",
        "//*[contains(text(),'Use o WhatsApp no seu computador')]",
        "//*[contains(text(),'Steps to log in')]",
    ]
    for sel in seletores_qr:
        try:
            elementos = driver.find_elements(By.XPATH, sel)
            for el in elementos:
                if el.is_displayed():
                    return True
        except Exception:
            continue
    return False


def _esta_logado(driver) -> bool:
    """
    Detecta se o WhatsApp Web está autenticado (chat list visível).

    Estratégia: procura QUALQUER um de vários elementos que existem
    quando o usuário está logado — assim sobrevive a mudanças de
    versão do WhatsApp Web.
    """
    from selenium.webdriver.common.by import By

    # Se há QR visível, definitivamente NÃO está logado
    if _detectar_qr_code(driver):
        return False

    # Indicadores de "logado" (qualquer um basta)
    indicadores = [
        # Painéis laterais (id estável há anos)
        "//*[@id='side']",
        "//*[@id='pane-side']",
        # Header da lista de conversas
        "//header",
        # Aria labels em PT/EN
        "//*[@aria-label='Lista de conversas']",
        "//*[@aria-label='Chat list']",
        "//*[@aria-label='Conversas']",
        "//*[@aria-label='Chats']",
        # Botão Nova conversa / Status / Comunidades (sempre presentes)
        "//*[@data-icon='chats']",
        "//*[@data-icon='chat']",
        "//*[@data-icon='community']",
        "//*[@data-icon='comunidades']",
        "//*[@data-icon='status']",
        "//*[@data-icon='new-chat-outline']",
        "//*[@data-testid='chat-list']",
        # Caixa de pesquisa
        "//div[@contenteditable='true'][@data-tab='3']",
        "//div[@contenteditable='true' and @role='textbox']",
        "//div[@contenteditable='true']",
    ]
    for sel in indicadores:
        try:
            elementos = driver.find_elements(By.XPATH, sel)
            for el in elementos:
                if el.is_displayed():
                    return True
        except Exception:
            continue
    return False


def _aguardar_login(driver, timeout: int) -> None:
    """
    Espera o WhatsApp Web ficar autenticado.
    NÃO aborta se QR estiver presente — esperar o usuário escanear.
    """
    inicio = time.time()
    while time.time() - inicio < timeout:
        if _esta_logado(driver):
            return
        time.sleep(1)
    raise TimeoutError("Login não confirmado dentro do timeout.")


def _achar_caixa_busca(driver):
    """
    Encontra a caixa de pesquisa lateral do WhatsApp Web / Business.

    Importante: a versão atual do WhatsApp Business usa um <input> com
    role="textbox" (NÃO mais <div contenteditable> como nas versões antigas).

    Estratégia em cascata: XPath → JavaScript.
    """
    from selenium.webdriver.common.by import By

    # ------- 1) XPaths em cascata (do mais específico ao mais genérico) -------
    seletores = [
        # ===== WhatsApp Business (versão atual, confirmado 2026-05-13) =====
        "//input[@aria-label='Pesquisar ou começar uma nova conversa']",
        "//input[contains(@aria-label,'Pesquisar')]",
        "//input[contains(@placeholder,'Pesquisar')]",
        "//input[contains(@aria-label,'Search')]",
        "//input[contains(@placeholder,'Search')]",
        "//*[@data-testid='chat-list-search-container']//input",
        "//*[@data-testid='chat-list-search-container']//*[@role='textbox']",
        "//input[@role='textbox' and @data-tab='3']",
        "//input[@role='textbox']",
        "//input[@data-tab='3']",

        # ===== WhatsApp Web normal (versões anteriores) =====
        "//div[@contenteditable='true'][@data-tab='3']",
        "//div[@role='textbox'][@title='Caixa de texto de pesquisa']",
        "//div[@contenteditable='true' and @data-tab]",
        "//div[@contenteditable='true'][contains(@aria-label,'esquisar')]",
        "//div[@contenteditable='true'][contains(@aria-label,'earch')]",

        # ===== Fallback genérico no painel lateral =====
        "//*[@id='side']//input",
        "//*[@id='side']//div[@contenteditable='true']",
        "//*[@id='pane-side']//input",
        "//*[@id='pane-side']//div[@contenteditable='true']",
        "//input",
        "//div[@contenteditable='true']",
    ]
    for sel in seletores:
        try:
            elementos = driver.find_elements(By.XPATH, sel)
            for el in elementos:
                try:
                    if el.is_displayed():
                        return el
                except Exception:
                    continue
        except Exception:
            continue

    # ------- 2) Fallback JavaScript: input OU contenteditable visível,
    #            posicionado no canto superior esquerdo (= caixa lateral) -------
    try:
        elemento = driver.execute_script("""
            const candidatos = document.querySelectorAll(
                'input, div[contenteditable="true"], [role="textbox"], [role="searchbox"]'
            );
            const visiveis = [];
            for (const el of candidatos) {
                if (el.offsetParent === null) continue;
                const r = el.getBoundingClientRect();
                if (r.width < 50 || r.height < 10) continue;
                visiveis.push({el: el, left: r.left, top: r.top});
            }
            visiveis.sort((a, b) => (a.top - b.top) || (a.left - b.left));
            return visiveis.length > 0 ? visiveis[0].el : null;
        """)
        if elemento is not None:
            return elemento
    except Exception:
        pass

    raise RuntimeError(
        "Caixa de pesquisa do WhatsApp Web não localizada por nenhuma estratégia. "
        "Verifique o screenshot 'erro_whatsapp_*.png' salvo na pasta."
    )


# Alias de compatibilidade com chamadas antigas
def _aguardar_chat_list(driver, timeout: int):
    _aguardar_login(driver, timeout)
    return _achar_caixa_busca(driver)


def _aguardar_whatsapp_carregar(driver, timeout=TIMEOUT_LOGIN):
    """Espera o WhatsApp Web carregar (barra de pesquisa visível)."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    # Em modo "enviar normal", se aparecer QR é porque a sessão expirou
    # e queremos abortar cedo com mensagem clara.
    inicio = time.time()
    while time.time() - inicio < timeout:
        if _detectar_qr_code(driver):
            raise TimeoutError(
                "A sessão do WhatsApp Web EXPIROU — apareceu QR code.\n"
                "Rode novamente:  python 05_enviar_whatsapp.py --primeiro-uso\n"
                "e escaneie o QR para renovar a sessão."
            )
        if _esta_logado(driver):
            return  # logado, segue o fluxo
        time.sleep(1)

    raise TimeoutError(
        "WhatsApp Web não carregou. Possíveis causas:\n"
        "  1) Sessão expirou — rode com --primeiro-uso para renovar.\n"
        "  2) Sem internet / WhatsApp Web fora do ar.\n"
        "  3) Celular desconectado da internet.\n"
        "Confira o screenshot 'erro_whatsapp_*.png' salvo na pasta."
    )


def _abrir_conversa(driver, nome_chat: str):
    """Procura o chat/grupo na lateral e clica para abrir."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    _aguardar_login(driver, timeout=TIMEOUT_ELEMENTO)
    busca = _achar_caixa_busca(driver)

    busca.click()
    time.sleep(0.5)
    busca.send_keys(Keys.CONTROL, "a")
    busca.send_keys(Keys.DELETE)
    time.sleep(0.3)
    busca.send_keys(nome_chat)
    time.sleep(2.0)  # tempo para a busca filtrar

    # Tenta clicar pelo title que contém o nome do chat
    seletores_resultado = [
        f"//span[@title='{nome_chat}']",
        f"//span[contains(@title, '{nome_chat}')]",
        f"//div[@role='listitem']//span[@title='{nome_chat}']",
    ]
    for sel in seletores_resultado:
        try:
            elemento = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, sel))
            )
            elemento.click()
            print(f"[OK] Chat '{nome_chat}' aberto.")
            time.sleep(1)
            return
        except Exception:
            continue

    # Última tentativa: pressiona Enter (vai pro primeiro resultado)
    busca.send_keys(Keys.ENTER)
    time.sleep(1.5)


def _achar_input_de_foto(driver):
    """
    Localiza o input file específico de 'Fotos e Vídeos' (não Sticker).

    Truque chave: o input de FOTO sempre inclui formatos de VÍDEO no
    accept (ex.: 'video/mp4'), enquanto o input de STICKER aceita
    apenas imagens. Filtrando por video/* garantimos o input certo.
    """
    from selenium.webdriver.common.by import By

    # Coleta TODOS os file inputs e mostra os accepts pra diagnóstico
    todos = driver.find_elements(By.XPATH, "//input[@type='file']")
    inputs_info = []
    for el in todos:
        try:
            acc = el.get_attribute("accept") or ""
            inputs_info.append((el, acc))
        except Exception:
            continue

    print(f"[DIAG] Inputs file no DOM: {len(inputs_info)}")
    for i, (_, acc) in enumerate(inputs_info):
        print(f"       [{i}] accept='{acc}'")

    # 1) Prioridade MÁXIMA: input que aceita video/* (definitivamente é Foto)
    for el, acc in inputs_info:
        if "video/" in acc and "image/" in acc:
            print(f"[OK] Input de FOTO localizado (com video no accept): '{acc}'")
            return el

    # 2) Aceita image/* mas NÃO é exclusivamente webp/png (sticker é específico)
    for el, acc in inputs_info:
        if "image/" in acc and "webp" not in acc:
            print(f"[OK] Input de imagem localizado (sem webp = não-sticker): '{acc}'")
            return el

    # 3) Último recurso: o primeiro input com image/ no accept
    for el, acc in inputs_info:
        if "image/" in acc:
            print(f"[AVISO] Usando input genérico (pode ser sticker): '{acc}'")
            return el

    return None


def _abrir_menu_anexar(driver):
    """Clica no ícone de clipe/anexar e espera o menu aparecer."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    botoes_anexar = [
        "//div[@title='Anexar']",
        "//button[@title='Anexar']",
        "//span[@data-icon='clip']",
        "//span[@data-icon='plus']",
        "//span[@data-icon='attach-menu-plus']",
        "//div[@role='button'][@title='Anexar']",
    ]
    for sel in botoes_anexar:
        try:
            el = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, sel))
            )
            el.click()
            time.sleep(0.8)
            return True
        except Exception:
            continue
    return False


def _copiar_imagem_para_clipboard(caminho_imagem: Path, max_tentativas: int = 3) -> bool:
    """
    Copia uma imagem para o clipboard do Windows no formato DIB.
    O WhatsApp Web, quando recebe Ctrl+V de imagem, SEMPRE trata como FOTO,
    nunca como sticker — por isso usamos esse método em vez de upload.

    Faz até `max_tentativas` tentativas porque OpenClipboard pode falhar se
    outro processo estiver mexendo no clipboard naquele momento.
    """
    # Importa dependencias antes do loop — falha aqui = problema de instalacao
    try:
        import io
        import win32clipboard
        from PIL import Image
    except ImportError as e:
        _wpp_debug(f"CLIPBOARD-FAIL | ImportError: {e} | pywin32 ou Pillow nao instalados")
        print(f"[ERRO] pywin32/Pillow nao instalados: {e}")
        print(f"[ERRO] Rode: pip install pywin32 Pillow")
        return False

    # Prepara o DIB uma vez so
    try:
        img = Image.open(caminho_imagem)
        if img.mode != "RGB":
            img = img.convert("RGB")
        output = io.BytesIO()
        img.save(output, format="BMP")
        dib = output.getvalue()[14:]
        output.close()
    except Exception as e:
        _wpp_debug(f"CLIPBOARD-FAIL | PIL conversao falhou: {e}")
        print(f"[AVISO] Falha ao converter imagem pra DIB: {e}")
        return False

    # Tenta abrir o clipboard ate max_tentativas vezes
    ultimo_erro = None
    for tentativa in range(1, max_tentativas + 1):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, dib)
            finally:
                win32clipboard.CloseClipboard()
            _wpp_debug(f"CLIPBOARD-OK | tentativa {tentativa}/{max_tentativas} | "
                       f"{caminho_imagem.name} ({len(dib)} bytes)")
            return True
        except Exception as e:
            ultimo_erro = e
            print(f"[AVISO] Tentativa {tentativa}/{max_tentativas} falhou: {e}")
            time.sleep(0.5)  # espera meio segundo antes de tentar de novo

    _wpp_debug(f"CLIPBOARD-FAIL | {max_tentativas} tentativas falharam | ultimo erro: {ultimo_erro}")
    print(f"[AVISO] Falha ao copiar imagem pro clipboard apos {max_tentativas} tentativas: {ultimo_erro}")
    return False


def _achar_caixa_mensagem(driver):
    """Encontra a caixa de texto onde a gente digita mensagem na conversa aberta."""
    from selenium.webdriver.common.by import By
    seletores = [
        # WhatsApp Business (atual)
        "//div[@contenteditable='true'][@aria-label='Digite uma mensagem']",
        "//div[@contenteditable='true'][@data-tab='10']",
        "//footer//div[@contenteditable='true']",
        "//*[@data-testid='conversation-compose-box-input']",
        "//*[@id='main']//div[@contenteditable='true']",
        # Genérico (último recurso)
        "//div[@contenteditable='true' and @role='textbox']",
    ]
    for sel in seletores:
        try:
            elementos = driver.find_elements(By.XPATH, sel)
            for el in elementos:
                if el.is_displayed():
                    return el
        except Exception:
            continue
    return None


def _achar_caixa_legenda_modal(driver):
    """Acha a caixa de texto que serve de legenda DEPOIS de colar a imagem.

    Fix 2026-06-20 v3 (UI nova do WhatsApp Web — sem modal separado):
    Descobrimos via screenshot que o WhatsApp Web NAO usa mais um modal
    separado pra preview de imagem. A imagem aparece no proprio chat como
    anexo pendente, e a propria "caixa de mensagem" (data-testid =
    conversation-compose-box-input) serve de legenda.

    Esta funcao agora simplesmente retorna a caixa de mensagem do chat,
    reusando _achar_caixa_mensagem.

    Retorna o WebElement da caixa ou None.
    """
    return _achar_caixa_mensagem(driver)


def _anexar_e_enviar_imagem(driver, caminho_imagem: Path, legenda: str = ""):
    """
    Envia uma imagem pra conversa aberta (com legenda opcional).

    Fluxo robusto reescrito em 2026-06-20 v3 (UI nova do WhatsApp Web):
    Descoberta via screenshot: o WhatsApp Web NAO usa mais modal separado.
    Apos Ctrl+V, a imagem aparece embutida no chat com um botao verde
    grande de Enviar e a CAIXA DE MENSAGEM DO CHAT vira a legenda.

    Sequencia:
      1) Copia imagem pro clipboard.
      2) Foca a caixa de mensagem do chat.
      3) Ctrl+V → imagem aparece como anexo pendente.
      4) Aguarda o botao "Enviar" (data-icon='send' visivel) aparecer.
      5) Re-foca a caixa (que agora e a caption) e digita a legenda
         via clipboard paste (resolve emojis).
      6) Clica no botao Enviar (verde grande, [data-icon='send']) OU
         pressiona Enter como fallback.
      7) CONFIRMA envio aguardando o botao Enviar SUMIR (volta a ser
         microfone/send_normal). Se nao sumir em 30s, levanta erro.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    print(f"[INFO] Anexando imagem (via clipboard): {caminho_imagem.name}")
    _wpp_debug(f"ANEXAR-INICIO | metodo=clipboard | arquivo={caminho_imagem.name}")

    # 1) Copia imagem pra clipboard
    if not _copiar_imagem_para_clipboard(caminho_imagem):
        _wpp_debug("ANEXAR-FALLBACK | usando file_input - PODE VIRAR STICKER!")
        print("[AVISO] Tentando upload via file input como fallback (PODE VIRAR STICKER)...")
        return _anexar_via_file_input(driver, caminho_imagem, legenda)
    _wpp_debug("ANEXAR-CLIPBOARD-OK | seguindo com Ctrl+V")

    # 2) Foca a caixa de mensagem do chat
    caixa = _achar_caixa_mensagem(driver)
    if caixa is None:
        raise RuntimeError("Nao localizei a caixa de mensagem da conversa.")
    caixa.click()
    time.sleep(0.5)

    # 3) Ctrl+V cola a imagem como anexo pendente no chat
    ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()

    # 4) Aguarda o "modo anexo" entrar — botao Enviar grande aparece
    # Pista chave: aparece um [data-icon='send'] CLICAVEL E VISIVEL.
    # Antes do paste, o botao do chat normalmente eh microfone (no send).
    SEND_XPATHS = [
        "//span[@data-icon='wds-ic-send-filled']/ancestor::div[@role='button'][1]",
        "//span[@data-icon='send']/ancestor::div[@role='button'][1]",
        "//div[@role='button'][@aria-label='Enviar']",
        "//div[@role='button'][@aria-label='Send']",
        "//button[@aria-label='Enviar']",
        "//div[@aria-label='Enviar']",
    ]
    botao_send = None
    inicio = time.time()
    while time.time() - inicio < 25:
        for sx in SEND_XPATHS:
            try:
                els = driver.find_elements(By.XPATH, sx)
                visiveis = [e for e in els if e.is_displayed()]
                if visiveis:
                    botao_send = visiveis[-1]   # ultimo = mais provavel ser o do preview
                    break
            except Exception:
                continue
        if botao_send is not None:
            break
        time.sleep(0.5)

    if botao_send is None:
        _wpp_debug("ANEXAR-FAIL | botao-send-nao-apareceu")
        raise RuntimeError(
            "Botao Enviar nao apareceu apos Ctrl+V (25s). "
            "Imagem provavelmente nao foi colada."
        )
    print("[OK] Modo anexo detectado (botao Enviar visivel).")
    _wpp_debug("ANEXAR-OK | botao-send-detectado")

    # 5) DIGITA a legenda: a caixa de mensagem do chat agora serve de caption
    if legenda:
        time.sleep(1.0)
        caption = _achar_caixa_mensagem(driver)
        if caption is None:
            _wpp_debug("LEGENDA-FAIL | caixa-mensagem-sumiu")
            raise RuntimeError("Caixa de mensagem sumiu apos colar imagem.")

        # Foca via JavaScript pra evitar interceptacao por overlay
        try:
            driver.execute_script("arguments[0].focus();", caption)
            time.sleep(0.3)
        except Exception:
            pass
        try:
            caption.click()
            time.sleep(0.3)
        except Exception:
            pass

        # Clipboard paste pra legenda (funciona com emojis)
        digitou_ok = False
        try:
            import win32clipboard  # type: ignore
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, legenda)
            finally:
                win32clipboard.CloseClipboard()
            time.sleep(0.3)
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("v").key_up(Keys.CONTROL).perform()
            time.sleep(1.2)
            digitou_ok = True
            _wpp_debug("LEGENDA-OK | via clipboard paste")
        except Exception as e:
            _wpp_debug(f"LEGENDA-CLIPBOARD-FAIL | {e}")
            # Fallback send_keys linha-a-linha
            try:
                linhas = legenda.split("\n")
                actions = ActionChains(driver)
                for i, linha in enumerate(linhas):
                    if i > 0:
                        actions.key_down(Keys.SHIFT).send_keys(Keys.ENTER).key_up(Keys.SHIFT)
                    if linha:
                        actions.send_keys(linha)
                actions.perform()
                time.sleep(1.5)
                digitou_ok = True
                _wpp_debug("LEGENDA-OK | via send_keys fallback")
            except Exception as e2:
                _wpp_debug(f"LEGENDA-SENDKEYS-FAIL | {e2}")

        if not digitou_ok:
            raise RuntimeError("Nao consegui digitar a legenda.")

        # Verifica se entrou no caption (innerText)
        try:
            txt_atual = driver.execute_script(
                "return arguments[0].innerText || arguments[0].textContent || '';",
                caption,
            ) or ""
        except Exception:
            txt_atual = ""
        marca = legenda.split("\n")[0].strip().strip("*")[:15]
        if marca and marca not in txt_atual:
            _wpp_debug(
                f"LEGENDA-WARN | texto-nao-confirmado | esperado~='{marca}' "
                f"encontrado='{txt_atual[:60]}'"
            )
            print(f"[AVISO] Legenda pode nao ter entrado (esperado ~ '{marca}').")
        else:
            print(f"[OK] Legenda digitada ({len(legenda)} chars) - confirmada no caption.")

    # 6) CLICA no botao Enviar
    # Re-acha o botao agora (pode ter mudado de identidade depois de digitar)
    botao_send = None
    for sx in SEND_XPATHS:
        try:
            els = driver.find_elements(By.XPATH, sx)
            visiveis = [e for e in els if e.is_displayed()]
            if visiveis:
                botao_send = visiveis[-1]
                break
        except Exception:
            continue

    enviou = False
    if botao_send is not None:
        try:
            botao_send.click()
            enviou = True
            _wpp_debug("SEND-CLICK-OK | botao detectado")
            print("[OK] Clique no botao Enviar.")
        except Exception as e:
            _wpp_debug(f"SEND-CLICK-FAIL | {e}")

    if not enviou:
        # Fallback: Enter
        try:
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            enviou = True
            _wpp_debug("SEND-FALLBACK | ENTER")
            print("[OK] Fallback: Enter pressionado.")
        except Exception as e:
            _wpp_debug(f"SEND-FAIL | {e}")
            raise RuntimeError(f"Nao consegui acionar o botao de enviar: {e}")

    # 7) CONFIRMA envio: o botao Enviar grande deve SUMIR (ou voltar a ser microfone)
    print("[INFO] Aguardando confirmacao real do envio...")
    fim = time.time() + 30
    sumiu = False
    while time.time() < fim:
        try:
            ainda_visivel = False
            # Procura QUALQUER send button que esteja DENTRO de uma area
            # de preview/anexo (nao o do chat normal vazio)
            for sx in SEND_XPATHS[:2]:  # so os 2 primeiros, mais especificos
                els = driver.find_elements(By.XPATH, sx)
                if any(e.is_displayed() for e in els):
                    ainda_visivel = True
                    break
            if not ainda_visivel:
                sumiu = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not sumiu:
        _wpp_debug("ANEXAR-WARN | botao-send-ainda-visivel-apos-30s")
        # Nao raise aqui porque pode ser que a UI mostre o send sempre.
        # Vamos confirmar pela presenca da mensagem no chat
        print("[AVISO] Botao Enviar continua visivel — verificando se mensagem entrou no chat...")

    # Confirma pela ULTIMA mensagem out do chat (com tick)
    tick_ok = False
    fim = time.time() + 25
    TICK_XPATHS = [
        "(//div[contains(@class,'message-out')])[last()]//span[contains(@data-icon,'check') or contains(@data-icon,'msg-')]",
        "(//div[@data-pre-plain-text])[last()]//span[contains(@data-icon,'check')]",
        "(//div[contains(@class,'message-out')])[last()]",
    ]
    while time.time() < fim:
        for tx in TICK_XPATHS:
            try:
                els = driver.find_elements(By.XPATH, tx)
                if any(e.is_displayed() for e in els):
                    tick_ok = True
                    break
            except Exception:
                continue
        if tick_ok:
            break
        time.sleep(0.5)

    if tick_ok:
        print("[OK] Mensagem enviada confirmada no chat.")
        _wpp_debug("ANEXAR-OK | mensagem-confirmada-no-chat")
    elif sumiu:
        print("[OK] Botao sumiu (envio aceito) — tick nao confirmado em 25s.")
        _wpp_debug("ANEXAR-WARN | botao-sumiu-sem-tick")
    else:
        _wpp_debug("ANEXAR-FAIL | botao-nao-sumiu-e-sem-tick")
        raise RuntimeError(
            "Cliquei em Enviar mas nem o botao sumiu nem a mensagem apareceu "
            "no chat em 55s. A imagem provavelmente NAO foi enviada."
        )

    time.sleep(2.0)


def _anexar_via_file_input(driver, caminho_imagem: Path, legenda: str = ""):
    """
    FALLBACK: anexa via file input (se o clipboard paste não funcionar).
    NOTA: este caminho PODE fazer WhatsApp tratar como sticker, dependendo
    da versão. Usar só como último recurso.
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    input_file = _achar_input_de_foto(driver)
    if input_file is None and _abrir_menu_anexar(driver):
        time.sleep(0.5)
        input_file = _achar_input_de_foto(driver)

    if input_file is None:
        raise RuntimeError("Não localizei o campo de anexar FOTO.")

    print(f"[INFO] (fallback) Anexando via file input: {caminho_imagem.name}")
    _wpp_debug(f"FILE-INPUT-ATIVO | {caminho_imagem.name} — risco de virar STICKER")
    input_file.send_keys(str(caminho_imagem.absolute()))
    time.sleep(2.5)

    if legenda:
        try:
            ActionChains(driver).send_keys(legenda).perform()
            time.sleep(0.6)
        except Exception:
            pass

    # Botão enviar
    for sel in [
        "//span[@data-icon='send']",
        "//div[@role='button'][@aria-label='Enviar']",
        "//button[@aria-label='Enviar']",
    ]:
        try:
            botao = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, sel))
            )
            botao.click()
            time.sleep(3.0)
            return
        except Exception:
            continue
    ActionChains(driver).send_keys(Keys.ENTER).perform()
    time.sleep(3.0)


# ============================================================
# FUNÇÕES PÚBLICAS
# ============================================================

def primeiro_uso():
    """
    Abre o WhatsApp Web pela primeira vez para você escanear o QR.
    Aguarda até 2 minutos para o login completar.
    """
    print("=" * 60)
    print("PRIMEIRO USO — escaneie o QR code com seu celular")
    print("=" * 60)
    print(f"[INFO] Perfil sendo salvo em: {PERFIL_CHROME}")
    print()

    # Primeiro uso: Chrome PRECISA estar visível para escanear o QR
    driver = _criar_driver(visivel=True)
    sucesso = False
    try:
        driver.get("https://web.whatsapp.com")
        print("[INFO] Página carregada. Olhe a JANELA DO CHROME que abriu.")
        print("[INFO] Se aparecer QR code, escaneie com o celular agora.")
        print("[INFO] Aguardando login (até 2 minutos)...")

        # IMPORTANTE: usamos _aguardar_login (não checa QR) porque
        # aqui o QR é justamente o que esperamos.
        _aguardar_login(driver, timeout=TIMEOUT_LOGIN)

        # Login bem-sucedido: chat list visível. Damos uns segundos para
        # o cache do WhatsApp Web ser gravado no perfil antes de fechar.
        print("[INFO] Login detectado — aguardando 8s para salvar a sessão...")
        time.sleep(8)
        sucesso = True
        print()
        print("=" * 60)
        print("[OK] LOGIN CONFIRMADO! Sessão salva.")
        print(f"     Perfil: {PERFIL_CHROME}")
        print("=" * 60)
        print("\nPróximas execuções já entrarão logadas automaticamente.")
    except KeyboardInterrupt:
        print("\n[CANCELADO] Operação interrompida pelo usuário.")
    except TimeoutError as e:
        print(f"\n[ERRO] Não consegui confirmar o login no tempo esperado.")
        print(f"        Detalhe: {e}")
        # Salva screenshot de erro pra diagnóstico
        try:
            erro_png = HERE / f"erro_primeiro_uso_{int(time.time())}.png"
            driver.save_screenshot(str(erro_png))
            print(f"[INFO] Screenshot salvo em: {erro_png}")
        except Exception:
            pass
    except Exception as e:
        print(f"\n[ERRO] Falha no primeiro uso: {type(e).__name__}: {e}")
        try:
            erro_png = HERE / f"erro_primeiro_uso_{int(time.time())}.png"
            driver.save_screenshot(str(erro_png))
            print(f"[INFO] Screenshot salvo em: {erro_png}")
        except Exception:
            pass
    finally:
        # O ChromeDriver às vezes solta um stack trace ao fechar no
        # Windows — não é problema real se o login já foi gravado.
        try:
            driver.quit()
        except Exception:
            pass

    if sucesso:
        print("\n>>> Tudo certo! Pode rodar agora:")
        print(">>>   python 05_enviar_whatsapp.py --teste")
    else:
        print("\n>>> Não consegui confirmar o login. Possíveis motivos:")
        print(">>>   - Você não escaneou o QR a tempo")
        print(">>>   - O celular não estava com internet na hora")
        print(">>>   - O Chrome normal já estava com WhatsApp Web aberto (causa conflito)")
        print(">>>")
        print(">>> Tente de novo:")
        print(">>>   python 05_enviar_whatsapp.py --primeiro-uso")


def enviar_dashboards(envios: dict, legenda: str = "") -> dict:
    """
    Envia múltiplos PNGs para múltiplos grupos numa MESMA sessão do Chrome.

    Args:
        envios: dict pode ter 2 formatos:
            - {nome_grupo: caminho_png, ...}                      → usa `legenda` global
            - {nome_grupo: (caminho_png, legenda_especifica), ...} → cada grupo tem sua legenda
        legenda: legenda usada como FALLBACK quando o valor do dict é só o path.

    Returns:
        dict {nome_grupo: True/False/erro_str} indicando sucesso de cada envio.
    """
    # Normaliza o dict de envios para sempre ter (path, legenda) como valor
    envios_norm = {}
    for nome, valor in envios.items():
        if isinstance(valor, (tuple, list)) and len(valor) >= 2:
            envios_norm[nome] = (Path(valor[0]), valor[1] or legenda)
        else:
            envios_norm[nome] = (Path(valor), legenda)

    # Validações
    grupos_invalidos = [g for g in envios_norm.keys() if "NOME DO GRUPO" in g.upper()]
    if grupos_invalidos:
        raise ValueError(
            f"Grupos com placeholder: {grupos_invalidos}\n"
            "Edite GRUPO_MONTAGEM_EXTERNA / GRUPO_ADMINISTRATIVO em 05_enviar_whatsapp.py"
        )
    for nome, (cam, _) in envios_norm.items():
        if not cam.exists():
            raise FileNotFoundError(f"PNG não encontrado para '{nome}': {cam}")

    print("=" * 60)
    print(f"ENVIANDO PARA {len(envios_norm)} GRUPO(S) DO WHATSAPP")
    for g in envios_norm:
        print(f"  → {g}")
    print("=" * 60)
    print("[INFO] Chrome rodando em modo discreto (fora da tela).")

    driver = _criar_driver(visivel=False)
    resultado = {}
    try:
        driver.get("https://web.whatsapp.com")
        print("[INFO] Aguardando WhatsApp Web autenticar...")
        _aguardar_whatsapp_carregar(driver, timeout=TIMEOUT_LOGIN)
        print("[OK] WhatsApp Web logado.")

        for nome_grupo, (caminho_png, legenda_grupo) in envios_norm.items():
            try:
                print(f"\n--- Enviando para '{nome_grupo}' ---")
                if legenda_grupo:
                    print(f"    Legenda: \"{legenda_grupo}\"")
                _abrir_conversa(driver, nome_grupo)
                _anexar_e_enviar_imagem(driver, caminho_png, legenda=legenda_grupo)
                print(f"[OK] '{nome_grupo}' enviado.")
                resultado[nome_grupo] = True
                time.sleep(2.0)  # margem entre envios
            except Exception as e:
                print(f"[ERRO] Falha ao enviar para '{nome_grupo}': {e}")
                resultado[nome_grupo] = f"ERRO: {e}"
                # Salva screenshot pra diagnóstico
                try:
                    erro_png = HERE / f"erro_whatsapp_{nome_grupo.replace(' ','_')}_{int(time.time())}.png"
                    driver.save_screenshot(str(erro_png))
                    print(f"[INFO] Screenshot do erro: {erro_png}")
                except Exception:
                    pass
                # Continua tentando os outros grupos

        return resultado
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def enviar(caminho_imagem: Path, grupo: Optional[str] = None,
           legenda: str = "") -> bool:
    """
    Envia uma imagem para o grupo configurado.

    Args:
        caminho_imagem: Path do PNG (gerado pela etapa 04)
        grupo:          nome do grupo (default = GRUPO_DESTINO)
        legenda:        texto opcional para acompanhar a imagem

    Returns:
        True se enviou com sucesso.
    """
    if grupo is None:
        grupo = GRUPO_DESTINO

    if grupo == "NOME DO GRUPO AQUI":
        raise ValueError(
            "Você precisa editar GRUPO_DESTINO em 05_enviar_whatsapp.py "
            "com o nome exato do grupo do WhatsApp."
        )

    if not Path(caminho_imagem).exists():
        raise FileNotFoundError(f"Imagem não encontrada: {caminho_imagem}")

    print("=" * 60)
    print(f"ENVIANDO PARA WHATSAPP — grupo: {grupo}")
    print("=" * 60)
    print("[INFO] Chrome rodando em modo discreto (fora da tela).")

    # Envio normal: Chrome posicionado off-screen
    driver = _criar_driver(visivel=False)
    try:
        driver.get("https://web.whatsapp.com")
        print("[INFO] Aguardando WhatsApp Web autenticar...")
        _aguardar_whatsapp_carregar(driver, timeout=TIMEOUT_LOGIN)
        print("[OK] WhatsApp Web logado.")
        _abrir_conversa(driver, grupo)
        _anexar_e_enviar_imagem(driver, Path(caminho_imagem), legenda=legenda)
        print(f"[SUCESSO] Imagem enviada para '{grupo}'.")
        return True
    except Exception as e:
        # Salva screenshot para diagnóstico em caso de erro
        try:
            erro_png = HERE / f"erro_whatsapp_{int(time.time())}.png"
            driver.save_screenshot(str(erro_png))
            print(f"[INFO] Screenshot de erro salvo em: {erro_png}")
        except Exception:
            pass
        raise
    finally:
        try:
            driver.quit()
        except Exception:
            pass


# ============================================================
# EXECUÇÃO MANUAL
# ============================================================

if __name__ == "__main__":
    if "--primeiro-uso" in sys.argv:
        primeiro_uso()
    elif "--teste" in sys.argv:
        # Captura screenshot da planilha atual e envia
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "card", HERE / "04_gerar_card.py")
        card_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(card_mod)
        caminho = card_mod.capturar_planilha()
        enviar(caminho)
    else:
        print("Uso:")
        print("  python 05_enviar_whatsapp.py --primeiro-uso")
        print("    → abre o Chrome para escanear o QR code (1ª vez)")
        print("  python 05_enviar_whatsapp.py --teste")
        print("    → gera card de exemplo e envia para GRUPO_DESTINO")
