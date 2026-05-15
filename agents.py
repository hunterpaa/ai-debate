"""
agents.py — Controle Playwright por site de IA.

IAs ativas: ChatGPT, DeepSeek, Gemini, Perplexity, Qwen, Mistral, Grok.
Grok: abstenções marcadas explicitamente no log para auditoria histórica.
"""

import asyncio
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
        "input":    'textarea',
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
    "perplexity": {
        "input":    'textarea[placeholder]',
        "submit":   'button[aria-label="Submit"]',
        "stop":     'button[aria-label="Stop"]',
        "response": ".prose",
    },
    "qwen": {
        "input":    'textarea',
        "submit":   'button[type="submit"]',
        "stop":     'button[aria-label="Stop"]',
        "response": ".markdown",
    },
    "mistral": {
        "input":    'textarea',
        "submit":   'button[type="submit"]',
        "stop":     'button[aria-label="Stop"]',
        "response": ".message-content",
    },
    "grok": {
        "input":    'textarea',
        "submit":   'button[type="submit"]',
        "stop":     'button[aria-label="Stop"]',
        "response": ".message-bubble",
    },
}

# ── Seletores alternativos (fallback) ─────────────────────────────────────────

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
    "perplexity": {
        "input":    '#ask-input, textarea',
        "submit":   'button[aria-label*="Submit"], button[type="submit"]',
        "response": '.answer-content, [data-testid*="answer"], .prose:last-child',
    },
    "qwen": {
        "input":    '#chat-input, #messageInput, textarea[placeholder]',
        "submit":   '.send-btn, button[class*="send"], button[aria-label*="Send"]',
        "response": '.markdown-body, .message-content:last-child, .chat-message:last-child',
    },
    "mistral": {
        "input":    'div[contenteditable="true"], textarea[placeholder]',
        "submit":   'button[aria-label*="Send"], button[aria-label*="Enviar"]',
        "response": '.message:last-child, .response:last-child, article:last-child',
    },
    "grok": {
        "input":    'textarea[placeholder], div[contenteditable="true"]',
        "submit":   'button[aria-label*="Send"], button[aria-label*="Submit"]',
        "response": '.message:last-child, [class*="message"]:last-child, [class*="response"]:last-child',
    },
}

# Timeouts de interação (ms)
FILL_TIMEOUT   = 60_000   # fill() — texto longo leva tempo em UIs lentas
CLICK_TIMEOUT  = 10_000   # click() após botão habilitado
ENABLED_WAIT   = 15_000   # espera botão ficar enabled
INPUT_VISIBLE  = 12_000   # espera input aparecer

# Limite de caracteres por IA — sites com restrição de input
# Valores ajustados para realismo: testes via Playwright mostram que ChatGPT/Gemini/DeepSeek
# aceitam prompts bem maiores via JS-injection (mode contenteditable). Perplexity continua
# 3k porque é restrição real do site (input curto de busca).
MAX_PROMPT_CHARS = {
    "perplexity": 3_000,   # restrição real do site (UI estilo busca)
    "grok":       8_000,   # estabilidade de UI (histórico de problemas com texto longo)
    "mistral":   12_000,
    "qwen":     12_000,
    "chatgpt":  24_000,
    "deepseek": 24_000,
    "gemini":   30_000,
}

# IAs que enviam com Enter em vez de botão (UI de busca/search-style)
ENTER_TO_SUBMIT = {"perplexity", "grok"}

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

# ── send_message ──────────────────────────────────────────────────────────────

