# OM_POR_HORA — Automação ZWM117 SAP

Automação Python para extração periódica de dados da transação **ZWM117** do SAP e envio consolidado via WhatsApp Web.

## Objetivo

Automatizar a coleta de indicadores de montagem (Sucesso, Insucesso, Iniciadas) executada de hora em hora e enviar dashboards visuais para grupos do WhatsApp, eliminando a coleta manual e garantindo padronização dos dados.

## Sistemas de Automação

O projeto contém **3 automações independentes**, uma pra cada Centro de Trabalho:

| Sistema | Centro | Horários | Grupos WhatsApp |
|---------|--------|----------|-----------------|
| **OM POR HORA** (`main.py`) | 0005 | 09:30, 10:30, 11:30, 13:30, 14:30, 15:30, 16:30, 17:30 | Montagem Externa Bemol + LogRev - Montagem - Adms |
| **BV** (`BV.PY`) | 0077 | 09:25, 10:25, 11:25, 13:25, 14:25, 15:25, 16:25, 17:25 | CD Boa Vista - Montagem |
| **PVH** (`PVH.PY`) | 0016 | 09:35, 10:35, 11:35, 13:35, 14:35, 15:35, 16:35, 17:35 | Montagens_CD PVH |

## Fluxo (por parcial)

1. **Abrir SAP** — `01_abrir_sap.py` conecta ao SAP GUI (com auto-detect de sessão zumbi/timeout)
2. **Executar ZWM117** — `02_executar_zwm117.py` navega até a transação e extrai indicadores
3. **Gravar histórico** — `03_gravar_historico.py` salva no JSON local do dia
4. **Gerar dashboards** — `04_gerar_card.py` renderiza HTML→JPG via Chrome headless
5. **Enviar WhatsApp** — `05_enviar_whatsapp.py` envia via Selenium com paste em clipboard (evita virar sticker)

## Tecnologias

- **Python 3.12**
- **SAP GUI Scripting** via `win32com`
- **Selenium** + **Chrome headless** para renderização HTML→imagem
- **Selenium** com perfil persistente para WhatsApp Web
- **PIL/Pillow** para conversão PNG→JPG
- **Windows Task Scheduler** para agendamento

## Instalação

```powershell
# Instala todas as dependências Python
.\instalar_dependencias.bat

# Agenda as tarefas no Windows Task Scheduler
.\agendar_tarefas.bat                                    # OM POR HORA
.\PVH-RBR-BV-\ AUTOMAÇÃO\agendar_bv.bat                  # BV
.\PVH-RBR-BV-\ AUTOMAÇÃO\agendar_pvh.bat                 # PVH

# Primeiro uso do WhatsApp (escanear QR code)
python 05_enviar_whatsapp.py --primeiro-uso
```

## Uso manual

```powershell
# Forçar uma parcial específica (1-8)
python main.py --parcial 3

# Só gerar dashboards, sem enviar
python main.py --parcial 3 --skip-whatsapp

# Só enviar pro grupo Montagem (pular Admin)
python main.py --parcial 3 --so-montagem
```

## Estrutura de arquivos

```
OM_POR_HORA/
├── 01_abrir_sap.py               # Abertura SAP + auto-reconnect
├── 02_executar_zwm117.py         # Executa ZWM117 com retry
├── 03_gravar_historico.py        # Grava JSON do dia (Seg-Sex + Sábado)
├── 04_gerar_card.py              # HTML→JPG via Chrome
├── 05_enviar_whatsapp.py         # WhatsApp via Selenium (clipboard paste)
├── main.py                       # Orquestrador OM POR HORA
├── templates/
│   ├── montagem_externa.html
│   └── administrativo.html
├── agendar_tarefas.bat           # Cria as 8 tarefas no Task Scheduler
├── desagendar_tarefas.bat        # Remove as 8 tarefas
├── instalar_dependencias.bat     # pip install requirements
├── bemol.png                     # Logo BEMOL
└── PVH-RBR-BV- AUTOMAÇÃO/        # Automações paralelas (BV e PVH)
    ├── BV.PY                     # Orquestrador BV
    ├── PVH.PY                    # Orquestrador PVH
    ├── agendar_bv.bat
    ├── agendar_pvh.bat
    └── templates/
```

## Diferenciação por dia da semana

Metas configuráveis por dia da semana em `03_gravar_historico.py`:
- **Segunda a Sexta:** meta total = 300
- **Sábado:** meta total = 300 (mesma progressão)

## Autor

**Sidney Albuquerque** — BEMOL S/A

## Licença

Uso interno BEMOL — projeto proprietário.
