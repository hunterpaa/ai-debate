"""
compiler.py — Integração com a API da Anthropic.

Claude atua como compilador inteligente: sintetiza as 4 respostas a cada rodada,
gera um veredicto final e extrai a decisão estruturada.
"""

import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, AI_ROLES

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ── System prompts ────────────────────────────────────────────────────────────

_SYSTEM_SYNTHESIS = """\
Você é um compilador inteligente de um debate entre 4 IAs. Recebe as respostas de rodada e deve:

1. Sintetizar os argumentos mais relevantes e as divergências reais entre as IAs
2. Identificar tensões intelectuais genuínas (onde as visões conflitam ou se complementam)
3. Criar UMA pergunta provocativa e específica que force todas as IAs a aprofundarem seus pontos

Seja direto e incisivo. Evite elogios. Provoque o debate real.
Formato: primeiro a síntese (2-3 parágrafos), depois "PERGUNTA PARA A PRÓXIMA RODADA:" e a pergunta.
Máximo 350 palavras no total.\
"""

_SYSTEM_VERDICT = """\
Você é um árbitro intelectual rigoroso. Recebe o histórico completo de um debate entre 4 IAs \
e deve produzir um veredicto final estruturado:

1. **Avaliação por IA**: qualidade argumentativa, originalidade, coerência com seu papel
2. **Insights mais valiosos**: os 3 argumentos mais impactantes do debate inteiro
3. **Convergências e divergências fundamentais**: o que as IAs concordam/discordam no fundo
4. **Veredicto sobre o tema**: qual a posição mais defensável após o debate
5. **MVP do debate**: qual IA contribuiu mais e por quê

Seja rigoroso, específico e baseie-se no conteúdo real do debate.
Máximo 600 palavras.\
"""

_SYSTEM_EXTRACT = """\
Extraia do veredicto abaixo exatamente 4 campos em JSON válido.
Retorne APENAS o JSON, sem markdown, sem explicação.
{
  "decisao": "o que foi decidido em uma frase",
  "descartado": "o que foi descartado e por quê, em uma frase",
  "risco_principal": "o maior risco identificado, em uma frase",
  "revisar_quando": "condição ou prazo para revisar essa decisão"
}\
"""

# ── Funções públicas ──────────────────────────────────────────────────────────

def synthesize_round(
    topic: str,
    round_num: int,
    responses: dict[str, str],
    ai_roles: dict[str, str] | None = None,
) -> str:
    """Sintetiza as respostas da rodada e gera pergunta provocativa."""
    roles = ai_roles if ai_roles is not None else AI_ROLES

    responses_block = "\n\n".join(
        f"### {name.upper()} — papel: {roles.get(name, name)}\n{resp}"
        for name, resp in responses.items()
    )

    user_msg = (
        f"**TEMA DO DEBATE:** {topic}\n"
        f"**RODADA:** {round_num}\n\n"
        f"**RESPOSTAS DAS 4 IAs:**\n\n{responses_block}\n\n"
        "---\nSintetize e crie a pergunta provocativa para a próxima rodada."
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=700,
        system=_SYSTEM_SYNTHESIS,
        messages=[{"role": "user", "content": user_msg}],
    )
    return message.content[0].text


def generate_verdict(
    topic: str,
    debate_history: list[dict],
    ai_roles: dict[str, str] | None = None,
    system_override: str | None = None,
) -> str:
    """Gera o veredicto final do debate."""
    roles = ai_roles if ai_roles is not None else AI_ROLES
    system = system_override if system_override else _SYSTEM_VERDICT

    history_block = ""
    for entry in debate_history:
        label = (
            f"Rodada {entry['round']}"
            if entry["round"] != "conclusao"
            else "Rodada Final (Conclusões)"
        )
        history_block += f"\n\n## {label}\n"
        for ai, resp in entry["responses"].items():
            history_block += f"\n**{ai.upper()} ({roles.get(ai, ai)}):**\n{resp}\n"
        if entry.get("synthesis"):
            history_block += f"\n**SÍNTESE CLAUDE:**\n{entry['synthesis']}\n"

    user_msg = (
        f"**TEMA:** {topic}\n\n"
        f"**HISTÓRICO COMPLETO DO DEBATE:**{history_block}\n\n"
        "---\nGere o veredicto final deste debate."
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return message.content[0].text


def extract_decision(topic: str, verdict: str) -> dict:
    """Extrai campos estruturados do veredicto via chamada separada à API."""
    user_msg = f"Tópico: {topic}\n\nVeredicto:\n{verdict}"

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=300,
            system=_SYSTEM_EXTRACT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = message.content[0].text.strip()
        return json.loads(raw)
    except Exception:
        return {
            "decisao": "",
            "descartado": "",
            "risco_principal": "",
            "revisar_quando": "",
        }
