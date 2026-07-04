"""
==============================================================
PROJETO: OM_por_HORA — Automação ZWM117 SAP
ETAPA  : 02 — Executar a transação ZWM117 e extrair indicadores
AUTOR  : Sidney Albuquerque (BEMOL S/A)
DESCRIÇÃO:
    Fluxo (baseado no script gravado pelo SAP GUI Recorder):
      1) Maximiza wnd[0].
      2) Vai para a transação ZWM117 (/nzwm117).
      3) F17 (btn[17]) — abre o seletor de variante.
      4) Em wnd[1], preenche txtENAME-LOW com a matrícula 21039.
      5) F8 (btn[8]) na popup para buscar/selecionar a variante.
      6) De volta a wnd[0], atualiza SO_DATA-LOW e SO_DATA-HIGH
         com a data de hoje (DD.MM.YYYY).
      7) F8 (btn[8] tbar[1]) para executar.
      8) Lê o tree control de resultado e extrai os totais de:
            - OM Sucesso
            - OM Insucesso
            - OMs Iniciadas
    Retorna um dicionário com os 3 valores inteiros.
==============================================================
"""

import sys
import time
import importlib.util
from datetime import datetime
from pathlib import Path

# Reaproveita a sessão criada pela etapa 01
HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location(
    "abrir_sap", HERE / "01_abrir_sap.py"
)
abrir_sap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abrir_sap)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

MATRICULA = "21039"               # criador da variante salva no SAP
TIMEOUT_RESULTADO = 60            # segundos para a ZWM117 carregar
TREE_ID = "wnd[0]/shellcont/shell/shellcont[1]/shell[1]"

# Critérios para identificar as 3 colunas relevantes no tree
# (o teste é feito sobre o TÍTULO da coluna, case-insensitive).
# Importante: "INSUCESSO" precisa vir antes de "SUCESSO" no código,
# porque "SUCESSO" também está contido em "INSUCESSO".

# ============================================================
# FUNÇÕES
# ============================================================

def abrir_zwm117(session) -> None:
    """Navega da tela inicial até o resultado da ZWM117."""
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

    # Caso surja popup pedindo para escolher entre várias variantes,
    # pressiona Enter para confirmar a primeira sugerida.
    try:
        if session.ActiveWindow.Name == "wnd[1]":
            session.findById("wnd[1]").sendVKey(0)
            time.sleep(0.5)
    except Exception:
        pass

    hoje = datetime.now().strftime("%d.%m.%Y")
    print(f"[INFO] Definindo período da execução: {hoje} a {hoje}")
    session.findById("wnd[0]/usr/ctxtSO_DATA-LOW").text = hoje
    session.findById("wnd[0]/usr/ctxtSO_DATA-HIGH").text = hoje

    print("[INFO] Executando relatório (F8)...")
    session.findById("wnd[0]/tbar[1]/btn[8]").press()

    # Aguarda o tree de resultado aparecer
    print("[INFO] Aguardando resultado carregar...")
    inicio = time.time()
    while time.time() - inicio < TIMEOUT_RESULTADO:
        try:
            session.findById(TREE_ID)
            time.sleep(2)  # pequena margem para o tree popular
            print("[OK] Tela de resultado carregada.")
            return
        except Exception:
            time.sleep(1)

    raise TimeoutError(
        "Tela de resultado da ZWM117 não apareceu no tempo esperado."
    )


def _to_int(valor) -> int:
    """Converte texto SAP para int (trata '1.234', '1,234', vazios)."""
    if valor is None:
        return 0
    s = str(valor).strip().replace(".", "").replace(",", "")
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        # Pode vir como "1.234,00" — pega só a parte inteira
        return int("".join(c for c in s if c.isdigit()) or "0")


def diagnostico_tree(session) -> None:
    """
    Imprime estrutura completa do tree control de resultado
    para ajudar a mapear node keys / column names.
    """
    print("\n" + "=" * 60)
    print("DIAGNÓSTICO DO TREE DE RESULTADO")
    print("=" * 60)
    tree = session.findById(TREE_ID)

    try:
        colunas = _coletar_colunas(tree)
        print(f"\nColunas ({len(colunas)}):")
        for i, col in enumerate(colunas):
            print(f"  [{i}] cname='{col['cname']}'  título='{col['titulo']}'")
    except Exception as e:
        print(f"[ERRO] Coleta de colunas falhou: {e}")
        colunas = []

    try:
        nodes = tree.GetAllNodeKeys()
        print(f"\nNós ({nodes.Count}) — mostrando os 3 primeiros:")
        for i in range(min(nodes.Count, 3)):
            node_key = nodes.ElementAt(i)
            try:
                texto_nodo = tree.GetNodeTextByKey(node_key)
            except Exception:
                texto_nodo = "(?)"
            print(f"  Node[{i}] key='{node_key}' texto='{texto_nodo}'")

            for col in colunas:
                try:
                    valor = tree.GetItemText(node_key, col["cname"])
                    if valor:
                        print(f"        '{col['titulo']}' ({col['cname']}) = '{valor}'")
                except Exception:
                    pass
    except Exception as e:
        print(f"[ERRO] GetAllNodeKeys falhou: {e}")
    print("=" * 60 + "\n")


