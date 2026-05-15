"""
import_logs.py — Importa todos os debates anteriores (.md) para a memória estruturada.

Lê os arquivos de logs/, extrai as respostas de cada agente por rodada e persiste
no graph_store + vector_store como MemoryChunks.

Uso: python import_logs.py
     python import_logs.py --dry-run   (mostra o que seria importado sem gravar)
"""
import io
import re
import sys
from pathlib import Path

# Força UTF-8 no stdout para suportar caracteres especiais no Windows
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Garante que o módulo memory está no path
sys.path.insert(0, str(Path(__file__).parent))


def _safe(text: str, limit: int = 100) -> str:
    """Remove caracteres que o terminal não consegue exibir."""
    return text[:limit].encode('ascii', errors='replace').decode('ascii')

from memory.persistence import persist_memory, MemoryChunk
from memory.graph_store import node_count, write_edge
from memory.vector_store import compute_pairwise_distance

LOGS_DIR = Path(__file__).parent / "logs"
DRY_RUN = "--dry-run" in sys.argv

# ── Parser de arquivo .md ─────────────────────────────────────────────────────

def extract_topic(lines: list[str]) -> str:
    for line in lines[:5]:
        if line.startswith("# "):
            # Remove ícone e prefixo de modo (ex: "# 🧬 Evolução da Super IA: Tema")
            text = line[2:].strip()
            # Remove ícones unicode no início
            text = re.sub(r'^[\U00010000-\U0010ffff☀-⛿✀-➿\s]+', '', text)
            # Remove prefixo "Modo: ", "Nome: " etc
            if ": " in text:
                parts = text.split(": ", 1)
                # Pega a parte mais longa (geralmente o tópico real)
                text = parts[1] if len(parts[1]) > len(parts[0]) else text
            return text.strip()[:200]
    return "tópico desconhecido"


def extract_date(lines: list[str]) -> str:
    for line in lines[:10]:
        m = re.search(r'\*\*Data:\*\*\s*(.+)', line)
        if m:
            return m.group(1).strip()
    return ""


def parse_sections(content: str) -> list[dict]:
    """
    Divide o markdown em seções por agente e rodada.
    Retorna lista de: {agent, round, text, type}
    """
    sections = []

    # Detecta rodadas e respostas com regex
    # Padrão: ## Rodada N ou ## Rodada Final
    # Depois: ### AGENTNAME — ...

    round_pattern = re.compile(
        r'^## (Rodada\s*\d+|Rodada Final[^#\n]*|Veredicto Final[^#\n]*)',
        re.MULTILINE | re.IGNORECASE
    )
    agent_pattern = re.compile(
        r'^### (CHATGPT|DEEPSEEK|GEMINI|Síntese Claude)[^\n]*',
        re.MULTILINE | re.IGNORECASE
    )

    # Divide por seção de rodada
    round_splits = list(round_pattern.finditer(content))

    for i, round_match in enumerate(round_splits):
        round_label = round_match.group(1).strip()

        # Determina número da rodada
        round_num_match = re.search(r'\d+', round_label)
        if "Final" in round_label or "Conclus" in round_label:
            round_num = "conclusao"
        elif "Veredicto" in round_label:
            continue  # pula veredicto
        elif round_num_match:
            round_num = int(round_num_match.group())
        else:
            round_num = i + 1

        # Texto desta rodada até a próxima
        start = round_match.end()
        end = round_splits[i + 1].start() if i + 1 < len(round_splits) else len(content)
        round_text = content[start:end]

        # Extrai respostas de cada agente dentro desta rodada
        agent_splits = list(agent_pattern.finditer(round_text))

        for j, agent_match in enumerate(agent_splits):
            agent_raw = agent_match.group(1).strip().lower()

            if "síntese" in agent_raw or "sintese" in agent_raw:
                agent = "claude"
                node_type = "synthesis"
            elif "chatgpt" in agent_raw:
                agent = "chatgpt"
                node_type = "argument"
            elif "deepseek" in agent_raw:
                agent = "deepseek"
                node_type = "argument"
            elif "gemini" in agent_raw:
                agent = "gemini"
                node_type = "argument"
            else:
                continue

            # Texto desta resposta até a próxima
            a_start = agent_match.end()
            a_end = agent_splits[j + 1].start() if j + 1 < len(agent_splits) else len(round_text)
            text = round_text[a_start:a_end].strip()

            # Remove linhas de cabeçalho vazias e separadores
            text = re.sub(r'\n---+\n?', '\n', text).strip()

            if len(text) > 50:  # ignora fragmentos muito pequenos
                sections.append({
                    "agent": agent,
                    "round": round_num,
                    "text": text,
                    "node_type": node_type,
                })

    return sections


