"""Relance campagne 2, agent 10 : « Faisons connaissance » (IdentityForm) d'un compte neuf, CGU exigées.
Un toucher simple puis, sur un autre compte neuf, le double toucher ; chaque requête Supabase est notée.
Usage : BOTS_OUT=<dossier> AP_PREFIX=… AP_PHONES=… .venv/bin/python -m tests.bots.acces_public_profil <simple|double>"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots.acces_public import NEW_BOTS, OUT, P, _double_tap, _sign_in_here
from tests.bots.bench import load_state
from tests.bots.common import q, sql


def run(browser, origin: str, mode: str) -> None:
    from tests.bots.setup_accounts import _png
    bot = NEW_BOTS["nora"]
    sql(f"delete from auth.users where phone = {q(bot.phone)}")
    p = P(browser, "nora", origin, f"identite-{mode}", fresh=True)
    page = p.page
    calls: list[str] = []
    page.on("request", lambda r: calls.append(f"→ {r.method} {r.url.split('?')[0][-70:]}") if "supabase" in r.url else None)
    page.on("response", lambda r: calls.append(f"← {r.status} {r.request.method} {r.url.split('?')[0][-70:]}") if "supabase" in r.url else None)
    try:
        p.goto("/events/")
        page.wait_for_timeout(3000)
        _sign_in_here(p, bot)
        photo = OUT / "nora-photo.png"
        photo.write_bytes(_png((200, 80, 140), 256))
        p.type(page.get_by_label("Prénom", exact=True), "Nora", "le prénom")
        p.type(page.get_by_label("Nom", exact=True), "Nouvelle", "le nom")
        p.type(page.get_by_label("Surnom", exact=True), "Bot Nora", "le surnom")
        with page.expect_file_chooser() as fc:
            p.tap(page.get_by_role("button", name="Choisir une photo"), "Choisir une photo")
        fc.value.set_files(str(photo))
        page.wait_for_timeout(1500)
        p.tap(page.get_by_role("button", name="Valider la photo"), "Valider la photo")
        page.wait_for_timeout(2000)
        calls.clear()
        btn = page.get_by_role("button", name="Continuer").first
        if mode == "double":
            _double_tap(p, btn, "Continuer (double)")
        else:
            p.tap(btn, "Continuer")
        sheet = False
        for _ in range(40):
            if page.get_by_role("button", name="J’accepte").count():
                sheet = True
                break
            page.wait_for_timeout(500)
        p.log(f"feuille CGU : {sheet}")
        p.shot("apres-continuer")
        if sheet:
            f.accept_terms_if_asked(p)
            page.wait_for_timeout(8000)
        p.shot("fin")
        p.log("requêtes : " + " | ".join(calls))
        prof = sql(f"""select display_name, avatar_url is not null av,
                       (select count(*) from public.terms_acceptances t where t.user_id = p.id) cgu
                       from public.profiles p where phone = {q(bot.phone)}""")
        p.log(f"base : {prof} ; adresse : {page.url}")
        if not prof or prof[0]["display_name"] != "Bot Nora":
            p.flag("🔴", f"« Faisons connaissance » ({mode}) : profil non enregistré", f"feuille CGU : {sheet} ; {prof}")
        p.save_session()
    finally:
        p.close()


if __name__ == "__main__":
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for m in sys.argv[1:]:
            run(browser, load_state()["origin"], m)
        browser.close()
