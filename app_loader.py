"""
app_loader.py — Carrega o código-fonte de qualquer app para análise pelas IAs.
"""
from pathlib import Path

_TEXT_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx',
    '.html', '.css', '.scss',
    '.json', '.md', '.txt', '.env',
    '.bat', '.sh', '.vbs', '.ps1',
}
_IGNORE_DIRS = {
    'node_modules', '.git', '__pycache__', '.next',
    'dist', 'build', '.venv', 'venv', 'env',
    'logs', '.claude', 'memory',
}
_IGNORE_FILES = {
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    '.gitignore', '.prettierrc', '.eslintrc',
}

# ── Caminhos dos apps ────────────────────────────────────────────────────────

APP_PATHS: dict[str, str] = {
    "meta":        r"C:\Users\thecr\Desktop\META",
    "tanaka":      r"C:\Users\thecr\Desktop\tanaka",
    "mergulho":    r"C:\Users\thecr\Desktop\Matteus-Sub",
    "debate":      str(Path(__file__).parent),
    "aquatech":    r"C:\Users\thecr\Desktop\ClimaTeck",
    "financeira":  r"C:\Users\thecr\Desktop\calculadora-financeira",
}

APP_DISPLAY: dict[str, dict] = {
    "meta": {
        "name":  "Meta App",
        "desc":  "Gerenciador de servidores, portas e apps",
        "icon":  "🔧",
        "roles": {
            "chatgpt":    "especialista em UX e experiência do usuário de dashboards e painéis de controle",
            "deepseek":   "especialista em arquitetura de sistemas, segurança de infraestrutura e performance",
            "gemini":     "especialista em features, roadmap e comparação com ferramentas similares (Portainer, PM2)",
            "perplexity": "auditora factual — pesquisa ferramentas similares no mercado e benchmarks reais",
            "qwen":       "estrategista de escala — avalia pela lente de operações de grande escala e múltiplos servidores",
            "mistral":    "especialista em segurança, privacidade e confiabilidade de sistemas de infraestrutura crítica",
            "grok":       "conecta ao presente — novas ferramentas DevOps, tendências de orquestração e tecnologias de 2025-2026",
        },
    },
    "tanaka": {
        "name":  "Tanaka Sports",
        "desc":  (
            "Ferramenta de jornalismo editorial da Duda (Maria Eduarda, jornalista do Diário de Cuiabá). "
            "NÃO é um app de consumo para atletas — é um mini-CMS de automação. "
            "Fluxo: busca notícias esportivas do GauchAZh (GraphQL) → scraping do conteúdo completo → "
            "busca foto no Google Imagens → legenda automática via Claude Vision → "
            "upload de foto para NextSite CMS → publicação automática via Tampermonkey. "
            "Stack: Node.js/Express (server.js), HTML vanilla PWA (app-duda.html), "
            "Tampermonkey (automação de browser), Claude Haiku API (legendas). "
            "Autenticação dupla no NextSite (login do jornal + login pessoal). "
            "Funciona local (localhost:3003) e em cloud (Render.com) em paralelo."
        ),
        "icon":  "⚡",
        "roles": {
            "chatgpt":    (
                "especialista em UX de ferramentas editoriais e automação de fluxo de publicação. "
                "Analisa a experiência da Duda ao usar o app para publicar matérias esportivas rapidamente: "
                "onde o fluxo trava, onde pode ser mais rápido, como a interface mobile pode melhorar, "
                "e como reduzir os passos até a publicação final."
            ),
            "deepseek":   (
                "especialista em Node.js, web scraping com cheerio, automação de browser via Tampermonkey, "
                "integração com CMSes legados via HTTP/form-data, e gestão de sessões PHP. "
                "Analisa server.js (endpoints, login automático, upload multipart, scraping do GauchAZh), "
                "tampermonkey.js (auto-preenchimento, recuperação de sessão expirada, reCAPTCHA), "
                "e propõe melhorias de robustez, performance e segurança do backend."
            ),
            "gemini":     (
                "especialista em workflows jornalísticos digitais, automação editorial e expansão de produto. "
                "Avalia o fluxo completo de publicação, o que está faltando para a Duda trabalhar mais rápido, "
                "como expandir o app para outros jornalistas ou outros portais, "
                "e quais integrações novas (ex: WhatsApp, Telegram, scheduling) fariam sentido."
            ),
            "perplexity": (
                "auditora factual — pesquisa ferramentas similares de automação jornalística "
                "(WordPress autopublish, n8n, Zapier, Buffer, ferramentas de newsroom) e CMSes como o NextSite. "
                "Verifica riscos reais de segurança de credenciais hardcoded em scripts Tampermonkey. "
                "Cita referências reais, não inventa."
            ),
            "qwen":       (
                "estrategista de escala editorial — avalia o app pela lente de múltiplos jornalistas, "
                "múltiplos portais e múltiplas fontes de notícias além do GauchAZh. "
                "O que mudaria na arquitetura se 10 jornalistas usassem ao mesmo tempo? "
                "Como monetizar ou licenciar a ferramenta para outros veículos regionais?"
            ),
            "mistral":    (
                "especialista em segurança de aplicações web — analisa os problemas críticos reais do app: "
                "credenciais hardcoded no código-fonte (login do jornal e pessoal visíveis no tampermonkey.js), "
                "PHPSESSID salvo em arquivo sem criptografia, server sem autenticação por padrão, "
                "e como resolver cada um desses problemas sem quebrar o fluxo da Duda."
            ),
            "grok":       (
                "conecta ao presente — tendências em automação de newsroom com IA, "
                "headless CMS e APIs de publicação em 2025-2026, "
                "como outros jornais regionais brasileiros estão usando automação editorial, "
                "e se existe algo melhor que Tampermonkey para automação de browser hoje."
            ),
        },
    },
    "mergulho": {
        "name":  "Matteus-Sub",
        "desc":  "Controle de mergulhos — Aquário Municipal de Cuiabá",
        "icon":  "🤿",
        "roles": {
            "chatgpt":    "especialista em UX para apps operacionais de mergulho e segurança aquática",
            "deepseek":   "especialista em arquitetura backend Node.js, Google APIs e integridade dos dados",
            "gemini":     "especialista em features, automação de relatórios e expansão do sistema",
            "perplexity": "auditora factual — normas internacionais de segurança em mergulho profissional e softwares similares",
            "qwen":       "estrategista de escala — avalia expansão para múltiplas unidades aquáticas e grandes aquários",
            "mistral":    "especialista em segurança crítica, compliance operacional e confiabilidade em ambiente subaquático",
            "grok":       "conecta ao presente — novas tecnologias de monitoramento subaquático, IoT e sensores em 2025-2026",
        },
    },
    "aquatech": {
        "name":  "AquaLog",
        "desc":  (
            "Sistema de gestão operacional do Aquário Municipal de Cuiabá, desenvolvido por Matteus "
            "(mergulhador profissional, dono da Matteus-Sub). "
            "Digitaliza operação hoje feita em papel: 22 tanques, 6 sistemas de filtragem (SSV A–F), "
            "8 parâmetros de água (pH, temperatura, NH3, NO2, NO3, GH, KH, O2), "
            "alimentação por tanque, checklists diários SSV Q, controle de mergulhos com timer, "
            "estoque com alertas de nível crítico, 7 funcionários reais, 4 perfis de acesso. "
            "Stack: React 18 + Vite (frontend porta 3009), Node.js + Express (backend porta 3001), "
            "JSON file-based storage (aqualog-data.json). "
            "ATENÇÃO: AquaLog.tsx é um arquivo antigo — o build atual usa App.jsx + páginas em src/pages/. "
            "Funcional com dados reais da operação (equipamentos: Altamar UV, Sanspray blowers, "
            "Astrapool chillers, VEICO filters). "
            "Objetivo futuro: escalar para o Bio Parque (maior aquário de água doce do mundo, "
            "em construção em Cuiabá, previsto 100+ tanques). "
            "Lacunas críticas: sem PWA/offline, sem IA/Claude integrado, sem JWT, "
            "senha em texto plano, JSON não escala para Bio Parque."
        ),
        "icon":  "🐠",
        "roles": {
            "chatgpt":  (
                "Especialista em UX para apps operacionais usados por equipes de campo no dia a dia. "
                "Analisa as 7 páginas do app (Dashboard, Água, Animais, Filtragem, Mergulho, Estoque, Rotina), "
                "identifica onde a experiência vai travar para funcionários sem experiência técnica "
                "usando no celular dentro do aquário, propõe melhorias de usabilidade, "
                "avalia o fluxo de checklists SSV Q vs o papel atual, e o que falta para o onboarding "
                "dos 7 funcionários reais ser bem-sucedido."
            ),
            "deepseek": (
                "Especialista em arquitetura full-stack Node.js + React. "
                "Analisa server/index.js (Express, 185 linhas), server/store.js (persistência JSON), "
                "src/api.js (cliente HTTP), o modelo de dados em aqualog-data.json, "
                "e propõe: migração de JSON para PostgreSQL, autenticação com bcrypt + JWT, "
                "como transformar em PWA com Service Worker para funcionar offline dentro do aquário "
                "(onde pode não ter sinal), e o que muda na arquitetura para escalar para o Bio Parque."
            ),
            "gemini":   (
                "Especialista em gestão de aquários, biologia aquática e operações de aquários públicos. "
                "Avalia se os 8 parâmetros monitorados (pH 6.8–7.5, temp 22–32°C, amônia crítica 0.5ppm etc) "
                "são suficientes para aquário profissional, o que falta no monitoramento de qualidade de água, "
                "se o módulo de alimentação captura o que importa para bem-estar dos animais, "
                "e quais features são críticas para a operação do Bio Parque (100+ tanques, espécies raras)."
            ),
            "perplexity": (
                "Auditora factual — pesquisa como aquários profissionais do mundo gerenciam suas operações "
                "digitalmente (AquaManager, ZooEasy, ZIMS, outros), o que essas ferramentas têm que o "
                "AquaLog ainda não tem, quais parâmetros de água são padrão em aquários certificados, "
                "e quais normas de segurança para mergulhadores em aquários públicos existem no Brasil. "
                "Cita referências reais, não inventa."
            ),
            "qwen": (
                "Estrategista de escala e produto. Avalia o AquaLog pela lente de um sistema que precisa "
                "ir de 22 tanques/1 aquário para 100+ tanques/múltiplos aquários (Bio Parque + futuro SaaS). "
                "O que muda na arquitetura, no modelo de dados e nas features para suportar múltiplas equipes "
                "simultâneas, múltiplos aquários, histórico de anos de operação? "
                "Como monetizar para outros aquários públicos brasileiros?"
            ),
            "mistral": (
                "Especialista em segurança e confiabilidade de sistemas operacionais críticos. "
                "Analisa os riscos reais do AquaLog: senha '1234' em texto plano no aqualog-data.json, "
                "sem autenticação no backend (endpoints públicos), JSON file sem proteção, "
                "o que acontece se o servidor cair no meio de um mergulho registrado, "
                "como garantir que checklists de segurança de mergulho não possam ser pulados, "
                "e compliance para sistema usado com animais vivos e mergulhadores profissionais."
            ),
            "grok": (
                "Conecta o AquaLog ao presente — sensores IoT para monitorar pH/temperatura em tempo real "
                "sem digitação manual (quais existem, quanto custam, como integrar), "
                "o que está acontecendo em tecnologia para aquários e zoológicos em 2025-2026, "
                "como integrar alertas automáticos via WhatsApp/Telegram para a equipe "
                "quando parâmetros saem do limite, e se existe alternativa melhor ao JSON file para "
                "persistência local que funcione offline dentro do aquário."
            ),
        },
    },
    "financeira": {
        "name":  "Calculadora Financeira",
        "desc":  (
            "CONCEITO DE PRODUTO — app ainda não existe, está sendo desenhado. "
            "Calculadora financeira pessoal/empresarial para o mercado brasileiro. "
            "Começa como solução para um amigo, objetivo é virar produto vendável. "
            "Criador já tem stack: React + Vite + Node.js + Express + Claude API + PWA. "
            "Concorrentes: Mobills, Organizze, Conta Azul (todos com problemas). "
            "Público-alvo em consideração: pessoas físicas, autônomos, MEIs. "
            "Modelo de negócio em consideração: freemium + assinatura R$19,90/mês + white-label para contadores. "
            "As IAs devem atuar como consultores de produto — propor funcionalidades, arquitetura, "
            "diferencial, modelo de negócio, roadmap, riscos. NÃO há código para analisar — "
            "o debate é para DEFINIR o que construir e como construir."
        ),
        "icon":  "💰",
        "roles": {
            "chatgpt":    (
                "Designer de produto e especialista em UX financeiro. "
                "Define quais funcionalidades são essenciais para o usuário brasileiro usar o app todo dia "
                "(não só instalar e esquecer), como organizar a interface para ser intuitiva no celular, "
                "quais fluxos causam abandono em apps financeiros, e o que faz alguém pagar "
                "em vez de usar o Mobills grátis. Pensa pela lente do usuário final."
            ),
            "deepseek":   (
                "Arquiteto técnico full-stack especializado em fintech. "
                "Propõe a arquitetura ideal para o produto: stack (React PWA vs nativo, "
                "SQLite local vs PostgreSQL cloud, offline-first vs online-only), "
                "modelo de dados para controle financeiro (contas, categorias, lançamentos, metas, relatórios), "
                "como estruturar para ser white-label, segurança de dados financeiros, "
                "e em que ordem construir para lançar a primeira versão mais rápido."
            ),
            "gemini":     (
                "Especialista em produto financeiro digital e mercado brasileiro de fintechs. "
                "Avalia o posicionamento do produto: qual nicho atacar primeiro "
                "(pessoa física? MEI? autônomo? pequena empresa?), "
                "quais funcionalidades são commodity vs diferencial, "
                "como o Pix muda o comportamento financeiro do brasileiro, "
                "e como integrar IA (Claude) de forma genuinamente útil — "
                "não como gimmick, mas como diferencial real que justifica cobrança."
            ),
            "perplexity": (
                "Auditora factual — pesquisa o mercado real de apps financeiros no Brasil: "
                "quantos usuários têm Mobills/Organizze/GuiaBolso, quanto cobram, "
                "quais são as reviews mais negativas (o que os usuários odeiam), "
                "quais funcionalidades são mais pedidas, "
                "e casos de sucesso de produtos financeiros que saíram de ferramenta pessoal "
                "para produto comercial no Brasil. Cita dados reais."
            ),
            "qwen":       (
                "Estrategista de negócio e monetização. "
                "Define o modelo de negócio ideal: freemium vs pago direto, "
                "quanto cobrar (referência: Organizze R$19,90/mês, Conta Azul R$69/mês), "
                "como estruturar white-label para contadores e escritórios de contabilidade "
                "(que têm dezenas de clientes e pagariam mais), "
                "como crescer de 1 usuário (o amigo) para 100, de 100 para 1000, "
                "e qual é o caminho mais rápido para o primeiro R$1.000/mês recorrente."
            ),
            "mistral":    (
                "Especialista em compliance, segurança e riscos legais de produtos financeiros no Brasil. "
                "Avalia: quais dados financeiros podem ser armazenados sem ser banco/fintech regulada, "
                "como a LGPD se aplica a dados de finanças pessoais, "
                "se precisa de alguma licença do Banco Central para operar, "
                "riscos de responsabilidade se o app der sugestão errada, "
                "e como proteger dados financeiros dos usuários (criptografia, backup, privacidade)."
            ),
            "grok":       (
                "Conecta ao presente — o que está acontecendo agora em fintech e apps financeiros "
                "no Brasil e no mundo em 2025-2026, "
                "quais funcionalidades de IA financeira estão sendo lançadas pelos grandes players, "
                "se open banking/open finance do Banco Central cria oportunidade para integrar "
                "dados bancários automaticamente, "
                "e se existe alguma tendência (ex: finanças por WhatsApp, agentes financeiros com IA) "
                "que o produto deveria surfar agora para ter vantagem competitiva."
            ),
        },
    },
    "debate": {
        "name":  "AI Debate Orchestrator",
        "desc":  "O próprio sistema de debate com super-IA",
        "icon":  "🧬",
        "roles": {
            "chatgpt":    "Arquiteta de Experiência — UX, novos modos e capacidades de colaboração",
            "deepseek":   "Engenheira de Sistema — arquitetura técnica, performance e confiabilidade",
            "gemini":     "Visionária de IA — inteligência coletiva, memória e evolução cognitiva",
            "perplexity": "Auditora de Verdade — verifica propostas com embasamento real e cita precedentes",
            "qwen":       "Estrategista de Escala Global — avalia propostas pela lente de bilhões de usuários",
            "mistral":    "Guardiã de Ética — questiona privacidade, dados e regulações das evoluções propostas",
            "grok":       "Integradora do Presente — traz tendências atuais do ecossistema de IA em 2025-2026",
        },
    },
}


