"""Campagne 2, correction lot D (web : fiche, liste, erreurs, accessibilité, réglages des notifications) : rejoue pour de
vrai, base de TEST, réglages de la prod, les constats des rapports 01, 04, 05, 06, 07, 09 et 10 que le lot D corrige.

Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.fix_lot_d <phase> [<phase>…]   (serveur du banc lancé avant)
Phases : prep, liste, passe, refus, introuvable, hors_ligne, requetes, entete, contraste, notifs, paiement, menage.
Titres : « [FIX-D] … », supprimés par « menage »."""
from __future__ import annotations

import json
import re
import sys
import traceback

from playwright.sync_api import sync_playwright

from tests.bots.bench import anomaly, load_state, phone as raw_phone, save_state
import time

from tests.bots import common, vie_evenement
from tests.bots.common import q
from tests.bots.vie_evenement import btn, create, go_list, in_list, open_event


def sql(query: str):
    """API de gestion partagée par les agents : on réessaie sur 429 (trop de requêtes) au lieu d'abandonner la phase."""
    for attempt in range(8):
        try:
            return common.sql(query)
        except RuntimeError as e:
            if "429" not in str(e) or attempt == 7:
                raise
            time.sleep(5 * (attempt + 1))


vie_evenement.sql = sql  # ev(), uid()… de vie_evenement passent aussi par la reprise


def ev(eid: str) -> dict:
    rows = sql(f"select * from public.events where id = '{eid}'")
    return rows[0] if rows else {}


def uid(key: str) -> str:
    return vie_evenement.uid(key)

PREFIX = "[FIX-D]"
GONE = "Cet événement n’existe plus ou ne t’est pas ouvert."
ENGLISH = re.compile(r"Cannot coerce|statement timeout|transaction is aborted|Unmatched Route|Page could not be found")


def phone(browser, key: str, origin: str, phase: str):
    """Téléphone du bot, connecté (vrai écran de connexion la première fois, session gardée ensuite)."""
    p = raw_phone(browser, key, origin, phase)
    p.sign_in()
    return p


def ok(p, cond: bool, what: str, severity: str = "🟠") -> bool:
    p.log(("✅ " if cond else "❌ ") + what)
    if not cond:
        p.flag(severity, what)
    return cond


def no_english(p, where: str) -> None:
    body = p.page.locator("body").inner_text()
    ok(p, not ENGLISH.search(body), f"aucun message technique anglais ({where})")


# ── Préparation ────────────────────────────────────────────────────────────────────────────────────────────────

def phase_prep(browser, origin):
    p = phone(browser, "orga2", origin, "prep")
    try:
        p.sign_in()
        ids = {}
        for key, title, offset in (("annule", f"{PREFIX} Annulé à venir", 3), ("payant", f"{PREFIX} Soirée payante", 4),
                                   ("passe", f"{PREFIX} Déjà passé", 5)):
            ids[key] = create(p, title, offset, ["Bots"])
            p.log(f"{key} → {ids[key]}")
        save_state(fixd=ids)
        # Payant (prix posé dans la base de TEST, comme le formulaire avancé) ; « passé » : terminé depuis 2 jours.
        sql(f"update public.events set price_chf = 15, payment_info = 'Twint 079 000 01 04' where id = '{ids['payant']}'")
        sql(f"update public.events set starts_at = now() - interval '2 days', ends_at = now() - interval '2 days' + interval '3 hours' where id = '{ids['passe']}'")
    finally:
        p.close()
    v = phone(browser, "vip1", origin, "prep")
    try:
        v.sign_in()
        ids = load_state()["fixd"]
        ids["proposition"] = create(v, f"{PREFIX} Proposition de Victor", 6, ["Bots"], None)
        save_state(fixd=ids)
        v.log(f"proposition → {ids['proposition']} statut {ev(ids['proposition']).get('status')}")
    finally:
        v.close()


# ── 1. Un événement à venir annulé reste dans « À venir » (rapport 06 bug 2) ───────────────────────────────────

