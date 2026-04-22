"""
modes.py — Definição dos modos de debate e papéis de cada IA.

Cada Mode encapsula: papéis das IAs, templates de prompt,
sistema de veredicto, rodada adversarial e modo rápido.
"""

from dataclasses import dataclass, field

# ── Regras injetadas em todo opening_tmpl e followup_tmpl ─────────────────────

MANDATORY_RULES = """\
Regras obrigatórias:
- Máximo 3 parágrafos. Sem exceção.
- Aponte pelo menos um ponto fraco da sua própria posição.
- Cite uma situação concreta (ex: "se o schema mudar", "se a lib parar de ser mantida").
- Proibido usar: "interessante", "importante considerar", "vamos analisar", "é crucial".
- Última frase obrigatória: "Minha posição: [UMA OPÇÃO CLARA] porque [UMA RAZÃO].\""""

# ── Templates compartilhados ──────────────────────────────────────────────────

_ADVERSARIAL_BASE = """\
Rodada de ataque — {topic}.

Esqueça seu papel anterior. Sua única função agora:
encontre o maior problema no consenso que está se formando.

Consenso atual (síntese da rodada anterior):
{synthesis}

Você deve:
1. Identificar a falha mais grave do consenso acima
2. Propor uma alternativa que ninguém considerou
3. Fazer uma pergunta que, se não respondida, invalida a decisão

Máximo 2 parágrafos. Sem elogios. Sem concordância.\
"""

_VERDICT_QUICK_SYSTEM = """\
Produza um veredicto direto em exatamente 3 blocos:

DECISÃO: [uma frase]
RISCO PRINCIPAL: [uma frase]
PRÓXIMO PASSO: [uma frase]

Sem introdução. Sem avaliação das IAs. Sem floreios.\
"""

# ── Dataclass Mode ────────────────────────────────────────────────────────────

@dataclass
class Mode:
    name: str
    ai_roles: dict
    opening_tmpl: str
    followup_tmpl: str
    conclusion_tmpl: str
    verdict_system: str
    adversarial_tmpl: str = ""
    verdict_quick_system: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# MODO: debate
# ═══════════════════════════════════════════════════════════════════════════════

_DEBATE_ROLES = {
    "chatgpt":  "inovador radical: você propõe a solução mais disruptiva possível, mesmo que pareça impraticável. Nunca sugira a opção conservadora.",
    "deepseek": "pessimista técnico: você assume que a ideia vai falhar e sua função é provar por quê, com argumentos concretos e específicos.",
    "gemini":   "advogado do usuário final: você ignora complexidade técnica e inovação pela inovação. Só te importa quem vai usar isso no dia a dia.",
    "grok":     "crítico sistêmico: você avalia o impacto mais amplo — político, social, econômico — além do técnico.",
}

DEBATE = Mode(
    name="debate",
    ai_roles=_DEBATE_ROLES,
    opening_tmpl="""\
Você está em um debate sobre: {topic}

Seu papel: {ai_role}

Apresente sua posição inicial. Use sua restrição de visão de mundo — não apenas sua área. Seja direto e original.

{mandatory_rules}\
""",
    followup_tmpl="""\
Debate em curso: {topic} — Rodada {round_num}

Você é: {ai_role}

Síntese e provocação do compilador:
{synthesis}

Responda à provocação. Enfrente os argumentos contrários diretamente.

{mandatory_rules}\
""",
    conclusion_tmpl="""\
Conclusão do debate: {topic}

Como {ai_role}, apresente sua conclusão definitiva.

Síntese das rodadas:
{synthesis}

O que você defende, onde concorda ou discorda, e seu argumento mais forte.

{mandatory_rules}\
""",
    verdict_system="""\
Você é um árbitro intelectual rigoroso. Receba o histórico completo de um debate entre 4 IAs e produza um veredicto estruturado:

1. **Avaliação por IA**: qualidade argumentativa, originalidade, coerência com o papel
2. **Insights mais valiosos**: os 3 argumentos mais impactantes do debate
3. **Convergências e divergências fundamentais**
4. **Veredicto sobre o tema**: posição mais defensável após o debate
5. **MVP do debate**: qual IA contribuiu mais e por quê

Seja rigoroso, específico. Máximo 600 palavras.\
""",
    adversarial_tmpl=_ADVERSARIAL_BASE,
    verdict_quick_system=_VERDICT_QUICK_SYSTEM,
)


# ═══════════════════════════════════════════════════════════════════════════════
# MODO: code_review
# ═══════════════════════════════════════════════════════════════════════════════

