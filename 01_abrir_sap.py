"""
==============================================================
PROJETO: OM_por_HORA — Automação ZEM117 SAP
ETAPA  : 01 — Abrir SAP GUI e conectar à PRD via SSO
AUTOR  : Sidney Albuquerque (BEMOL S/A)
DESCRIÇÃO:
    Fluxo conforme o SAP Logon 770 da BEMOL:
        Conexões → 1. BEMOL-SSO → ECC-SSO → PRD-SSO

    Como o ambiente é SSO (Single Sign-On), o login é feito
    automaticamente com as credenciais do Windows.

    Este script descobre o NOME EXATO da conexão PRD-SSO
    automaticamente lendo o arquivo SAPUILandscape.xml,
    evitando erro "SAP Logon connection entry not found".
==============================================================
"""

import os
import time
import subprocess
import xml.etree.ElementTree as ET
import win32com.client
from pathlib import Path

# ============================================================
# CONFIGURAÇÕES
# ============================================================

SAP_LOGON_PATH = r"C:\Program Files (x86)\SAP\FrontEnd\SAPgui\saplogon.exe"

# Nome EXATO da conexão como aparece no SAP Logon da BEMOL:
#   Conexões → 1. BEMOL-SSO → ECC-SSO → "PRD-SSO [SAPPRD]"
SAP_CONNECTION_NAME = "PRD-SSO [SAPPRD]"

# Critérios de fallback — caso o nome acima mude um dia, o script
# ainda tentará descobrir uma conexão cujo nome contenha TODAS
# essas palavras-chave (case-insensitive).
PALAVRAS_CHAVE_CONEXAO = ["PRD", "SSO"]

# Último recurso, se nada for encontrado.
SAP_CONNECTION_NAME_FALLBACK = "PRD-SSO [SAPPRD]"

# Caminhos possíveis do arquivo de configuração do SAP Logon
CAMINHOS_LANDSCAPE = [
    Path(os.environ.get("APPDATA", "")) / "SAP" / "Common" / "SAPUILandscape.xml",
    Path("C:/ProgramData/SAP/Common/SAPUILandscapeGlobal.xml"),
    Path(os.environ.get("APPDATA", "")) / "SAP" / "Common" / "SAPUILandscapeGlobal.xml",
]

TIMEOUT_LOGON      = 30
TIMEOUT_POS_LOGIN  = 25

# ============================================================
# FUNÇÕES
# ============================================================

def abrir_sap_logon() -> None:
    """Garante que o processo SAP Logon esteja em execução."""
    import psutil
    for proc in psutil.process_iter(["name"]):
        nome = (proc.info.get("name") or "").lower()
        if "saplogon.exe" in nome:
            print("[OK] SAP Logon já está em execução.")
            return

    if not Path(SAP_LOGON_PATH).exists():
        raise FileNotFoundError(
            f"SAP Logon não encontrado em: {SAP_LOGON_PATH}\n"
            "Ajuste SAP_LOGON_PATH no topo do script."
        )

    print("[INFO] Iniciando SAP Logon...")
    subprocess.Popen([SAP_LOGON_PATH])

    inicio = time.time()
    while time.time() - inicio < TIMEOUT_LOGON:
        for proc in psutil.process_iter(["name"]):
            nome = (proc.info.get("name") or "").lower()
            if "saplogon.exe" in nome:
                time.sleep(3)  # margem para a UI ficar pronta
                print("[OK] SAP Logon iniciado.")
                return
        time.sleep(1)

    raise TimeoutError("Tempo esgotado aguardando o SAP Logon iniciar.")


def descobrir_conexao_alvo() -> str:
    """
    Primeiro tenta usar SAP_CONNECTION_NAME (nome exato).
    Caso ele não seja localizado no SAPUILandscape.xml, faz
    busca por palavras-chave. Em último caso, devolve o fallback.
    """
    # 1) Tenta confirmar que o nome exato existe no XML
    nomes_no_xml = []
    for caminho in CAMINHOS_LANDSCAPE:
        if not caminho.exists():
            continue
        try:
            tree = ET.parse(caminho)
            root = tree.getroot()
            for svc in root.iter("Service"):
                nome = svc.attrib.get("name", "")
                if nome:
                    nomes_no_xml.append(nome)
        except Exception as e:
            print(f"[AVISO] Falha ao ler {caminho}: {e}")

    if SAP_CONNECTION_NAME in nomes_no_xml:
        print(f"[OK] Usando conexão configurada: '{SAP_CONNECTION_NAME}'")
        return SAP_CONNECTION_NAME

    # 2) Busca por palavras-chave (fallback inteligente)
    candidatos = [
        n for n in nomes_no_xml
        if all(p.upper() in n.upper() for p in PALAVRAS_CHAVE_CONEXAO)
    ]
    candidatos = list(dict.fromkeys(candidatos))

    if candidatos:
        escolhida = candidatos[0]
        print(f"[OK] Conexão descoberta automaticamente: '{escolhida}'")
        if len(candidatos) > 1:
            print(f"     (outras candidatas: {candidatos[1:]})")
        return escolhida

    # 3) Último recurso
    print(f"[AVISO] Nenhuma conexão localizada no XML.")
    print(f"        Tentando fallback direto: '{SAP_CONNECTION_NAME_FALLBACK}'")
    return SAP_CONNECTION_NAME_FALLBACK


