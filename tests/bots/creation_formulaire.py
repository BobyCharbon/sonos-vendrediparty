"""Campagne 2, agent 01 : création d'un événement par le formulaire (simple et avancé), chaque champ vérifié en base.

Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.creation_formulaire <phase…>
Phases : simple avance sondage erreurs limites double double_cgu reseau brouillon retour roles modele nettoyage
Titres préfixés « [C2-01] » ; seuls les groupes Bots / Bots 2 et les comptes Bot … sont utilisés."""
from __future__ import annotations

import json
import re
import sys
import traceback

from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots.bench import OUT, anomaly, load_state, phone, save_state
from tests.bots.common import GROUP_BOTS, GROUP_BOTS_2, q, sql

PREFIX = "[C2-01] "
NEW_TAG = "c2-01-test"
LIMITS_ONLY: set[str] = set()  # vide : tous les cas limites
FINDINGS = OUT / "constats.jsonl"


def note(what: str, value) -> None:
    """Constat (marche / ne marche pas) gardé pour le rapport."""
    with FINDINGS.open("a") as fh:
        fh.write(json.dumps({"what": what, "value": value}, ensure_ascii=False, default=str) + "\n")
    print(f"CONSTAT {what} : {value}", flush=True)


def ev_by_title(title: str) -> list[dict]:
    return sql(f"select * from public.events where title = {q(title)} order by created_at")


def children(eid: str) -> dict:
    one = lambda s: sql(s.replace("$E", q(eid)))
    return {
        "tags": [r["name"] for r in one("select t.name from event_tags et join tags t on t.id = et.tag_id where et.event_id = $E")],
        "organizers": [r["display_name"] for r in one(
            "select p.display_name from event_organizers o join profiles p on p.id = o.user_id where o.event_id = $E")],
        "groups": [r["name"] for r in one("select g.name from event_groups eg join member_groups g on g.id = eg.group_id where eg.event_id = $E")],
        "invites": one("select count(*)::int n, count(*) filter (where via_group)::int via_group from event_invites where event_id = $E")[0],
        "slots": [r["s"] for r in one("select to_char(starts_at at time zone 'Europe/Zurich', 'YYYY-MM-DD HH24:MI') s from date_options where event_id = $E order by starts_at")],
        "polls": one("""select p.question, p.multiple_choice, p.anonymous, p.members_can_add_options, p.results_after_vote,
                        array(select label from poll_options o where o.poll_id = p.id order by sort) options
                        from polls p where p.event_id = $E order by sort"""),
        "bring": one("select label, quantity from bring_items where event_id = $E order by sort"),
        "category": (one("select c.name from events e left join categories c on c.id = e.category_id where e.id = $E")[0]["name"]),
    }


def zurich(ts_col: str, eid: str) -> str | None:
    r = sql(f"select to_char({ts_col} at time zone 'Europe/Zurich', 'YYYY-MM-DD HH24:MI') v from events where id = {q(eid)}")
    return r[0]["v"] if r else None


def compare(p, what: str, actual: dict, expected: dict) -> None:
    bad = {k: (actual.get(k), v) for k, v in expected.items() if actual.get(k) != v}
    note(f"{what} : champs vérifiés en base", {"ok": sorted(set(expected) - set(bad)), "écarts (base, attendu)": bad})
    if bad:
        p.flag("🔴", f"{what} : champs mal enregistrés en base", json.dumps(bad, ensure_ascii=False, default=str)[:600])


def alerts(p) -> list[str]:
    p.page.wait_for_timeout(500)
    return [t.strip() for t in p.page.get_by_role("alert").all_inner_texts() if t.strip()]


def open_form(p, advanced: bool = False) -> None:
    p.goto("/events/event/new")
    p.see(p.page.get_by_label("Titre", exact=True), "le formulaire", 60000)
    if advanced:
        p.tap(p.page.get_by_role("tab", name="Avancé"), "Avancé")


def set_time(p, label: str, hour: str) -> None:
    p.page.get_by_label(f"{label} : heure", exact=True).select_option(hour)


def submit_btn(p):
    for label in ("Publier", "Envoyer pour validation", "Enregistrer"):
        b = p.page.get_by_role("button", name=label, exact=True)
        if b.count():
            return b.last, label
    return None, None


def submit(p, label: str = "Publier") -> str | None:
    """Comme flows.submit, mais patiente 90 s (base de TEST chargée par 10 agents) et note la durée."""
    import time
    page = p.page
    t0 = time.monotonic()
    p.tap(page.get_by_role("button", name=label, exact=True).last, label)
    accept = page.get_by_role("button", name=re.compile("J.accepte"))
    deadline = time.monotonic() + 90
    on_fiche = lambda: bool(f.EVENT_URL.search(page.url)) and not page.url.rstrip("/").endswith("/edit")
    while time.monotonic() < deadline and not on_fiche():
        if accept.count() and accept.first.is_visible():
            f.accept_terms_if_asked(p)
        page.wait_for_timeout(1000)
    if not on_fiche():
        p.flag("🔴", f"« {label} » n'ouvre pas la fiche en 90 s", f"{page.url} ; messages={alerts(p)}")
        return None
    note(f"durée de « {label} » jusqu'à la fiche (s)", round(time.monotonic() - t0, 1))
    page.wait_for_timeout(2000)
    return f.event_id(p)