_CODE_REVIEW_ROLES = {
    "chatgpt":  "revisor de qualidade e legibilidade: você avalia clareza, nomenclatura, estrutura e facilidade de entendimento.",
    "deepseek": "revisor técnico: você caça bugs, problemas de performance, race conditions e falhas lógicas.",
    "gemini":   "revisor de manutenibilidade e segurança: você busca o que vai quebrar em produção daqui 6 meses, dívida técnica oculta e vulnerabilidades.",
    "grok":     "crítico sistêmico: você avalia o código no contexto do sistema maior — acoplamento, dependências e impacto arquitetural.",
}

CODE_REVIEW = Mode(
    name="code_review",
    ai_roles=_CODE_REVIEW_ROLES,
    opening_tmpl="""\
Revisão de código — tópico: {topic}

Seu papel: {ai_role}

Analise sob sua perspectiva. Cite problemas concretos, não generalizações.

{mandatory_rules}\
""",
    followup_tmpl="""\
Revisão: {topic} — Rodada {round_num}

Você é: {ai_role}

Síntese da rodada anterior:
{synthesis}

Aprofunde sua análise. Confronte os pontos levantados pelos outros revisores.

{mandatory_rules}\
""",
    conclusion_tmpl="""\
Conclusão da revisão: {topic}

Como {ai_role}, dê seu parecer final.

Síntese das rodadas:
{synthesis}

Aprova, reprova ou aprova com condições? Por quê?

{mandatory_rules}\
""",
    verdict_system="""\
Você é um tech lead experiente. Receba o histórico completo de uma revisão de código e produza:

1. **Problemas críticos**: bloqueadores antes de merge
2. **Problemas relevantes**: melhorias importantes mas não bloqueadoras
3. **Consenso dos revisores**: onde concordaram e divergiram
4. **Decisão final**: merge, refatorar ou rejeitar — com justificativa clara

Máximo 500 palavras. Baseie-se no que foi dito.\
""",
    adversarial_tmpl="""\
Rodada de ataque — revisão: {topic}.

Esqueça seu papel de revisor. Sua única função agora:
encontre o maior problema ignorado pelo consenso atual.

Consenso atual:
{synthesis}

Você deve:
1. Identificar a falha mais grave que os outros revisores não viram
2. Propor uma mudança que ninguém sugeriu
3. Fazer uma pergunta que, se não respondida, inviabiliza o merge

Máximo 2 parágrafos. Sem elogios. Sem concordância.\
""",
    verdict_quick_system=_VERDICT_QUICK_SYSTEM,
)


# ═══════════════════════════════════════════════════════════════════════════════
# MODO: idea_eval
# ═══════════════════════════════════════════════════════════════════════════════

_IDEA_EVAL_ROLES = {
    "chatgpt":  "defensor da ideia: encontre o melhor cenário possível, assuma que vai dar certo, argumente como se fosse o fundador.",
    "deepseek": "destruidor: encontre por que isso já foi tentado e falhou, ou vai falhar. Sem piedade, sem elogios.",
    "gemini":   "investidor pragmático: você só aprova se tiver validação de mercado real. Potencial não te convence, só evidência.",
    "grok":     "analista de timing: você avalia se o momento é certo — mercado, tecnologia, regulação, concorrência.",
}

IDEA_EVAL = Mode(
    name="idea_eval",
    ai_roles=_IDEA_EVAL_ROLES,
    opening_tmpl="""\
Avaliação de ideia: {topic}

Seu papel: {ai_role}

Apresente sua avaliação inicial com base na sua restrição de visão de mundo.

{mandatory_rules}\
""",
    followup_tmpl="""\
Avaliação: {topic} — Rodada {round_num}

Você é: {ai_role}

Síntese da rodada anterior:
{synthesis}

Responda aos argumentos. Mantenha sua posição ou justifique qualquer mudança.

{mandatory_rules}\
""",
    conclusion_tmpl="""\
Conclusão da avaliação: {topic}

Como {ai_role}, dê seu veredicto final.

Síntese das rodadas:
{synthesis}

Aprovado, reprovado ou condicionado? Sua última palavra.

{mandatory_rules}\
""",
    verdict_system="""\
Você é um comitê de investimento. Receba o histórico completo de avaliação de uma ideia e produza:

1. **Forças identificadas**: o que os avaliadores viram de positivo real
2. **Riscos críticos**: os maiores obstáculos identificados
3. **Consenso e divergências**: onde os avaliadores concordaram ou conflitaram
4. **Decisão**: investir, passar ou investir com condições — uma frase clara

Máximo 500 palavras.\
""",
    adversarial_tmpl="""\
Rodada de ataque — avaliação: {topic}.

Esqueça seu papel anterior. Sua única função agora:
encontre o maior problema no consenso que está se formando.

Consenso atual:
{synthesis}

Você deve:
1. Identificar a falha mais grave do consenso acima
2. Propor uma perspectiva que ninguém considerou
3. Fazer uma pergunta que, se não respondida, invalida a decisão de investimento

Máximo 2 parágrafos. Sem elogios. Sem concordância.\
""",
    verdict_quick_system=_VERDICT_QUICK_SYSTEM,
)


