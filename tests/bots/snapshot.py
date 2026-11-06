"""Outil de mise au point : arbre d'accessibilité d'une page vue par un bot (sans les options d'heure).
Usage : BOTS_OUT=… .venv/bin/python -m tests.bots.snapshot <bot> <chemin> [attente_ms]"""
import sys

from playwright.sync_api import sync_playwright

from tests.bots.bench import load_state, phone

if __name__ == "__main__":
    key, path = sys.argv[1], sys.argv[2]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        p = phone(b, key, load_state()["origin"], "snapshot")
        p.goto(path)
        p.page.wait_for_timeout(int(sys.argv[3]) if len(sys.argv) > 3 else 4000)
        for line in p.page.locator("body").aria_snapshot().splitlines():
            if "option \"" not in line:
                print(line)
        p.shot("snapshot", full=True)
        p.close()
