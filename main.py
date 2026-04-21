"""
main.py — Orquestrador principal do AI Debate.

Pré-requisitos:
  1. Chrome aberto com CDP ativo → execute launch_chrome.py
  2. Esteja logado nas 4 IAs no Chrome
  3. ANTHROPIC_API_KEY configurada em config.py ou como variável de ambiente

Uso:
  python main.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

from config import (
    CDP_URL, AI_URLS, AI_ROLES, DEFAULT_ROUNDS,
    LOGS_DIR, ANTHROPIC_API_KEY,
)
from agents import send_message, wait_for_response_complete, get_last_response
from compiler import synthesize_round, generate_verdict

# ── Prompt builders ───────────────────────────────────────────────────────────

def _prompt_opening(topic: str, ai_name: str) -> str:
    return (
        f"Você está participando de um debate entre 4 IAs sobre o tema:\n\n"
        f"**{topic}**\n\n"
        f"Seu papel neste debate: {AI_ROLES[ai_name]}.\n\n"
        "Apresente sua posição inicial sobre o tema com base no seu papel. "
        "Seja direto, original e use sua perspectiva específica para trazer um ângulo único.\n"
        "Máximo 200 palavras."
    )

def _prompt_followup(topic: str, ai_name: str, synthesis: str, round_num: int) -> str:
    return (
        f"Debate em curso sobre: **{topic}**\n\n"
        f"Rodada {round_num}. Você é o {AI_ROLES[ai_name]}.\n\n"
        f"Síntese e pergunta provocativa do compilador:\n\n{synthesis}\n\n"
        "Responda à provocação acima. Aprofunde sua perspectiva e enfrente diretamente "
        "os argumentos contrários. Máximo 200 palavras."
    )

def _prompt_conclusion(topic: str, ai_name: str, synthesis: str) -> str:
    return (
        f"Conclusão do debate sobre: **{topic}**\n\n"
        f"Como {AI_ROLES[ai_name]}, esta é sua resposta final.\n\n"
        f"Síntese das rodadas anteriores:\n\n{synthesis}\n\n"
        "Apresente sua conclusão definitiva: o que você defende, onde concorda ou discorda "
        "das outras perspectivas, e qual é seu argumento mais forte. Máximo 250 palavras."
    )

# ── Markdown logger ───────────────────────────────────────────────────────────

class DebateLogger:
    def __init__(self, topic: str):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:40].strip()
        self.path: Path = LOGS_DIR / f"debate_{ts}_{safe}.md"
        self._lines: list[str] = []

        self._append(f"# Debate AI: {topic}\n")
        self._append(f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        self._append("---\n")
        self._append("## Participantes\n")
        for ai, role in AI_ROLES.items():
            self._append(f"- **{ai.upper()}**: {role}")
        self._append("\n---\n")
        self._flush()

    def _append(self, text: str):
        self._lines.append(text)

    def _flush(self):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self._lines))

    def log_round(self, label: str, responses: dict[str, str], synthesis: str = ""):
        self._append(f"\n## {label}\n")
        for ai, resp in responses.items():
            self._append(f"\n### {ai.upper()} — {AI_ROLES[ai]}\n")
            self._append(resp)
            self._append("")
        if synthesis:
            self._append("\n### Síntese Claude\n")
            self._append(synthesis)
            self._append("")
        self._flush()

    def log_verdict(self, verdict: str):
        self._append("\n---\n")
        self._append("## Veredicto Final (Claude)\n")
        self._append(verdict)
        self._append(f"\n---\n*Debate gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}*")
        self._flush()
        print(f"\n✓ Debate salvo em: {self.path}")

# ── Tab management ────────────────────────────────────────────────────────────

async def get_or_open_tab(context: BrowserContext, ai_name: str) -> Page:
    """Reutiliza aba existente do site ou abre uma nova."""
    url = AI_URLS[ai_name]
    domain = url.split("//")[1].split("/")[0].replace("www.", "")

    for page in context.pages:
        try:
            if domain in page.url:
                print(f"  ✓ [{ai_name}] aba encontrada → {page.url[:70]}")
                await page.bring_to_front()
                return page
        except Exception:
            continue

    print(f"  + [{ai_name}] abrindo nova aba → {url}")
    page = await context.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    return page

# ── Single-agent task ─────────────────────────────────────────────────────────

async def run_agent(page: Page, ai_name: str, prompt: str) -> str:
    """Envia prompt e coleta resposta de uma IA."""
    print(f"  → [{ai_name}] enviando prompt...")
    try:
        await send_message(page, ai_name, prompt)
        print(f"  ⏳ [{ai_name}] aguardando geração...")
        await wait_for_response_complete(page, ai_name)
        response = await get_last_response(page, ai_name)
        print(f"  ✓ [{ai_name}] {len(response)} chars coletados")
        return response
    except Exception as exc:
        print(f"  ✗ [{ai_name}] erro: {exc}")
        return f"[Erro em {ai_name}: {exc}]"

# ── Debate orchestrator ───────────────────────────────────────────────────────

async def run_debate(topic: str, num_rounds: int):
    print("O orquestrador iniciou com sucesso!")
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "SUA_CHAVE_AQUI":
        print("\n✗ Configure ANTHROPIC_API_KEY em config.py ou como variável de ambiente.")
        sys.exit(1)

    logger = DebateLogger(topic)
    history: list[dict] = []

    print(f"\n{'═'*60}")
    print(f"  DEBATE: {topic}")
    print(f"  Rodadas: {num_rounds} + 1 conclusão")
    print(f"{'═'*60}\n")

    async with async_playwright() as pw:
        print(f"Conectando ao Chrome via CDP ({CDP_URL})...")
        try:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            print(f"\n✗ Não foi possível conectar ao Chrome: {exc}")
            print("\nSolução: execute  python launch_chrome.py  antes de main.py")
            sys.exit(1)

        context = browser.contexts[0]

        # ── Prepara as 4 abas ─────────────────────────────────────────────
        print("\n[Preparando abas]\n")
        pages: dict[str, Page] = {}
        for ai in ["chatgpt", "deepseek", "gemini", "grok"]:
            pages[ai] = await get_or_open_tab(context, ai)
            await asyncio.sleep(1)

        synthesis = ""

        # ── Rodadas de debate ─────────────────────────────────────────────
        for rnd in range(1, num_rounds + 1):
            print(f"\n{'─'*50}")
            print(f"  RODADA {rnd}/{num_rounds}")
            print(f"{'─'*50}\n")

            prompts = (
                {ai: _prompt_opening(topic, ai) for ai in pages}
                if rnd == 1
                else {ai: _prompt_followup(topic, ai, synthesis, rnd) for ai in pages}
            )

            # Todas as IAs em paralelo
            results = await asyncio.gather(
                *[run_agent(pages[ai], ai, prompts[ai]) for ai in pages],
                return_exceptions=True,
            )
            responses = {
                ai: r if isinstance(r, str) else f"[Exceção: {r}]"
                for ai, r in zip(pages.keys(), results)
            }

            print(f"\n  [Claude] sintetizando rodada {rnd}...")
            synthesis = synthesize_round(topic, rnd, responses)
            print(f"  ✓ síntese: {synthesis[:120]}...")

            label = f"Rodada {rnd}"
            logger.log_round(label, responses, synthesis)
            history.append({"round": rnd, "responses": responses, "synthesis": synthesis})

        # ── Rodada de conclusão ───────────────────────────────────────────
        print(f"\n{'─'*50}")
        print(f"  RODADA FINAL: Conclusões")
        print(f"{'─'*50}\n")

        conclusion_prompts = {ai: _prompt_conclusion(topic, ai, synthesis) for ai in pages}
        results = await asyncio.gather(
            *[run_agent(pages[ai], ai, conclusion_prompts[ai]) for ai in pages],
            return_exceptions=True,
        )
        conclusions = {
            ai: r if isinstance(r, str) else f"[Exceção: {r}]"
            for ai, r in zip(pages.keys(), results)
        }

        logger.log_round("Rodada Final — Conclusões", conclusions)
        history.append({"round": "conclusao", "responses": conclusions, "synthesis": ""})

        # ── Veredicto final ───────────────────────────────────────────────
        print(f"\n  [Claude] gerando veredicto final...")
        verdict = generate_verdict(topic, history)

        print(f"\n{'═'*60}")
        print("  VEREDICTO FINAL")
        print(f"{'═'*60}\n")
        print(verdict)

        logger.log_verdict(verdict)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║    AI DEBATE ORCHESTRATOR  v1.0          ║")
    print("╚══════════════════════════════════════════╝\n")

    topic = input("📌 Tema do debate: ").strip()
    if not topic:
        topic = "O impacto da IA na criatividade humana"
        print(f"   (usando tema padrão: {topic})")

    rounds_raw = input(f"🔢 Número de rodadas [padrão {DEFAULT_ROUNDS}]: ").strip()
    try:
        num_rounds = int(rounds_raw) if rounds_raw else DEFAULT_ROUNDS
        num_rounds = max(1, min(num_rounds, 10))
    except ValueError:
        num_rounds = DEFAULT_ROUNDS

    asyncio.run(run_debate(topic, num_rounds))

if __name__ == "__main__":
    main()
