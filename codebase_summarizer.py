"""
codebase_summarizer.py — Resume o codebase de um app via Claude Haiku, com cache por hash.

Substitui o dump bruto de 200k chars que era enviado para as IAs (e brutalmente
truncado para 12k pelos limites de input dos sites). Em vez disso, gera um resumo
estruturado de ~3.000 chars que dá panorama do app a TODAS as IAs participantes,
e o RAG (codebase_rag.py) complementa com os arquivos relevantes ao papel de cada IA.

Cache: hash sha256 do conteúdo concatenado de todos os arquivos. Se nada mudou,
reusa o resumo sem chamar a API. Cache fica em memory/codebase_cache/.
"""
import hashlib
import json
from pathlib import Path
from datetime import datetime

import anthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL_FAST

CACHE_DIR = Path(__file__).parent / "memory" / "codebase_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_CLIENT = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=120.0)

_SYSTEM_SUMMARY = """\
Você é um analista de software experiente. Recebe o código-fonte completo de um app e produz \
um resumo estruturado para outras IAs especialistas analisarem o app sem precisar ler tudo.

Formato OBRIGATÓRIO (markdown, máximo 3000 caracteres):

## O que o app faz
[2-3 frases: propósito, usuário-alvo, função principal]

## Stack e arquitetura
[Linguagens, frameworks, principais dependências, padrão arquitetural]

## Mapa dos arquivos principais
Para cada arquivo importante (no máximo 12):
- `caminho/arquivo.ext` — o que faz, em uma frase

## Pontos críticos visíveis
[Bugs óbvios, gambiarras, credenciais hardcoded, vulnerabilidades, performance ruim — \
no máximo 5 itens, citando arquivo e linha quando possível]

## Oportunidades de melhoria
[Melhorias estruturais possíveis, no máximo 5 itens]

Seja direto, técnico, sem elogios. Cite caminhos de arquivo reais. Não invente nada \
que não está no código.\
"""


def _hash_files(files: dict[str, str]) -> str:
    """Calcula sha256 estável do conjunto de arquivos."""
    h = hashlib.sha256()
    for path in sorted(files.keys()):
        h.update(path.encode("utf-8"))
        h.update(b"\0")
        h.update(files[path].encode("utf-8", errors="replace"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def _cache_path(app_key: str, hash_id: str) -> Path:
    return CACHE_DIR / f"{app_key}_{hash_id}.md"


def _meta_path(app_key: str, hash_id: str) -> Path:
    return CACHE_DIR / f"{app_key}_{hash_id}.json"


def get_or_create_summary(
    app_key: str,
    files: dict[str, str],
    max_codebase_chars: int = 80_000,
) -> str:
    """
    Retorna o resumo do codebase. Usa cache por hash do conteúdo.

    files: dict {caminho_relativo: conteúdo}
    max_codebase_chars: trunca o codebase enviado ao Haiku (não o resumo).
    """
    if not files:
        return f"[Nenhum arquivo encontrado para o app '{app_key}']"

    hash_id = _hash_files(files)
    cache = _cache_path(app_key, hash_id)

    # Cache hit
    if cache.exists():
        try:
            return cache.read_text(encoding="utf-8")
        except Exception:
            pass  # fallback: regenera

    # Monta o codebase para o Haiku, respeitando max_codebase_chars
    chunks = []
    total = 0
    omitidos = 0
    for path in sorted(files.keys()):
        content = files[path]
        entry = f"\n=== {path} ===\n{content}\n"
        if total + len(entry) > max_codebase_chars:
            omitidos += 1
            continue
        chunks.append(entry)
        total += len(entry)
    if omitidos:
        chunks.append(f"\n[... {omitidos} arquivo(s) omitidos por limite de input ao resumidor ...]\n")

    user_msg = (
        f"App: {app_key}\n"
        f"Total de arquivos no app: {len(files)}\n"
        f"Tamanho total enviado: {total // 1000}k chars\n\n"
        f"CÓDIGO-FONTE:\n{''.join(chunks)}\n\n"
        "---\nProduza o resumo estruturado conforme as instruções."
    )

    try:
        msg = _CLIENT.messages.create(
            model=CLAUDE_MODEL_FAST,
            max_tokens=1500,
            system=_SYSTEM_SUMMARY,
            messages=[{"role": "user", "content": user_msg}],
        )
        summary = msg.content[0].text.strip()
    except Exception as exc:
        # Fallback local: lista os arquivos
        summary = _local_fallback(app_key, files, str(exc))

    # Persiste cache
    try:
        cache.write_text(summary, encoding="utf-8")
        _meta_path(app_key, hash_id).write_text(
            json.dumps({
                "app_key": app_key,
                "hash":    hash_id,
                "files":   len(files),
                "ts":      datetime.now().isoformat(),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return summary


def _local_fallback(app_key: str, files: dict[str, str], error: str) -> str:
    """Resumo mínimo gerado localmente quando o Haiku falha."""
    lines = [
        f"## Resumo local — {app_key}",
        f"_(API Haiku indisponível: {error[:100]} — usando fallback)_\n",
        f"## Mapa dos arquivos ({len(files)} total)",
    ]
    for path in sorted(files.keys())[:20]:
        size = len(files[path])
        lines.append(f"- `{path}` ({size // 1000}k chars)")
    if len(files) > 20:
        lines.append(f"- ... e mais {len(files) - 20} arquivos")
    return "\n".join(lines)


def clear_cache_for(app_key: str):
    """Remove cache de um app específico (útil quando você quer forçar reanálise)."""
    for f in CACHE_DIR.glob(f"{app_key}_*.md"):
        try:
            f.unlink()
        except Exception:
            pass
    for f in CACHE_DIR.glob(f"{app_key}_*.json"):
        try:
            f.unlink()
        except Exception:
            pass
