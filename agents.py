"""
agents.py — Controle Playwright por site de IA.

Desafios técnicos por site:
- ChatGPT : input é div[contenteditable], não <textarea>; detecção anti-bot requer type() lento
- DeepSeek: textarea normal, mas seletores mudam com deploys frequentes
- Gemini  : componente web customizado (rich-textarea), requer clique antes de digitar
- Grok    : textarea padrão, mas sem stop-button detectável — usa heurística de texto estável
"""

import asyncio
from typing import Optional
from playwright.async_api import Page

from config import RESPONSE_TIMEOUT_SEC, GENERATION_START_TIMEOUT

# ── Seletores primários ───────────────────────────────────────────────────────

SELECTORS = {
    "chatgpt": {
        "input":    '#prompt-textarea',
        "submit":   'button[data-testid="send-button"]',
        "stop":     'button[data-testid="stop-button"]',
        "response": '[data-message-author-role="assistant"] .markdown',
    },
    "deepseek": {
        "input":    '#chat-input',
        "submit":   'button[aria-label="Send"]',
        "stop":     'button[aria-label="Stop"]',
        "response": ".ds-markdown",
    },
    "gemini": {
        "input":    'div.ql-editor[contenteditable="true"]',
        "submit":   'button.send-button',
        "stop":     'button[aria-label="Stop response"]',
        "response": ".model-response-text",
    },
    "grok": {
        "input":    'textarea',
        "submit":   'button[type="submit"]',
        "stop":     None,  # Grok não tem stop-button detectável — usa heurística
        "response": '[data-testid="message-bubble"]',
    },
}

# ── Seletores alternativos (fallback quando o primário falha) ─────────────────

FALLBACKS = {
    "chatgpt": {
        "input":    'div[contenteditable="true"][data-placeholder]',
        "submit":   'button[aria-label*="Send"], button[aria-label*="Enviar"]',
        "response": 'article[data-testid*="conversation-turn"]:last-of-type .markdown, '
                    'article[data-testid*="conversation-turn"]:last-of-type .prose',
    },
    "deepseek": {
        "input":    'textarea[placeholder]',
        "submit":   '.send-button, button[class*="send"]',
        "response": '.message-content:last-child, .ds-markdown:last-child',
    },
    "gemini": {
        "input":    'rich-textarea div[contenteditable], .ql-editor',
        "submit":   'button[aria-label*="Send"], button[aria-label*="Enviar"]',
        "response": 'response-container-content, .response-content, model-response',
    },
    "grok": {
        "input":    'div[contenteditable="true"], [role="textbox"]',
        "submit":   'button[class*="send"], button[class*="submit"]',
        "response": '[class*="message"]:last-child [class*="content"], '
                    '[class*="MessageBubble"]:last-child',
    },
}

# ── IAs que usam contenteditable (requer type() em vez de fill()) ─────────────
CONTENTEDITABLE_AIS = {"chatgpt", "gemini"}

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _visible_locator(page: Page, *selectors: str, timeout: int = 8000):
    """Tenta cada seletor em ordem; retorna o primeiro visível ou None."""
    for sel in selectors:
        if not sel:
            continue
        try:
            loc = page.locator(sel).last
            await loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    return None


async def _count_responses(page: Page, ai_name: str) -> int:
    """Conta quantas respostas do assistente existem na página."""
    sel = SELECTORS[ai_name]["response"]
    fb  = FALLBACKS.get(ai_name, {}).get("response", "")
    for s in [sel, fb]:
        if not s:
            continue
        try:
            return await page.locator(s).count()
        except Exception:
            continue
    return 0

# ── send_message ──────────────────────────────────────────────────────────────

