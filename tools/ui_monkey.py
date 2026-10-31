#!/usr/bin/env python3
"""Bots navigateur : trois téléphones (Chromium, format iPhone) ouvrent chaque jeu et touchent au hasard les boutons
visibles, jusqu'à une heure donnée. Note chaque erreur JavaScript de la page et chaque trace du serveur.

  PYTHONPATH=. .venv/bin/python tools/ui_monkey.py <rapport.txt> <HH:MM fin>
"""
import datetime as dt
import random
import sys
import time
from collections import Counter

from playwright.sync_api import sync_playwright

from tests.e2e.helpers import Phone, Server

GAMES = ["beerpong", "room", "biskit", "never", "whoof", "likely", "debate", "blackjack", "casino", "pyramid", "divan",
         "tmc", "quiz", "undercover", "roulette", "president"]
SAFE = ('#gamePlay button:visible:not([disabled]):not([data-gdrawer="exit"]):not([data-gact="end"]):not(.g-quit)'
        ', #gPause button:visible')


def main_cli():
    report, hhmm = sys.argv[1], sys.argv[2]
    h, m = map(int, hhmm.split(":"))
    until = dt.datetime.now().replace(hour=h, minute=m, second=0)
    if until <= dt.datetime.now():
        until += dt.timedelta(days=1)
    rng = random.Random(int(time.time()))
    js, server_traces, taps, rounds = Counter(), [], 0, 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        while dt.datetime.now() < until:
            server = Server()
            phones = [Phone(browser, server, n) for n in ("Boby", "Lea", "Tom")]
            try:
                kind = rng.choice(GAMES)
                code = phones[0].create(kind)
                for p in phones[1:]:
                    p.join(code)
                    p.act("join")
                phones[0].act("addguest", guess="Mamie")
                end = time.time() + 90
                while time.time() < end and dt.datetime.now() < until:
                    p = rng.choice(phones)
                    btns = p.page.locator(SAFE)
                    n = btns.count()
                    if n:
                        try:
                            btns.nth(rng.randrange(n)).evaluate("el => el.click()", timeout=1500)
                            taps += 1
                        except Exception:
                            pass
                    time.sleep(rng.uniform(0.05, 0.25))
                rounds += 1
            except Exception as e:
                js[f"[bot] {kind}: {type(e).__name__}: {str(e)[:120]}"] += 1
            finally:
                for p in phones:
                    for err in p.errors:
                        js[f"{kind}: {err[:200]}"] += 1
                    p.close()
                trace = server.errors()
                if trace:
                    server_traces.append(f"--- {kind}\n{trace[-1500:]}")
                server.stop()
            with open(report, "w") as f:
                f.write(f"Bots navigateur : {rounds} parties, {taps} touchers\n")
                f.write(f"Erreurs JavaScript : {sum(js.values())}\n")
                for k, c in js.most_common(30):
                    f.write(f"  ×{c} {k}\n")
                f.write(f"Traces serveur : {len(server_traces)}\n")
                f.write("\n".join(server_traces[-10:]))
        browser.close()


if __name__ == "__main__":
    main_cli()
