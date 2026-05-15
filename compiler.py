"""
compiler.py — Integração com a API da Anthropic.

Claude atua como:
  1. Compilador de síntese a cada rodada
  2. Árbitro de tensões cognitivas (meta-debate)
  3. Gerador de veredicto final
  4. Avaliador de saúde do workspace (evaluate_workspace_health)
  5. Extrator de princípios do debate para knowledge_base

Upgrades ativos:
  - ERS (Echo Risk Score): detecta convergência de eco entre agentes
  - ChromaDB: memória vetorial persistente de sínteses
  - Fallback hierárquico: síntese local se Claude API falhar
"""

import uuid
import datetime as _dt

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, CLAUDE_MODEL_FAST

# ── ChromaDB singleton ────────────────────────────────────────────────────────
# Inicializado lazy na primeira chamada. _chroma_client = False indica falha.

_chroma_client = None
_chroma_collection = None


def _get_chroma_collection():
    """Retorna a collection ChromaDB ou None se indisponível."""
    global _chroma_client, _chroma_collection
    if _chroma_client is False:
        return None
    if _chroma_client is not None:
        return _chroma_collection
    try:
        import chromadb
        _chroma_client = chromadb.PersistentClient(path="./debate_memory")
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        except ImportError:
            from chromadb.utils import embedding_functions
            SentenceTransformerEmbeddingFunction = embedding_functions.SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        _chroma_collection = _chroma_client.get_or_create_collection(
            name="debate_rounds",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        return _chroma_collection
    except Exception:
        _chroma_client = False
        return None

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=90.0)

# ── System prompts ────────────────────────────────────────────────────────────

_SYSTEM_SYNTHESIS = """\
Você é um compilador inteligente de um debate entre até 7 IAs. Recebe as respostas de rodada e deve:

1. Sintetizar os argumentos mais relevantes e as divergências reais entre as IAs
2. Identificar tensões intelectuais genuínas (onde as visões conflitam ou se complementam)
3. Criar UMA pergunta provocativa e específica que force todas as IAs a aprofundarem seus pontos

Seja direto e incisivo. Evite elogios. Provoque o debate real.
Formato: primeiro a síntese (2-3 parágrafos), depois "PERGUNTA PARA A PRÓXIMA RODADA:" e a pergunta.
Máximo 350 palavras no total.\
"""

_SYSTEM_VERDICT = """\
Você é um árbitro intelectual rigoroso. Recebe o histórico completo de um debate entre até 7 IAs \
e deve produzir um veredicto final estruturado:

1. **Avaliação por IA**: qualidade argumentativa, originalidade, coerência com seu papel
2. **Insights mais valiosos**: os 3 argumentos mais impactantes do debate inteiro
3. **Convergências e divergências fundamentais**: o que as IAs concordam/discordam no fundo
4. **Veredicto sobre o tema**: qual a posição mais defensável após o debate
5. **MVP do debate**: qual IA contribuiu mais e por quê

Seja rigoroso, específico e baseie-se no conteúdo real do debate.
Máximo 600 palavras.\
"""

_SYSTEM_META_DEBATE = """\
Você é um árbitro de tensões cognitivas num debate entre IAs.
Foi detectada alta divergência semântica entre os agentes nesta rodada.

Sua tarefa:
1. Identifique EXATAMENTE onde está a contradição principal
2. Avalie qual posição tem mais suporte lógico/empírico
3. Formule uma síntese que FORCE resolução explícita na próxima rodada

Formato: contradição identificada (1 parágrafo) + veredicto parcial (1 parágrafo) +
"RESOLUÇÃO OBRIGATÓRIA NA PRÓXIMA RODADA:" + instrução específica para cada IA.
Máximo 350 palavras.\
"""

_SYSTEM_WORKSPACE_HEALTH = """\
Você é um avaliador de consistência cognitiva de um sistema multi-IA.
Recebe o estado atual do workspace compartilhado e o histórico do debate.

Sua tarefa:
1. Avalie se o raciocínio coletivo está progredindo ou girando em círculos
2. Identifique contradições diretas com fatos estabelecidos
3. Se necessário, sugira rollback parcial (especifique qual hipótese remover)
4. Extraia UM princípio novo descoberto nesta rodada (frase curta, objetiva)

Formato:
SAÚDE: [SAUDÁVEL | ATENÇÃO | CRÍTICO]
ANÁLISE: (1 parágrafo)
PRINCÍPIO: (frase curta — ou "nenhum" se não houver)
AÇÃO: [CONTINUAR | ROLLBACK_PARCIAL | ROLLBACK_TOTAL]
Máximo 200 palavras.\
"""

_SYSTEM_PRINCIPLE_EXTRACTOR = """\
Você é um destilador de conhecimento. Recebe uma síntese de debate entre IAs.
Extraia UM princípio operacional concreto que o sistema aprendeu nesta rodada.
Deve ser uma frase curta (máximo 120 caracteres), objetiva e reutilizável.
Responda APENAS com a frase do princípio, sem prefixos ou explicações.
Se não houver princípio novo, responda com: NENHUM\
"""


