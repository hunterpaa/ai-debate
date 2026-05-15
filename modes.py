"""
modes.py — Dois modos de operação do AI Debate.

  • "auto"  → Claude analisa o contexto e escolhe quais IAs participam e com qual papel
  • "turbo" → Todas as 7 IAs debatem sem filtro, máximo poder de perspectivas
"""
from dataclasses import dataclass


@dataclass
class Mode:
    key: str
    name: str
    description: str
    icon: str
    ai_roles: dict
    opening_tmpl: str
    followup_tmpl: str
    conclusion_tmpl: str
    synthesis_system: str
    verdict_system: str


_BASE_SYNTHESIS = (
    "Você é Claude — compilador de debate entre IAs. Ao sintetizar:\n"
    "1. Identifique as divergências REAIS (não superficiais)\n"
    "2. Aponte tensões intelectuais genuínas\n"
    "3. Crie UMA pergunta provocativa que force aprofundamento no próximo turno\n"
    "Foco desta sessão: {foco_sintese}\n"
    "Formato: síntese (2-3 parágrafos com profundidade) + 'PERGUNTA:' + a pergunta."
)

_BASE_VERDICT = (
    "Você é árbitro de um debate entre IAs. Produza um veredicto claro e completo:\n"
    "1. Avalie cada IA: qualidade argumentativa e originalidade\n"
    "2. Os insights mais valiosos do debate\n"
    "3. Convergências e divergências fundamentais\n"
    "4. Conclusão sobre o tema\n"
    "5. MVP: qual IA contribuiu mais e por quê\n"
    "Seja completo e específico — este é o veredicto final. Aprofunde-se em cada ponto."
)

_OPENING = (
    "Você está num debate entre IAs sobre:\n\n**{topic}**\n\n"
    "{custom_context_block}"
    "Seu papel específico neste debate: **{role}**\n\n"
    "{extra_instruction}\n\n"
    "Apresente sua posição inicial com base no seu papel. "
    "Seja direto, original, profundo e provoque as outras perspectivas."
)

_FOLLOWUP = (
    "Debate sobre **{topic}** — Rodada {round_num}.\n\n"
    "Você é: **{role}**\n\n"
    "Síntese e provocação do compilador:\n\n{synthesis}\n\n"
    "Responda à provocação com profundidade. Aprofunde, traga argumentos novos "
    "e defenda sua perspectiva com nuance."
)

_CONCLUSION = (
    "Conclusão do debate sobre **{topic}**.\n\n"
    "Como **{role}**, apresente sua posição final.\n\n"
    "Síntese das rodadas:\n\n{synthesis}\n\n"
    "Qual é seu argumento definitivo? Onde concorda ou discorda e por quê? "
    "Seja completo e aprofundado — esta é sua contribuição final."
)


_AUTO = Mode(
    key="auto",
    name="Debate Automático",
    description="Claude analisa o contexto e escolhe quais IAs participam e com qual papel",
    icon="🎯",
    ai_roles={},  # preenchido dinamicamente pelo smart_engine
    opening_tmpl=_OPENING,
    followup_tmpl=_FOLLOWUP,
    conclusion_tmpl=_CONCLUSION,
    synthesis_system=_BASE_SYNTHESIS,
    verdict_system=_BASE_VERDICT,
)

_TURBO = Mode(
    key="turbo",
    name="Turbo — Todas as IAs",
    description="Todas as 7 IAs debatem sem filtro — máximo poder de perspectivas",
    icon="⚡",
    ai_roles={},  # preenchido com AI_ROLES do config no orchestrator
    opening_tmpl=_OPENING,
    followup_tmpl=_FOLLOWUP,
    conclusion_tmpl=_CONCLUSION,
    synthesis_system=_BASE_SYNTHESIS,
    verdict_system=_BASE_VERDICT,
)

MODES: dict[str, Mode] = {
    "auto":  _AUTO,
    "turbo": _TURBO,
}
