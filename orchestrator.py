"""
orchestrator.py — Debate limpo, sem memória persistente.

Fluxo:
  1. Resolve modo (auto → smart_engine escolhe IAs; turbo → todas as 7)
  2. Abre browser e tabs das IAs em paralelo
  3. Executa N rodadas: envia prompts → coleta respostas → Claude sintetiza
  4. Rodada final de conclusão + veredicto do Claude
  5. Salva markdown em logs/
"""
import asyncio
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Awaitable

from playwright.async_api import async_playwright, BrowserContext, Page

from config import AI_URLS, LOGS_DIR, ANTHROPIC_API_KEY, DEBATE_PROFILE_DIR, BROWSER_CHANNEL, AI_ROLES
from agents import send_message, wait_for_response_complete, get_last_response, MAX_PROMPT_CHARS
from smart_engine import detect_mode as _smart_detect
from compiler import synthesize_round as _synthesize, generate_verdict as _verdict
from modes import MODES, Mode
from dataclasses import replace as _dc_replace

Emitter = Callable[[dict], Awaitable[None]] | None


# ── Emit helper ───────────────────────────────────────────────────────────────

async def _emit(emit: Emitter, event: dict):
    if emit:
        await emit(event)
    else:
        t = event.get("type", "")
        if t == "status":
            print(f"  {event['message']}")
        elif t == "round_start":
            print(f"\n{'─'*50}\n  RODADA {event['round']}/{event['total']}\n{'─'*50}\n")
        elif t == "agent_thinking":
            print(f"  → [{event['ai']}] gerando resposta...")
        elif t == "agent_done":
            print(f"  ✓ [{event['ai']}] {len(event['text'])} chars")
        elif t == "synthesis_done":
            print(f"  [Claude] síntese: {event['text'][:100]}...")
        elif t == "verdict_done":
            print(f"\n{'═'*60}\n  VEREDICTO FINAL\n{'═'*60}\n{event['text']}")
        elif t == "error":
            import sys
            print(f"  ✗ Erro: {event['message']}", file=sys.stderr)


# ── Markdown ──────────────────────────────────────────────────────────────────

def _build_markdown(topic: str, mode: Mode, history: list, verdict: str) -> str:
    lines = [
        f"# {mode.icon} {mode.name}: {topic}\n",
        f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n",
        "---\n## Participantes\n",
    ]
    for ai, role in mode.ai_roles.items():
        lines.append(f"- **{ai.upper()}**: {role}")
    lines.append("\n---\n")

    for entry in history:
        label = (
            "Rodada Final — Conclusões"
            if entry["round"] == "conclusao"
            else f"Rodada {entry['round']}"
        )
        lines.append(f"\n## {label}\n")
        for ai, resp in entry["responses"].items():
            lines.append(f"\n### {ai.upper()} — {mode.ai_roles.get(ai, '')}\n")
            lines.append(resp)
            lines.append("")
        if entry.get("synthesis"):
            lines.append(f"\n### Síntese Claude\n{entry['synthesis']}\n")

    lines += [
        "\n---\n",
        "## Veredicto Final (Claude)\n",
        verdict,
        f"\n---\n*Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}*",
    ]
    return "\n".join(lines)


def _save_markdown(topic: str, mode: Mode, history: list, verdict: str):
    content = _build_markdown(topic, mode, history, verdict)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in " -_" else "" for c in topic)[:40].strip()
    path = LOGS_DIR / f"{mode.key}_{ts}_{safe}.md"
    path.write_text(content, encoding="utf-8")
    return path, content


# ── Browser ───────────────────────────────────────────────────────────────────

async def _launch_browser(pw):
    DEBATE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        user_data_dir=str(DEBATE_PROFILE_DIR),
        headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
        slow_mo=80,
    )
    try:
        if BROWSER_CHANNEL:
            return await pw.chromium.launch_persistent_context(channel=BROWSER_CHANNEL, **kwargs)
    except Exception:
        pass
    return await pw.chromium.launch_persistent_context(**kwargs)


async def _get_or_open_tab(context: BrowserContext, ai_name: str) -> Page:
    url    = AI_URLS[ai_name]
    domain = url.split("//")[1].split("/")[0].replace("www.", "")
    for page in context.pages:
        try:
            if domain in page.url and "blank" not in page.url:
                await page.bring_to_front()
                return page
        except Exception:
            continue
    page = await context.new_page()
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(2)
    return page