async def send_message(page: Page, ai_name: str, text: str) -> None:
    """
    Digita o texto no campo de entrada e clica em Enviar.
    ChatGPT e Gemini usam contenteditable → type() com delay para evitar detecção.
    """
    sel = SELECTORS[ai_name]
    fb  = FALLBACKS.get(ai_name, {})

    # Localiza o input
    inp = await _visible_locator(
        page,
        sel["input"],
        fb.get("input", ""),
        timeout=12000,
    )
    if inp is None:
        raise RuntimeError(f"[{ai_name}] Campo de input não encontrado. "
                           "Verifique se está logado e a página está carregada.")

    await inp.click()
    await asyncio.sleep(0.4)

    # Limpa o campo
    await page.keyboard.press("Control+a")
    await asyncio.sleep(0.15)
    await page.keyboard.press("Delete")
    await asyncio.sleep(0.2)

    # Digita o texto
    if ai_name in CONTENTEDITABLE_AIS:
        # Digitação humana simulada — reduz chance de bloqueio no ChatGPT
        await inp.type(text, delay=12)
    else:
        await inp.fill(text)

    await asyncio.sleep(0.5)

    # Localiza e clica no botão de envio
    submit_btn = await _visible_locator(
        page,
        sel["submit"],
        fb.get("submit", ""),
        timeout=5000,
    )
    if submit_btn:
        await submit_btn.click()
    else:
        # Fallback: Enter funciona na maioria dos sites
        await inp.press("Enter")

    await asyncio.sleep(0.5)

# ── wait_for_response_complete ────────────────────────────────────────────────

async def wait_for_response_complete(page: Page, ai_name: str) -> bool:
    """
    Aguarda a IA terminar de gerar a resposta.

    Estratégia por site:
    - ChatGPT / DeepSeek / Gemini: espera stop-button aparecer, depois desaparecer
    - Grok: não tem stop-button — usa heurística: espera texto parar de crescer
    """
    stop_sel = SELECTORS[ai_name].get("stop")

    if stop_sel:
        # ① Aguarda geração começar (stop-button aparece)
        try:
            await page.wait_for_selector(
                stop_sel, state="visible",
                timeout=GENERATION_START_TIMEOUT * 1000
            )
        except Exception:
            # Se não apareceu, a geração pode ter sido instantânea — continua
            pass

        # ② Aguarda geração terminar (stop-button some)
        try:
            await page.wait_for_selector(
                stop_sel, state="hidden",
                timeout=RESPONSE_TIMEOUT_SEC * 1000
            )
            await asyncio.sleep(0.8)  # aguarda DOM estabilizar
            return True
        except Exception:
            print(f"  ⚠ [{ai_name}] Timeout aguardando fim da geração.")
            return False

    else:
        # ── Heurística para Grok ──────────────────────────────────────────
        resp_sel = SELECTORS[ai_name]["response"]
        last_text = ""
        stable_count = 0
        start = asyncio.get_event_loop().time()

        # Aguarda texto aparecer primeiro
        await asyncio.sleep(3)

        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > RESPONSE_TIMEOUT_SEC:
                return False

            try:
                elements = page.locator(resp_sel)
                count = await elements.count()
                if count > 0:
                    current_text = await elements.last.inner_text()
                    if current_text == last_text and len(current_text) > 30:
                        stable_count += 1
                        if stable_count >= 3:  # estável por 3 ciclos (~4.5s)
                            return True
                    else:
                        stable_count = 0
                    last_text = current_text
            except Exception:
                pass

            await asyncio.sleep(1.5)

# ── get_last_response ─────────────────────────────────────────────────────────

async def get_last_response(page: Page, ai_name: str) -> str:
    """
    Extrai o texto da última resposta do assistente.
    Tenta seletores primário e fallback; como último recurso varre o main.
    """
    sel = SELECTORS[ai_name]["response"]
    fb  = FALLBACKS.get(ai_name, {}).get("response", "")

    await asyncio.sleep(0.6)  # DOM settle

    for selector in [s for s in [sel, fb] if s]:
        try:
            elements = page.locator(selector)
            count = await elements.count()
            if count > 0:
                text = await elements.last.inner_text()
                text = text.strip()
                if len(text) > 20:
                    return text
        except Exception:
            continue

    # Último recurso: tenta extrair do contexto geral da página
    for generic in ["main", "[role='main']", "#__next main", "body"]:
        try:
            el = page.locator(generic)
            if await el.count() > 0:
                full = await el.last.inner_text()
                lines = [ln.strip() for ln in full.splitlines() if len(ln.strip()) > 60]
                if lines:
                    # Pega as últimas linhas substanciais como aproximação da resposta
                    return "\n".join(lines[-15:])
        except Exception:
            continue

    return "[Erro: resposta não pôde ser extraída — verifique os seletores]"
