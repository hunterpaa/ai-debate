"""
smart_engine.py — Claude analisa qualquer tema e retorna configuração
dinâmica de papéis e prompts para o debate.
"""
import json
import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL_FAST as CLAUDE_MODEL

_CLIENT = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """Você é o orquestrador inteligente de um sistema de debate com 7 IAs disponíveis.

IAs disponíveis e seus superpoderes únicos:
- chatgpt: criatividade, inovação, ideias disruptivas, narrativa
- deepseek: lógica, raciocínio técnico, matemática, ceticismo
- gemini: análise multidisciplinar, síntese visual, perspectiva ampla
- perplexity: âncora factual — cita fontes reais, questiona sem evidência
- qwen: mercado asiático, escala de bilhões, estratégia não-ocidental
- mistral: ética, privacidade, GDPR, perspectiva europeia, ceticismo regulatório
- grok: tempo real — dados e eventos atuais, conecta o debate ao presente

Analise o tema e selecione as IAs que trazem perspectivas GENUINAMENTE DIFERENTES para ele.
Regras:
- Mínimo 3 IAs, máximo 7
- Só inclua uma IA se ela agrega algo que as outras não têm
- Para temas técnicos: prefira deepseek + perplexity
- Para temas globais/geopolíticos: inclua qwen + mistral
- Para temas com dados atuais: inclua grok
- Para temas éticos/regulatórios: inclua mistral
- Evite redundância — chatgpt e gemini juntos precisam ter papéis bem distintos

Responda APENAS com JSON válido (sem markdown, sem explicação fora do JSON):
{
  "tipo_detectado": "nome curto do tipo de análise",
  "justificativa": "1-2 frases: por que estas IAs e não as outras para este tema",
  "roles": {
    "ia_selecionada_1": "papel específico — foco em X deste tema",
    "ia_selecionada_2": "papel específico — foco em Y deste tema"
  },
  "instrucao_abertura": "instrução extra de 1 frase para a abertura do debate (não repita o papel)",
  "foco_sintese": "o que Claude deve focar ao sintetizar cada rodada (máx 20 palavras)"
}

Inclua apenas as IAs selecionadas no campo "roles". Não inclua todas se não forem necessárias."""


def detect_mode(topic: str, past_context: str = "") -> dict:
    """Analisa o tema, seleciona as IAs certas e retorna configuração dinâmica."""
    try:
        content = f"Tema:\n{topic}"
        if past_context:
            content += f"\n\nContexto de debates anteriores relevantes:\n{past_context[:1000]}"

        msg = _CLIENT.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=800,
            system=_SYSTEM,
            messages=[{"role": "user", "content": content}]
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw)
        # Garante mínimo de 3 IAs
        if len(result.get("roles", {})) < 3:
            return _fallback(topic)
        return result
    except Exception:
        return _fallback(topic)


def _fallback(topic: str) -> dict:
    """Fallback genérico se Claude falhar — usa as 3 IAs base."""
    return {
        "tipo_detectado": "Debate de Ideias",
        "justificativa": "Modo padrão: debate multi-perspectiva sobre o tema.",
        "roles": {
            "chatgpt":  "especialista em criatividade, inovação e ideias disruptivas",
            "deepseek": "especialista em lógica, raciocínio técnico e ceticismo",
            "gemini":   "especialista em perspectivas multidisciplinares e síntese",
        },
        "instrucao_abertura": "Apresente sua perspectiva única com base no seu papel.",
        "foco_sintese": "tensões e divergências reais entre as perspectivas",
    }