def _file_priority(p: Path) -> int:
    """
    Prioridade de leitura de arquivos:
    0 = primeiro (mais importante para as IAs entenderem o app)
    Documentação e lógica vêm antes de markup/estilo.
    """
    ext = p.suffix.lower()
    if ext in {'.md', '.txt'}:            return 0   # contexto/docs primeiro
    if ext in {'.py', '.js', '.ts', '.tsx', '.jsx'}: return 1   # lógica de código
    if ext in {'.json', '.env', '.sh', '.bat', '.vbs', '.ps1'}: return 2  # config/scripts
    if ext in {'.html'}:                  return 3   # markup (depois da lógica)
    if ext in {'.css', '.scss'}:          return 4   # estilos por último
    return 5


def load_app_codebase(app_key: str, max_chars: int = 200_000) -> str:
    """
    Lê todos os arquivos de código de um app e retorna como string formatada.
    Arquivos de documentação (.md) e lógica (.js/.py) têm prioridade sobre HTML/CSS.
    Retorna mensagem de erro se o diretório não existir.
    """
    path_str = APP_PATHS.get(app_key, "")
    root = Path(path_str)

    if not root.exists():
        return (
            f"[⚠️  Diretório do app '{app_key}' não encontrado: {path_str}]\n"
            f"Configure o caminho correto em app_loader.py → APP_PATHS['{app_key}']"
        )

    files = []
    for p in sorted(root.rglob("*")):
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in _TEXT_EXTENSIONS and p.name not in _IGNORE_FILES:
            files.append(p)

    # Ordena por prioridade (docs/lógica antes de HTML/CSS), depois alfabeticamente dentro de cada grupo
    files.sort(key=lambda p: (_file_priority(p), str(p.relative_to(root)).lower()))

    if not files:
        return f"[Nenhum arquivo de código encontrado em {root}]"

    chunks = []
    total = 0
    omitidos = 0
    for p in files:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            relative = p.relative_to(root)
            header = f"\n{'═'*60}\n📄  {relative}\n{'═'*60}\n"
            entry = header + content + "\n"
            if total + len(entry) > max_chars:
                omitidos += 1
                continue  # pula este arquivo mas tenta os menores seguintes
            chunks.append(entry)
            total += len(entry)
        except Exception:
            pass

    if omitidos:
        chunks.append(
            f"\n[... {omitidos} arquivo(s) omitidos por limite de tamanho ({max_chars // 1000}k chars) ...]\n"
        )

    info = APP_DISPLAY.get(app_key, {})
    header = (
        f"{'═'*60}\n"
        f"🗂  CODEBASE: {info.get('name', app_key)}\n"
        f"    {info.get('desc', '')}\n"
        f"    {len(files)} arquivo(s) | {total // 1000}k chars carregados\n"
        f"{'═'*60}\n"
    )
    return header + "".join(chunks)


