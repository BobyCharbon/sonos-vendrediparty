"""Campagne 2, relance de l'agent 01 (07.11) : ce que les corrections C1 / A / H ont changé dans le formulaire.

Usage : BOTS_OUT=<dossier> C01_PREFIX="[R-01] " .venv/bin/python -m tests.bots.creation_formulaire_relance <phase…>
Phases : blocage orphelin orphelin_android refus messages dates_passees modifier_passe nettoyage
Seuls les groupes Bots / Bots 2 et les comptes Bot … sont utilisés ; les blocages ajoutés ici sont retirés à la fin."""
from __future__ import annotations

import json
import re
import sys
import traceback
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright

from tests.bots import creation_formulaire as cf
from tests.bots import flows as f
from tests.bots.bench import anomaly, load_state
from tests.bots.common import GROUP_BOTS, q, sql

PREFIX = cf.PREFIX
note, alerts, signed, open_form, submit = cf.note, cf.alerts, cf.signed, cf.open_form, cf.submit
LEAVE = "Abandonner les changements ?"


def uid(name: str) -> str:
    return sql(f"select id from profiles where display_name = {q(name)}")[0]["id"]


def rows(title: str) -> list[dict]:
    return sql(f"select id, status from public.events where title = {q(title)} order by created_at")


# ── Bug 1 : un groupe avec une personne bloquée (correction A) ──────────────────────────────────────────────────

def _publish_to_bots(p, title: str) -> str | None:
    open_form(p, advanced=True)
    f.fill(p, "Titre", title)
    f.set_date(p, "Début", f.day(9), "19:00")
    f.audience_invite_groups(p, [GROUP_BOTS])
    return submit(p, "Publier")


def phase_blocage(browser, origin, only=None):
    olga, gus = uid("Bot Olga"), uid("Bot Gus")
    added: list[tuple[str, str]] = []
    try:
        for who, (a, b) in (("Olga bloque Gus", (olga, gus)), ("Gus bloque Olga", (gus, olga))):
            exists = sql(f"select 1 from direct_blocks where user_id = {q(a)} and blocked_id = {q(b)}")
            if not exists:
                sql(f"insert into direct_blocks (user_id, blocked_id) values ({q(a)}, {q(b)})")
                added.append((a, b))
            p = signed(browser, "orga1", origin, "r01-blocage")
            try:
                title = f"{PREFIX}Groupe avec blocage ({who})"
                eid = _publish_to_bots(p, title)
                got = rows(title)
                inv = sql(f"""select p.display_name from event_invites i join profiles p on p.id = i.user_id
                              where i.event_id = {q(got[-1]['id'])} order by 1""") if got else []
                res = {"fiche": bool(eid), "base": got, "invités": [r["display_name"] for r in inv], "messages": alerts(p)}
                note(f"blocage ({who}) : invitation du groupe Bots", res)
                p.shot("blocage")
                if not eid or not got or got[-1]["status"] != "published":
                    p.flag("🔴", f"blocage ({who}) : le groupe Bots ne peut toujours pas être invité", json.dumps(res, ensure_ascii=False))
                elif "Bot Gus" in res["invités"]:
                    p.flag("🟠", f"blocage ({who}) : la personne en blocage est quand même invitée", str(res))
                if len(got) > 1:
                    p.flag("🟠", f"blocage ({who}) : brouillon fantôme", str(got))
            finally:
                p.close()
            for a, b in added:
                sql(f"delete from direct_blocks where user_id = {q(a)} and blocked_id = {q(b)}")
            added.clear()
    finally:
        for a, b in added:
            sql(f"delete from direct_blocks where user_id = {q(a)} and blocked_id = {q(b)}")
        note("blocages de test retirés", sql(f"select count(*) n from direct_blocks where (user_id, blocked_id) in "
                                              f"(({q(olga)}, {q(gus)}), ({q(gus)}, {q(olga)}))"))


# ── Bug 2 : publication ratée en route → brouillon repris ou supprimé (correction C1) ───────────────────────────

BRING = re.compile(r".*/rest/v1/bring_items.*")


