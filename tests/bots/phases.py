"""Phases de la campagne des bots (ordre : voir README)."""
from __future__ import annotations

from tests.bots.bench import phone
from tests.bots.common import BOTS


def _keys(only, account=True):
    return [b.key for b in BOTS if (b.has_account_at_start or not account) and (not only or b.key in only)]


def phase_connexion(browser, origin, only):
    """Chaque bot avec un compte se connecte (numéro + code fixe) et regarde la liste des événements."""
    for key in _keys(only):
        p = phone(browser, key, origin, "connexion")
        try:
            p.sign_in()
            p.see(p.page.get_by_label("Rechercher un événement"), "la liste des événements", 30000)
            p.shot("liste")
            p.finger_scroll("liste des événements")
            p.check_texts_cut("liste")
        finally:
            p.close()


def phase_essai(browser, origin, only):
    """Essai : ouvre le formulaire et capture (mise au point du banc)."""
    p = phone(browser, "orga1", origin, "essai")
    try:
        p.goto("/events/event/new")
        p.page.wait_for_timeout(3000)
        p.shot("form-haut")
        p.shot("form-complet", full=True)
        print(p.page.accessibility.snapshot() if hasattr(p.page, "accessibility") else "")
    finally:
        p.close()


def phase_creation_simple(browser, origin, only):
    from tests.bots.flows import create_simple
    from tests.bots.bench import save_state
    p = phone(browser, "orga1", origin, "creation-simple")
    try:
        eid = create_simple(p, "Bot Raclette (simple)", 5, ["Bots"])
        p.log(f"événement créé : {eid}")
        if eid:
            save_state(e_simple=eid)
            p.shot("fiche-apres-publication")
            p.shot("fiche-complete", full=True)
            p.scroll_to_bottom("fiche")
    finally:
        p.close()


def phase_explore_invite(browser, origin, only):
    from tests.bots.bench import load_state
    p = phone(browser, "orga1", origin, "explore")
    try:
        p.goto(f"/events/event/{load_state()['e_simple']}")
        p.page.wait_for_timeout(3000)
        p.tap(p.page.get_by_role("button", name="Inviter", exact=True), "Inviter")
        p.page.wait_for_timeout(1500)
        p.shot("feuille-inviter")
        print(p.dump("feuille-inviter"))
    finally:
        p.close()