def phase_liste(browser, origin):
    ids = load_state()["fixd"]
    o = phone(browser, "orga2", origin, "liste")
    try:
        if ev(ids["annule"]).get("status") == "cancelled":
            o.log("déjà annulé (passage précédent)")
            raise StopIteration
        open_event(o, ids["annule"])
        o.tap(btn(o, "Annuler l’événement"), "Annuler l’événement")
        o.tap(btn(o, "Oui, annuler"), "Oui, annuler")
        o.page.wait_for_timeout(4000)
        ok(o, ev(ids["annule"]).get("status") == "cancelled", "base : événement annulé")
    except StopIteration:
        pass
    finally:
        o.close()
    for key in ("orga2", "vip1", "admin"):
        p = phone(browser, key, origin, "liste")
        try:
            p.sign_in()
            go_list(p)
            title = f"{PREFIX} Annulé à venir"
            seen = in_list(p, title)
            ok(p, seen, f"« À venir » montre l'événement annulé ({key})")
            if seen:
                card = p.page.get_by_role("link", name=re.compile(re.escape(title)))
                label = card.first.get_attribute("aria-label") or ""
                ok(p, "annulé" in label, f"carte annoncée « annulé » au lecteur d'écran : « {label} »")
                deco = p.page.get_by_text(title, exact=True).first.evaluate("e => getComputedStyle(e).textDecorationLine")
                ok(p, "line-through" in deco, f"titre barré ({deco})", "🟡")
                ok(p, p.page.get_by_text("Annulé", exact=True).count() > 0, "pastille « Annulé »")
            p.shot("liste-annule")
            if key == "admin" and seen:
                p.tap(p.page.get_by_role("link", name=re.compile(re.escape(title))).first, "ouvre l'annulé")
                ok(p, p.see(btn(p, "Rouvrir l’événement"), "Rouvrir l’événement", 60000), "l'admin retrouve « Rouvrir »")
        finally:
            p.close()


# ── 2. Événement terminé : réponses fermées à l'écran (rapport 06 bug 4) ──────────────────────────────────────

def phase_passe(browser, origin):
    ids = load_state()["fixd"]
    p = phone(browser, "vip1", origin, "passe")
    try:
        open_event(p, ids["passe"])
        p.shot("fiche-passee")
        ok(p, p.page.get_by_text("Les réponses sont closes", exact=False).count() > 0, "« Les réponses sont closes »")
        present = p.page.get_by_role("button", name=re.compile("^Présent"))
        disabled = present.count() == 0 or all(present.nth(i).is_disabled() or present.nth(i).get_attribute("aria-disabled") == "true"
                                               for i in range(present.count()))
        ok(p, disabled, "bouton Présent grisé sur un événement terminé")
        rows = sql(f"select status from public.rsvps where event_id = '{ids['passe']}' and user_id = '{uid('vip1')}'")
        ok(p, not rows, "aucune réponse enregistrée")
    finally:
        p.close()


# ── 3. Refuser depuis la fiche : confirmation + motif (rapport 06 bug 8) ───────────────────────────────────────

def phase_refus(browser, origin):
    ids = load_state()["fixd"]
    eid = ids.get("proposition")
    p = phone(browser, "admin", origin, "refus")
    try:
        if not eid or ev(eid).get("status") != "pending":
            p.flag("🟠", f"proposition absente ou pas en attente : {eid}")
            return
        open_event(p, eid)
        p.tap(btn(p, "Refuser"), "Refuser")
        p.page.wait_for_timeout(800)
        ok(p, ev(eid).get("status") == "pending", "un toucher sur Refuser ne refuse pas encore")
        field = p.page.get_by_label("Motif du refus (optionnel)")
        ok(p, field.count() > 0, "champ du motif affiché")
        p.shot("refus-motif")
        p.tap(btn(p, "Annuler"), "Annuler (garder)")
        ok(p, ev(eid).get("status") == "pending", "Annuler garde la proposition")
        p.tap(btn(p, "Refuser"), "Refuser")
        p.type(p.page.get_by_label("Motif du refus (optionnel)"), "Date déjà prise (test lot D)", "le motif")
        p.tap(btn(p, "Confirmer le refus"), "Confirmer le refus")
        p.page.wait_for_timeout(4000)
        row = ev(eid)
        ok(p, row.get("status") == "rejected" and row.get("rejection_reason") == "Date déjà prise (test lot D)",
           f"base : refusé avec motif ({row.get('status')}, {row.get('rejection_reason')})")
        ok(p, p.see(p.page.get_by_text("Motif du refus : Date déjà prise", exact=False), "motif sur la fiche", 30000), "motif affiché")
    finally:
        p.close()


