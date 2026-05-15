import os
from pathlib import Path

# ── Anthropic API ─────────────────────────────────────────────────────────────
# Defina via variável de ambiente ou substitua pela sua chave
ANTHROPIC_API_KEY = (
    os.environ.get("ANTHROPIC_API_KEY")
    or "sk-ant-..."  # cole sua chave aqui
)

# ── Claude models ─────────────────────────────────────────────────────────────
CLAUDE_MODEL      = "claude-sonnet-4-6"
CLAUDE_MODEL_FAST = "claude-haiku-4-5-20251001"

# ── Perfil dedicado do browser ────────────────────────────────────────────────
# Na primeira execução, setup.py abre o browser para você fazer login nas IAs.
DEBATE_PROFILE_DIR = Path(os.environ.get("DEBATE_PROFILE_DIR",
    str(Path.home() / "AppData" / "Local" / "chrome-debate-profile")))

BROWSER_CHANNEL = "chrome"

# ── Debate ────────────────────────────────────────────────────────────────────
DEFAULT_ROUNDS = 3

# ── URLs das IAs ──────────────────────────────────────────────────────────────
AI_URLS = {
    "chatgpt":    "https://chatgpt.com",
    "deepseek":   "https://chat.deepseek.com",
    "gemini":     "https://gemini.google.com/app",
    "perplexity": "https://www.perplexity.ai",
    "qwen":       "https://chat.qwen.ai",
    "mistral":    "https://chat.mistral.ai",
    "grok":       "https://grok.com",
}

# ── Papéis fixos de cada IA ───────────────────────────────────────────────────
AI_ROLES = {
    "chatgpt":    "especialista em criatividade, inovação e geração de ideias disruptivas",
    "deepseek":   "especialista em lógica, raciocínio técnico, matemática e programação",
    "gemini":     "especialista em análise visual, design, UX e perspectivas multimídia",
    "perplexity": "âncora factual — cita fontes reais e questiona afirmações sem evidência",
    "qwen":       "especialista em mercado asiático — perspectiva oriental em escala de bilhões",
    "mistral":    "especialista em ética, privacidade e soberania de dados — perspectiva europeia GDPR",
    "grok":       "repórter em tempo real — traz dados e eventos atuais, questiona com o presente",
}

# ── Timeouts ──────────────────────────────────────────────────────────────────
RESPONSE_TIMEOUT_SEC = 180
GENERATION_START_TIMEOUT = 20

# ── Logs ──────────────────────────────────────────────────────────────────────
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
