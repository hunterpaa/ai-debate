import os
from pathlib import Path

# ── Anthropic API ─────────────────────────────────────────────────────────────
# Coloque sua chave aqui OU defina a variável de ambiente ANTHROPIC_API_KEY
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")

# ── Claude model ──────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"

# ── Chrome CDP (Remote Debugging Protocol) ───────────────────────────────────
# Chrome precisa ser iniciado com --remote-debugging-port=9222
# Use launch_chrome.py para isso
CDP_URL = "http://localhost:9222"

# ── Debate ────────────────────────────────────────────────────────────────────
DEFAULT_ROUNDS = 3  # rodadas de debate + 1 conclusão automática

# ── URLs das IAs ──────────────────────────────────────────────────────────────
AI_URLS = {
    "chatgpt":  "https://chatgpt.com",
    "deepseek": "https://chat.deepseek.com",
    "gemini":   "https://gemini.google.com/app",
    "grok":     "https://grok.com",
}

# ── Papéis fixos de cada IA ───────────────────────────────────────────────────
AI_ROLES = {
    "chatgpt":  "especialista em criatividade, inovação e geração de ideias disruptivas",
    "deepseek": "especialista em lógica, raciocínio técnico, matemática e programação",
    "gemini":   "especialista em análise visual, design, UX e perspectivas multimídia",
    "grok":     "especialista em crítica construtiva, ceticismo inteligente e provocação intelectual",
}

# ── Timeouts ──────────────────────────────────────────────────────────────────
RESPONSE_TIMEOUT_SEC = 180   # tempo máximo aguardando uma resposta
GENERATION_START_TIMEOUT = 20  # tempo máximo para geração começar (stop button aparecer)

# ── Logs ──────────────────────────────────────────────────────────────────────
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
