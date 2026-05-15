"""
setup.py — Primeira configuração do AI Debate Orchestrator.

Execute UMA VEZ antes de usar main.py.
Abre o browser com o perfil dedicado para que você faça login nas 4 IAs.
Os logins ficam salvos para sempre — não precisa repetir.

Uso:
  python setup.py
"""

import asyncio
from playwright.async_api import async_playwright
from config import DEBATE_PROFILE_DIR, BROWSER_CHANNEL, AI_URLS


async def setup():
    print("╔══════════════════════════════════════════╗")
    print("║    AI Debate — Configuração Inicial      ║")
    print("╚══════════════════════════════════════════╝\n")

    DEBATE_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Perfil de debate: {DEBATE_PROFILE_DIR}\n")

    print("O browser vai abrir com as 4 abas das IAs.")
    print("Faça login em cada uma. Depois volte aqui e pressione Enter.\n")
    input("Pressione Enter para abrir o browser...")

    async with async_playwright() as pw:
        launch_kwargs = dict(
            user_data_dir=str(DEBATE_PROFILE_DIR),
            headless=False,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ],
            ignore_default_args=["--enable-automation"],
        )

        try:
            if BROWSER_CHANNEL:
                context = await pw.chromium.launch_persistent_context(
                    channel=BROWSER_CHANNEL, **launch_kwargs
                )
                print(f"✓ Chrome ({BROWSER_CHANNEL}) iniciado")
            else:
                raise Exception("sem canal")
        except Exception as e:
            print(f"  Chrome falhou ({e}), usando Chromium do Playwright...")
            context = await pw.chromium.launch_persistent_context(**launch_kwargs)
            print("✓ Chromium iniciado")

        # Abre as 3 abas (Grok removido)
        pages = {}
        for ai, url in AI_URLS.items():
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            pages[ai] = page
            print(f"  ✓ [{ai}] → {url}")
            await asyncio.sleep(1)

        print(f"\n{'─'*50}")
        print("Faça login nas 4 IAs no browser que abriu.")
        print("Quando terminar, volte aqui.")
        print(f"{'─'*50}\n")
        input("Pressione Enter quando estiver logado em todas as 4 IAs...")

        # Verifica se as abas ainda estão abertas
        logged = []
        for ai, page in pages.items():
            try:
                url = page.url
                logged.append(f"  ✓ {ai}: {url[:60]}")
            except Exception:
                logged.append(f"  ? {ai}: aba fechada")
        print("\nStatus das abas:")
        print("\n".join(logged))

        await context.close()

    print(f"\n{'═'*50}")
    print("✓ Setup concluído! Logins salvos no perfil de debate.")
    print("\nAgora execute:  python main.py")
    print(f"{'═'*50}\n")


if __name__ == "__main__":
    asyncio.run(setup())