def _fail_midway(p, title: str, in_app: bool = False) -> list[dict]:
    page = p.page
    if in_app:  # ouvert depuis la liste (même document) : le retour du navigateur passe par la garde de l'app
        p.goto("/events/")
        p.tap(page.get_by_role("button", name="Proposer un événement"), "+ Proposer", timeout=60000)
        p.see(page.get_by_label("Titre", exact=True), "le formulaire", 30000)
        if page.get_by_role("tab", name="Avancé").get_attribute("aria-selected") != "true":
            p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
    else:
        open_form(p, advanced=True)
    f.fill(p, "Titre", title)
    f.set_date(p, "Début", f.day(8), "19:00")
    p.tap(page.get_by_role("button", name="+ Ajouter un objet"), "+ Ajouter un objet")
    page.get_by_placeholder("Fromage, pain…").last.fill("Chips")
    page.route(BRING, lambda route: route.abort() if route.request.method == "POST" else route.continue_())
    p.tap(page.get_by_role("button", name="Publier", exact=True).last, "Publier (coupure sur « qui amène quoi »)")
    page.wait_for_timeout(4000)
    f.accept_terms_if_asked(p)
    page.wait_for_timeout(2000)
    page.unroute(BRING)
    got = rows(title)
    note(f"« {title} » : message après l'échec", {"message": alerts(p), "base": got})
    p.shot("orphelin-echec")
    return got


def _abandon(p, title: str, how: str) -> None:
    page = p.page
    leave = page.get_by_role("dialog", name=LEAVE)
    if how == "annuler":
        p.tap(page.get_by_role("button", name="Retour : Annuler"), "‹ Annuler")
    else:
        cf.browser_back(p)
    page.wait_for_timeout(1500)
    shown = leave.count() > 0 and leave.first.is_visible()
    text = leave.first.inner_text() if shown else ""
    note(f"orphelin ({how}) : question", {"affichée": shown, "texte": text})
    p.shot(f"orphelin-question-{how}")
    if not shown:
        p.flag("🟠", f"brouillon commencé ({how}) : pas de question en partant", page.url)
        return
    if "brouillon commencé est supprimé" not in text:
        p.flag("🟡", f"brouillon commencé ({how}) : la question ne dit pas que le brouillon sera supprimé", text)
    p.tap(leave.get_by_role("button", name="Abandonner"), "Abandonner")
    page.wait_for_timeout(3000)
    left = rows(title)
    note(f"orphelin ({how}) : après « Abandonner »", {"page": page.url, "base": left})
    if left:
        p.flag("🟠", f"« Abandonner » ({how}) : le brouillon commencé reste en base", str(left))
    if "/event/new" in page.url:
        p.flag("🟠", f"« Abandonner » ({how}) : on reste sur le formulaire", page.url)


def phase_orphelin(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "r01-orphelin")
    page = p.page
    try:
        # a) Échec, puis « Annuler » → Abandonner : le brouillon disparaît
        title = PREFIX + "Orphelin abandonné"
        got = _fail_midway(p, title)
        if len(got) != 1 or got[0]["status"] != "draft":
            p.flag("🟠", "échec en route : état inattendu en base", str(got))
        _abandon(p, title, "annuler")
        # b) Échec, puis « Enregistrer en brouillon » : le même brouillon est gardé, et on part sans question
        title = PREFIX + "Orphelin gardé en brouillon"
        _fail_midway(p, title)
        p.tap(page.get_by_role("button", name="Enregistrer en brouillon"), "Enregistrer en brouillon")
        page.wait_for_timeout(4000)
        got = rows(title)
        bring = sql(f"select count(*) n from bring_items where event_id = {q(got[0]['id'])}")[0]["n"] if got else None
        note("orphelin puis « Enregistrer en brouillon »", {"page": page.url, "base": got, "objets": bring, "messages": alerts(p)})
        p.shot("orphelin-garde")
        if len(got) != 1 or got[0]["status"] != "draft" or bring != 1:
            p.flag("🟠", "orphelin puis « Enregistrer en brouillon » : résultat inattendu", f"{got} objets={bring}")
        # Ce brouillon voulu ne doit pas être effacé par un retour ensuite
        if f.EVENT_URL.search(page.url):
            p.goto(f"/events/event/{got[0]['id']}/edit")
            p.see(page.get_by_label("Titre", exact=True), "le brouillon rouvert", 30000)
            f.fill(p, "Description", "changement puis abandon")
            _abandon_keep(p, title)
    finally:
        p.close()