# ── Funções públicas ──────────────────────────────────────────────────────────

def compute_ers(responses: dict) -> float:
    """
    Echo Risk Score: similaridade semântica média entre as respostas dos agentes.
    ERS > 0.75 = convergência suspeita (eco cognitivo).
    ERS < 0.50 = divergência genuína (saudável).
    """
    try:
        from memory.vector_store import compute_pairwise_distance
        texts = list(responses.values())
        if len(texts) < 2:
            return 0.0
        pairs = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                dist = compute_pairwise_distance(texts[i], texts[j])
                pairs.append(1.0 - dist)  # similaridade = 1 - distância
        return round(sum(pairs) / len(pairs), 3) if pairs else 0.0
    except Exception:
        return 0.0


def store_round(
    synthesis_text: str,
    topic: str,
    ers_score: float = 0.0,
    decision_status: str = "provisional",
    claims: list | None = None,
    conflicts: list | None = None,
) -> str:
    """
    Grava síntese no ChromaDB vetorial com metadados estruturados.
    Retorna round_id para rastreabilidade (vazio se ChromaDB indisponível).
    """
    collection = _get_chroma_collection()
    if collection is None:
        return ""
    try:
        round_id = str(uuid.uuid4())
        collection.add(
            ids=[round_id],
            documents=[synthesis_text],
            metadatas=[{
                "timestamp": _dt.datetime.now().isoformat(),
                "topic": topic[:200],
                "ers_score": float(ers_score),
                "decision_status": decision_status,
                "claims": ",".join(claims or [])[:500],
                "conflicts": ",".join(conflicts or [])[:500],
            }],
        )
        return round_id
    except Exception:
        return ""


def recall_similar_rounds(
    query_text: str,
    top_k: int = 3,
    similarity_threshold: float = 0.65,
    max_ers: float = 0.75,
) -> str:
    """
    Recupera sínteses passadas semanticamente similares ao tópico atual.
    Filtra por relevância (≥ threshold) e rejeita memória de eco (ERS > max_ers).
    Retorna string formatada pronta para injeção no prompt dos agentes.
    """
    collection = _get_chroma_collection()
    if collection is None:
        return ""
    try:
        total = collection.count()
        if total == 0:
            return ""
        results = collection.query(
            query_texts=[query_text],
            n_results=min(top_k, total),
            include=["documents", "metadatas", "distances"],
        )
        docs      = results.get("documents", [[]])[0]
        metas     = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        filtered = []
        for doc, meta, dist in zip(docs, metas, distances):
            similarity = 1.0 - dist
            if similarity < similarity_threshold:
                continue
            if meta.get("ers_score", 0.0) > max_ers:
                continue
            filtered.append((doc, meta, similarity))

        if not filtered:
            return ""

        lines = ["[SÍNTESES ANTERIORES RELEVANTES — memória vetorial]"]
        for doc, meta, sim in filtered:
            status = meta.get("decision_status", "provisional")
            ers    = meta.get("ers_score", 0.0)
            lines.append(
                f"• relevância {sim:.0%} | ERS {ers:.2f} | status: {status}\n"
                f"  {doc[:400]}..."
            )
        return "\n".join(lines)
    except Exception:
        return ""


def _fallback_synthesis(topic: str, round_num: int, responses: dict) -> str:
    """Síntese local usada quando a API Claude está indisponível."""
    lines = [
        f"[SÍNTESE LOCAL — API Claude indisponível]\n\nTema: {topic} | Rodada {round_num}\n"
    ]
    for agent, text in responses.items():
        first = next(
            (l.strip() for l in text.splitlines() if len(l.strip()) > 30),
            text[:150],
        )
        lines.append(f"**{agent.upper()}:** {first[:200]}")
    lines.append(
        "\n⚠️ Síntese gerada localmente. Debate continua mas síntese é limitada. "
        "Verifique a API Claude e tente novamente."
    )
    return "\n".join(lines)


def synthesize_round(
    topic: str,
    round_num: int,
    responses: dict[str, str],
    system_override: str | None = None,
    ers_score: float = 0.0,
) -> str:
    system = system_override or _SYSTEM_SYNTHESIS
    if ers_score > 0.75:
        system += (
            f"\n\n⚠️ ALERTA DE ECO COGNITIVO: O Echo Risk Score desta rodada é {ers_score:.0%}. "
            "As IAs estão convergindo de forma semanticamente suspeita. "
            "Na síntese, destaque explicitamente onde pode haver eco e formule a questão "
            "para forçar divergência genuína na próxima rodada."
        )

    responses_block = "\n\n".join(
        f"### {name.upper()}\n{resp}" for name, resp in responses.items()
    )
    user_msg = (
        f"**TEMA:** {topic}\n**RODADA:** {round_num}\n\n"
        f"**RESPOSTAS:**\n\n{responses_block}\n\n"
        "---\nSintetize e crie a provocação para a próxima rodada."
    )

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        synthesis = message.content[0].text
    except Exception:
        synthesis = _fallback_synthesis(topic, round_num, responses)

    store_round(synthesis, topic, ers_score=ers_score)
    return synthesis


