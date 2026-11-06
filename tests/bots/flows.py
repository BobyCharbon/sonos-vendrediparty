"""Gestes réutilisables des bots dans le module Événements (vrais écrans, vrais boutons)."""
from __future__ import annotations

import re
from datetime import date, timedelta

from tests.bots.bench import Phone

EVENT_URL = re.compile(r"/events/event/([0-9a-f-]{36})")


def day(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def event_id(p: Phone) -> str | None:
    m = EVENT_URL.search(p.page.url)
    return m.group(1) if m else None


def chip(p: Phone, name: str, exact: bool = False):
    """Puce (bouton) ; une puce choisie commence par « ✓ »."""
    return p.page.get_by_role("button", name=re.compile(rf"^(✓ )?{re.escape(name)}{'$' if exact else ''}"))


def selected(locator) -> bool:
    return (locator.get_attribute("aria-label") or locator.inner_text()).startswith("✓")


def set_date(p: Phone, label: str, when: str, hour: str) -> None:
    page = p.page
    p.log(f"règle {label} : {when} {hour}")
    page.get_by_label(f"{label} : jour", exact=True).fill(when)
    page.get_by_label(f"{label} : heure", exact=True).select_option(hour)


def toggle(p: Phone, label: str, on: bool = True) -> None:
    sw = p.page.get_by_label(label, exact=True)
    sw.scroll_into_view_if_needed()
    if sw.is_checked() != on:
        p.tap(sw, f"interrupteur {label} → {'oui' if on else 'non'}")
    else:
        p.log(f"interrupteur {label} déjà {'oui' if on else 'non'}")


def accept_terms_if_asked(p: Phone) -> bool:
    """Feuille CGU (terms_required) : le bot la lit jusqu'en bas (au doigt) et accepte."""
    page = p.page
    accept = page.get_by_role("button", name=re.compile("J.accepte"))
    try:
        accept.first.wait_for(state="visible", timeout=5000)
    except Exception:
        return False
    p.shot("cgu")
    p.scroll_to_bottom("feuille CGU", tries=3)
    p.tap(accept.first, "J'accepte (CGU)")
    page.wait_for_timeout(1500)
    return True


def submit(p: Phone, label: str = "Publier") -> str | None:
    page = p.page
    p.tap(page.get_by_role("button", name=label, exact=True).last, label)
    page.wait_for_timeout(2500)
    if accept_terms_if_asked(p):
        p.log("CGU acceptées, nouvel essai attendu")
        page.wait_for_timeout(2500)
    try:
        page.wait_for_url(EVENT_URL, timeout=15000)
    except Exception:
        p.flag("🔴", f"« {label} » n'ouvre pas la fiche de l'événement", page.url)
        return None
    page.wait_for_timeout(2000)
    return event_id(p)


def fill(p: Phone, label: str, text: str) -> None:
    field = p.page.get_by_label(label, exact=True).first
    field.scroll_into_view_if_needed()
    p.type(field, text, label)


def audience_invite_groups(p: Phone, groups: list[str]) -> None:
    invite = chip(p, "Sur invitation", exact=True)
    if not selected(invite):
        p.tap(invite, "Sur invitation")
    vip = chip(p, "👥 Vendredi Party")
    # Vendredi Party contient de vrais membres : jamais choisi par un bot (coché par défaut !)
    if vip.count() and selected(vip.first):
        p.tap(vip.first, "décocher Vendredi Party (vrais membres)")
    for g in groups:
        c = chip(p, f"{g} · ").first
        if not c.count():
            p.log(f"groupe {g} absent des choix (le bot n'en fait pas partie)")
            continue
        if not selected(c):
            p.tap(c, f"groupe {g}")


def create_simple(p: Phone, title: str, offset_days: int, groups: list[str], submit_label: str | None = "Publier") -> str | None:
    p.goto("/events/event/new")
    p.see(p.page.get_by_label("Titre", exact=True), "le formulaire")
    fill(p, "Titre", title)
    fill(p, "Description", "Événement de test des bots (banc tests/bots). Ignorer.")
    set_date(p, "Début", day(offset_days), "19:30")
    fill(p, "Lieu", "Salle des bots, Vevey")
    audience_invite_groups(p, groups)
    p.shot("formulaire-simple-rempli")
    p.scroll_to_bottom("formulaire simple")
    p.check_texts_cut("formulaire simple")
    if submit_label is None:  # selon les droits : Publier ou Envoyer pour validation
        submit_label = "Publier" if p.page.get_by_role("button", name="Publier", exact=True).count() else "Envoyer pour validation"
    return submit(p, submit_label)
