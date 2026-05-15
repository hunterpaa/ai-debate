"""
launch_chrome.py — Abre o Chrome com remote debugging ativado.

Execute ESTE script primeiro, depois execute main.py.

Por que é necessário:
  Playwright precisa se conectar ao Chrome via CDP (porta 9222).
  O Chrome usa seu perfil real (logins salvos) em vez de criar um perfil limpo.
  Se o Chrome já estiver aberto sem CDP, ele precisa ser fechado primeiro.
"""

import subprocess
import sys
import os
import time
import urllib.request
import urllib.error

# ── Caminhos do Chrome no Windows ─────────────────────────────────────────────
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
    # Microsoft Edge como alternativa (também funciona com CDP)
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

# Perfil do usuário (usa o perfil padrão onde os logins estão salvos)
USER_DATA_DIR = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data")
CDP_PORT = 9222

def find_browser() -> str | None:
    for path in CHROME_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None

def is_cdp_already_running() -> bool:
    try:
        with urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/version", timeout=2):
            return True
    except Exception:
        return False

def main():
    print("╔══════════════════════════════════════════╗")
    print("║  Chrome CDP Launcher para AI Debate      ║")
    print("╚══════════════════════════════════════════╝\n")

    # Verifica se CDP já está rodando
    if is_cdp_already_running():
        print(f"✓ Chrome já está rodando com CDP na porta {CDP_PORT}.")
        print("  Execute  python main.py  para iniciar o debate.\n")
        return

    # Localiza o executável
    browser_path = find_browser()
    if not browser_path:
        print("✗ Chrome/Edge não encontrado nos caminhos padrão.")
        print("\nSoluções:")
        print("  1. Instale o Google Chrome")
        print("  2. Ou adicione o caminho manualmente em CHROME_CANDIDATES neste arquivo")
        sys.exit(1)

    print(f"✓ Navegador encontrado: {browser_path}")
    print(f"✓ Perfil: {USER_DATA_DIR}")
    print(f"\n⚠  Se o Chrome já estiver aberto, FECHE-O antes de continuar.")
    input("   Pressione Enter quando o Chrome estiver fechado...")

    cmd = [
        browser_path,
        f"--remote-debugging-port={CDP_PORT}",
        "--remote-debugging-address=127.0.0.1",   # FIX: necessário no Windows para vincular a porta
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--profile-directory=Default",             # garante o perfil principal com logins salvos
        # Abre as 4 abas do debate diretamente
        "https://chatgpt.com",
        "https://chat.deepseek.com",
        "https://gemini.google.com/app",
        "https://grok.com",
    ]

    print(f"\n→ Iniciando Chrome com CDP na porta {CDP_PORT}...")
    proc = subprocess.Popen(cmd)
    print(f"  PID: {proc.pid}")

    # Aguarda CDP ficar disponível — Chrome precisa de ~6-8s no Windows
    print("\n  Aguardando CDP ficar disponível", end="", flush=True)
    for _ in range(30):          # até 30 segundos
        time.sleep(1)
        print(".", end="", flush=True)
        if is_cdp_already_running():
            break
    print()

    if is_cdp_already_running():
        print("\n✓ CDP ativo! Chrome pronto com seu perfil e logins.")
        print("\nPróximos passos:")
        print("  1. Verifique se está logado nas 4 IAs nas abas abertas")
        print("  2. Depois execute:  python main.py")
        print("\n(Mantenha este terminal aberto enquanto o debate rodar)")
    else:
        print("\n✗ CDP não respondeu após 30s. Tente:")
        print("  - Feche o Chrome e execute este script novamente")
        print("  - Ou execute main.py mesmo assim (pode funcionar)")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nChrome encerrado.")

if __name__ == "__main__":
    main()
