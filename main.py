"""
main.py — Interface de terminal do AI Debate Orchestrator.

Pré-requisitos:
  1. Chrome aberto com CDP ativo → execute launch_chrome.py
  2. Esteja logado nas 4 IAs no Chrome
  3. ANTHROPIC_API_KEY configurada em config.py ou como variável de ambiente

Uso:
  python main.py
"""

import asyncio
import sys

from config import DEFAULT_ROUNDS, ANTHROPIC_API_KEY
from modes import MODES, DEFAULT_MODE
from orchestrator import run_debate


def _pick_mode() -> object:
    """Exibe menu de modos e retorna o Mode selecionado."""
    mode_list = list(MODES.items())
    print("\nModos disponíveis:")
    for i, (name, mode) in enumerate(mode_list, 1):
        print(f"  [{i}] {name}")
    raw = input(f"Modo [padrão: {DEFAULT_MODE.name}]: ").strip()
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(mode_list):
            return mode_list[idx][1]
    if raw in MODES:
        return MODES[raw]
    return DEFAULT_MODE


def _print_verdict(verdict: str, decision: dict) -> None:
    width = 60
    print(f"\n{'═'*width}")
    print("  VEREDICTO FINAL")
    print(f"{'═'*width}\n")
    print(verdict)

    if decision.get("decisao"):
        print(f"\n{'─'*width}")
        print("  DECISÃO EXTRAÍDA")
        print(f"{'─'*width}")
        print(f"  Decisão:        {decision.get('decisao', '')}")
        print(f"  Descartado:     {decision.get('descartado', '')}")
        print(f"  Risco principal:{decision.get('risco_principal', '')}")
        print(f"  Revisar quando: {decision.get('revisar_quando', '')}")
        print(f"{'─'*width}\n")


def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║    AI DEBATE ORCHESTRATOR  v2.0          ║")
    print("╚══════════════════════════════════════════╝\n")

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "SUA_CHAVE_AQUI":
        print("✗ Configure ANTHROPIC_API_KEY em config.py ou como variável de ambiente.")
        sys.exit(1)

    topic = input("📌 Tema do debate: ").strip()
    if not topic:
        topic = "O impacto da IA na criatividade humana"
        print(f"   (usando tema padrão: {topic})")

    print(f"\n{'─'*50}")
    print("  [D] Debate normal")
    print("  [Q] Modo Rápido (1 rodada, veredicto direto)")
    quick_raw = input("  Escolha [D/Q, padrão D]: ").strip().upper()
    quick = quick_raw == "Q"

    mode = _pick_mode()

    if not quick:
        rounds_raw = input(f"\n🔢 Número de rodadas [padrão {DEFAULT_ROUNDS}]: ").strip()
        try:
            num_rounds = int(rounds_raw) if rounds_raw else DEFAULT_ROUNDS
            num_rounds = max(1, min(num_rounds, 10))
        except ValueError:
            num_rounds = DEFAULT_ROUNDS
    else:
        num_rounds = 1
        print("   (modo rápido: 1 rodada, veredicto direto)")

    print(f"\n{'═'*50}")
    print(f"  TEMA:   {topic}")
    print(f"  MODO:   {mode.name}")
    print(f"  RODADAS:{num_rounds}{' + conclusão' if not quick else ' (sem conclusão)'}")
    print(f"{'═'*50}\n")

    result = asyncio.run(run_debate(
        topic=topic,
        num_rounds=num_rounds,
        mode=mode,
        quick=quick,
        emit=None,
    ))

    _print_verdict(result["verdict"], result["decision"])


if __name__ == "__main__":
    main()