def _coletar_colunas(tree) -> list[dict]:
    """
    Retorna [{cname, titulo}, ...] para todas as colunas do tree.
    Usa GetColumnTitles() (alinhado por índice com GetColumnNames())
    e cai para GetColumnTitleFromName() se necessário.
    """
    nomes = tree.GetColumnNames()
    n = nomes.Count

    titulos_por_indice = [None] * n
    try:
        titulos_obj = tree.GetColumnTitles()
        for i in range(min(n, titulos_obj.Count)):
            titulos_por_indice[i] = titulos_obj.ElementAt(i)
    except Exception:
        pass

    resultado = []
    for i in range(n):
        cname = nomes.ElementAt(i)
        titulo = titulos_por_indice[i]
        if not titulo:
            # fallback: tenta API alternativa por nome
            for metodo in ("GetColumnTitleFromName", "GetColumnHeaderText"):
                try:
                    t = getattr(tree, metodo)(cname)
                    if t:
                        titulo = t
                        break
                except Exception:
                    continue
        resultado.append({"cname": cname, "titulo": (titulo or "").strip()})
    return resultado


def ler_indicadores(session) -> dict:
    """
    Extrai os 3 indicadores da grid de resultado da ZWM117.

    Estrutura real (confirmada via screenshots):
      - Linhas (nodes): cada montador; a 1ª linha é 'TOTAL'.
      - Colunas visíveis: "OMs Atribuídas", "OMs Iniciadas",
        "Total de OM", "OM Insucesso", "OM Sucesso", "OM Cliente",
        "OM Interna", "OM Loja", "OM Avaria", "Cliente"...

    Estratégia robusta:
      1) Coleta TODAS as colunas com (cname, titulo).
      2) Para cada indicador, identifica TODAS as candidatas (título
         contendo a palavra-chave). Pode haver colunas técnicas
         duplicadas (hidden) — por isso coletamos todas.
      3) Encontra a linha 'TOTAL'.
      4) Para cada indicador, lê o valor em cada candidata e escolhe
         a primeira que tem texto não-vazio na linha TOTAL.
    """
    tree = session.findById(TREE_ID)
    indicadores = {"sucesso": 0, "insucesso": 0, "iniciadas": 0}

    # 1) Coletar todas as colunas
    try:
        colunas = _coletar_colunas(tree)
    except Exception as e:
        raise RuntimeError(f"Não foi possível listar colunas do tree: {e}")

    # 2) Separar candidatas por indicador
    candidatas = {"sucesso": [], "insucesso": [], "iniciadas": []}
    for col in colunas:
        titulo = col["titulo"].upper()
        if not titulo:
            continue  # coluna sem título = provavelmente hidden
        # Importante: testar INSUCESSO antes de SUCESSO
        if "INSUCESSO" in titulo:
            candidatas["insucesso"].append(col)
        elif "SUCESSO" in titulo:
            candidatas["sucesso"].append(col)
        elif "INICIAD" in titulo:
            candidatas["iniciadas"].append(col)

    print("\n[INFO] Candidatas encontradas por indicador:")
    for k, lst in candidatas.items():
        if lst:
            descr = ", ".join(f"'{c['titulo']}' (cname='{c['cname']}')" for c in lst)
            print(f"  - {k}: {descr}")
        else:
            print(f"  - {k}: (nenhuma!)")

    # 3) Encontrar a linha TOTAL
    try:
        nodes = tree.GetAllNodeKeys()
    except Exception as e:
        raise RuntimeError(f"Não foi possível listar nós do tree: {e}")

    node_total = None
    for i in range(nodes.Count):
        node_key = nodes.ElementAt(i)
        try:
            texto = (tree.GetNodeTextByKey(node_key) or "").strip().upper()
        except Exception:
            texto = ""
        if texto == "TOTAL":
            node_total = node_key
            print(f"[OK] Linha TOTAL encontrada (node key='{node_key}').")
            break

    if node_total is None and nodes.Count > 0:
        node_total = nodes.ElementAt(0)
        print(f"[AVISO] Linha 'TOTAL' não localizada — usando primeiro nó '{node_total}'.")

    if node_total is None:
        raise RuntimeError("Nenhum nó encontrado no tree de resultado.")

    # 4) Para cada indicador, ler valores das candidatas e escolher a melhor
    def _escolher_e_ler(lista_candidatas: list[dict], label: str) -> int:
        if not lista_candidatas:
            print(f"  [AVISO] Sem candidata para '{label}' — retornando 0.")
            return 0

        avaliadas = []
        for c in lista_candidatas:
            try:
                raw = tree.GetItemText(node_total, c["cname"])
            except Exception as e:
                raw = ""
                print(f"  [AVISO] Falha ao ler '{c['cname']}': {e}")
            avaliadas.append({**c, "raw": raw or ""})

        # Preferência: raw não-vazio com dígito
        com_digito = [a for a in avaliadas if any(ch.isdigit() for ch in a["raw"])]
        if com_digito:
            escolhida = com_digito[0]
        else:
            # Se tudo veio vazio (e.g. Sucesso=0 mostrado como branco),
            # pega a coluna candidata com título mais "exato".
            preferidos = [a for a in avaliadas if a["titulo"].upper().startswith(("OM ", "OMS "))]
            escolhida = preferidos[0] if preferidos else avaliadas[0]

        valor = _to_int(escolhida["raw"])
        print(f"  [OK] {label.upper():10s} = {valor:>6}  "
              f"(coluna '{escolhida['titulo']}' / cname='{escolhida['cname']}', raw='{escolhida['raw']}')")
        return valor

    print("\n[INFO] Lendo valores da linha TOTAL:")
    indicadores["sucesso"]   = _escolher_e_ler(candidatas["sucesso"],   "sucesso")
    indicadores["insucesso"] = _escolher_e_ler(candidatas["insucesso"], "insucesso")
    indicadores["iniciadas"] = _escolher_e_ler(candidatas["iniciadas"], "iniciadas")

    # Sanity dump completo da linha TOTAL — ajuda a debugar futuras quebras
    print("\n[DEBUG] Linha TOTAL completa:")
    for col in colunas:
        try:
            raw = tree.GetItemText(node_total, col["cname"])
        except Exception:
            raw = "(erro)"
        if raw and raw.strip():
            print(f"  título='{col['titulo']}'  cname='{col['cname']}'  valor='{raw}'")

    return indicadores


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

