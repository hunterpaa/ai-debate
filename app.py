import asyncio
import json
import logging
import sys
import threading
import traceback
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    filename=str(Path(__file__).parent / "error.log"),
    level=logging.ERROR,
    format="%(asctime)s %(message)s",
    encoding="utf-8",
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from modes import MODES
from orchestrator import run_debate


@asynccontextmanager
async def lifespan(application):
    def _handler(loop, context):
        if isinstance(context.get("exception"), ConnectionResetError):
            return
        loop.default_exception_handler(context)
    asyncio.get_event_loop().set_exception_handler(_handler)
    yield


app = FastAPI(title="AI Debate Orchestrator", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/erro", response_class=HTMLResponse)
async def ver_erros():
    log = Path(__file__).parent / "error.log"
    content = log.read_text(encoding="utf-8") if log.exists() else "Nenhum erro registrado ainda."
    return f"""<html><head><meta charset='utf-8'>
    <style>body{{background:#0a0a10;color:#e2e2f0;font-family:monospace;padding:2rem}}
    pre{{background:#111118;border:1px solid #1e1e2e;padding:1rem;border-radius:8px;
         white-space:pre-wrap;word-break:break-all;font-size:0.85rem;color:#f87171}}
    a{{color:#4d9fff}}</style></head>
    <body><h2 style='color:#f59e0b'>Log de Erros</h2>
    <a href='/'>← Voltar</a><br><br>
    <pre>{content}</pre>
    <script>setTimeout(()=>location.reload(), 5000)</script>
    </body></html>"""


# ── API: Modes & Logs ─────────────────────────────────────────────────────────

@app.get("/api/modes")
async def get_modes():
    return [
        {"key": m.key, "name": m.name, "description": m.description, "icon": m.icon}
        for m in MODES.values()
    ]


@app.get("/api/logs")
async def list_logs():
    from config import LOGS_DIR
    files = sorted(LOGS_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.name, "path": str(f)} for f in files[:20]]


@app.get("/api/logs/{filename}")
async def get_log(filename: str):
    from config import LOGS_DIR
    path = LOGS_DIR / filename
    if not path.exists() or not path.is_file():
        return {"error": "arquivo não encontrado"}
    return {"content": path.read_text(encoding="utf-8")}


# ── API: Preview (modo auto) ──────────────────────────────────────────────────

class PreviewRequest(BaseModel):
    topic: str
    custom_context: str = ""


@app.post("/api/preview")
async def preview_selection(req: PreviewRequest):
    """
    Retorna quais IAs Claude selecionaria para o contexto, antes de iniciar o debate.
    Use no modo auto para mostrar a seleção ao usuário antes de confirmar.
    """
    from smart_engine import detect_mode
    full_topic = req.topic
    if req.custom_context:
        full_topic += "\n\n" + req.custom_context
    try:
        result = await asyncio.to_thread(detect_mode, full_topic)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── WebSocket: Debate ─────────────────────────────────────────────────────────

@app.websocket("/ws/debate")
async def debate_websocket(websocket: WebSocket):
    await websocket.accept()

    async def emit(event: dict):
        try:
            await websocket.send_text(json.dumps(event, ensure_ascii=False))
        except Exception:
            pass

    try:
        raw    = await websocket.receive_text()
        config = json.loads(raw)

        topic             = config.get("topic", "").strip()
        mode_key          = config.get("mode", "auto")
        num_rounds        = max(1, min(int(config.get("rounds", 3)), 5))
        custom_context    = config.get("custom_context", "").strip()
        debate_id         = config.get("debate_id") or str(uuid.uuid4())
        preselected_roles = config.get("preselected_roles") or None

        if mode_key not in MODES:
            await emit({"type": "error", "message": f"Modo '{mode_key}' não existe. Use 'auto' ou 'turbo'."})
            return

        if not topic:
            await emit({"type": "error", "message": "Tema não pode ser vazio."})
            return

        await emit({"type": "debate_id", "debate_id": debate_id})

        loop  = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def emit_from_thread(event: dict):
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def debate_thread():
            tloop = asyncio.new_event_loop()
            asyncio.set_event_loop(tloop)

            async def thread_emit(event):
                emit_from_thread(event)

            try:
                tloop.run_until_complete(
                    run_debate(
                        topic, num_rounds, mode_key,
                        thread_emit, custom_context, debate_id,
                        preselected_roles,
                    )
                )
            except Exception as exc:
                logging.error(traceback.format_exc())
                emit_from_thread({"type": "error", "message": str(exc)})
            finally:
                emit_from_thread(None)
                tloop.close()

        threading.Thread(target=debate_thread, daemon=True).start()

        while True:
            event = await queue.get()
            if event is None:
                break
            await websocket.send_text(json.dumps(event, ensure_ascii=False))

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        await emit({"type": "error", "message": "Payload inválido."})
    except Exception as exc:
        logging.error(traceback.format_exc())
        try:
            await emit({"type": "error", "message": str(exc)})
        except Exception:
            pass


if __name__ == "__main__":
    print("\n╔══════════════════════════════════════════╗")
    print("║    AI DEBATE ORCHESTRATOR                ║")
    print("╠══════════════════════════════════════════╣")
    print("║  http://localhost:3007                   ║")
    print("║                                          ║")
    print("║  Modos disponíveis:                      ║")
    print("║  🎯 auto  — Claude escolhe as IAs        ║")
    print("║  ⚡ turbo — Todas as 7 IAs debatem       ║")
    print("╚══════════════════════════════════════════╝\n")
    uvicorn.run(app, host="0.0.0.0", port=3007, log_level="info")