# ── 4. Lien vers un événement supprimé / non ouvert, page inconnue (rapports 06, 09, 10) ──────────────────────

def phase_introuvable(browser, origin):
    ids = load_state()["fixd"]
    o = phone(browser, "orga2", origin, "introuvable")
    try:
        o.goto("/events/event/00000000-0000-4000-8000-000000000000")
        o.see(o.page.get_by_text(GONE), "message événement introuvable", 60000)
        o.shot("fiche-inexistante")
        ok(o, o.page.get_by_text(GONE).count() > 0, "« Cet événement n’existe plus ou ne t’est pas ouvert. »")
        ok(o, btn(o, "Réessayer").count() == 0, "pas de « Réessayer » inutile")
        ok(o, btn(o, "Retour aux événements").count() > 0, "« Retour aux événements »")
        no_english(o, "fiche inexistante")
        o.goto("/events/nimportequoi")
        o.see(o.page.get_by_text("Page introuvable").first, "page introuvable", 30000)
        o.shot("page-inconnue")
        ok(o, o.page.get_by_role("heading", name="Page introuvable").count() > 0, "page inconnue en français (titre)")
        no_english(o, "page inconnue")
    finally:
        o.close()
    # Guest connectée, pas invitée à un événement de groupe : même message (avant : « Cannot coerce… » + Réessayer).
    g = phone(browser, "guest2", origin, "introuvable")
    try:
        g.sign_in()
        g.goto(f"/events/event/{ids['payant']}")
        g.page.wait_for_timeout(8000)
        g.shot("fiche-non-invitee")
        body = g.page.locator("body").inner_text()
        g.log(f"écran : {body[:200]!r}")
        no_english(g, "fiche non invitée")
    finally:
        g.close()


# ── 5. Hors ligne : « Pas de connexion », puis la fiche se charge seule (rapport 09 bug 3) ─────────────────────

def phase_hors_ligne(browser, origin):
    ids = load_state()["fixd"]
    p = phone(browser, "orga2", origin, "hors_ligne")
    try:
        go_list(p)
        p.ctx.set_offline(True)
        card = p.page.get_by_role("link", name=re.compile("Soirée payante")).first
        p.tap(card, "carte « Soirée payante » (hors ligne)")
        p.page.wait_for_timeout(6000)
        p.shot("fiche-hors-ligne")
        ok(p, p.page.get_by_text("Pas de connexion", exact=False).count() > 0, "« Pas de connexion » au lieu du squelette sans fin")
        p.ctx.set_offline(False)
        p.page.evaluate("window.dispatchEvent(new Event('online'))")
        ok(p, p.see(p.page.get_by_role("heading", name=re.compile("Soirée payante")), "fiche chargée au retour du réseau", 60000),
           "la fiche se charge seule au retour du réseau")
        p.shot("fiche-reseau-revenu")
    except Exception:
        p.ctx.set_offline(False)
        raise
    finally:
        p.close()


# ── 6. La fiche ne lit plus tout Party, temps réel filtré (rapports 06, 09, 10) ───────────────────────────────

def phase_requetes(browser, origin):
    ids = load_state()["fixd"]
    p = phone(browser, "vip1", origin, "requetes")
    seen: list[str] = []
    try:
        go_list(p)
        p.page.on("request", lambda r: seen.append(r.url) if "/rest/v1/" in r.url else None)
        p.page.on("websocket", lambda ws: ws.on("framesent", lambda payload: seen.append("WS " + str(payload)[:600])))
        open_event(p, ids["payant"])
        p.page.wait_for_timeout(3000)
        rest = [u for u in seen if u.startswith("http")]
        profiles = [u for u in rest if "/profiles?" in u and "display_name" in u and "events_created_by" not in u]
        ok(p, all("id=in." in u for u in profiles), f"profils filtrés sur les personnes de l'événement ({len(profiles)} requêtes)")
        ok(p, not [u for u in rest if "/poll_results?" in u and "poll_id=in." not in u], "résultats de sondages jamais lus en entier")
        ok(p, not [u for u in rest if "/poll_votes?" in u and "poll_id=in." not in u], "votes jamais lus en entier")
        # Le canal de la fiche (« event-<id> ») ; « pending » est la pastille globale de l'onglet (lib/pending.ts).
        subs = [u for u in seen if u.startswith("WS") and "postgres_changes" in u and f"realtime:event-{ids['payant']}" in u]
        ok(p, bool(subs), "canal temps réel de la fiche ouvert")
        unfiltered = [s for s in subs if re.search(r'"table":"(date_votes|poll_votes)"(?![^}]*"filter")', s)]
        ok(p, not unfiltered, "aucun abonnement temps réel aux votes de tout Party")
        (p.dir / "requetes-fiche.json").write_text(json.dumps(seen, ensure_ascii=False, indent=1))
    finally:
        p.close()


