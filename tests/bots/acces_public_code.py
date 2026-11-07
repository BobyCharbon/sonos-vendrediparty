"""Relance campagne 2, agent 10 : double toucher « Recevoir un code par SMS » (le 2e toucher ouvre la Confidentialité ?)
puis retour arrière : l'étape du code est-elle gardée ?
Usage : BOTS_OUT=<dossier> AP_PHONES=… .venv/bin/python -m tests.bots.acces_public_code"""
from __future__ import annotations

from playwright.sync_api import sync_playwright

from tests.bots.acces_public import NEW_BOTS, P, _double_tap
from tests.bots.bench import load_state


def run(browser, origin: str) -> None:
    bot = NEW_BOTS["noe"]
    p = P(browser, "noe", origin, "code-double", fresh=True)
    page = p.page
    try:
        p.goto("/events/")
        field = page.get_by_label("Ton numéro de téléphone", exact=True)
        field.wait_for(timeout=60000)
        p.type(field, "0" + bot.phone[2:], "le numéro")
        _double_tap(p, page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS")
        page.wait_for_timeout(4000)
        p.shot("apres-double")
        p.log(f"après le double toucher : {page.url}")
        on_privacy = "/privacy" in page.url
        if on_privacy:
            p.flag("🟡", "double toucher « Recevoir un code » : le 2e toucher ouvre la page Confidentialité", page.url)
            back = page.get_by_role("button", name="sign-in")
            p.log(f"bouton retour lu « sign-in » : {back.count() > 0}")
            page.go_back()
            page.wait_for_timeout(3000)
            p.shot("retour")
            code = page.get_by_placeholder("123456", exact=True)
            p.log(f"retour : {page.url} ; champ du code visible : {code.count() > 0}")
            if not code.count():
                p.flag("🟠", "après la Confidentialité, retour : l'étape du code est perdue (il faut redemander un code)",
                       page.locator("body").inner_text()[:300])
    finally:
        p.close()


if __name__ == "__main__":
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        run(browser, load_state()["origin"])
        browser.close()