def import_file(path: Path, dry_run: bool = False) -> int:
    """
    Importa um arquivo .md. Retorna número de chunks gravados.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"  ✗ Erro ao ler {path.name}: {e}")
        return 0

    lines = content.splitlines()
    topic = extract_topic(lines)
    date = extract_date(lines)
    sections = parse_sections(content)

    if not sections:
        print(f"  AVISO: Nenhuma resposta encontrada em: {path.name}")
        return 0

    print(f"\n  >> {_safe(path.name, 70)}")
    print(f"     Topico: {_safe(topic, 80)}...")
    print(f"     Data: {_safe(date)} | Secoes: {len(sections)}")

    if dry_run:
        for s in sections:
            print(f"       [{s['agent']:8}] rodada {str(s['round']):8} - {len(s['text'])} chars")
        return len(sections)

    # Grava chunks e coleta node_ids por agente nesta rodada
    node_ids_by_round: dict[str | int, dict[str, str]] = {}
    chunks_saved = 0

    # Calcula scores simplificados (sem histórico no momento da importação)
    agent_sections = [s for s in sections if s["agent"] != "claude"]

    for s in agent_sections:
        chunk = MemoryChunk(
            content=s["text"],
            agent=s["agent"],
            round_num=s["round"],
            topic=topic,
            confidence=0.75,  # score neutro para dados históricos
            node_type=s["node_type"],
            metadata={"imported_from": path.name, "date": date},
        )
        result = persist_memory(chunk)

        if result.status != "failed":
            chunks_saved += 1
            rnd = s["round"]
            node_ids_by_round.setdefault(rnd, {})[s["agent"]] = result.node_id
            print(f"       OK [{s['agent']:8}] rodada {str(rnd):8} -> {result.status}")
        else:
            print(f"       ERR [{s['agent']:8}] rodada {str(s['round']):8} -> FALHOU")

    # Grava arestas entre agentes da mesma rodada
    for rnd, agents_nodes in node_ids_by_round.items():
        agent_list = list(agents_nodes.keys())
        responses_by_agent = {
            s["agent"]: s["text"]
            for s in sections
            if s["round"] == rnd and s["agent"] in agents_nodes
        }
        for i in range(len(agent_list)):
            for j in range(i + 1, len(agent_list)):
                a, b = agent_list[i], agent_list[j]
                if a in responses_by_agent and b in responses_by_agent:
                    dist = compute_pairwise_distance(responses_by_agent[a], responses_by_agent[b])
                    relation = "contradicts" if dist > 0.6 else "complements"
                    try:
                        write_edge(agents_nodes[a], agents_nodes[b], relation, strength=dist)
                    except Exception:
                        pass

    return chunks_saved


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    md_files = sorted(LOGS_DIR.glob("*.md"))

    if not md_files:
        print("Nenhum arquivo .md encontrado em logs/")
        return

    sep = "=" * 60
    print(sep)
    print("  IMPORTACAO DE DEBATES HISTORICOS")
    if DRY_RUN:
        print("  MODO: DRY-RUN (nada sera gravado)")
    print(f"  Arquivos encontrados: {len(md_files)}")
    print(f"  Nos antes: {node_count()}")
    print(sep)

    total_chunks = 0
    total_files = 0

    for path in md_files:
        n = import_file(path, dry_run=DRY_RUN)
        if n > 0:
            total_chunks += n
            total_files += 1

    print(f"\n{sep}")
    print("  Concluido!")
    print(f"  Arquivos processados: {total_files}/{len(md_files)}")
    label = "que seriam gravados" if DRY_RUN else "gravados"
    print(f"  Chunks {label}: {total_chunks}")
    if not DRY_RUN:
        print(f"  Nos no grafo agora: {node_count()}")
    print(sep)


if __name__ == "__main__":
    main()
