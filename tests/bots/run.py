"""Lance une ou plusieurs phases de la campagne : .venv/bin/python -m tests.bots.run <phase> [<phase>…] [--only bot,bot]
Le serveur du banc doit tourner (tests.bots.serve) : son adresse est lue dans state.json."""
from __future__ import annotations

import sys
import traceback

from playwright.sync_api import sync_playwright

from tests.bots import phases, rights, scenario
from tests.bots.bench import anomaly, load_state


def main(argv: list[str]) -> None:
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        only = set(argv[i + 1].split(","))
        argv = argv[:i] + argv[i + 2:]
    origin = load_state()["origin"]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name in argv:
            step = (getattr(scenario, f"phase_{name}", None) or getattr(rights, f"phase_{name}", None)
                    or getattr(phases, f"phase_{name}"))
            print(f"════ phase {name} ════", flush=True)
            try:
                step(browser, origin, only)
            except Exception as e:  # une phase cassée n'arrête pas les suivantes : elle devient une anomalie
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