def _sessao_viva(connection) -> bool:
    """
    Testa se uma conexão SAP ainda tem sessão ATIVA (não expirou).

    O SAP normalmente desconecta sessões após 30-60min de inatividade.
    Como nossa automação roda de hora em hora, a sessão pode estar
    "zumbi" — o objeto COM existe mas qualquer operação falha.

    Estratégia: tenta ler informações básicas e acessar wnd[0].
    Se qualquer uma falhar (COM error, AttributeError, etc.), tratamos
    como sessão morta e a reconexão é forçada.
    """
    try:
        if connection.Children.Count == 0:
            return False
        session = connection.Children(0)
        # Testes que falham em sessões zumbi:
        usuario = session.Info.User
        if not (usuario or "").strip():
            return False
        # Tentativa de acessar a janela principal — se a sessão morreu,
        # esse findById lança exception.
        _ = session.findById("wnd[0]")
        return True
    except Exception:
        return False


def conectar_prd_sso() -> "win32com.client.CDispatch":
    """
    Abre a conexão PRD-SSO e retorna a sessão autenticada via SSO.
    Detecta automaticamente sessões expiradas (timeout SAP por inatividade)
    e reconecta sozinho — sem precisar de intervenção.
    """
    nome_conexao = descobrir_conexao_alvo()

    try:
        sap_gui_auto = win32com.client.GetObject("SAPGUI")
    except Exception as e:
        raise RuntimeError(
            "Não foi possível acessar o SAP GUI Scripting.\n"
            "Verifique se:\n"
            "  - O SAP Logon está aberto;\n"
            "  - O scripting está habilitado no servidor "
            "(RZ11 → sapgui/user_scripting = TRUE);\n"
            "  - O scripting está habilitado no cliente "
            "(Opções → Acessibilidade e scripting → Scripting)."
        ) from e

    application = sap_gui_auto.GetScriptingEngine

    # ---------- 1) Procura conexão existente PRD-SSO ----------
    connection = None
    for i in range(application.Connections.Count):
        conn = application.Children(i)
        descricao = (conn.Description or "").upper()
        if nome_conexao.upper() in descricao or "PRD" in descricao:
            # ---------- 2) Testa se a sessão dela está VIVA ou ZUMBI ----------
            if _sessao_viva(conn):
                connection = conn
                print(f"[OK] Conexão SAP '{conn.Description}' ainda viva — reutilizando.")
                break
            else:
                # Conexão existe mas sessão expirou (timeout SAP).
                # Fecha pra forçar reconexão limpa.
                print(f"[INFO] Conexão SAP '{conn.Description}' EXPIROU por inatividade. Fechando...")
                try:
                    conn.CloseConnection()
                except Exception as e:
                    print(f"[AVISO] Erro ao fechar conexão zumbi: {e}")
                time.sleep(1.5)  # dá tempo do SAP processar o fechamento

    # ---------- 3) Se não tem conexão (ou era zumbi), abre nova ----------
    if connection is None:
        print(f"[INFO] Abrindo nova conexão SAP: {nome_conexao}")
        try:
            connection = application.OpenConnection(nome_conexao, True)
        except Exception as e:
            raise RuntimeError(
                f"Falha ao abrir conexão '{nome_conexao}'.\n"
                "Execute primeiro o script 00_listar_conexoes.py para\n"
                "ver o nome EXATO cadastrado no seu SAP Logon e ajustar\n"
                "PALAVRAS_CHAVE_CONEXAO / SAP_CONNECTION_NAME_FALLBACK.\n\n"
                f"Erro original: {e}"
            ) from e

    # Aguarda a sessão ser criada
    inicio = time.time()
    while connection.Children.Count == 0:
        if time.time() - inicio > TIMEOUT_POS_LOGIN:
            raise TimeoutError("A sessão SAP não foi criada no tempo esperado.")
        time.sleep(0.5)

    session = connection.Children(0)

    # Trata pop-up de múltiplos logins (se aparecer)
    try:
        session.findById("wnd[1]/usr/radMULTI_LOGON_OPT2").select()
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        print("[INFO] Aviso de múltiplos logins tratado.")
    except Exception:
        pass

    # Trata qualquer outro pop-up genérico
    try:
        session.findById("wnd[1]").sendVKey(0)
    except Exception:
        pass

    # Aguarda autenticação SSO completar
    inicio = time.time()
    while time.time() - inicio < TIMEOUT_POS_LOGIN:
        try:
            if (session.Info.User or "").strip():
                break
        except Exception:
            pass
        time.sleep(0.5)

    print("[OK] Sessão SAP autenticada via SSO.")
    return session