def get_app_info(app_key: str) -> dict:
    """Retorna metadados do app (nome, icon, roles)."""
    return APP_DISPLAY.get(app_key, {
        "name": app_key,
        "desc": "",
        "icon": "📦",
        "roles": {
            "chatgpt":  "analista de UX e experiência do usuário",
            "deepseek": "analista técnico de arquitetura e código",
            "gemini":   "analista de produto e roadmap",
        },
    })


def load_app_files(app_key: str, max_file_chars: int = 50_000) -> dict[str, str]:
    """
    Lê todos os arquivos de código de um app e retorna como dict {path_relativo: conteúdo}.
    Usado pelo codebase_summarizer e codebase_rag (em vez do dump cru truncado).

    max_file_chars: corta arquivos individuais muito grandes (raros, mas package-lock etc).
    """
    path_str = APP_PATHS.get(app_key, "")
    root = Path(path_str)

    if not root.exists():
        return {}

    files: dict[str, str] = {}
    paths = []
    for p in sorted(root.rglob("*")):
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in _TEXT_EXTENSIONS and p.name not in _IGNORE_FILES:
            paths.append(p)

    paths.sort(key=lambda p: (_file_priority(p), str(p.relative_to(root)).lower()))

    for p in paths:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_file_chars:
                content = content[:max_file_chars] + f"\n\n[... arquivo truncado em {max_file_chars} chars ...]"
            relative = str(p.relative_to(root)).replace("\\", "/")
            files[relative] = content
        except Exception:
            pass

    return files


def load_app_files(app_key: str, max_file_chars: int = 50_000) -> dict[str, str]:
    """
    Lê todos os arquivos de código de um app e retorna como dict {path_relativo: conteúdo}.
    Usado pelo codebase_summarizer e codebase_rag (em vez do dump cru truncado).

    max_file_chars: corta arquivos individuais muito grandes (raros, mas package-lock etc).
    """
    path_str = APP_PATHS.get(app_key, "")
    root = Path(path_str)

    if not root.exists():
        return {}

    files: dict[str, str] = {}
    paths = []
    for p in sorted(root.rglob("*")):
        if any(part in _IGNORE_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in _TEXT_EXTENSIONS and p.name not in _IGNORE_FILES:
            paths.append(p)

    paths.sort(key=lambda p: (_file_priority(p), str(p.relative_to(root)).lower()))

    for p in paths:
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_file_chars:
                content = content[:max_file_chars] + f"\n\n[... arquivo truncado em {max_file_chars} chars ...]"
            relative = str(p.relative_to(root)).replace("\\", "/")
            files[relative] = content
        except Exception:
            pass

    return files