def _abandon_keep(p, title: str) -> None:
    """Brouillon voulu, rouvert puis modifié : « Abandonner » ne doit PAS le supprimer."""
    page = p.page
    leave = page.get_by_role("dialog", name=LEAVE)
    p.tap(page.get_by_role("button", name="Retour : Annuler"), "‹ Annuler")
    page.wait_for_timeout(1500)
    if not (leave.count() and leave.first.is_visible()):
        note("brouillon rouvert modifié + Annuler : question", False)
        return
    text = leave.first.inner_text()
    p.tap(leave.get_by_role("button", name="Abandonner"), "Abandonner")
    page.wait_for_timeout(2500)
    left = rows(title)
    note("brouillon voulu, rouvert, Abandonner", {"texte": text, "base": left})
    if not left:
        p.flag("🔴", "« Abandonner » sur un brouillon enregistré exprès le SUPPRIME", text)


def phase_orphelin_android(browser, origin, only=None):
    p = signed(browser, "orga2", origin, "r01-orphelin-android")
    try:
        # Formulaire ouvert par son adresse (rechargement, lien) : seul le navigateur demande ; « Quitter » garde le brouillon ?
        title = PREFIX + "Orphelin Android (adresse)"
        _fail_midway(p, title)
        _abandon(p, title, "retour")
        title = PREFIX + "Orphelin Android"
        _fail_midway(p, title, in_app=True)
        _abandon(p, title, "retour")
        # c) Échec puis nouvel essai : publié, un seul événement, un seul objet
        title = PREFIX + "Orphelin repris"
        _fail_midway(p, title)
        p.tap(p.page.get_by_role("button", name="Publier", exact=True).last, "Publier (nouvel essai)")
        p.page.wait_for_timeout(5000)
        got = rows(title)
        bring = sql(f"select count(*) n from bring_items where event_id = {q(got[0]['id'])}")[0]["n"] if got else None
        note("orphelin repris : nouvel essai", {"page": p.page.url, "base": got, "objets": bring})
        if len(got) != 1 or got[0]["status"] != "published" or bring != 1:
            p.flag("🟠", "orphelin repris : résultat inattendu", f"{got} objets={bring}")
    finally:
        p.close()


# ── Refus du filtre de la base (vraie base, sans simulation) ────────────────────────────────────────────────────