def synthesize_meta_debate(
    topic: str,
    round_num: int,
    responses: dict[str, str],
    tension_info: dict,
    authority_scores: dict[str, float] | None = None,
) -> str:
    """Síntese especial quando cognitive_tension_score > threshold dinâmico."""
    responses_block = "\n\n".join(
        f"### {name.upper()} (autoridade: {authority_scores.get(name, 0.5):.0%})\n{resp}"
        for name, resp in responses.items()
    )
    pair     = tension_info.get("most_tense_pair", [])
    pair_str = " vs ".join(p.upper() for p in pair) if pair else "agentes"
    threshold_used = tension_info.get("threshold_used", 0.7)

    user_msg = (
        f"**TEMA:** {topic}\n**RODADA:** {round_num}\n"
        f"**TENSÃO DETECTADA:** {tension_info.get('max_tension', 0):.0%} "
        f"(threshold dinâmico: {threshold_used:.0%}, par mais tenso: {pair_str})\n\n"
        f"**RESPOSTAS:**\n\n{responses_block}\n\n"
        "---\nResolva a tensão e exija posicionamento explícito na próxima rodada."
    )
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            system=_SYSTEM_META_DEBATE,
            messages=[{"role": "user", "content": user_msg}],
        )
        synthesis = message.content[0].text
    except Exception:
        synthesis = _fallback_synthesis(topic, round_num, responses)

    store_round(synthesis, topic, ers_score=0.0, decision_status="meta_debate")
    return synthesis


def generate_verdict(
    topic: str,
    debate_history: list[dict],
    system_override: str | None = None,
) -> str:
    history_block = ""
    for entry in debate_history:
        label = (
            "Rodada Final"
            if entry["round"] == "conclusao"
            else f"Rodada {entry['round']}"
        )
        history_block += f"\n\n## {label}\n"
        for ai, resp in entry["responses"].items():
            history_block += f"\n**{ai.upper()}:**\n{resp}\n"
        if entry.get("synthesis"):
            history_block += f"\n**SÍNTESE:**\n{entry['synthesis']}\n"

    user_msg = (
        f"**TEMA:** {topic}\n\n**HISTÓRICO:**{history_block}\n\n"
        "---\nGere o veredicto final."
    )
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=3000,
            system=system_override or _SYSTEM_VERDICT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return message.content[0].text
    except Exception:
        return "[VEREDICTO INDISPONÍVEL — API Claude fora do ar durante a geração do veredicto final.]"


def evaluate_workspace_health(
    workspace_state: dict,
    round_synthesis: str,
    round_num: int,
) -> dict:
    """
    Avalia a saúde cognitiva do workspace após uma rodada.
    Retorna: {status, analysis, principle, action}
    """
    state_summary = {
        "version":         workspace_state.get("version", 0),
        "hypotheses":      workspace_state.get("state", {}).get("hypotheses", [])[-5:],
        "accepted_facts":  workspace_state.get("state", {}).get("accepted_facts", [])[-5:],
        "open_conflicts":  workspace_state.get("state", {}).get("open_conflicts", [])[-3:],
        "decisions":       workspace_state.get("state", {}).get("decisions", [])[-5:],
    }

    user_msg = (
        f"**RODADA:** {round_num}\n\n"
        f"**ESTADO DO WORKSPACE:**\n{state_summary}\n\n"
        f"**SÍNTESE DESTA RODADA:**\n{round_synthesis[:500]}\n\n"
        "---\nAvalie a saúde cognitiva do sistema."
    )

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL_FAST,
            max_tokens=300,
            system=_SYSTEM_WORKSPACE_HEALTH,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = message.content[0].text
        return _parse_health_response(raw)
    except Exception:
        return {"status": "SAUDÁVEL", "analysis": "", "principle": "NENHUM", "action": "CONTINUAR"}


def extract_principle(synthesis: str) -> str:
    """Extrai um princípio operacional de uma síntese. Retorna '' se não houver."""
    try:
        message = client.messages.create(
            model=CLAUDE_MODEL_FAST,
            max_tokens=60,
            system=_SYSTEM_PRINCIPLE_EXTRACTOR,
            messages=[{"role": "user", "content": synthesis[:800]}],
        )
        result = message.content[0].text.strip()
        if result.upper() == "NENHUM" or not result:
            return ""
        return result[:120]
    except Exception:
        return ""


def _parse_health_response(raw: str) -> dict:
    lines  = raw.splitlines()
    result = {"status": "SAUDÁVEL", "analysis": "", "principle": "NENHUM", "action": "CONTINUAR"}
    for line in lines:
        if line.startswith("SAÚDE:"):
            result["status"] = line.split(":", 1)[1].strip()
        elif line.startswith("ANÁLISE:"):
            result["analysis"] = line.split(":", 1)[1].strip()
        elif line.startswith("PRINCÍPIO:"):
            result["principle"] = line.split(":", 1)[1].strip()
        elif line.startswith("AÇÃO:"):
            result["action"] = line.split(":", 1)[1].strip()
    return result