# ── Agent runner ──────────────────────────────────────────────────────────────

async def _run_one_agent(page: Page, ai_name: str, prompt: str, emit: Emitter) -> str:
    await _emit(emit, {"type": "agent_thinking", "ai": ai_name})
    try:
        await send_message(page, ai_name, prompt)
        await wait_for_response_complete(page, ai_name)
        response = await get_last_response(page, ai_name)
        await _emit(emit, {"type": "agent_done", "ai": ai_name, "text": response})
        return response
    except Exception as exc:
        err = (
            f"[ABSTENÇÃO FORÇADA — grok: falha de UI ({exc}). Esta voz não participou desta rodada.]"
            if ai_name == "grok"
            else f"[Erro em {ai_name}: {exc}]"
        )
        await _emit(emit, {"type": "agent_done", "ai": ai_name, "text": err})
        return err


# ── Main orchestrator ─────────────────────────────────────────────────────────

async def run_debate(
    topic: str,
    num_rounds: int,
    mode_key: str = "auto",
    emit: Emitter = None,
    custom_context: str = "",
    debate_id: str = "",
    preselected_roles: dict | None = None,
) -> tuple[str, str]:
    """
    Executa o debate completo.
    preselected_roles: papéis já confirmados pelo usuário via /api/preview (modo auto).
    Retorna (markdown_content, markdown_path).
    """
    if not ANTHROPIC_API_KEY or "SUA_CHAVE" in ANTHROPIC_API_KEY:
        await _emit(emit, {"type": "error", "message": "ANTHROPIC_API_KEY não configurada."})
        return "", ""

    mode = MODES.get(mode_key, MODES["auto"])
    extra_instruction = ""
    foco_sintese = "tensões e divergências reais entre as perspectivas"

    # ── Resolve papéis das IAs ────────────────────────────────────────────────
    if mode_key == "auto":
        if preselected_roles:
            mode = _dc_replace(mode, ai_roles=preselected_roles)
            await _emit(emit, {"type": "roles_confirmed", "roles": preselected_roles})
        else:
            await _emit(emit, {"type": "status", "message": "🎯 Analisando contexto e selecionando IAs..."})
            full_topic = topic + ("\n\n" + custom_context if custom_context else "")
            try:
                smart_config = await asyncio.to_thread(_smart_detect, full_topic)
            except Exception:
                smart_config = {}

            if smart_config:
                dynamic_roles    = smart_config.get("roles", {})
                extra_instruction = smart_config.get("instrucao_abertura", "")
                foco_sintese     = smart_config.get("foco_sintese", foco_sintese)
                synthesis_sys    = mode.synthesis_system.replace("{foco_sintese}", foco_sintese)
                mode = _dc_replace(mode, ai_roles=dynamic_roles, synthesis_system=synthesis_sys)
                await _emit(emit, {
                    "type":          "mode_detected",
                    "tipo":          smart_config.get("tipo_detectado", "Debate"),
                    "justificativa": smart_config.get("justificativa", ""),
                    "roles":         dynamic_roles,
                    "foco_sintese":  foco_sintese,
                })
            else:
                dynamic_roles = {
                    "chatgpt":  "especialista em criatividade e inovação",
                    "deepseek": "especialista em lógica e ceticismo técnico",
                    "gemini":   "especialista em perspectivas multidisciplinares",
                }
                mode = _dc_replace(mode, ai_roles=dynamic_roles)
                await _emit(emit, {"type": "roles_assigned", "roles": dynamic_roles})

    elif mode_key == "turbo":
        synthesis_sys = mode.synthesis_system.replace("{foco_sintese}", foco_sintese)
        mode = _dc_replace(mode, ai_roles=dict(AI_ROLES), synthesis_system=synthesis_sys)
        await _emit(emit, {"type": "roles_assigned", "roles": mode.ai_roles})

    ai_names = list(mode.ai_roles.keys())

    await _emit(emit, {
        "type": "debate_start", "topic": topic, "mode": mode_key,
        "mode_name": mode.name, "rounds": num_rounds,
        "ais": ai_names, "roles": mode.ai_roles,
    })

    history: list[dict] = []

    def _fit_synthesis(syn: str, ai: str) -> str:
        max_syn = max(300, MAX_PROMPT_CHARS.get(ai, 12_000) - 1200)
        if len(syn) <= max_syn:
            return syn
        return syn[:max_syn] + "\n\n[...síntese truncada para caber no limite desta IA]"

    def _fmt(tmpl: str, ai: str, cur_rnd: int = 1, cur_syn: str = "") -> str:
        role     = mode.ai_roles.get(ai, "")
        ctx_block = f"**Contexto adicional:**\n{custom_context}\n\n" if custom_context else ""
        d = defaultdict(str, {
            "topic":               topic,
            "ai_name":             ai,
            "role":                role,
            "synthesis":           _fit_synthesis(cur_syn, ai),
            "round_num":           str(cur_rnd),
            "custom_context":      custom_context,
            "custom_context_block": ctx_block,
            "extra_instruction":   extra_instruction,
        })
        return tmpl.format_map(d)

    try:
        async with async_playwright() as pw:
            await _emit(emit, {"type": "status", "message": "Iniciando browser..."})
            context = await _launch_browser(pw)

            await _emit(emit, {"type": "status", "message": "Abrindo abas das IAs em paralelo..."})
            page_list = await asyncio.gather(
                *[_get_or_open_tab(context, ai) for ai in ai_names],
                return_exceptions=True,
            )
            pages: dict[str, Page] = {}
            for ai, page in zip(ai_names, page_list):
                if isinstance(page, Exception):
                    raise page
                pages[ai] = page
            await asyncio.sleep(1.0)

            synthesis = ""

            # ── Rodadas ───────────────────────────────────────────────────────
            for rnd in range(1, num_rounds + 1):
                await _emit(emit, {"type": "round_start", "round": rnd, "total": num_rounds})

                prompts = {
                    ai: _fmt(
                        mode.opening_tmpl if rnd == 1 else mode.followup_tmpl,
                        ai, rnd, synthesis
                    )
                    for ai in pages
                }

                results = await asyncio.gather(
                    *[_run_one_agent(pages[ai], ai, prompts[ai], emit) for ai in pages],
                    return_exceptions=True,
                )
                responses = {
                    ai: r if isinstance(r, str) else f"[Exceção: {r}]"
                    for ai, r in zip(pages.keys(), results)
                }

                await _emit(emit, {"type": "synthesis_start"})
                synthesis = await asyncio.to_thread(
                    _synthesize, topic, rnd, responses, mode.synthesis_system, 0.0
                )
                await _emit(emit, {"type": "synthesis_done", "text": synthesis, "round": rnd})

                history.append({"round": rnd, "responses": responses, "synthesis": synthesis})

            # ── Conclusão ─────────────────────────────────────────────────────
            await _emit(emit, {"type": "round_start", "round": "conclusao", "total": num_rounds})
            conclusion_prompts = {
                ai: _fmt(mode.conclusion_tmpl, ai, num_rounds, synthesis)
                for ai in pages
            }
            results = await asyncio.gather(
                *[_run_one_agent(pages[ai], ai, conclusion_prompts[ai], emit) for ai in pages],
                return_exceptions=True,
            )
            conclusions = {
                ai: r if isinstance(r, str) else f"[Exceção: {r}]"
                for ai, r in zip(pages.keys(), results)
            }
            history.append({"round": "conclusao", "responses": conclusions, "synthesis": ""})

            # ── Veredicto ─────────────────────────────────────────────────────
            await _emit(emit, {"type": "verdict_start"})
            verdict = await asyncio.to_thread(_verdict, topic, history, mode.verdict_system)
            await _emit(emit, {"type": "verdict_done", "text": verdict})

            # ── Salva markdown ─────────────────────────────────────────────────
            md_path, md_content = _save_markdown(topic, mode, history, verdict)
            await _emit(emit, {
                "type":          "debate_complete",
                "markdown_path": str(md_path),
                "markdown":      md_content,
            })

            await context.close()
            import time; time.sleep(3)
            return md_content, str(md_path)

    except Exception as exc:
        await _emit(emit, {"type": "error", "message": f"Erro no debate: {exc}"})
        return "", ""