async def send_message(page: Page, ai_name: str, text: str) -> None:
    """
    Insere o texto e envia.

    Todos os sites usam fill() — mais rápido que type() e não causa timeout
    com textos longos. ChatGPT/Gemini (contenteditable) recebem um clique
    + Ctrl+A antes para garantir foco e limpeza.
    """
    # Trunca texto para o limite da IA (prompts com codebase podem ser imensos)
    max_chars = MAX_PROMPT_CHARS.get(ai_name)
    if max_chars and len(text) > max_chars:
        text = text[:max_chars - 100] + "\n\n[...truncado por limite de caracteres]"

    sel = SELECTORS[ai_name]
    fb  = FALLBACKS.get(ai_name, {})

    # ── Localiza input ────────────────────────────────────────────────────
    inp = await _visible_locator(
        page, sel["input"], fb.get("input", ""),
        timeout=INPUT_VISIBLE,
    )
    if inp is None:
        raise RuntimeError(
            f"[{ai_name}] Campo de input não encontrado. "
            "Verifique se está logado e a página está carregada."
        )

    # ── Foca e limpa ──────────────────────────────────────────────────────
    await inp.click()
    await asyncio.sleep(0.3)
    await page.keyboard.press("Control+a")
    await asyncio.sleep(0.1)
    await page.keyboard.press("Delete")
    await asyncio.sleep(0.2)

    # ── Insere texto e envia ──────────────────────────────────────────────
    if ai_name == "deepseek":
        # DeepSeek usa React — fill() não aciona o state manager.
        # Solução: setar valor via native setter do React + disparar eventos + Enter.
        await page.evaluate(
            """(text) => {
                const el = document.querySelector('textarea');
                if (!el) return;
                el.focus();
                const setter = Object.getOwnPropertyDescriptor(
                    HTMLTextAreaElement.prototype, 'value'
                ).set;
                setter.call(el, text);
                el.dispatchEvent(new Event('input',  {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }""",
            text,
        )
        await asyncio.sleep(0.5)
        # Tenta botões de envio em ordem; Enter só como último recurso
        for _ds_sel in ['button[aria-label="Send"]', 'div[role="button"][aria-label="Send"]', 'button:has(svg)[class*="send"]']:
            try:
                _btn = page.locator(_ds_sel).last
                if await _btn.count() > 0 and await _btn.is_visible():
                    await _btn.click()
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                pass
            await asyncio.sleep(0.3)
        await inp.press("Enter")
        return  # encerra aqui — não precisa do bloco de botão abaixo

    # Perplexity/Grok: UI estilo busca — Enter é o método primário
    if ai_name in ENTER_TO_SUBMIT:
        await inp.fill(text, timeout=FILL_TIMEOUT)
        await asyncio.sleep(0.5)
        await inp.press("Enter")
        await asyncio.sleep(0.5)
        return

    # ChatGPT: contenteditable — usa JS para textos longos (fill falha acima de ~8k chars)
    if ai_name == "chatgpt" and len(text) > 4_000:
        await page.evaluate(
            """(text) => {
                const el = document.querySelector('#prompt-textarea p') ||
                           document.querySelector('#prompt-textarea') ||
                           document.querySelector('div[contenteditable="true"]');
                if (!el) return;
                el.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, text);
            }""",
            text,
        )
        await asyncio.sleep(0.6)
        submit_btn = await _visible_locator(
            page, 'button[data-testid="send-button"]',
            'button[aria-label*="Send"]', timeout=INPUT_VISIBLE,
        )
        if submit_btn:
            await submit_btn.click(timeout=CLICK_TIMEOUT)
        else:
            await page.keyboard.press("Enter")
        await asyncio.sleep(0.5)
        return

    await inp.fill(text, timeout=FILL_TIMEOUT)
    await asyncio.sleep(0.4)

    # ── Clica no botão de envio ───────────────────────────────────────────
    submit_sel = sel["submit"]
    submit_btn = await _visible_locator(
        page, submit_sel, FALLBACKS.get(ai_name, {}).get("submit", ""),
        timeout=INPUT_VISIBLE,
    )
    if submit_btn:
        try:
            is_enabled = await submit_btn.is_enabled()
            if not is_enabled:
                await asyncio.sleep(1)
            await submit_btn.click(timeout=CLICK_TIMEOUT)
        except Exception:
            await inp.press("Enter")
    else:
        await inp.press("Enter")

    await asyncio.sleep(0.5)

# ── wait_for_response_complete ────────────────────────────────────────────────

async def wait_for_response_complete(page: Page, ai_name: str) -> bool:
    """
    Aguarda a IA terminar de gerar.
    Estratégia: espera stop-button aparecer (geração iniciou) depois sumir (terminou).
    """
    stop_sel = SELECTORS[ai_name].get("stop")
    if not stop_sel:
        return True  # sem stop-button: assume concluído (não deve ocorrer com 3 IAs ativas)

    # ① Aguarda geração começar
    try:
        await page.wait_for_selector(
            stop_sel, state="visible",
            timeout=GENERATION_START_TIMEOUT * 1000,
        )
    except Exception:
        pass  # pode ter sido instantâneo

    # ② Aguarda geração terminar
    try:
        await page.wait_for_selector(
            stop_sel, state="hidden",
            timeout=RESPONSE_TIMEOUT_SEC * 1000,
        )
        await asyncio.sleep(0.8)
        return True
    except Exception:
        print(f"  ⚠ [{ai_name}] Timeout aguardando fim da geração — coletando o que há.")
        return False

# ── get_last_response ─────────────────────────────────────────────────────────

async def get_last_response(page: Page, ai_name: str) -> str:
    """Extrai o texto da última resposta do assistente."""
    sel = SELECTORS[ai_name]["response"]
    fb  = FALLBACKS.get(ai_name, {}).get("response", "")

    await asyncio.sleep(0.6)

    for selector in [s for s in [sel, fb] if s]:
        try:
            elements = page.locator(selector)
            if await elements.count() > 0:
                text = (await elements.last.inner_text()).strip()
                if len(text) > 20:
                    return text
        except Exception:
            continue

    # Fallback genérico
    for generic in ["main", "[role='main']", "#__next main", "body"]:
        try:
            el = page.locator(generic)
            if await el.count() > 0:
                full = await el.last.inner_text()
                lines = [ln.strip() for ln in full.splitlines() if len(ln.strip()) > 60]
                if lines:
                    return "\n".join(lines[-15:])
        except Exception:
            continue

    return "[Erro: resposta não pôde ser extraída]"
