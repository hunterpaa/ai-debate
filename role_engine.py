"""
role_engine.py — Atribuição dinâmica de papéis via Claude.
Classifica o problema e seleciona os 3 papéis mais especializados e opostos.
Ativo apenas no modo "debate". Outros modos usam papéis fixos definidos em modes.py.
"""
import json

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL_FAST as CLAUDE_MODEL

_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0)

_SYSTEM = """\
Você é um especialista em design de debates entre IAs.
Dado um tópico, classifique-o e retorne 3 papéis especializados ideais para debatê-lo.

Responda APENAS com JSON válido, sem markdown nem explicações:
{
  "problem_category": "engenharia|produto|estrategia|ciencia|filosofia|negocio|criativo|outro",
  "roles": {
    "chatgpt": "papel específico e detalhado (máx 15 palavras)",
    "deepseek": "papel específico e detalhado (máx 15 palavras)",
    "gemini": "papel específico e detalhado (máx 15 palavras)"
  }
}

Regra: os papéis devem ser OPOSTOS e COMPLEMENTARES para maximizar tensão produtiva.\
"""

_FALLBACK = {
    "chatgpt":  "especialista em criatividade, inovação e soluções disruptivas",
    "deepseek": "especialista em lógica, análise técnica e ceticismo crítico",
    "gemini":   "especialista em perspectivas multidisciplinares e síntese sistêmica",
}


def assign_roles(topic: str, mode_key: str) -> dict[str, str]:
    """
    Retorna {agent: role} com papéis dinamicamente escolhidos para o tópico.
    Só age no modo 'debate'. Fallback silencioso se a API falhar.
    """
    if mode_key != "debate":
        return {}

    try:
        msg = _client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=_SYSTEM,
            messages=[{"role": "user", "content": f"Tópico: {topic}"}],
        )
        text = msg.content[0].text.strip()
        start, end = text.find("{"), text.rfind("}") + 1
        data = json.loads(text[start:end])
        roles = data.get("roles", {})
        if all(k in roles for k in ("chatgpt", "deepseek", "gemini")):
            return roles
    except Exception:
        pass

    return _FALLBACK
