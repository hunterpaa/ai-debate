"""
codebase_rag.py — RAG sobre os arquivos do codebase usando ChromaDB.

Indexa cada arquivo do app como um documento e, para cada IA, recupera os
arquivos mais relevantes ao papel/role específico dela. Substitui o envio
do codebase cru truncado às cegas.

Como funciona:
  1. index_codebase(app_key, files) — cada arquivo vira um chunk no ChromaDB.
     Arquivos > 4000 chars são divididos em sub-chunks com overlap.
  2. retrieve_for_role(app_key, role_description, top_k) — busca semântica
     usando o role_description como query. Retorna os arquivos/trechos mais
     relevantes formatados para injeção no prompt.

Cache: o índice é namespaced por app_key. O hash do conteúdo é guardado num
metadado; se mudar, o índice é recriado.
"""
import hashlib
from pathlib import Path

# ChromaDB já é dependência do compiler.py — reusamos a mesma instância
_chroma_client = None
_collection = None
_indexed_apps: dict[str, str] = {}  # app_key → hash atual indexado


def _get_collection():
    """Retorna a collection ChromaDB para arquivos do codebase, ou None."""
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        SbertEF = embedding_functions.SentenceTransformerEmbeddingFunction
        _chroma_client = chromadb.PersistentClient(path="./debate_memory")
        ef = SbertEF(model_name="all-MiniLM-L6-v2")
        _collection = _chroma_client.get_or_create_collection(
            name="codebase_files",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        return _collection
    except Exception:
        return None


def _hash_files(files: dict[str, str]) -> str:
    h = hashlib.sha256()
    for path in sorted(files.keys()):
        h.update(path.encode("utf-8"))
        h.update(files[path].encode("utf-8", errors="replace"))
    return h.hexdigest()[:16]


def _chunk_file(path: str, content: str, max_chunk: int = 3500, overlap: int = 200) -> list[tuple[str, str]]:
    """Divide arquivo grande em chunks. Retorna lista de (chunk_id, text)."""
    if len(content) <= max_chunk:
        return [(path, content)]
    chunks = []
    start = 0
    idx = 0
    while start < len(content):
        end = min(start + max_chunk, len(content))
        # Tenta quebrar em quebra de linha próxima
        if end < len(content):
            nl = content.rfind("\n", start, end)
            if nl > start + max_chunk // 2:
                end = nl
        chunk_id = f"{path}#part{idx}"
        chunks.append((chunk_id, content[start:end]))
        idx += 1
        start = max(end - overlap, start + 1)
        if start >= len(content):
            break
    return chunks


def _delete_app_index(app_key: str):
    """Remove todos os chunks de um app antes de reindexar."""
    coll = _get_collection()
    if coll is None:
        return
    try:
        existing = coll.get(where={"app_key": app_key})
        ids = existing.get("ids", [])
        if ids:
            coll.delete(ids=ids)
    except Exception:
        pass


def index_codebase(app_key: str, files: dict[str, str]) -> bool:
    """
    Indexa os arquivos do app no ChromaDB. Reindexa apenas se o hash mudou.
    Retorna True se o índice está pronto, False se ChromaDB indisponível.
    """
    coll = _get_collection()
    if coll is None:
        return False

    new_hash = _hash_files(files)
    if _indexed_apps.get(app_key) == new_hash:
        return True  # já indexado e não mudou

    # Verifica se já foi indexado em sessão anterior com mesmo hash
    try:
        sample = coll.get(where={"app_key": app_key}, limit=1)
        metas = sample.get("metadatas") or []
        if metas and metas[0].get("content_hash") == new_hash:
            _indexed_apps[app_key] = new_hash
            return True
    except Exception:
        pass

    # Reindexa
    _delete_app_index(app_key)

    ids, docs, metas = [], [], []
    for path, content in files.items():
        for chunk_id, chunk_text in _chunk_file(path, content):
            full_id = f"{app_key}::{chunk_id}"
            ids.append(full_id)
            # Doc inclui o caminho como contexto pra busca semântica
            docs.append(f"Arquivo: {path}\n\n{chunk_text}")
            metas.append({
                "app_key":      app_key,
                "path":         path,
                "chunk_id":     chunk_id,
                "content_hash": new_hash,
                "size":         len(chunk_text),
            })

    if not ids:
        return False

    try:
        # Adiciona em batches de 50 para evitar timeout do embedding
        BATCH = 50
        for i in range(0, len(ids), BATCH):
            coll.add(
                ids=ids[i:i+BATCH],
                documents=docs[i:i+BATCH],
                metadatas=metas[i:i+BATCH],
            )
        _indexed_apps[app_key] = new_hash
        return True
    except Exception:
        return False


def retrieve_for_role(
    app_key: str,
    role_description: str,
    top_k: int = 4,
    max_total_chars: int = 12000,
) -> str:
    """
    Recupera os arquivos/trechos mais relevantes ao papel da IA.
    Retorna string formatada pronta para injeção no prompt.
    """
    coll = _get_collection()
    if coll is None:
        return ""

    try:
        results = coll.query(
            query_texts=[role_description],
            n_results=top_k,
            where={"app_key": app_key},
            include=["documents", "metadatas", "distances"],
        )
    except Exception:
        return ""

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not docs:
        return ""

    parts = ["## Arquivos relevantes ao seu papel\n"]
    total = len(parts[0])
    for doc, meta, dist in zip(docs, metas, distances):
        sim = 1.0 - float(dist)
        path = meta.get("path", "?")
        chunk_id = meta.get("chunk_id", path)
        header = f"\n### `{chunk_id}` (relevância {sim:.0%})\n```\n"
        footer = "\n```\n"
        budget = max_total_chars - total - len(header) - len(footer) - 80
        if budget <= 200:
            break
        body = doc if len(doc) <= budget else (doc[:budget] + "\n... [truncado]")
        parts.append(header + body + footer)
        total += len(header) + len(body) + len(footer)

    return "".join(parts)


def stats(app_key: str = "") -> dict:
    """Estatísticas do índice (debug)."""
    coll = _get_collection()
    if coll is None:
        return {"available": False}
    try:
        if app_key:
            r = coll.get(where={"app_key": app_key})
            return {
                "available": True,
                "app_key": app_key,
                "indexed_chunks": len(r.get("ids", [])),
            }
        return {
            "available": True,
            "total_chunks": coll.count(),
        }
    except Exception:
        return {"available": False}
