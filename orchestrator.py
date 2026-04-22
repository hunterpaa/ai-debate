"""
orchestrator.py — Orquestração do debate, desacoplada do modo de execução.

Padrão de emissão:
  emit=None      → imprime no terminal
  emit=callable  → chama emit(event_dict) para WebSocket/SSE
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, BrowserContext, Page

from config import CDP_URL, AI_URLS, LOGS_DIR
from agents import send_message, wait_for_response_complete, get_last_response
from compiler import synthesize_round, generate_verdict, extract_decision
from modes import Mode, DEFAULT_MODE, MANDATORY_RULES

_AIS = ["chatgpt", "deepseek", "gemini", "grok"]

# ── Emit helper ───────────────────────────────────────────────────────────────

def _emit(emit_fn, event: dict) -> None:
    if emit_fn is not None:
        emit_fn(event)
    else:
        msg = event.get("message") or ""
        if not msg and event.get("type") == "synthesis":
            msg = f"[síntese rodada {event.get('round')}] {str(event.get('content', ''))[:100]}..."
        elif not msg and event.get("type") == "verdict":
            msg = "[veredicto gerado]"
        elif not msg and event.get("type") == "decision_extracted":
            d = event.get("data", {})
            msg = f"[decisão] {d.get('decisao', '')}"
        if msg:
            print(f"  {msg}")

# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    tmpl: str,
    topic: str,
    ai_name: str,
    mode: Mode,
    synthesis: str = "",
    round_num: int = 1,
) -> str:
    return tmpl.format(
        topic=topic,
        ai_role=mode.ai_roles.get(ai_name, ai_name),
        synthesis=synthesis,
        round_num=round_num,
        mandatory_rules=MANDATORY_RULES,
    )

# ── Logger ────────────────────────────────────────────────────────────────────

class DebateLogger:
    def __init__(self, topic: str, mode_name: str, ai_roles: dict):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:40].strip()
        self.path: Path = LOGS_DIR / f"debate_{ts}_{safe}.md"
        self._lines: list[str] = []
        self._ai_roles = ai_roles

        self._append(f"# Debate AI: {topic}\n")
        self._append(f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  **Modo:** {mode_name}\n")
        self._append("---\n")
        self._append("## Participantes\n")
        for ai, role in ai_roles.items():
            self._append(f"- **{ai.upper()}**: {role}")
        self._append("\n---\n")
        self._flush()

    def _append(self, text: str) -> None:
        self._lines.append(text)

    def _flush(self) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(self._lines))

    def log_round(self, label: str, responses: dict[str, str], synthesis: str = "") -> None:
        self._append(f"\n## {label}\n")
        for ai, resp in responses.items():
            self._append(f"\n### {ai.upper()} — {self._ai_roles.get(ai, ai)}\n")
            self._append(resp)
            self._append("")
        if synthesis:
            self._append("\n### Síntese Claude\n")
            self._append(synthesis)
            self._append("")
        self._flush()

    def log_verdict(self, verdict: str) -> None:
        self._append("\n---\n")
        self._append("## Veredicto Final (Claude)\n")
        self._append(verdict)
        self._append(f"\n---\n*Debate gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}*")
        self._flush()
        print(f"\n✓ Debate salvo em: {self.path}")

# ── Tab management ────────────────────────────────────────────────────────────

async def _get_or_open_tab(context: BrowserContext, ai_name: str) -> Page:
    url = AI_URLS[ai_name]
    domain = url.split("//")[1].split("/")[0].replace("www.", "")

    for page in context.pages:
        try:
            if domain in page.url:
                await page.bring_to_front()
                return page
        except Exception:
            continue

    page = await context.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(3)
    return page

# ── Single-agent task ─────────────────────────────────────────────────────────

async def _run_agent(page: Page, ai_name: str, prompt: str, emit_fn) -> str:
    _emit(emit_fn, {"type": "status", "message": f"[{ai_name}] enviando prompt..."})
    try:
        await send_message(page, ai_name, prompt)
        _emit(emit_fn, {"type": "status", "message": f"[{ai_name}] aguardando geração..."})
        await wait_for_response_complete(page, ai_name)
        response = await get_last_response(page, ai_name)
        _emit(emit_fn, {
            "type": "agent_response",
            "agent": ai_name,
            "chars": len(response),
            "message": f"[{ai_name}] {len(response)} chars coletados",
        })
        return response
    except Exception as exc:
        _emit(emit_fn, {"type": "error", "agent": ai_name, "message": f"[{ai_name}] erro: {exc}"})
        return f"[Erro em {ai_name}: {exc}]"

# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run_debate(
    topic: str,
    num_rounds: int,
    mode: Mode = DEFAULT_MODE,
    quick: bool = False,
    emit=None,
) -> dict:
    """
    Executa o debate completo.

    Args:
        topic:      Tema do debate.
        num_rounds: Número de rodadas (forçado para 1 se quick=True).
        mode:       Modo de debate (instância de Mode).
        quick:      Se True, 1 rodada + veredicto direto sem conclusão.
        emit:       Callback de eventos. None → terminal, callable → WebSocket/SSE.

    Returns:
        Dict com topic, mode, verdict, decision, history.
    """
    if quick:
        num_rounds = 1

    _emit(emit, {
        "type": "debate_start",
        "topic": topic,
        "mode": mode.name,
        "num_rounds": num_rounds,
        "quick": quick,
        "message": f"Iniciando debate — modo: {mode.name} | rodadas: {num_rounds}{' | QUICK' if quick else ''}",
    })

    history: list[dict] = []
    synthesis = ""

    async with async_playwright() as pw:
        _emit(emit, {"type": "status", "message": f"Conectando ao Chrome via CDP ({CDP_URL})..."})
        try:
            browser = await pw.chromium.connect_over_cdp(CDP_URL)
        except Exception as exc:
            _emit(emit, {"type": "error", "message": f"Falha ao conectar Chrome: {exc}"})
            raise

        context = browser.contexts[0]
        logger = DebateLogger(topic, mode.name, mode.ai_roles)

        _emit(emit, {"type": "status", "message": "Preparando abas..."})
        pages: dict[str, Page] = {}
        for ai in _AIS:
            pages[ai] = await _get_or_open_tab(context, ai)
            await asyncio.sleep(1)

        # ── Rodada adversarial ativa na rodada do meio (se num_rounds >= 3) ──
        adversarial_round = 2 if num_rounds >= 3 else None

        # ── Rodadas de debate ─────────────────────────────────────────────────
        for rnd in range(1, num_rounds + 1):
            _emit(emit, {
                "type": "round_start",
                "round": rnd,
                "total": num_rounds,
                "message": f"{'─'*40}\nRODADA {rnd}/{num_rounds}",
            })

            use_adversarial = bool(rnd == adversarial_round and mode.adversarial_tmpl)

            if use_adversarial:
                _emit(emit, {"type": "status", "message": "Rodada adversarial ativada"})
                prompts = {
                    ai: mode.adversarial_tmpl.format(topic=topic, synthesis=synthesis)
                    for ai in pages
                }
            elif rnd == 1:
                prompts = {
                    ai: _build_prompt(mode.opening_tmpl, topic, ai, mode)
                    for ai in pages
                }
            else:
                prompts = {
                    ai: _build_prompt(
                        mode.followup_tmpl, topic, ai, mode,
                        synthesis=synthesis, round_num=rnd,
                    )
                    for ai in pages
                }

            results = await asyncio.gather(
                *[_run_agent(pages[ai], ai, prompts[ai], emit) for ai in pages],
                return_exceptions=True,
            )
            responses = {
                ai: r if isinstance(r, str) else f"[Exceção: {r}]"
                for ai, r in zip(pages.keys(), results)
            }

            _emit(emit, {"type": "status", "message": f"[Claude] sintetizando rodada {rnd}..."})
            synthesis = synthesize_round(topic, rnd, responses, mode.ai_roles)
            _emit(emit, {"type": "synthesis", "round": rnd, "content": synthesis})

            logger.log_round(f"Rodada {rnd}", responses, synthesis)
            history.append({"round": rnd, "responses": responses, "synthesis": synthesis})

        # ── Rodada de conclusão (pulada no modo quick) ────────────────────────
        if not quick:
            _emit(emit, {"type": "round_start", "round": "conclusao", "message": "RODADA FINAL: Conclusões"})
            conclusion_prompts = {
                ai: _build_prompt(mode.conclusion_tmpl, topic, ai, mode, synthesis=synthesis)
                for ai in pages
            }
            results = await asyncio.gather(
                *[_run_agent(pages[ai], ai, conclusion_prompts[ai], emit) for ai in pages],
                return_exceptions=True,
            )
            conclusions = {
                ai: r if isinstance(r, str) else f"[Exceção: {r}]"
                for ai, r in zip(pages.keys(), results)
            }
            logger.log_round("Rodada Final — Conclusões", conclusions)
            history.append({"round": "conclusao", "responses": conclusions, "synthesis": ""})

        # ── Veredicto ─────────────────────────────────────────────────────────
        _emit(emit, {"type": "status", "message": "[Claude] gerando veredicto final..."})
        system_override = mode.verdict_quick_system if quick else None
        verdict = generate_verdict(topic, history, mode.ai_roles, system_override=system_override)
        _emit(emit, {"type": "verdict", "content": verdict})
        logger.log_verdict(verdict)

        # ── Extração estruturada de decisão ───────────────────────────────────
        decision = extract_decision(topic, verdict)
        decision["mode"] = mode.name
        decision["timestamp"] = datetime.utcnow().isoformat()

        log_entry = json.dumps({
            "timestamp": decision["timestamp"],
            "mode":      decision["mode"],
            "topic":     topic,
            "decisao":        decision.get("decisao", ""),
            "descartado":     decision.get("descartado", ""),
            "risco_principal": decision.get("risco_principal", ""),
            "revisar_quando": decision.get("revisar_quando", ""),
        }, ensure_ascii=False)

        with (LOGS_DIR / "decisions.log").open("a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

        _emit(emit, {"type": "decision_extracted", "data": decision})

        return {
            "topic":    topic,
            "mode":     mode.name,
            "verdict":  verdict,
            "decision": decision,
            "history":  history,
        }