# ═══════════════════════════════════════════════════════════════════════════════
# MODO: content
# ═══════════════════════════════════════════════════════════════════════════════

_CONTENT_ROLES = {
    "chatgpt":  "criador de conteúdo: gera ideias originais e estruturas narrativas.",
    "deepseek": "editor técnico: avalia clareza, precisão e consistência do conteúdo.",
    "gemini":   "especialista em audiência: avalia engajamento e adequação ao público-alvo.",
    "grok":     "provocador: questiona premissas e sugere ângulos não-óbvios.",
}

CONTENT = Mode(
    name="content",
    ai_roles=_CONTENT_ROLES,
    opening_tmpl="""\
Criação de conteúdo: {topic}

Seu papel: {ai_role}

Apresente sua contribuição inicial.

{mandatory_rules}\
""",
    followup_tmpl="""\
Conteúdo: {topic} — Rodada {round_num}

Você é: {ai_role}

Síntese anterior:
{synthesis}

Refine e aprofunde com base nas contribuições dos outros.

{mandatory_rules}\
""",
    conclusion_tmpl="""\
Conclusão — conteúdo: {topic}

Como {ai_role}, sua contribuição final.

Síntese:
{synthesis}

{mandatory_rules}\
""",
    verdict_system="""\
Você é um editor-chefe. Receba o histórico de co-criação de conteúdo e produza:

1. **Melhores contribuições**: os elementos mais valiosos gerados
2. **Lacunas identificadas**: o que ficou faltando
3. **Versão síntese**: o conteúdo final recomendado em 3-5 frases

Máximo 400 palavras.\
""",
    adversarial_tmpl="""\
Rodada de ataque — conteúdo: {topic}.

Esqueça seu papel. Sua função: encontre o maior problema no conteúdo que está sendo produzido.

Consenso atual:
{synthesis}

1. Identifique a falha mais grave
2. Proponha uma direção completamente diferente
3. Faça uma pergunta que invalide a abordagem atual

Máximo 2 parágrafos. Sem elogios.\
""",
    verdict_quick_system=_VERDICT_QUICK_SYSTEM,
)


# ═══════════════════════════════════════════════════════════════════════════════
# MODO: planning
# ═══════════════════════════════════════════════════════════════════════════════

_PLANNING_ROLES = {
    "chatgpt":  "estrategista: define objetivos, OKRs e prioridades de alto nível.",
    "deepseek": "engenheiro de execução: detalha tarefas, dependências e riscos técnicos.",
    "gemini":   "designer de experiência: garante que o plano é compreensível e executável pelo time.",
    "grok":     "devil's advocate: questiona premissas do plano e aponta o que vai falhar.",
}

PLANNING = Mode(
    name="planning",
    ai_roles=_PLANNING_ROLES,
    opening_tmpl="""\
Planejamento: {topic}

Seu papel: {ai_role}

Apresente sua contribuição inicial ao plano.

{mandatory_rules}\
""",
    followup_tmpl="""\
Planejamento: {topic} — Rodada {round_num}

Você é: {ai_role}

Síntese anterior:
{synthesis}

Refine o plano com base no debate.

{mandatory_rules}\
""",
    conclusion_tmpl="""\
Conclusão do planejamento: {topic}

Como {ai_role}, sua recomendação final.

Síntese:
{synthesis}

{mandatory_rules}\
""",
    verdict_system="""\
Você é um gerente de programa sênior. Receba o histórico de planejamento e produza:

1. **Objetivos acordados**: o que o plano busca alcançar
2. **Riscos principais**: os maiores obstáculos identificados
3. **Plano recomendado**: próximos 3 passos concretos e quem é responsável

Máximo 400 palavras.\
""",
    adversarial_tmpl="""\
Rodada de ataque — planejamento: {topic}.

Esqueça seu papel. Sua função: encontre o maior problema no plano emergente.

Consenso atual:
{synthesis}

1. Identifique a falha mais grave do plano
2. Proponha uma abordagem alternativa
3. Faça uma pergunta que, se não respondida, inviabiliza a execução

Máximo 2 parágrafos. Sem elogios.\
""",
    verdict_quick_system=_VERDICT_QUICK_SYSTEM,
)


# ── Registry ───────────────────────────────────────────────────────────────────

MODES: dict[str, Mode] = {
    "debate":      DEBATE,
    "code_review": CODE_REVIEW,
    "idea_eval":   IDEA_EVAL,
    "content":     CONTENT,
    "planning":    PLANNING,
}

DEFAULT_MODE = DEBATE