# ── 7. En-tête à 360 px, texte agrandi (rapport 09 bug 4) ; ✕ 44 px (bug 7) ───────────────────────────────────

def phase_entete(browser, origin):
    ids = load_state()["fixd"]
    p = phone(browser, "vip1", origin, "entete")
    try:
        p.page.set_viewport_size({"width": 360, "height": 780})
        p.goto(f"/events/event/{ids['payant']}")  # ouvert par un lien : « ‹ Événements » dans l'en-tête
        p.page.get_by_role("heading", level=1).first.wait_for(timeout=60000)
        p.page.add_style_tag(content="html{zoom:1.3}")
        p.page.wait_for_timeout(1200)
        p.shot("entete-360-130")
        back = p.page.get_by_role("button", name=re.compile("^Retour"))
        mute = p.page.get_by_role("button", name=re.compile("sourdine|Réactiver", re.I))
        if back.count() and mute.count():
            b, m = back.first.bounding_box(), mute.first.bounding_box()
            ok(p, b["x"] + b["width"] <= m["x"] + 1, f"« ‹ Événements » ne passe plus sous la Sourdine ({b} / {m})")
        else:
            p.log(f"retour {back.count()} / sourdine {mute.count()}")
        p.page.add_style_tag(content="html{zoom:1}")
        p.page.set_viewport_size({"width": 390, "height": 844})
        p.page.reload()
        p.page.get_by_role("heading", level=1).first.wait_for(timeout=60000)
        p.page.wait_for_timeout(1500)
        report = p.page.get_by_role("button", name="Signaler cet événement")
        report.scroll_into_view_if_needed()
        p.tap(report, "Signaler cet événement")
        close = p.page.get_by_role("button", name="Fermer").first
        close.wait_for(timeout=15000)
        box = close.bounding_box()
        p.shot("feuille-signaler")
        ok(p, box["width"] >= 44 and box["height"] >= 44, f"✕ de la feuille {box['width']}×{box['height']}", "🟡")
        p.tap(close, "✕")
    finally:
        p.close()


# ── 8. Contraste des pastilles actives (rapport 09 bug 5) ─────────────────────────────────────────────────────

def phase_contraste(browser, origin):
    p = phone(browser, "vip1", origin, "contraste")
    try:
        go_list(p)
        colors = p.page.evaluate("""() => [...document.querySelectorAll('div')]
            .map(e => getComputedStyle(e).backgroundColor).filter(c => c.includes('217, 42, 115'))""")
        ok(p, bool(colors), "pastille active en rose foncé (#D92A73)", "🟡")
        # Texte blanc posé (directement ou par la pastille glissante) sur un fond #FF4F9A : contraste 3,07:1.
        white_on_pink = p.page.evaluate("""() => [...document.querySelectorAll('div')]
            .filter(e => getComputedStyle(e).color === 'rgb(255, 255, 255)' && e.innerText && e.innerText.trim())
            .filter(e => { const r = e.getBoundingClientRect();
                return document.elementsFromPoint(r.x + r.width / 2, r.y + r.height / 2)
                  .some(b => getComputedStyle(b).backgroundColor === 'rgb(255, 79, 154)'); })
            .map(e => e.innerText.trim()).slice(0, 10)""")
        ok(p, not white_on_pink, f"plus de texte blanc sur #FF4F9A ({white_on_pink})", "🟡")
        hidden = p.page.evaluate("""() => [...document.querySelectorAll('[aria-hidden="true"] [tabindex="0"]')].length""")
        p.log(f"éléments focalisables dans une zone masquée (haut de liste) : {hidden}")
        p.finger_scroll("liste vers le bas", distance=-700)
        p.page.wait_for_timeout(800)
        hidden = p.page.evaluate("""() => [...document.querySelectorAll('[aria-hidden="true"] [tabindex="0"], [aria-hidden="true"][tabindex="0"]')]
            .map(e => e.getAttribute('aria-label'))""")
        ok(p, "Proposer un événement" not in hidden, f"« + Proposer » effacé non focalisable ({hidden})", "🟡")
    finally:
        p.close()