def obter_sessao_segura():
    """
    Função TOPO-NIVEL recomendada para automações agendadas.

    Combina 3 garantias em uma só chamada:

    1) SAP FECHADO     → abre o SAP Logon automaticamente (abrir_sap_logon).
    2) SAP EM TIMEOUT  → detecta sessão zumbi e relogga via SSO
                          (conectar_prd_sso já faz isso internamente).
    3) USUÁRIO USANDO  → se a sessão base tem transação ativa ou pop-up
                          modal aberto, abre uma SESSÃO PARALELA na mesma
                          conexão (createSession). Assim a automação roda
                          numa janela separada sem interromper o trabalho
                          do usuário. SAP suporta até 6 sessões simultâneas.

    Retorna: o objeto session pronto pra navegar (já no menu inicial ou
    pronto pra receber /n<transacao>).
    """
    print("[INFO] Garantindo sessão SAP segura...")

    # ETAPA 1+2: garante SAP aberto e sessão viva (relogga se expirou)
    abrir_sap_logon()
    base_session = conectar_prd_sso()
    connection = base_session.Parent  # objeto Connection (pai da Session)

    # ETAPA 3: detecta se o usuário está usando a sessão base
    em_uso = False
    motivo_uso = ""
    try:
        transacao = (base_session.Info.Transaction or "").strip().upper()
        # SESSION_MANAGER / SMEN / S000 = menu inicial = não está sendo usado
        if transacao and transacao not in ("", "SESSION_MANAGER", "SMEN", "S000"):
            em_uso = True
            motivo_uso = f"transação ativa: {transacao}"
    except Exception:
        pass

    # Também considera em uso se tem janela modal (pop-up) aberta
    if not em_uso:
        try:
            base_session.findById("wnd[1]")
            em_uso = True
            motivo_uso = "janela modal (wnd[1]) aberta"
        except Exception:
            pass

    if not em_uso:
        print("[OK] Sessão SAP livre — usando ela.")
        return base_session

    # SESSÃO BASE EM USO — cria uma paralela pra não roubar a do usuário
    print(f"[INFO] Sessão SAP está em uso ({motivo_uso}).")
    print("[INFO] Criando sessão PARALELA para não interromper o usuário...")

    qtd_antes = connection.Children.Count
    try:
        base_session.createSession()
    except Exception as e:
        print(f"[AVISO] Falha ao criar sessão paralela: {e}")
        print("[AVISO] Vai usar a sessão base — pode interromper o usuário.")
        return base_session

    # Aguarda a nova sessão aparecer (até 25s — algumas máquinas demoram mais)
    inicio = time.time()
    nova_session = None
    while time.time() - inicio < 25.0:
        if connection.Children.Count > qtd_antes:
            try:
                nova_session = connection.Children(connection.Children.Count - 1)
                # Espera a sessão terminar de inicializar (até 8s adicionais)
                pronta = False
                inicio_init = time.time()
                while time.time() - inicio_init < 8.0:
                    try:
                        wnd = nova_session.findById("wnd[0]")
                        # Tenta tambem ler o usuario — confirma que SSO carregou
                        _ = nova_session.Info.User
                        # Sanity check: forca menu inicial pra garantir estado limpo
                        try:
                            nova_session.findById("wnd[0]/tbar[0]/okcd").text = "/n"
                            nova_session.findById("wnd[0]").sendVKey(0)
                            time.sleep(0.5)
                        except Exception:
                            pass
                        pronta = True
                        break
                    except Exception:
                        time.sleep(0.5)

                if pronta:
                    print(f"[OK] Sessão paralela criada e inicializada (índice {connection.Children.Count - 1}).")
                    return nova_session
            except Exception as e:
                print(f"[AVISO] Falha verificando sessão paralela: {e}")
        time.sleep(0.5)

    print("[AVISO] Sessão paralela não confirmada em 25s. Usando sessão base.")
    return base_session


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("OM_por_HORA — Etapa 01: Abrir SAP GUI (PRD-SSO)")
    print("=" * 60)

    abrir_sap_logon()
    session = conectar_prd_sso()

    print("\n[SUCESSO] Sessão SAP pronta para receber comandos.")
    print(f"  Usuário      : {session.Info.User}")
    print(f"  Mandante     : {session.Info.Client}")
    print(f"  Sistema      : {session.Info.SystemName}")
    print(f"  Transação    : {session.Info.Transaction or '(menu inicial)'}")
    print("\nPróxima etapa: executar a transação ZEM117.")
