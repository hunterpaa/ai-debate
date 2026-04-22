"""
app.py — API web para o AI Debate Orchestrator.

Uso:
  pip install flask
  python app.py

Endpoints:
  POST /debate   → inicia debate, retorna resultado JSON
  GET  /modes    → lista modos disponíveis
"""

import asyncio
import threading
from flask import Flask, request, jsonify, Response, stream_with_context
import json

from config import ANTHROPIC_API_KEY
from modes import MODES, DEFAULT_MODE
from orchestrator import run_debate

app = Flask(__name__)

# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.route("/modes", methods=["GET"])
def list_modes():
    return jsonify({
        name: list(mode.ai_roles.keys())
        for name, mode in MODES.items()
    })


@app.route("/debate", methods=["POST"])
def start_debate():
    """
    Body JSON:
      topic    (str, obrigatório)
      mode     (str, default "debate")
      rounds   (int, default 3)
      quick    (bool, default false)
      stream   (bool, default false) — se true, usa SSE
    """
    data = request.get_json(force=True, silent=True) or {}

    topic = data.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Campo 'topic' é obrigatório"}), 400

    mode_name = data.get("mode", DEFAULT_MODE.name)
    if mode_name not in MODES:
        return jsonify({"error": f"Modo '{mode_name}' inválido. Disponíveis: {list(MODES)}"}), 400

    mode  = MODES[mode_name]
    rounds = int(data.get("rounds", 3))
    quick  = bool(data.get("quick", False))
    stream = bool(data.get("stream", False))

    if stream:
        return _stream_debate(topic, rounds, mode, quick)
    else:
        return _blocking_debate(topic, rounds, mode, quick)


def _blocking_debate(topic, rounds, mode, quick):
    """Executa o debate de forma bloqueante e retorna JSON ao final."""
    try:
        result = asyncio.run(run_debate(
            topic=topic,
            num_rounds=rounds,
            mode=mode,
            quick=quick,
            emit=None,
        ))
        result.pop("history", None)  # omite histórico completo por padrão
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def _stream_debate(topic, rounds, mode, quick):
    """Executa o debate com Server-Sent Events para streaming de eventos."""
    event_queue: list[str] = []
    done = threading.Event()

    def emit_fn(event: dict):
        event_queue.append(f"data: {json.dumps(event, ensure_ascii=False)}\n\n")

    def run_in_thread():
        asyncio.run(run_debate(
            topic=topic,
            num_rounds=rounds,
            mode=mode,
            quick=quick,
            emit=emit_fn,
        ))
        done.set()

    thread = threading.Thread(target=run_in_thread, daemon=True)
    thread.start()

    def generate():
        sent = 0
        while not done.is_set() or sent < len(event_queue):
            while sent < len(event_queue):
                yield event_queue[sent]
                sent += 1
            import time
            time.sleep(0.1)
        yield "data: {\"type\": \"done\"}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "SUA_CHAVE_AQUI":
        print("✗ Configure ANTHROPIC_API_KEY em config.py ou como variável de ambiente.")
    else:
        print("AI Debate API iniciando em http://localhost:5000")
        app.run(host="0.0.0.0", port=5000, debug=False)