def executar(diagnostico: bool = False) -> dict:
    """
    Função principal: abre SAP, executa ZWM117 e retorna os indicadores.

    Inclui camada de RETRY para sessão expirada — se o SAP cair durante
    a navegação (timeout de sessão), fecha tudo e tenta de novo do zero.
    """
    MAX_TENTATIVAS = 2  # 1ª normal + 1ª retry após reconexão
    ultimo_erro = None

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            # obter_sessao_segura cobre 3 casos:
            #  1) SAP fechado          → abre SAP Logon
            #  2) Sessão em timeout    → relogga via SSO
            #  3) Usuário usando SAP   → cria sessão paralela
            session = abrir_sap.obter_sessao_segura()

            abrir_zwm117(session)

            if diagnostico:
                diagnostico_tree(session)

            indicadores = ler_indicadores(session)

            print("\n" + "=" * 60)
            print("INDICADORES EXTRAÍDOS")
            print("=" * 60)
            print(f"  Sucesso   : {indicadores['sucesso']}")
            print(f"  Insucesso : {indicadores['insucesso']}")
            print(f"  Iniciadas : {indicadores['iniciadas']}")
            print("=" * 60 + "\n")

            return indicadores

        except Exception as e:
            ultimo_erro = e
            msg = str(e).lower()
            # Detecta erros típicos de sessão SAP expirada/zumbi:
            sinais_de_sessao_morta = [
                "object", "session", "control could not be found",
                "session is not active", "rpc",
                "connection", "remote procedure call failed",
                "the rpc server", "unspecified error"
            ]
            parece_sessao_morta = any(s in msg for s in sinais_de_sessao_morta)

            if tentativa < MAX_TENTATIVAS and parece_sessao_morta:
                print(f"\n[AVISO] Erro na tentativa {tentativa} — parece sessão SAP expirada.")
                print(f"        Erro: {e}")
                print(f"        Fechando conexões zumbi e tentando de novo...\n")
                # Força fechar todas as conexões abertas pra começar do zero
                try:
                    import win32com.client
                    sap_gui = win32com.client.GetObject("SAPGUI")
                    app = sap_gui.GetScriptingEngine
                    for i in range(app.Connections.Count - 1, -1, -1):
                        try:
                            app.Children(i).CloseConnection()
                        except Exception:
                            pass
                except Exception:
                    pass
                time.sleep(2.5)
                continue
            else:
                # Esgotou tentativas OU erro que não é de sessão — propaga
                raise

    # Se chegou aqui é porque todas falharam
    raise RuntimeError(
        f"Falha ao executar ZWM117 após {MAX_TENTATIVAS} tentativas. "
        f"Último erro: {ultimo_erro}"
    )


if __name__ == "__main__":
    # Use `python 02_executar_zwm117.py --diagnostico` na primeira
    # execução para inspecionar a estrutura do tree.
    diag = "--diagnostico" in sys.argv or "-d" in sys.argv
    executar(diagnostico=diag)