def phase_refus(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "r01-refus")
    page = p.page
    try:
        # Titre refusé : rien n'est créé, la phrase de la base s'affiche (sans « content_refused: »)
        open_form(p, advanced=True)
        f.fill(p, "Titre", PREFIX + "Soirée sale arabe")
        f.set_date(p, "Début", f.day(8), "19:00")
        p.tap(page.get_by_role("button", name="Publier", exact=True).last, "Publier (titre haineux)")
        page.wait_for_timeout(4000)
        f.accept_terms_if_asked(p)
        page.wait_for_timeout(1500)
        msg = alerts(p)
        got = rows(PREFIX + "Soirée sale arabe")
        note("titre refusé par le filtre", {"message": msg, "base": got})
        p.shot("refus-titre")
        if got:
            p.flag("🔴", "titre haineux enregistré", str(got))
        if not msg or any("content_refused" in m or "Un souci technique" in m for m in msg):
            p.flag("🟠", "titre refusé : message absent, brut ou générique", str(msg))
        # Question de sondage refusée APRÈS la création du brouillon : message « pas encore publié »
        title = PREFIX + "Sondage refusé"
        f.fill(p, "Titre", title)
        p.tap(page.get_by_role("button", name="+ Ajouter un sondage"), "+ Ajouter un sondage")
        f.fill(p, "Question du sondage 1", "Sale arabe ?")
        page.get_by_label("Sondage 1, option 1", exact=True).fill("Oui")
        page.get_by_label("Sondage 1, option 2", exact=True).fill("Non")
        p.tap(page.get_by_role("button", name="Publier", exact=True).last, "Publier (question haineuse)")
        page.wait_for_timeout(5000)
        msg = alerts(p)
        got = rows(title)
        note("question de sondage refusée", {"message": msg, "base": got})
        p.shot("refus-sondage")
        if any(r["status"] == "published" for r in got):
            p.flag("🔴", "événement publié malgré la question refusée", str(got))
        if not any("pas encore publié" in m for m in msg):
            p.flag("🟡", "question refusée : pas de « pas encore publié »", str(msg))
        # Corrigée puis nouvel essai
        f.fill(p, "Question du sondage 1", "On mange quoi ?")
        p.tap(page.get_by_role("button", name="Publier", exact=True).last, "Publier (question corrigée)")
        page.wait_for_timeout(5000)
        got = rows(title)
        polls = sql(f"select question from polls where event_id = {q(got[0]['id'])}") if got else []
        note("question corrigée : nouvel essai", {"page": page.url, "base": got, "sondages": polls})
        if len(got) != 1 or got[0]["status"] != "published" or len(polls) != 1:
            p.flag("🟠", "question corrigée : résultat inattendu", f"{got} {polls}")
        # Insulte légère : masquée, pas refusée
        open_form(p)
        f.fill(p, "Titre", PREFIX + "Fête du connard")
        f.set_date(p, "Début", f.day(8), "19:00")
        eid = submit(p, "Publier")
        stored = sql(f"select title from events where id = {q(eid)}") if eid else []
        note("titre avec insulte légère", {"fiche": bool(eid), "base": stored})
        p.shot("refus-masque")
    finally:
        p.close()


# ── Bug 3 : messages techniques en anglais (réponses simulées de la base) ───────────────────────────────────────

FAKE = [
    ("57014", "canceling statement due to statement timeout", 500),
    ("25P02", "current transaction is aborted, commands ignored until end of transaction block", 500),
    ("22003", "numeric field overflow", 400),
    ("22P02", 'invalid input syntax for type integer: "2.7"', 400),
    ("PGRST301", "JWT expired", 401),
    ("XX000", "Something unexpected happened in the database", 500),
    ("", "upstream connect error or disconnect/reset before headers. reset reason: connection termination", 503),
]


def phase_messages(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "r01-messages")
    page = p.page
    try:
        for code, message, status in FAKE:
            open_form(p)
            f.fill(p, "Titre", PREFIX + "Message " + (code or "503"))
            f.set_date(p, "Début", f.day(8), "19:00")
            body = json.dumps({"code": code, "message": message, "details": None, "hint": None})

            def make(body: str, status: int):
                def fake(route, _request=None):
                    if route.request.method == "POST":
                        route.fulfill(status=status, body=body, headers={"content-type": "application/json"})
                    else:
                        route.continue_()
                return fake
            fake = make(body, status)
            pat = re.compile(r".*/rest/v1/events(\?.*)?$")
            page.route(pat, fake)
            p.tap(page.get_by_role("button", name="Publier", exact=True).last, f"Publier ({message[:30]})")
            page.wait_for_timeout(3000)
            f.accept_terms_if_asked(p)
            page.wait_for_timeout(1500)
            page.unroute(pat)
            shown = alerts(p)
            note(f"message pour « {message[:50]} »", shown)
            english = [m for m in shown if re.search(r"\b(the|statement|transaction|overflow|invalid|syntax|expired|error|reset|upstream)\b", m, re.I)]
            if english or not shown:
                p.shot("message-anglais")
                p.flag("🟠", f"erreur technique affichée en anglais ou rien : « {message[:60]} »", str(shown))
    finally:
        p.close()


# ── Dates : cas restés ouverts après la correction C1 ───────────────────────────────────────────────────────────