# ── 9. Réglages › Notifications : heures de silence et interrupteurs (rapport 07 bugs 4 et 5) ─────────────────

def prefs(key: str) -> dict:
    return sql(f"select * from public.notification_prefs where user_id = '{uid(key)}'")[0]


def phase_notifs(browser, origin):
    before = prefs("vip1")
    p = phone(browser, "vip1", origin, "notifs")
    try:
        if before["quiet_start"] is None:
            sql(f"update public.notification_prefs set quiet_start = '23:00', quiet_end = '08:00' where user_id = '{uid('vip1')}'")
        p.goto("/events/settings/notifications")
        start = p.page.get_by_label("Début (HH:MM)")
        start.wait_for(timeout=60000)
        start.fill("")
        start.type("22:30")
        p.page.keyboard.press("Tab")
        p.page.wait_for_timeout(3500)
        ok(p, str(prefs("vip1")["quiet_start"]).startswith("22:30"), f"Début enregistré au départ du champ ({prefs('vip1')['quiet_start']})")
        end = p.page.get_by_label("Fin (HH:MM)")
        end.fill("")
        end.type("7h")
        p.page.keyboard.press("Enter")
        p.page.wait_for_timeout(3500)
        ok(p, str(prefs("vip1")["quiet_end"]).startswith("07:00"), f"Fin « 7h » enregistrée à Entrée ({prefs('vip1')['quiet_end']})")
        start.fill("")
        start.type("99")
        p.page.keyboard.press("Tab")
        p.page.wait_for_timeout(1000)
        ok(p, p.page.get_by_text("Saisis une heure entre 00:00 et 23:59", exact=False).count() > 0, "message de saisie visible")
        start.fill("")
        start.type("07:00")
        p.page.keyboard.press("Tab")
        p.page.wait_for_timeout(1000)
        ok(p, p.page.get_by_text("doivent être différents", exact=False).count() > 0, "message « début = fin » visible")
        p.shot("silence")
        ok(p, p.page.get_by_text("Nouveau sondage", exact=True).count() > 0, "Membre VIP : « Nouveau sondage » affiché")
    finally:
        sql(f"""update public.notification_prefs set quiet_start = {q(str(before['quiet_start'])) if before['quiet_start'] else 'null'},
                quiet_end = {q(str(before['quiet_end'])) if before['quiet_end'] else 'null'} where user_id = '{uid('vip1')}'""")
        p.close()
    for key in ("membre1", "guest2"):
        m = phone(browser, key, origin, "notifs")
        try:
            m.sign_in()
            m.goto("/events/settings/notifications")
            m.page.get_by_text("Pause et heures de silence").wait_for(timeout=60000)
            m.page.wait_for_timeout(1000)
            m.shot("interrupteurs")
            gone = ["Nouveau sondage", "Rappel pour voter", "Un organisateur répond pour moi", "Paiement de ma place confirmé",
                    "Billet prêt", "Réponses à mes événements", "Ma proposition validée ou refusée", "Quelqu’un dit avoir payé",
                    "Messages des discussions"]
            shown = [t for t in gone if m.page.get_by_text(t, exact=True).count()]
            ok(m, not shown, f"{key} : interrupteurs jamais honorés masqués (encore là : {shown})")
            ok(m, m.page.get_by_text("Place libérée", exact=True).count() > 0, f"{key} : « Place libérée » (honoré) reste")
        finally:
            m.close()


# ── 10. « J'ai payé » / « Reçu » sans recharger (rapport 05 bug 5) ────────────────────────────────────────────

