"""
==============================================================
DIAGNÓSTICO — WhatsApp Web visível
USO:
    python diagnostico_whatsapp.py

DESCRIÇÃO:
    Abre o Chrome do robô VISÍVEL (não esconde) e imprime tudo
    o que ele consegue ver na tela: estado do login, todos os
    elementos contenteditable, posição da caixa de busca, etc.

    Use isso para entender por que o envio normal está falhando.
==============================================================
"""

import sys
import time
import importlib.util
from pathlib import Path

HERE = Path(__file__).parent

# Reaproveita as funções do 05_enviar_whatsapp.py
spec = importlib.util.spec_from_file_location("wpp", HERE / "05_enviar_whatsapp.py")
wpp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wpp)


def diagnosticar():
    print("=" * 60)
    print("DIAGNÓSTICO — WhatsApp Web visível")
    print("=" * 60)
    print()

    # Abre o Chrome VISÍVEL (não esconde)
    driver = wpp._criar_driver(visivel=True)

    try:
        driver.get("https://web.whatsapp.com")
        print("[INFO] WhatsApp Web carregando...")
        print("[INFO] Aguardando login (até 60s)...")

        # Espera login
        inicio = time.time()
        while time.time() - inicio < 60:
            if wpp._esta_logado(driver):
                print("[OK] Logado!")
                break
            if wpp._detectar_qr_code(driver):
                print("[INFO] QR code visível. Escaneie agora.")
            time.sleep(2)
        else:
            print("[ERRO] Timeout aguardando login.")

        time.sleep(3)  # Espera UI estabilizar

        print("\n" + "=" * 60)
        print("INSPEÇÃO DA PÁGINA")
        print("=" * 60)

        # Imprime o título
        print(f"\nTítulo da página: {driver.title}")
        print(f"URL atual: {driver.current_url}")

        # Busca TUDO que pode ser um input no WhatsApp Business
        print("\n--- TODOS os elementos potencialmente de busca/input ---")
        info = driver.execute_script("""
            const out = [];
            // Seletores de tudo que pode receber texto
            const seletores = [
                'div[contenteditable="true"]',
                'input',
                'textarea',
                '[role="textbox"]',
                '[role="searchbox"]',
                '[role="combobox"]',
                '[contenteditable]',
                '[aria-placeholder]',
                '[data-lexical-editor]',
                '[data-testid*="search"]',
                '[data-testid*="chat-list-search"]',
            ];

            const vistos = new Set();
            for (const sel of seletores) {
                try {
                    const els = document.querySelectorAll(sel);
                    for (const el of els) {
                        if (vistos.has(el)) continue;
                        vistos.add(el);
                        const r = el.getBoundingClientRect();
                        if (el.offsetParent === null) continue;  // só visíveis
                        if (r.width < 20 || r.height < 10) continue;
                        out.push({
                            tag: el.tagName.toLowerCase(),
                            largura: Math.round(r.width),
                            altura: Math.round(r.height),
                            top: Math.round(r.top),
                            left: Math.round(r.left),
                            contenteditable: el.getAttribute('contenteditable') || '',
                            placeholder: el.getAttribute('placeholder') || el.getAttribute('aria-placeholder') || '',
                            aria_label: el.getAttribute('aria-label') || '',
                            role: el.getAttribute('role') || '',
                            data_tab: el.getAttribute('data-tab') || '',
                            data_testid: el.getAttribute('data-testid') || '',
                            data_lexical: el.getAttribute('data-lexical-editor') || '',
                            title: el.getAttribute('title') || '',
                            type: el.getAttribute('type') || '',
                            seletor_match: sel,
                        });
                    }
                } catch (e) {}
            }
            return out;
        """)
        if not info:
            print("  NENHUM elemento de input encontrado!")
        for i, x in enumerate(info):
            print(f"\n  [{i}] <{x['tag']}>  {x['largura']}x{x['altura']} @ ({x['left']}, {x['top']})")
            print(f"      matched seletor:  {x.get('seletor_match','')}")
            if x.get("contenteditable"): print(f"      contenteditable:  {x['contenteditable']}")
            if x.get("placeholder"):    print(f"      placeholder:      {x['placeholder']}")
            if x.get("aria_label"):     print(f"      aria-label:       {x['aria_label']}")
            if x.get("role"):           print(f"      role:             {x['role']}")
            if x.get("data_tab"):       print(f"      data-tab:         {x['data_tab']}")
            if x.get("data_testid"):    print(f"      data-testid:      {x['data_testid']}")
            if x.get("data_lexical"):   print(f"      data-lexical:     {x['data_lexical']}")
            if x.get("title"):          print(f"      title:            {x['title']}")
            if x.get("type"):           print(f"      type:             {x['type']}")

        # Procura especificamente algo com "Pesquisar" no texto/placeholder
        print("\n--- Elementos relacionados a PESQUISA ---")
        pesquisa = driver.execute_script("""
            const out = [];
            // Procura por texto "Pesquisar" ou "Search"
            const todos = document.querySelectorAll('*');
            for (const el of todos) {
                if (el.offsetParent === null) continue;
                const t = el.innerText || '';
                const al = el.getAttribute('aria-label') || '';
                const ap = el.getAttribute('aria-placeholder') || '';
                const p = el.getAttribute('placeholder') || '';
                const ti = el.getAttribute('title') || '';
                const tudo = (t + ' ' + al + ' ' + ap + ' ' + p + ' ' + ti).toLowerCase();
                if (tudo.includes('pesquisar') || tudo.includes('search')) {
                    const r = el.getBoundingClientRect();
                    if (r.width < 30 || r.height < 15) continue;
                    out.push({
                        tag: el.tagName.toLowerCase(),
                        largura: Math.round(r.width),
                        altura: Math.round(r.height),
                        top: Math.round(r.top),
                        left: Math.round(r.left),
                        aria_label: al,
                        aria_placeholder: ap,
                        placeholder: p,
                        title: ti,
                        text_curto: t.substring(0, 50),
                        outer: el.outerHTML.substring(0, 200),
                    });
                    if (out.length >= 10) break;
                }
            }
            return out;
        """)
        if not pesquisa:
            print("  NENHUM elemento com 'pesquisar' encontrado!")
        for i, x in enumerate(pesquisa):
            print(f"\n  [{i}] <{x['tag']}>  {x['largura']}x{x['altura']} @ ({x['left']}, {x['top']})")
            if x.get("aria_label"):      print(f"      aria-label:       {x['aria_label']}")
            if x.get("aria_placeholder"):print(f"      aria-placeholder: {x['aria_placeholder']}")
            if x.get("placeholder"):     print(f"      placeholder:      {x['placeholder']}")
            if x.get("text_curto"):      print(f"      texto:            {x['text_curto']}")
            print(f"      outerHTML[:200]:  {x['outer']}")

        # Salva print da tela
        png = HERE / "diagnostico_tela.png"
        driver.save_screenshot(str(png))
        print(f"\n[OK] Screenshot completo salvo em: {png}")

        # Salva HTML pra inspeção
        html_path = HERE / "diagnostico_pagina.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"[OK] HTML completo salvo em: {html_path}")

        print("\n" + "=" * 60)
        print("Pressione ENTER aqui no terminal quando quiser fechar o Chrome.")
        print("(Você pode interagir com o WhatsApp Web normalmente antes.)")
        print("=" * 60)
        input()

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    diagnosticar()