def phase_dates_passees(browser, origin, only=None):
    p = signed(browser, "orga1", origin, "r01-dates")
    page = p.page
    cases = [
        ("date limite de réponse déjà passée", "rsvp"),
        ("fin du vote déjà passée", "poll"),
    ]
    try:
        for case, kind in cases:
            open_form(p, advanced=True)
            title = f"{PREFIX}Date {case}"
            f.fill(p, "Titre", title)
            if kind == "rsvp":
                f.set_date(p, "Début", f.day(8), "19:00")
                f.set_date(p, "Date limite de réponse (optionnel)", f.day(-1), "12:00")
            else:
                p.tap(page.get_by_role("tab", name="Date à définir"), "Date à définir")
                f.set_date(p, "Créneau 1", f.day(8), "19:00")
                f.set_date(p, "Créneau 2", f.day(9), "19:00")
                f.set_date(p, "Fin du vote (optionnel)", f.day(-1), "12:00")
            p.tap(page.get_by_role("button", name="Enregistrer en brouillon"), "Enregistrer en brouillon")
            page.wait_for_timeout(3500)
            f.accept_terms_if_asked(p)
            page.wait_for_timeout(1000)
            got = rows(title)
            note(f"date : {case}", {"message": alerts(p), "base": got})
            p.shot("date-passee")
            if got:
                p.flag("🟡", f"{case} : accepté sans un mot (l'événement naît fermé)", str(got))
    finally:
        p.close()


def phase_modifier_passe(browser, origin, only=None):
    """Événement déjà commencé (début il y a 3 h) : le modifier sans toucher au début reste possible ; un brouillon
    dont le début est passé peut-il être publié tel quel ?"""
    olga = uid("Bot Olga")
    start = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:00+00")
    made = {}
    for status in ("draft", "published"):
        title = f"{PREFIX}Déjà commencé ({status})"
        r = sql(f"""insert into public.events (title, created_by, status, date_mode, starts_at, visibility, public_link)
                   values ({q(title)}, {q(olga)}, 'draft', 'fixed', {q(start)}, 'all', true) returning id""")
        made[status] = (r[0]["id"], title)
        if status == "published":  # public : ne prévient jamais personne (events_public_silent)
            sql(f"update public.events set status = 'published' where id = {q(r[0]['id'])}")
    p = signed(browser, "orga1", origin, "r01-modifier-passe")
    page = p.page
    try:
        eid, title = made["published"]
        p.goto(f"/events/event/{eid}/edit")
        p.see(page.get_by_label("Titre", exact=True), "Modifier (déjà commencé)", 60000)
        page.wait_for_timeout(1500)
        f.fill(p, "Description", "Ajout après le début")
        p.tap(page.get_by_role("button", name="Enregistrer", exact=True).last, "Enregistrer")
        page.wait_for_timeout(4000)
        desc = sql(f"select description from events where id = {q(eid)}")[0]["description"]
        note("modifier un événement commencé (début inchangé)", {"message": alerts(p), "base": desc, "page": page.url})
        if desc != "Ajout après le début":
            p.flag("🟠", "un événement déjà commencé ne peut plus être modifié", str(alerts(p)))
        eid, title = made["draft"]
        p.goto(f"/events/event/{eid}/edit")
        p.see(page.get_by_label("Titre", exact=True), "brouillon au début passé", 60000)
        page.wait_for_timeout(1500)
        btn = cf.submit_btn(p)
        p.tap(btn[0], f"{btn[1]} (brouillon au début passé)")
        page.wait_for_timeout(4000)
        st = sql(f"select status from events where id = {q(eid)}")[0]["status"]
        note("brouillon au début passé : Publier", {"message": alerts(p), "statut": st})
        p.shot("brouillon-passe")
        if st in ("published", "pending"):
            p.flag("🟡", "un brouillon dont le début est passé se publie sans avertissement", f"statut={st}")
    finally:
        p.close()


def phase_nettoyage(browser=None, origin=None, only=None):
    cf.phase_nettoyage()


def main(argv: list[str]) -> None:
    origin = load_state()["origin"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv:
            print(f"════ phase {name} ════", flush=True)
            try:
                globals()[f"phase_{name}"](browser, origin)
            except Exception as e:
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