def signed(browser, key: str, origin: str, phase: str):
    """Connexion robuste (base lente) : attend l'écran de connexion OU la liste, jusqu'à 3 essais."""
    from tests.bots.common import OTP
    p = phone(browser, key, origin, phase)
    page = p.page
    for attempt in range(3):
        p.goto("/events/")
        login = page.get_by_label("Ton numéro de téléphone", exact=True)
        listed = page.get_by_label("Rechercher un événement")
        try:
            login.or_(listed).first.wait_for(state="visible", timeout=60000)
        except Exception:
            p.log(f"ni connexion ni liste (essai {attempt + 1})")
            continue
        if listed.count() and listed.first.is_visible():
            return p
        p.type(login, "0" + p.bot.phone[2:], "le numéro")
        p.tap(page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS")
        code = page.get_by_placeholder("123456", exact=True)
        code.wait_for(state="visible", timeout=90000)
        p.type(code, OTP, "le code")
        p.tap(page.get_by_role("button", name="Se connecter", exact=True), "Se connecter")
        try:
            listed.first.wait_for(state="visible", timeout=60000)
            return p
        except Exception:
            p.log(f"liste absente après connexion (essai {attempt + 1})")
    return p


# ── 1. Formulaire simple ────────────────────────────────────────────────────────────────────────────────────────

SIMPLE_TITLE = PREFIX + "Raclette simple 🧀🎉"
SIMPLE_DESC = ("Une longue description avec des emoji 🎶🍷🔥 et des retours à la ligne.\n\n"
               "Deuxième paragraphe : « guillemets », apostrophe d’ici, accents éàüç. " + "Bla " * 120).strip()


def phase_simple(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "c01-simple")
    page = p.page
    try:
        open_form(p)
        p.shot("simple-vide", full=True)
        mode = page.get_by_role("tab", name="Simple").get_attribute("aria-selected")
        note("mode par défaut (nouveau téléphone)", f"Simple sélectionné = {mode}")
        public_selected = f.selected(f.chip(p, "Publique + lien", exact=True).first)
        note("audience par défaut", "Publique + lien" if public_selected else "Sur invitation")
        f.fill(p, "Titre", SIMPLE_TITLE)
        f.fill(p, "Description", SIMPLE_DESC)
        p.tap(f.chip(p, "Soirée", exact=True).first, "catégorie Soirée")
        p.tap(f.chip(p, "Sport", exact=True).first, "catégorie Sport (remplace Soirée)")
        f.set_date(p, "Début", f.day(5), "19:30")
        f.set_date(p, "Fin (optionnel)", f.day(5), "23:55")
        with p.step("recherche Google Maps"):
            box = page.get_by_label("Chercher un lieu sur Google Maps", exact=True)
            if box.count():
                box.fill("Place du Marché Vevey")
                page.wait_for_timeout(2500)
                p.shot("google-maps")
                sugg = page.locator('[role="list"] [role="button"]')
                note("Google Maps : propositions", sugg.count())
                if sugg.count():
                    p.tap(sugg.first, "première proposition Google")
                    page.wait_for_timeout(2000)
                    note("Google Maps : lieu rempli", page.get_by_label("Lieu", exact=True).input_value())
                else:
                    note("Google Maps : message", page.get_by_text(re.compile("Google Maps ne répond pas")).count())
            else:
                note("Google Maps", "champ absent (pas de clé)")
        f.fill(p, "Lieu", "Salle des bots C2-01, Vevey")
        f.toggle(p, "Pot commun", True)
        p.shot("simple-rempli", full=True)
        p.scroll_to_bottom("formulaire simple")
        cut = p.check_texts_cut("formulaire simple")
        if cut:
            p.flag("🟡", "formulaire simple : textes coupés", "; ".join(cut))
        _btn, label = submit_btn(p)
        note("bouton d'envoi (organisateur)", label)
        eid = submit(p, label)
        if not eid:
            return
        save_state(c01_simple=eid)
        p.shot("simple-fiche", full=True)
        e = ev_by_title(SIMPLE_TITLE)
        note("simple : lignes en base", len(e))
        e = e[-1]
        e["category"] = children(eid)["category"]
        e["starts"], e["ends"] = zurich("starts_at", eid), zurich("ends_at", eid)
        compare(p, "simple", e, {
            "description": SIMPLE_DESC, "category": "Sport", "status": "published", "date_mode": "fixed",
            "starts": f"{f.day(5)} 19:30", "ends": f"{f.day(5)} 23:55", "location_name": "Salle des bots C2-01, Vevey",
            "visibility": "all", "public_link": True, "pot_enabled": True, "forum_enabled": True, "allow_maybe": True,
            "allow_plus_ones": True, "max_plus_ones": 10, "waitlist_enabled": True, "max_participants": None,
            "price_chf": None, "show_participants": True, "tickets_enabled": False, "notify_on_publish": False,
            "announce_group": False, "reminders": ["7d", "1d", "2h", "0h"],
        })
        # Fiche : la description et le titre s'affichent en entier
        if not page.get_by_text("Raclette simple 🧀🎉").count():
            p.flag("🟠", "fiche : le titre avec emoji n'apparaît pas")
    finally:
        p.close()


# ── 2. Formulaire avancé : chaque option ────────────────────────────────────────────────────────────────────────

ADV_TITLE = PREFIX + "Soirée avancée – toutes options"


def fill_advanced(p, title: str) -> None:
    page = p.page
    f.fill(p, "Titre", title)
    f.fill(p, "Description", "Toutes les options du formulaire avancé. 🎟️")
    p.tap(f.chip(p, "Voyage", exact=True).first, "catégorie Voyage")
    p.tap(f.chip(p, "#karting", exact=True).first, "tag #karting")
    p.tap(f.chip(p, "#bar", exact=True).first, "tag #bar")
    with p.step("créer un tag"):
        tag_box = page.get_by_placeholder("Nouveau tag", exact=True)
        if tag_box.count():
            tag_box.fill("#" + NEW_TAG.upper())
            p.tap(page.get_by_role("button", name="Créer", exact=True), "Créer le tag")
            page.wait_for_timeout(2500)
            note("nouveau tag créé et coché", f.selected(f.chip(p, f"#{NEW_TAG}", exact=True).first))
        else:
            note("création de tag", "champ absent pour ce rôle")
    f.set_date(p, "Début", f.day(8), "20:00")
    f.set_date(p, "Fin (optionnel)", f.day(9), "02:00")
    f.fill(p, "Lieu", "Chez les bots")
    f.fill(p, "Adresse", "Rue du Lac 12, 1800 Vevey")
    f.fill(p, "Lien (site, carte…)", "https://maps.google.com/?q=Vevey")
    f.fill(p, "Prix / pers. (CHF)", "12,50")
    f.fill(p, "Paiement", "TWINT 079 000 01 03")
    f.toggle(p, "Billets QR", True)
    # Bot Olga a bloqué Bot Gus (groupe Bots) : voir le bug « groupe avec une personne bloquée » ; ici Bots 2.
    f.audience_invite_groups(p, [GROUP_BOTS_2])
    f.toggle(p, "Prévenir le groupe", True)
    p.shot("annonce-phrase")
    f.fill(p, "Nombre de places (vide = illimité)", "3")
    f.toggle(p, "Liste d’attente", True)
    f.toggle(p, "Réponse « Peut-être » autorisée", False)
    f.toggle(p, "Accompagnants (+1)", True)
    f.fill(p, "Accompagnants max par personne (vide = illimité)", "2")
    f.toggle(p, "Liste des participants visible", False)
    f.set_date(p, "Date limite de réponse (optionnel)", f.day(7), "12:00")
    p.tap(f.chip(p, "Bot Oscar", exact=True).first, "co-organisateur Bot Oscar")
    p.tap(f.chip(p, "Bot Côme", exact=True).first, "co-organisateur Bot Côme")
    p.tap(f.chip(p, "Bot Côme", exact=True).first, "retirer Bot Côme")
    f.toggle(p, "Pot commun", True)
    # Mini-sondages : 2, dont un avec options et cases, un retiré puis remis
    p.tap(page.get_by_role("button", name="+ Ajouter un sondage"), "+ Ajouter un sondage")
    f.fill(p, "Question du sondage 1", "Raclette ou fondue ?")
    page.get_by_label("Sondage 1, option 1", exact=True).fill("Raclette")
    page.get_by_label("Sondage 1, option 2", exact=True).fill("Fondue")
    p.tap(page.get_by_role("button", name="+ Ajouter une option").first, "+ Ajouter une option")
    page.get_by_label("Sondage 1, option 3", exact=True).fill("Les deux")
    p.tap(f.chip(p, "Choix multiple", exact=True).first, "Choix multiple")
    p.tap(f.chip(p, "Anonyme", exact=True).first, "Anonyme")
    p.tap(page.get_by_role("button", name="+ Ajouter un sondage"), "+ Ajouter un sondage (2)")
    f.fill(p, "Question du sondage 2", "Quelle musique ?")
    page.get_by_label("Sondage 2, option 1", exact=True).fill("Rock")
    page.get_by_label("Sondage 2, option 2", exact=True).fill("")
    p.tap(f.chip(p, "Options libres", exact=True).nth(1), "Options libres (sondage 2)")
    p.tap(f.chip(p, "Résultats après vote", exact=True).nth(1), "Résultats après vote (sondage 2)")
    # Qui amène quoi : 3 objets, un retiré
    for label, qty in (("Pain", ""), ("Bouteilles de vin", "6"), ("À retirer", "")):
        p.tap(page.get_by_role("button", name="+ Ajouter un objet"), "+ Ajouter un objet")
        page.get_by_placeholder("Fromage, pain…").last.fill(label)
        if qty:
            page.get_by_label(re.compile("^Quantité de")).last.fill(qty)
    p.tap(page.get_by_role("button", name="✕").last, "retirer « À retirer »")
    f.toggle(p, "Forum de l’événement", False)


def phase_avance(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "c01-avance")
    page = p.page
    try:
        open_form(p, advanced=True)
        fill_advanced(p, ADV_TITLE)
        p.shot("avance-rempli", full=True)
        p.scroll_to_bottom("formulaire avancé")
        cut = p.check_texts_cut("formulaire avancé")
        if cut:
            p.flag("🟡", "formulaire avancé : textes coupés", "; ".join(cut))
        eid = submit(p, "Publier")
        if not eid:
            note("avance : erreurs affichées", alerts(p))
            return
        save_state(c01_adv=eid)
        p.shot("avance-fiche", full=True)
        e = ev_by_title(ADV_TITLE)[-1]
        e.update(children(eid))
        e["starts"], e["ends"], e["rsvp"] = zurich("starts_at", eid), zurich("ends_at", eid), zurich("rsvp_deadline", eid)
        e["price"] = float(e["price_chf"]) if e["price_chf"] is not None else None
        e["invites_n"] = e["invites"]["n"]
        compare(p, "avancé", e, {
            "category": "Voyage", "tags": sorted(["karting", "bar", NEW_TAG]), "starts": f"{f.day(8)} 20:00",
            "ends": f"{f.day(9)} 02:00", "location_name": "Chez les bots", "location_address": "Rue du Lac 12, 1800 Vevey",
            "location_url": "https://maps.google.com/?q=Vevey", "price": 12.5, "payment_info": "TWINT 079 000 01 03",
            "tickets_enabled": True, "visibility": "invited", "public_link": False, "groups": [GROUP_BOTS_2],
            "announce_group": True, "max_participants": 3, "waitlist_enabled": True, "allow_maybe": False,
            "allow_plus_ones": True, "max_plus_ones": 2, "show_participants": False, "rsvp": f"{f.day(7)} 12:00",
            "organizers": ["Bot Oscar"], "pot_enabled": True, "forum_enabled": False, "status": "published",
            "polls": [
                {"question": "Raclette ou fondue ?", "multiple_choice": True, "anonymous": True, "members_can_add_options": False,
                 "results_after_vote": False, "options": ["Raclette", "Fondue", "Les deux"]},
                {"question": "Quelle musique ?", "multiple_choice": False, "anonymous": False, "members_can_add_options": True,
                 "results_after_vote": True, "options": ["Rock"]}],
            "bring": [{"label": "Pain", "quantity": None}, {"label": "Bouteilles de vin", "quantity": 6}],
        })
        e["tags"] = sorted(e["tags"])
        note("avancé : invités recopiés du groupe Bots", e["invites"])
        ann = sql(f"select * from public.event_announcements where event_id = {q(eid)}") if sql(
            "select to_regclass('public.event_announcements') r")[0]["r"] else "table absente"
        note("avancé : demande « Prévenir le groupe »", ann)
        # Relire le formulaire en modification : tout revient-il ?
        p.goto(f"/events/event/{eid}/edit")
        p.see(page.get_by_label("Titre", exact=True), "le formulaire de modification", 30000)
        page.wait_for_timeout(2000)
        reread = {
            "titre": page.get_by_label("Titre", exact=True).input_value(),
            "prix": page.get_by_label("Prix / pers. (CHF)", exact=True).input_value(),
            "places": page.get_by_label("Nombre de places (vide = illimité)", exact=True).input_value(),
            "max +1": page.get_by_label("Accompagnants max par personne (vide = illimité)", exact=True).input_value(),
            "peut-être": page.get_by_label("Réponse « Peut-être » autorisée", exact=True).is_checked(),
            "forum": page.get_by_label("Forum de l’événement", exact=True).is_checked(),
            "annonce": page.get_by_label("Prévenir le groupe", exact=True).is_checked() if page.get_by_label("Prévenir le groupe", exact=True).count() else None,
            "bouton": submit_btn(p)[1],
        }
        note("avancé : formulaire relu en modification", reread)
        p.shot("avance-relu", full=True)
    finally:
        p.close()


# ── 3. Sondage de dates ─────────────────────────────────────────────────────────────────────────────────────────

POLL_TITLE = PREFIX + "Sondage de dates"


def phase_sondage(browser, origin, only=None):
    p = signed(browser, "orga2", origin, "c01-sondage")
    page = p.page
    try:
        open_form(p, advanced=True)
        f.fill(p, "Titre", POLL_TITLE)
        p.tap(page.get_by_role("tab", name="Date à définir"), "Date à définir")
        disabled = page.get_by_role("tab", name="Simple").get_attribute("aria-disabled")
        note("sondage : bascule Simple désactivée", disabled)
        f.set_date(p, "Créneau 1", f.day(12), "19:00")
        f.set_date(p, "Créneau 2", f.day(13), "19:00")
        p.tap(page.get_by_role("button", name="+ Ajouter un créneau"), "+ Ajouter un créneau")
        f.set_date(p, "Créneau 3", f.day(14), "20:30")
        p.tap(page.get_by_role("button", name="+ Ajouter un créneau"), "+ Ajouter un créneau (4)")
        f.set_date(p, "Créneau 4", f.day(15), "18:00")
        p.tap(page.get_by_role("button", name="✕").nth(1), "retirer le créneau 2")
        f.set_date(p, "Fin du vote (optionnel)", f.day(10), "20:00")
        f.toggle(p, "Les membres peuvent proposer des dates", False)
        f.toggle(p, "Fixer la date automatiquement", True)
        f.fill(p, "Lieu", "Bar des bots")
        f.audience_invite_groups(p, [GROUP_BOTS])
        p.shot("sondage-rempli", full=True)
        eid = submit(p, "Publier")
        if not eid:
            note("sondage : erreurs", alerts(p))
            return
        save_state(c01_poll=eid)
        p.shot("sondage-fiche", full=True)
        e = ev_by_title(POLL_TITLE)[-1]
        e.update(children(eid))
        e["deadline"] = zurich("poll_deadline", eid)
        compare(p, "sondage de dates", e, {
            "date_mode": "poll", "starts_at": None, "slots": [f"{f.day(12)} 19:00", f"{f.day(14)} 20:30", f"{f.day(15)} 18:00"],
            "deadline": f"{f.day(10)} 20:00", "members_can_propose_dates": False, "auto_fix_date": True, "status": "published",
        })
        n_buttons = page.get_by_role("button", name=re.compile(r"^Oui : ")).count()
        note("sondage : créneaux affichés sur la fiche", n_buttons)
    finally:
        p.close()


# ── 4. Erreurs de saisie ────────────────────────────────────────────────────────────────────────────────────────

ERR_TITLE = PREFIX + "Erreurs"


def try_submit(p, case: str, expect: str | None) -> None:
    """Touche Publier ; l'erreur attendue doit s'afficher et aucun événement ne doit naître."""
    before = len(ev_by_title(ERR_TITLE))
    btn, _ = submit_btn(p)
    p.tap(btn, f"Publier ({case})")
    p.page.wait_for_timeout(2500)
    shown = alerts(p)
    after = ev_by_title(ERR_TITLE)
    left = "/event/new" not in p.page.url
    note(f"erreur « {case} »", {"message": shown, "attendu": expect, "événements créés": len(after) - before, "page quittée": left})
    if expect and not any(expect in s for s in shown):
        sev = "🔴" if len(after) > before else "🟠"
        p.flag(sev, f"saisie invalide « {case} » : message attendu absent", f"affiché={shown} ; créés={len(after) - before}")
    if expect is None and not shown and len(after) == before:
        p.flag("🟠", f"« {case} » : rien ne se passe", "")
    if len(after) > before:
        for e in after[before:]:
            sql(f"delete from public.events where id = {q(e['id'])}")
        p.log("événement créé à tort supprimé")


def phase_erreurs(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "c01-erreurs")
    page = p.page
    try:
        open_form(p, advanced=True)
        try_submit(p, "formulaire vide", "Il manque un titre")
        f.fill(p, "Titre", "    ")
        try_submit(p, "titre en espaces", "Il manque un titre")
        f.fill(p, "Titre", ERR_TITLE)
        try_submit(p, "sans date de début", "Début : obligatoire")
        f.set_date(p, "Début", f.day(4), "19:30")
        f.set_date(p, "Fin (optionnel)", f.day(4), "18:00")
        try_submit(p, "fin avant début (même jour)", "La fin doit être après le début")
        f.set_date(p, "Fin (optionnel)", f.day(4), "19:30")
        try_submit(p, "fin = début", "La fin doit être après le début")
        p.tap(page.get_by_role("button", name="Effacer : Fin (optionnel)"), "Effacer la fin")
        for value, expect in (("-5", "Le prix doit être un montant positif ou zéro"), ("abc", "Le prix doit être"),
                              ("1'000", "Le prix doit être")):
            f.fill(p, "Prix / pers. (CHF)", value)
            try_submit(p, f"prix {value}", expect)
        f.fill(p, "Prix / pers. (CHF)", "")
        for value in ("-2", "0", "2.5", "abc"):
            f.fill(p, "Nombre de places (vide = illimité)", value)
            try_submit(p, f"places {value}", "Nombre de places invalide")
        f.fill(p, "Nombre de places (vide = illimité)", "")
        for value in ("www.vevey.ch", "javascript:alert(1)", "ftp://x.ch"):
            f.fill(p, "Lien (site, carte…)", value)
            try_submit(p, f"lien {value}", "Le lien doit")
        f.fill(p, "Lien (site, carte…)", "")
        # Sur invitation sans personne
        p.tap(f.chip(p, "Sur invitation", exact=True).first, "Sur invitation")
        vip = f.chip(p, "👥 Vendredi Party")
        if vip.count() and f.selected(vip.first):
            p.tap(vip.first, "décocher Vendredi Party")
        try_submit(p, "sur invitation sans groupe", "Choisis qui inviter")
        f.audience_invite_groups(p, [GROUP_BOTS])
        # Mini-sondage incomplet
        p.tap(page.get_by_role("button", name="+ Ajouter un sondage"), "+ Ajouter un sondage")
        try_submit(p, "sondage sans question", "Un sondage n’a pas de question")
        f.fill(p, "Question du sondage 1", "Une seule option ?")
        page.get_by_label("Sondage 1, option 1", exact=True).fill("Seule")
        try_submit(p, "sondage à une option", "au moins deux options")
        p.tap(page.get_by_role("button", name="Retirer ce sondage"), "Retirer ce sondage")
        # Sondage de dates incomplet
        p.tap(page.get_by_role("tab", name="Date à définir"), "Date à définir")
        f.toggle(p, "Les membres peuvent proposer des dates", False)
        f.set_date(p, "Créneau 1", f.day(12), "19:00")
        try_submit(p, "sondage de dates : un seul créneau", "Propose au moins deux créneaux")
        p.tap(page.get_by_role("tab", name="Date fixée"), "Date fixée")
        # Cas acceptés en silence (constats) : dates passées, date limite après l'événement, accompagnants hors bornes.
        p.shot("erreurs-fin", full=True)
    finally:
        p.close()


def phase_limites(browser, origin, only=None):
    # Cas limites qui passent : chacun dans un formulaire neuf, enregistré en BROUILLON (rien n'est publié)
    cases = [c for c in [
        ("début hier", {"start": (-1, "19:30")}),
        ("date limite de réponse après le début", {"start": (4, "19:30"), "rsvp": (6, "12:00")}),
        ("fin du vote après le premier créneau", {"poll": True}),
        ("accompagnants max -3", {"start": (4, "19:30"), "plus": "-3"}),
        ("accompagnants max 0", {"start": (4, "19:30"), "plus": "0"}),
        ("accompagnants max 50", {"start": (4, "19:30"), "plus": "50"}),
        ("titre de 200 caractères", {"start": (4, "19:30"), "title": PREFIX + "x" * 200}),
        ("accompagnants max 2.7", {"start": (4, "19:30"), "plus": "2.7"}),
        ("prix 1000000000", {"start": (4, "19:30"), "price": "1000000000"}),
        ("prix 12.345", {"start": (4, "19:30"), "price": "12.345"}),
    ] if not LIMITS_ONLY or c[0] in LIMITS_ONLY]
    p = signed(browser, "orga1", origin, "c01-limites")
    page = p.page
    try:
        for case, opt in cases:
            with p.step(case):
                open_form(p, advanced=True)
                title = opt.get("title") or f"{PREFIX}Limite {case}"
                f.fill(p, "Titre", title)
                typed = page.get_by_label("Titre", exact=True).input_value()
                if opt.get("poll"):
                    p.tap(page.get_by_role("tab", name="Date à définir"), "Date à définir")
                    f.set_date(p, "Créneau 1", f.day(5), "19:00")
                    f.set_date(p, "Créneau 2", f.day(6), "19:00")
                    f.set_date(p, "Fin du vote (optionnel)", f.day(20), "19:00")
                else:
                    f.set_date(p, "Début", f.day(opt["start"][0]), opt["start"][1])
                if "rsvp" in opt:
                    f.set_date(p, "Date limite de réponse (optionnel)", f.day(opt["rsvp"][0]), opt["rsvp"][1])
                if "plus" in opt:
                    f.fill(p, "Accompagnants max par personne (vide = illimité)", opt["plus"])
                if "price" in opt:
                    f.fill(p, "Prix / pers. (CHF)", opt["price"])
                p.tap(page.get_by_role("button", name="Enregistrer en brouillon"), "Enregistrer en brouillon")
                page.wait_for_timeout(3500)
                f.accept_terms_if_asked(p)
                shown = alerts(p)
                rows = sql(f"select id, max_plus_ones, price_chf, length(title) n, status from events where title like {q(typed[:60] + '%')} and created_by = (select id from profiles where display_name = 'Bot Olga')")
                note(f"limite « {case} »", {"message": shown, "en base": rows, "longueur saisie": len(typed)})
                p.shot("limite")
    finally:
        p.close()


# ── 5. Double envoi ─────────────────────────────────────────────────────────────────────────────────────────────

DOUBLE_TITLE = PREFIX + "Double envoi"


def phase_double(browser, origin, only=None):
    p = signed(browser, "orga2", origin, "c01-double")
    page = p.page
    try:
        open_form(p)
        f.fill(p, "Titre", DOUBLE_TITLE)
        f.set_date(p, "Début", f.day(6), "19:00")
        btn, _label = submit_btn(p)
        btn.scroll_into_view_if_needed()
        p.log("double toucher très rapide sur Publier")
        for _ in range(3):
            btn.tap(no_wait_after=True, force=True)
        page.wait_for_timeout(1000)
        f.accept_terms_if_asked(p)
        page.wait_for_url(f.EVENT_URL, timeout=90000)
        page.wait_for_timeout(3000)
        rows = ev_by_title(DOUBLE_TITLE)
        note("double envoi : événements créés", len(rows))
        if len(rows) != 1:
            p.flag("🔴", f"triple toucher sur Publier : {len(rows)} événements", "")
        # Double clic souris (Android tablette / bureau)
        open_form(p)
        f.fill(p, "Titre", DOUBLE_TITLE + " (dblclick)")
        f.set_date(p, "Début", f.day(6), "19:00")
        submit_btn(p)[0].dblclick()
        page.wait_for_url(f.EVENT_URL, timeout=90000)
        page.wait_for_timeout(3000)
        rows = ev_by_title(DOUBLE_TITLE + " (dblclick)")
        note("double clic : événements créés", len(rows))
        if len(rows) != 1:
            p.flag("🔴", f"double clic sur Publier : {len(rows)} événements", "")
        p.shot("double-fiche")
    finally:
        p.close()


SLOW_TERMS = """(() => { const real = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.includes('/rpc/my_terms')) await new Promise((r) => setTimeout(r, 9000));
    return real(input, init); }; })();"""


def phase_double_cgu(browser, origin, only=None):
    """Réseau lent : la réponse « CGU déjà acceptées ? » (my_terms) met 9 s. Double toucher sur Publier pendant ce temps."""
    p = signed(browser, "orga1", origin, "c01-double-cgu")
    page = p.page
    try:
        title = PREFIX + "Double envoi réseau lent"
        p.ctx.add_init_script(SLOW_TERMS)
        p.goto("/events/event/new")
        page.get_by_label("Titre", exact=True).wait_for(timeout=60000)
        page.get_by_label("Titre", exact=True).fill(title)
        f.set_date(p, "Début", f.day(6), "19:00")
        btn = submit_btn(p)[0]
        btn.scroll_into_view_if_needed()
        p.log("deux touchers sur Publier à 0,4 s d'intervalle, réponse CGU encore en route")
        btn.tap(no_wait_after=True)
        page.wait_for_timeout(400)
        btn.tap(no_wait_after=True, force=True)
        page.wait_for_timeout(2000)
        p.shot("double-cgu-attente")
        try:
            page.wait_for_url(f.EVENT_URL, timeout=90000)
        except Exception:
            pass
        page.wait_for_timeout(8000)
        rows = ev_by_title(title)
        note("double toucher pendant la vérification des CGU : événements créés", [(r["id"], r["status"]) for r in rows])
        if len(rows) > 1:
            p.flag("🔴", f"double toucher sur Publier (réseau lent, vérification des CGU) : {len(rows)} événements", str(rows))
        p.shot("double-cgu-fin")
    finally:
        p.close()


# ── 6. Réseau coupé pendant l'envoi ─────────────────────────────────────────────────────────────────────────────

NET_TITLE = PREFIX + "Réseau coupé"


def phase_reseau(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "c01-reseau")
    page = p.page
    try:
        open_form(p, advanced=True)
        f.fill(p, "Titre", NET_TITLE)
        f.set_date(p, "Début", f.day(7), "19:00")
        p.tap(page.get_by_role("button", name="+ Ajouter un sondage"), "+ Ajouter un sondage")
        f.fill(p, "Question du sondage 1", "Oui ou non ?")
        page.get_by_label("Sondage 1, option 1", exact=True).fill("Oui")
        page.get_by_label("Sondage 1, option 2", exact=True).fill("Non")
        p.tap(page.get_by_role("button", name="+ Ajouter un objet"), "+ Ajouter un objet")
        page.get_by_placeholder("Fromage, pain…").last.fill("Chips")
        # a) hors ligne complet
        p.ctx.set_offline(True)
        p.tap(submit_btn(p)[0], "Publier (hors ligne)")
        page.wait_for_timeout(3000)
        note("hors ligne : message", alerts(p))
        p.shot("hors-ligne")
        note("hors ligne : événements créés", len(ev_by_title(NET_TITLE)))
        p.ctx.set_offline(False)
        # b) coupure au milieu : l'événement est inséré, « qui amène quoi » échoue
        page.route(re.compile(r".*/rest/v1/bring_items.*"),
                   lambda route: route.abort() if route.request.method == "POST" else route.continue_())
        p.tap(submit_btn(p)[0], "Publier (coupure au milieu)")
        page.wait_for_timeout(4000)
        f.accept_terms_if_asked(p)
        page.wait_for_timeout(2000)
        msg = alerts(p)
        rows = ev_by_title(NET_TITLE)
        note("coupure au milieu : message et base", {"message": msg, "lignes": [(r["id"], r["status"]) for r in rows]})
        p.shot("coupure")
        page.unroute(re.compile(r".*/rest/v1/bring_items.*"))
        p.tap(submit_btn(p)[0], "Publier (nouvel essai)")
        page.wait_for_timeout(5000)
        rows = ev_by_title(NET_TITLE)
        res = {"lignes": [(r["id"], r["status"]) for r in rows], "url": page.url}
        if rows:
            ch = children(rows[-1]["id"])
            res.update(polls=len(ch["polls"]), options=[pp["options"] for pp in ch["polls"]], bring=ch["bring"])
        note("nouvel essai après coupure", res)
        if len(rows) != 1:
            p.flag("🔴", "nouvel essai après coupure : événement en double", str(res))
        elif rows[0]["status"] != "published":
            p.flag("🟠", "nouvel essai après coupure : pas publié", str(res))
        if rows and (res.get("polls") != 1 or len(res.get("bring", [])) != 1):
            p.flag("🔴", "nouvel essai après coupure : sondage ou objet en double / manquant", str(res))
        p.shot("apres-essai")
    finally:
        p.close()


# ── 7. Brouillon ────────────────────────────────────────────────────────────────────────────────────────────────

DRAFT_TITLE = PREFIX + "Brouillon"


def phase_brouillon(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "c01-brouillon")
    page = p.page
    try:
        open_form(p)
        f.fill(p, "Titre", DRAFT_TITLE)
        with p.step("brouillon sans date"):
            p.tap(page.get_by_role("button", name="Enregistrer en brouillon"), "Enregistrer en brouillon (sans date)")
            page.wait_for_timeout(2500)
            note("brouillon sans date : message", alerts(p))
        f.set_date(p, "Début", f.day(11), "19:00")
        p.tap(page.get_by_role("button", name="Enregistrer en brouillon"), "Enregistrer en brouillon")
        page.wait_for_timeout(3000)
        f.accept_terms_if_asked(p)
        page.wait_for_url(f.EVENT_URL, timeout=90000)
        eid = f.event_id(p)
        save_state(c01_draft=eid)
        row = sql(f"select status from events where id = {q(eid)}")
        note("brouillon : statut en base", row)
        p.shot("brouillon-fiche", full=True)
        note("brouillon : mention sur la fiche", page.get_by_text(re.compile("[Bb]rouillon")).count())
        # Liste : le brouillon apparaît-il pour l'organisatrice ?
        p.goto("/events/")
        page.wait_for_timeout(3000)
        note("brouillon visible dans la liste", page.get_by_text(DRAFT_TITLE).count())
        p.shot("liste-brouillon")
        # Modifier puis publier
        p.goto(f"/events/event/{eid}/edit")
        p.see(page.get_by_label("Titre", exact=True), "le formulaire du brouillon", 30000)
        page.wait_for_timeout(1500)
        note("brouillon rouvert : boutons", {"envoi": submit_btn(p)[1],
                                            "brouillon": page.get_by_role("button", name="Enregistrer en brouillon").count()})
        f.fill(p, "Lieu", "Lieu ajouté au brouillon")
        eid2 = submit(p, submit_btn(p)[1])
        row = sql(f"select status, location_name from events where id = {q(eid)}")
        note("brouillon publié", {"même id": eid2 == eid, "base": row})
        if not row or row[0]["status"] != "published":
            p.flag("🔴", "brouillon : la publication ne passe pas", str(row))
    finally:
        p.close()


# ── 8. Retour arrière et rechargement en plein formulaire ───────────────────────────────────────────────────────

def phase_retour(browser, origin, only=None):
    p = signed(browser, "orga2", origin, "c01-retour")
    page = p.page
    try:
        page.wait_for_timeout(2500)
        p.tap(page.get_by_role("button", name="Proposer un événement"), "+ Proposer", timeout=60000)
        p.see(page.get_by_label("Titre", exact=True), "le formulaire")
        p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
        f.fill(p, "Titre", PREFIX + "Retour arrière")
        f.fill(p, "Description", "Texte tapé avant le retour")
        f.fill(p, "Nombre de places (vide = illimité)", "8")
        p.log("retour arrière du navigateur (geste)")
        page.go_back()
        page.wait_for_timeout(2000)
        note("retour arrière : page", page.url)
        note("retour arrière : confirmation demandée", "aucune boîte" if "/event/new" not in page.url else "resté")
        p.shot("apres-retour")
        page.go_forward()
        page.wait_for_timeout(2500)
        kept = page.get_by_label("Titre", exact=True).input_value() if page.get_by_label("Titre", exact=True).count() else None
        note("retour puis avancer : titre conservé", kept)
        p.tap(page.get_by_role("tab", name="Avancé"), "Avancé") if page.get_by_role("tab", name="Avancé").count() else None
        f.fill(p, "Titre", PREFIX + "Rechargement")
        f.fill(p, "Nombre de places (vide = illimité)", "8")
        page.reload()
        p.see(page.get_by_label("Titre", exact=True), "le formulaire rechargé", 30000)
        page.wait_for_timeout(1500)
        note("rechargement : titre conservé", page.get_by_label("Titre", exact=True).input_value())
        note("rechargement : mode retenu", page.get_by_role("tab", name="Avancé").get_attribute("aria-selected"))
        p.shot("apres-rechargement")
        # Fermer par la croix / « Annuler » s'il existe
        close = page.get_by_role("button", name=re.compile("^(Annuler|Fermer|Retour)$"))
        note("bouton Annuler/Fermer/Retour visible sur le formulaire", close.count())
        note("événements « Retour/Rechargement » créés", sql(f"select count(*) n from events where title in ({q(PREFIX + 'Retour arrière')}, {q(PREFIX + 'Rechargement')})"))
    finally:
        p.close()


# ── 9. Rôles : admin, co-admin, organisateur, Membre VIP, Membre sans droit ─────────────────────────────────────

def phase_roles(browser, origin, only=None):
    import os
    keys = (os.environ.get("C01_ROLES") or "admin,coadmin,orga2,vip1,membre1").split(",")
    for key in keys:
        p = signed(browser, key, origin, "c01-roles")
        page = p.page
        try:
            page.wait_for_timeout(3000)
            propose = page.get_by_role("button", name="Proposer un événement").count()
            p.goto("/events/event/new")
            try:
                page.get_by_label("Titre", exact=True).or_(page.get_by_text("Tu ne peux pas proposer")).first.wait_for(timeout=60000)
            except Exception:
                p.log("ni formulaire ni refus en 60 s")
            if not page.get_by_label("Titre", exact=True).count():
                note(f"rôle {key}", {"Proposer": propose, "formulaire": False,
                                      "écran": page.locator("body").inner_text()[:200]})
                p.shot("refus")
                continue
            p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
            page.wait_for_timeout(800)
            seen = {
                "Proposer": propose, "bouton": submit_btn(p)[1],
                "modèles": page.get_by_text("Partir d’un modèle").count(),
                "Enregistrer comme modèle": page.get_by_role("button", name="Enregistrer comme modèle").count(),
                "créer un tag": page.get_by_placeholder("Nouveau tag").count(),
                "mini-sondages": page.get_by_role("button", name="+ Ajouter un sondage").count(),
                "Vendredi Party proposé": f.chip(p, "👥 Vendredi Party").count(),
                "groupes": [c for c in page.get_by_role("button", name=re.compile(r" · \d+$")).all_inner_texts()],
                "bandeau validation": page.get_by_text("Un admin doit valider").count(),
                "public par défaut": f.selected(f.chip(p, "Publique + lien", exact=True).first),
            }
            note(f"rôle {key}", seen)
            p.shot("formulaire-role", full=True)
            title = f"{PREFIX}Rôle {key}"
            f.fill(p, "Titre", title)
            f.set_date(p, "Début", f.day(6), "19:00")
            f.audience_invite_groups(p, [GROUP_BOTS])
            eid = submit(p, submit_btn(p)[1])
            row = sql(f"select status, visibility from events where title = {q(title)}")
            note(f"rôle {key} : envoi", {"fiche": bool(eid), "base": row, "messages": alerts(p)})
            if eid:
                p.shot("fiche-role")
        finally:
            p.close()


# ── 10. Modèles d'événement ─────────────────────────────────────────────────────────────────────────────────────

TPL_NAME = "C2-01 modèle"


def phase_modele(browser, origin, only=None):
    p = signed(browser, "admin", origin, "c01-modele")
    page = p.page
    try:
        open_form(p, advanced=True)
        f.fill(p, "Titre", PREFIX + "Modèle source")
        p.tap(f.chip(p, "Resto", exact=True).first, "catégorie Resto")
        f.fill(p, "Lieu", "Resto des bots")
        f.fill(p, "Prix / pers. (CHF)", "30")
        f.fill(p, "Nombre de places (vide = illimité)", "6")
        f.set_date(p, "Début", f.day(9), "19:00")
        f.audience_invite_groups(p, [GROUP_BOTS])
        p.tap(page.get_by_role("button", name="+ Ajouter un objet"), "+ Ajouter un objet")
        page.get_by_placeholder("Fromage, pain…").last.fill("Dessert")
        p.tap(page.get_by_role("button", name="Enregistrer comme modèle"), "Enregistrer comme modèle")
        f.fill(p, "Nom du modèle", TPL_NAME)
        p.tap(page.get_by_role("button", name="Enregistrer le modèle"), "Enregistrer le modèle")
        page.wait_for_timeout(2500)
        tpl = sql(f"select id, shared, data from event_templates where name = {q(TPL_NAME)}")
        note("modèle enregistré", {"lignes": len(tpl), "données": tpl[0]["data"] if tpl else None})
        open_form(p, advanced=True)
        page.wait_for_timeout(2000)
        p.tap(page.get_by_role("button", name=f"Remplir avec le modèle {TPL_NAME}"), "appliquer le modèle")
        page.wait_for_timeout(1000)
        got = {
            "titre": page.get_by_label("Titre", exact=True).input_value(),
            "lieu": page.get_by_label("Lieu", exact=True).input_value(),
            "prix": page.get_by_label("Prix / pers. (CHF)", exact=True).input_value(),
            "places": page.get_by_label("Nombre de places (vide = illimité)", exact=True).input_value(),
            "début": page.get_by_label("Début : jour", exact=True).input_value(),
            "objet": page.get_by_placeholder("Fromage, pain…").all() and page.get_by_placeholder("Fromage, pain…").first.input_value(),
            "Resto choisi": f.selected(f.chip(p, "Resto", exact=True).first),
            "groupe Bots": f.selected(f.chip(p, f"{GROUP_BOTS} · ").first),
        }
        note("modèle appliqué : formulaire", got)
        p.shot("modele-applique", full=True)
        f.fill(p, "Titre", PREFIX + "Depuis le modèle")
        f.set_date(p, "Début", f.day(10), "19:00")
        eid = submit(p, "Publier")
        if eid:
            e = ev_by_title(PREFIX + "Depuis le modèle")[-1]
            e.update(children(eid))
            e["price"] = float(e["price_chf"]) if e["price_chf"] is not None else None
            compare(p, "événement depuis un modèle", e, {"category": "Resto", "location_name": "Resto des bots", "price": 30.0,
                                                         "max_participants": 6, "groups": [GROUP_BOTS],
                                                         "bring": [{"label": "Dessert", "quantity": None}]})
        # Suppression du modèle par l'écran
        open_form(p)
        page.wait_for_timeout(2000)
        row = page.get_by_role("button", name=f"Remplir avec le modèle {TPL_NAME}").locator("xpath=..")
        p.tap(row.get_by_role("button", name="🗑"), "🗑 modèle")
        p.tap(row.get_by_role("button", name="Supprimer ?"), "Supprimer ?")
        page.wait_for_timeout(2000)
        note("modèle supprimé par l'écran", sql(f"select count(*) n from event_templates where name = {q(TPL_NAME)}"))
    finally:
        p.close()


# ── Nettoyage : seulement MES événements [C2-01], mon tag et mon modèle ─────────────────────────────────────────

def phase_nettoyage(browser=None, origin=None, only=None):
    gone = sql(f"delete from public.events where title like {q(PREFIX + '%')} returning id")
    tag = sql(f"delete from public.tags where name = {q(NEW_TAG)} returning id")
    tpl = sql(f"delete from public.event_templates where name = {q(TPL_NAME)} returning id")
    note("nettoyage", {"événements": len(gone), "tag": len(tag), "modèle": len(tpl)})


def main(argv: list[str]) -> None:
    origin = load_state()["origin"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv:
            print(f"════ phase {name} ════", flush=True)
            try:
                globals()[f"phase_{name}"](browser, origin)
            except Exception as e:  # une phase cassée n'arrête pas les suivantes
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