def phase_paiement(browser, origin):
    ids = load_state()["fixd"]
    eid = ids["payant"]
    org = phone(browser, "orga2", origin, "paiement")
    inv = phone(browser, "vip1", origin, "paiement")
    try:
        open_event(inv, eid)
        present = inv.page.get_by_role("button", name=re.compile("^Présent")).first
        inv.tap(present, "Présent")
        inv.page.wait_for_timeout(4000)
        open_event(org, eid)
        org.shot("orga-avant")
        pay = inv.page.get_by_role("button", name=re.compile("Payer")).first
        inv.tap(pay, "Payer l’organisateur")
        inv.tap(inv.page.get_by_role("button", name=re.compile("J’ai payé|J'ai payé")).first, "J’ai payé")
        inv.page.wait_for_timeout(2000)
        inv.shot("invite-declare")
        ok(org, org.see(org.page.get_by_role("button", name="Reçu ✓").first, "« Reçu ✓ » chez l'organisateur sans recharger", 45000),
           "la déclaration apparaît chez l'organisateur sans recharger")
        org.shot("orga-a-confirmer")
        org.tap(org.page.get_by_role("button", name="Reçu ✓").first, "Reçu ✓")
        ok(inv, inv.see(inv.page.get_by_text("Place payée", exact=False).first, "« Place payée » chez l'invité sans recharger", 45000),
           "« Place payée » chez l'invité sans recharger")
        inv.shot("invite-paye")
    finally:
        org.close()
        inv.close()


# ── 11. Co-organisateur « Membre » : Activité « Co-organisateur », pas d'« Annuler » sans « Modifier » (note du lot A) ──

def phase_coorga(browser, origin):
    ids = load_state()["fixd"]
    eid = ids["payant"]
    # Ajout comme le formulaire (ligne event_organizers) ; le déclencheur de la base envoie « coorganizer_added ».
    sql(f"insert into public.event_organizers (event_id, user_id) values ('{eid}', '{uid('membre1')}') on conflict do nothing")
    m = phone(browser, "membre1", origin, "coorga")
    try:
        kinds = sql(f"select kind, title from public.notifications where event_id = '{eid}' and user_id = '{uid('membre1')}'")
        m.log(f"notifications en base : {kinds}")
        m.goto("/events/activity")
        m.page.get_by_text("Notifications des événements").wait_for(timeout=60000)
        m.page.wait_for_timeout(2500)
        m.shot("activite")
        if any(k["kind"] == "coorganizer_added" for k in kinds):
            title = next(k["title"] for k in kinds if k["kind"] == "coorganizer_added")
            ok(m, m.page.get_by_text(title, exact=True).count() > 0, f"Activité montre « {title} » (coorganizer_added)")
        else:
            m.flag("🟡", "pas de notification coorganizer_added en base (migration du lot A absente de TEST ?)")
        open_event(m, eid)
        m.shot("fiche-coorga-membre")
        ok(m, btn(m, "Modifier").count() == 0, "co-organisateur Membre : pas de « Modifier »")
        ok(m, btn(m, "Annuler l’événement").count() == 0, "co-organisateur Membre : pas d'« Annuler l’événement »")
    finally:
        m.close()
    a = phone(browser, "admin", origin, "coorga")
    try:
        open_event(a, ids["annule"])
        if btn(a, "Rouvrir l’événement").count():
            a.tap(btn(a, "Rouvrir l’événement"), "Rouvrir l’événement")
            a.tap(btn(a, "Oui, rouvrir"), "Oui, rouvrir")
            a.page.wait_for_timeout(4000)
        ok(a, ev(ids["annule"]).get("status") == "published", "rouvert par l'admin")
        notes = sql(f"select p.display_name who, n.kind, n.title from public.notifications n join public.profiles p on p.id = n.user_id where n.event_id = '{ids['annule']}' order by n.created_at")
        a.log(f"notifications de l'événement : {notes}")
    finally:
        a.close()


# ── Ménage ─────────────────────────────────────────────────────────────────────────────────────────────────────

def phase_menage(browser, origin):
    rows = sql(f"delete from public.events where title like {q(PREFIX + '%')} returning id, title") or []
    print(f"supprimés : {rows}")
    left = sql(f"select count(*) n from public.events where title like {q(PREFIX + '%')}")[0]["n"]
    print(f"restants : {left}")


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
