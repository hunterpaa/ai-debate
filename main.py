"""
main.py — Modo terminal do AI Debate Orchestrator.
Para a interface web, use: python app.py
"""

import asyncio
from modes import MODES
from orchestrator import run_debate
from config import DEFAULT_ROUNDS


def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║    AI DEBATE ORCHESTRATOR  v2.0          ║")
    print("║    (Para interface web: python app.py)   ║")
    print("╚══════════════════════════════════════════╝\n")

    print("Modos disponíveis:")
    for m in MODES.values():
        print(f"  {m.icon}  {m.key:<15} {m.name}")

    mode_key = input("\nModo [padrão: debate]: ").strip() or "debate"
    if mode_key not in MODES:
        print(f"Modo '{mode_key}' não existe. Usando 'debate'.")
        mode_key = "debate"

    mode = MODES[mode_key]
    topic = input(f"\n{mode.icon} {mode.name} — tema/input: ").strip()
    if not topic:
        topic = "O impacto da IA na criatividade humana"
        print(f"   (usando padrão: {topic})")

    rounds_raw = input(f"Rodadas [padrão {DEFAULT_ROUNDS}]: ").strip()
    try:
        num_rounds = max(1, min(int(rounds_raw), 10)) if rounds_raw else DEFAULT_ROUNDS
    except ValueError:
        num_rounds = DEFAULT_ROUNDS

    asyncio.run(run_debate(topic, num_rounds, mode_key, emit=None))


if __name__ == "__main__":
    main()
