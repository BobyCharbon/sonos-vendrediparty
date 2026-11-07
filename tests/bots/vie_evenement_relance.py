"""Campagne 2, RELANCE de l'agent 06 : vie de l'événement côté organisation, après les corrections (lots A, C1, D).

Rejoue les phases de `vie_evenement.py` (préfixe « [R-06] ») ; les phases dont le comportement attendu a changé sont
redéfinies ici : retour arrière (« Abandonner les changements ? »), en-tête de Modifier, co-organisateurs (Membre non
proposé, notification), annulé visible dans « À venir », « Événement rétabli », notification gardée après suppression,
refus depuis la fiche (confirmation + motif), événement passé (réponses closes à l'écran, et par l'API), blocage.

Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.vie_evenement_relance <phase> [<phase>…]"""
from __future__ import annotations

import re
import sys
import traceback

import httpx
from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots import vie_evenement as ve
from tests.bots.bench import anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, GROUP_BOTS, TEST_URL, Session, q, sql

PREFIX = ve.PREFIX = "[R-06]"
btn, ev, notes, open_event, open_edit, advanced, save, uid, db_now = (
    ve.btn, ve.ev, ve.notes, ve.open_event, ve.open_edit, ve.advanced, ve.save, ve.uid, ve.db_now)
go_list, tab, in_list, organizers, create, error_shown = ve.go_list, ve.tab, ve.in_list, ve.organizers, ve.create, ve.error_shown
held = ve.held

# Phases reprises telles quelles (préfixe changé)
phase_connexion = ve.phase_connexion
phase_preparer = ve.phase_preparer
phase_modifier = ve.phase_modifier
phase_visibilite = ve.phase_visibilite
phase_liste = ve.phase_liste
phase_reseau = ve.phase_reseau


def back_nav(page) -> None:
    """Retour du navigateur ; « Abandonner les changements ? » retient la navigation (go_back n'aboutit pas)."""
    try:
        page.go_back(timeout=4000)
    except Exception:
        pass


def boxes_overlap(a: dict | None, b: dict | None) -> bool:
    if not a or not b:
        return False
    return not (a["x"] + a["width"] <= b["x"] or b["x"] + b["width"] <= a["x"]
                or a["y"] + a["height"] <= b["y"] or b["y"] + b["height"] <= a["y"])


# ── Bug 1 : blocage dans le groupe ─────────────────────────────────────────────────────────────────────────────

def phase_blocage(browser, origin):
    olga, gus = uid("orga1"), uid("guest1")
    had = sql(f"select count(*) n from public.direct_blocks where user_id = '{olga}' and blocked_id = '{gus}'")[0]["n"]
    save_state(r6_block_had=bool(had))
    if not had:
        sql(f"insert into public.direct_blocks (user_id, blocked_id) values ('{olga}', '{gus}')")
    p = phone(browser, "orga1", origin, "blocage")
    try:
        eid = create(p, f"{PREFIX} Blocage", 8, [GROUP_BOTS])
        save_state(r6_block=eid)
        p.shot("blocage-apres-publier")
        body = p.page.locator("body").inner_text()
        if "ne peux pas inviter" in body:
            p.flag("🔴", "blocage : « tu ne peux pas inviter cette personne » à la publication pour un groupe")
    finally:
        p.close()
    rows = sql(f"select id, status from public.events where title = {q(PREFIX + ' Blocage')}")
    print("événements Blocage :", rows)
    if rows:
        eid = rows[0]["id"]
        inv = sql(f"""select p.display_name from public.event_invites i join public.profiles p on p.id = i.user_id
                      where i.event_id = '{eid}' order by 1""")
        names = [r["display_name"] for r in inv or []]
        print("invités :", names)
        if rows[0]["status"] != "published":
            anomaly("orga1", "🔴", f"blocage : l'événement de groupe reste en {rows[0]['status']}")
        if "Bot Gus" in names:
            anomaly("orga1", "🟠", "blocage : le membre bloqué est quand même invité")
        if "Bot Victor" not in names:
            anomaly("orga1", "🟠", "blocage : les autres membres du groupe ne sont pas invités", str(names))
    if len(rows) > 1:
        anomaly("orga1", "🟠", f"blocage : {len(rows)} événements créés (brouillons laissés ?)", str(rows))
    if not had:
        sql(f"delete from public.direct_blocks where user_id = '{olga}' and blocked_id = '{gus}'")


# ── Bugs 11, 12 + dates : formulaire de modification ──────────────────────────────────────────────────────────

def phase_erreurs(browser, origin):
    eid = load_state()["c6_e1"]
    before = ev(eid)
    p = phone(browser, "orga2", origin, "erreurs")
    page = p.page
    try:
        open_edit(p, eid)
        with p.step("en-tête de Modifier : retour et titre ne se chevauchent pas"):
            back = page.get_by_text(re.compile("Annuler$")).first
            title = page.get_by_text("Modifier", exact=True).first
            bb, tb = back.bounding_box() if back.count() else None, title.bounding_box() if title.count() else None
            p.log(f"en-tête : retour={bb} titre={tb} libellé retour={back.inner_text() if back.count() else None!r}")
            p.shot("entete-modifier")
            if boxes_overlap(bb, tb):
                p.flag("🟡", "en-tête de Modifier : le retour chevauche toujours le titre")
        advanced(p)
        cases = [
            ("Titre", "", "Il manque un titre"),
            ("Prix / pers. (CHF)", "-5", "Le prix doit être un montant positif"),
            ("Prix / pers. (CHF)", "12.345", "deux chiffres après la virgule"),
            ("Nombre de places (vide = illimité)", "0", "Nombre de places invalide"),
            ("Lien (site, carte…)", "javascript:alert(1)", "Le lien doit commencer par https"),
            ("Lien (site, carte…)", "pas une adresse", "Le lien doit être une adresse complète"),
        ]
        original = {"Titre": before["title"], "Prix / pers. (CHF)": "", "Nombre de places (vide = illimité)": "",
                    "Lien (site, carte…)": ""}
        for label, value, message in cases:
            with p.step(f"erreur {label} = « {value} »"):
                f.fill(p, label, value)
                p.tap(btn(p, "Enregistrer").last, "Enregistrer")
                page.wait_for_timeout(1200)
                if not error_shown(p, message):
                    p.flag("🟠", f"modification : « {value} » dans {label} sans le message « {message} »")
                if not ve.EDIT_URL.search(page.url):
                    p.flag("🔴", f"modification : enregistré malgré « {value} » dans {label}")
                    open_edit(p, eid)
                    advanced(p)
                f.fill(p, label, original[label])
        with p.step("fin avant le début"):
            f.set_date(p, "Début", f.day(7), "19:30")
            f.set_date(p, "Fin (optionnel)", f.day(6), "18:00")
            p.tap(btn(p, "Enregistrer").last, "Enregistrer")
            page.wait_for_timeout(1200)
            if not error_shown(p, "La fin doit être après le début"):
                p.flag("🟠", "fin avant le début : pas de message")
        with p.step("début déplacé dans le passé"):
            f.set_date(p, "Début", f.day(-1), "19:30")
            f.set_date(p, "Fin (optionnel)", f.day(-1), "23:00")
            p.tap(btn(p, "Enregistrer").last, "Enregistrer")
            page.wait_for_timeout(1200)
            p.shot("debut-passe")
            if not error_shown(p, "Le début est déjà passé"):
                p.flag("🟠", "modification : début déplacé à hier sans message")
            if ev(eid)["starts_at"] != before["starts_at"]:
                p.flag("🔴", "modification : début passé enregistré")
            f.set_date(p, "Début", f.day(7), "19:30")
            f.set_date(p, "Fin (optionnel)", f.day(7), "23:00")
        with p.step("retour arrière → « Abandonner les changements ? » → Continuer à modifier"):
            f.fill(p, "Titre", f"{PREFIX} NE PAS ENREGISTRER")
            back_nav(page)
            page.wait_for_timeout(2000)
            p.shot("retour-question")
            dialog = page.get_by_text("Abandonner les changements ?").first
            if not p.see(dialog, "la question « Abandonner les changements ? »", 5000):
                p.flag("🟡", "Modifier → retour arrière : aucune question, changements perdus", page.url)
            else:
                p.tap(btn(p, "Continuer à modifier"), "Continuer à modifier")
                page.wait_for_timeout(1000)
                kept = page.get_by_label("Titre", exact=True).input_value() if page.get_by_label("Titre", exact=True).count() else None
                p.log(f"après « Continuer » : URL={page.url} titre={kept!r}")
                if kept != f"{PREFIX} NE PAS ENREGISTRER":
                    p.flag("🟠", "« Continuer à modifier » : la saisie est perdue", str(kept))
                with p.step("retour arrière → Abandonner"):
                    back_nav(page)
                    page.wait_for_timeout(1500)
                    p.tap(btn(p, "Abandonner"), "Abandonner")
                    page.wait_for_timeout(2500)
                    p.shot("apres-abandon")
                    p.log(f"URL après Abandonner : {page.url}")
                    if ve.EDIT_URL.search(page.url):
                        p.flag("🟠", "« Abandonner » ne quitte pas le formulaire")
            if ev(eid)["title"] != before["title"]:
                p.flag("🔴", "retour arrière : la modification a été enregistrée quand même")
        with p.step("« ‹ Annuler » de l'en-tête après une saisie"):
            open_edit(p, eid)
            f.fill(p, "Description", "Ne pas garder")
            p.tap(page.get_by_role("button", name=re.compile("Annuler$")).first, "‹ Annuler")
            page.wait_for_timeout(1200)
            p.shot("annuler-entete")
            if not page.get_by_text("Abandonner les changements ?").count():
                p.flag("🟡", "« ‹ Annuler » de Modifier : pas de question après une saisie")
            else:
                p.tap(btn(p, "Abandonner"), "Abandonner")
                page.wait_for_timeout(2000)
    finally:
        p.close()


# ── Bugs 6, 7 : co-organisateurs ──────────────────────────────────────────────────────────────────────────────

def phase_coorga(browser, origin):
    eid = load_state()["c6_e1"]
    since = db_now()
    p = phone(browser, "orga2", origin, "coorga")
    try:
        with p.step("ajouter Bot Olga ; Bot Marc (Membre) ne doit plus être proposé"):
            open_edit(p, eid)
            advanced(p)
            marc = f.chip(p, "Bot Marc", exact=True)
            p.log(f"puce Bot Marc proposée : {marc.count()}")
            if marc.count():
                p.flag("🟡", "co-organisateurs : un Membre (sans droit de modifier) est encore proposé")
            c = f.chip(p, "Bot Olga", exact=True).first
            if not f.selected(c):
                p.tap(c, "Bot Olga")
            p.shot("coorga-choisis", full=True)
            if not save(p):
                p.flag("🔴", "co-organisateurs : Enregistrer ne revient pas à la fiche")
        orgs = organizers(eid)
        p.log(f"base : co-organisateurs {orgs}")
        if orgs != ["Bot Olga"]:
            p.flag("🔴", f"co-organisateurs enregistrés : {orgs}")
    finally:
        p.close()
    n = [x for x in notes(eid, since) if x["who"] == "Bot Olga"]
    print("notifications à Olga :", n)
    if not any(x["kind"] == "coorganizer_added" for x in n):
        anomaly("orga2", "🟡", "co-organisateur ajouté : Bot Olga n'est pas prévenue", str(n))
    p = phone(browser, "orga1", origin, "coorga")
    try:
        p.goto("/events/activity")
        p.page.wait_for_timeout(4000)
        p.shot("activite-coorga")
        item = p.page.get_by_role("button", name=re.compile("Co-organisateur")).first
        if p.see(item, "« Co-organisateur » dans l'Activité", 15000):
            p.tap(item, "notification Co-organisateur")
            p.page.wait_for_url(ve.FICHE_URL, timeout=45000)
            p.page.wait_for_timeout(2000)
            p.shot("fiche-depuis-coorga")
        else:
            p.flag("🟡", "Activité : la notification « Co-organisateur » n'apparaît pas")
        with p.step("co-organisatrice Olga : modifier le lieu"):
            open_edit(p, eid)
            f.fill(p, "Lieu", "Salle d'Olga, Vevey")
            if not save(p):
                p.flag("🔴", "co-organisatrice : Enregistrer ne revient pas à la fiche", p.page.url)
        row = ev(eid)
        if row["location_name"] != "Salle d'Olga, Vevey":
            p.flag("🔴", "co-organisatrice : lieu non enregistré")
        if row["created_by"] != uid("orga2"):
            p.flag("🔴", "co-organisatrice : le créateur a changé")
    finally:
        p.close()
    phase_coorga_membre(browser, origin)


def phase_coorga_membre(browser, origin):
    """Bot Marc (Membre) mis co-organisateur par la base (l'écran ne le propose plus) : ni Modifier ni Annuler, et la
    base refuse l'annulation avec son jeton."""
    eid = load_state()["c6_e1"]
    marc = uid("membre1")
    sql(f"insert into public.event_organizers (event_id, user_id) values ('{eid}', '{marc}') on conflict do nothing")
    p = phone(browser, "membre1", origin, "coorga")
    try:
        open_event(p, eid)
        p.shot("fiche-coorga-membre", full=True)
        has_edit, has_cancel = btn(p, "Modifier").count(), btn(p, "Annuler l’événement").count()
        p.log(f"Marc (Membre co-organisateur) : Modifier={has_edit} Annuler={has_cancel}")
        if not has_edit and has_cancel:
            p.flag("🟡", "co-organisateur Membre : ne peut pas modifier, mais voit « Annuler l'événement »")
    finally:
        p.close()
    s = Session(BY_KEY["membre1"].phone)
    r = httpx.patch(f"{TEST_URL}/rest/v1/events?id=eq.{eid}", headers={**s.headers, "Prefer": "return=representation"},
                    json={"status": "cancelled"}, timeout=30)
    print("Marc annule par l'API :", r.status_code, r.text[:200], "statut base :", ev(eid)["status"])
    if ev(eid)["status"] == "cancelled":
        anomaly("membre1", "🔴", "co-organisateur Membre : la base accepte son annulation")
        sql(f"update public.events set status = 'published' where id = '{eid}'")
    sql(f"delete from public.event_organizers where event_id = '{eid}' and user_id = '{marc}'")


# ── Bugs 2, 3, 9, 10 : annuler / rouvrir / supprimer ──────────────────────────────────────────────────────────

def phase_annuler(browser, origin):
    eid = load_state()["c6_e1"]
    title = ev(eid)["title"]
    since = db_now()
    p = phone(browser, "orga2", origin, "annuler")
    page = p.page
    try:
        open_event(p, eid)
        with p.step("Annuler → Garder (rien ne change)"):
            p.tap(btn(p, "Annuler l’événement"), "Annuler l'événement")
            p.tap(btn(p, "Garder"), "Garder")
            page.wait_for_timeout(800)
            if ev(eid)["status"] != "published":
                p.flag("🔴", "« Garder » a annulé l'événement")
        with p.step("Annuler → double toucher sur « Oui, annuler »"):
            p.tap(btn(p, "Annuler l’événement"), "Annuler l'événement")
            b = btn(p, "Oui, annuler")
            b.wait_for(timeout=15000)
            box = b.bounding_box()
            page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(3500)
            p.shot("annule", full=True)
            p.expect_or_flag(page.get_by_text("Cet événement a été annulé."), "le bandeau « annulé »")
        if ev(eid)["status"] != "cancelled":
            p.flag("🔴", f"annuler : statut {ev(eid)['status']}")
        with p.step("liste après annulation"):
            go_list(p)
            found = {}
            for t in ("À venir", "Sondages", "En attente", "Brouillons", "Passés"):
                tab(p, t)
                found[t] = in_list(p, title)
                if t == "À venir":
                    p.shot("liste-a-venir-annule")
                    p.log(f"pastille « Annulé » : {page.get_by_text('Annulé', exact=True).count()}")
            p.log(f"événement annulé (date future) visible dans : {found}")
            if not found.get("À venir"):
                p.flag("🟠", "événement annulé (date à venir) : absent de « À venir »", str(found))
        with p.step("Modifier un événement annulé (reste annulé)"):
            open_edit(p, eid)
            f.fill(p, "Description", "Modifiée après annulation.")
            save(p)
            if ev(eid)["status"] != "cancelled":
                p.flag("🔴", "modifier un annulé le republie")
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications d'annulation :", n)
    cancelled = [x for x in n if x["title"] == "Événement annulé"]
    who = [x["who"] for x in cancelled]
    for w in ("Bot Victor", "Bot Vera", "Bot Olga"):
        if w not in who:
            anomaly("orga2", "🟠", f"annulation : {w} n'a pas reçu « Événement annulé »", str(n))
    if len(who) != len(set(who)):
        anomaly("orga2", "🟡", "annulation (double toucher) : « Événement annulé » en double", str(who))
    p = phone(browser, "vip2", origin, "annuler-vu")
    try:
        go_list(p)
        p.shot("liste-invitee-annule")
        if not in_list(p, title):
            p.flag("🟠", "invitée : l'événement annulé n'est pas dans « À venir »")
        open_event(p, eid)
        p.shot("fiche-annulee-invitee", full=True)
        if p.page.get_by_role("radiogroup").count():
            p.flag("🟠", "événement annulé : l'invitée peut encore répondre")
    finally:
        p.close()
    since = db_now()
    p = phone(browser, "admin", origin, "rouvrir")
    page = p.page
    try:
        go_list(p)
        p.log(f"admin : annulé visible dans « À venir » : {in_list(p, title)}")
        open_event(p, eid)
        with p.step("Rouvrir (admin)"):
            p.tap(btn(p, "Rouvrir l’événement"), "Rouvrir l'événement")
            p.tap(btn(p, "Oui, rouvrir"), "Oui, rouvrir")
            page.wait_for_timeout(3000)
            p.shot("rouvert")
        if ev(eid)["status"] != "published":
            p.flag("🔴", "rouvrir : pas republié")
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications après réouverture :", n)
    if any(x["kind"] == "approved" for x in n):
        anomaly("admin", "🟠", "rouvrir : « Proposition validée » envoyée à la créatrice", str(n))
    back = {x["who"] for x in n if x["title"] == "Événement rétabli"}
    for w in ("Bot Victor", "Bot Vera"):
        if w not in back:
            anomaly("admin", "🟠", f"rouvrir : {w} ne reçoit pas « Événement rétabli »", str(n))
    p = phone(browser, "vip1", origin, "rouvrir-vu")
    try:
        p.goto("/events/activity")
        p.page.wait_for_timeout(4000)
        p.shot("activite-retabli")
        item = p.page.get_by_role("button", name=re.compile("Événement rétabli")).first
        if p.see(item, "« Événement rétabli » dans l'Activité", 15000):
            p.tap(item, "Événement rétabli")
            p.page.wait_for_url(ve.FICHE_URL, timeout=45000)
            p.page.wait_for_timeout(2500)
            p.shot("fiche-retablie")
            if p.page.get_by_text("Cet événement a été annulé.").count():
                p.flag("🟠", "fiche ouverte depuis « Événement rétabli » : encore annulée")
        else:
            p.flag("🟠", "Activité de Victor : pas de « Événement rétabli »")
    finally:
        p.close()
    # Oscar annule de nouveau puis supprime
    since = db_now()
    p = phone(browser, "orga2", origin, "supprimer")
    page = p.page
    try:
        open_event(p, eid)
        p.tap(btn(p, "Annuler l’événement"), "Annuler l'événement")
        p.tap(btn(p, "Oui, annuler"), "Oui, annuler")
        page.wait_for_timeout(3000)
        with p.step("Supprimer → Garder puis Oui, supprimer"):
            p.tap(btn(p, "Supprimer l’événement"), "Supprimer l'événement")
            p.tap(btn(p, "Garder"), "Garder")
            page.wait_for_timeout(600)
            if not ev(eid):
                p.flag("🔴", "« Garder » a supprimé l'événement")
            p.tap(btn(p, "Supprimer l’événement"), "Supprimer l'événement")
            p.tap(btn(p, "Oui, supprimer"), "Oui, supprimer")
            page.wait_for_timeout(3000)
            p.shot("apres-suppression")
            p.log(f"URL : {page.url}")
        if ev(eid):
            p.flag("🔴", "supprimer : l'événement est toujours en base")
        with p.step("ouvrir le lien d'un événement supprimé"):
            p.goto(f"/events/event/{eid}")
            page.wait_for_timeout(6000)
            p.shot("lien-supprime")
            body = page.locator("body").inner_text()
            p.log(body[:300])
            if "Cannot coerce" in body or "JSON" in body:
                p.flag("🟠", "lien d'un événement supprimé : erreur technique affichée", body[:200])
            if "Réessayer" in body:
                p.flag("🟡", "lien d'un événement supprimé : « Réessayer » proposé")
    finally:
        p.close()
    kept = sql(f"""select p.display_name who, n.title, n.event_id, n.data from public.notifications n
                   join public.profiles p on p.id = n.user_id
                   where n.created_at >= '{since}' and n.title = 'Événement annulé' and n.body like {q('%' + title[:20] + '%')}""")
    print("« Événement annulé » après suppression :", kept)
    if not any(k["who"] == "Bot Victor" for k in kept or []):
        anomaly("orga2", "🟡", "suppression : la notification « Événement annulé » a disparu de l'Activité de Victor", str(kept))
    p = phone(browser, "vip1", origin, "supprime-vu")
    try:
        p.goto("/events/activity")
        p.page.wait_for_timeout(4000)
        p.shot("activite-apres-suppression")
        item = p.page.get_by_role("button", name=re.compile("Événement annulé.*Vie A")).first
        if p.see(item, "« Événement annulé » après suppression", 10000):
            p.tap(item, "Événement annulé (supprimé)")
            p.page.wait_for_timeout(2500)
            p.shot("toucher-annule-supprime")
            p.log(f"URL après toucher : {p.page.url}")
    finally:
        p.close()


# ── Proposition → refus motivé (page Administration) → renvoi → validation (repris, locator corrigé) ──

def phase_proposition(browser, origin):
    since = db_now()
    p = phone(browser, "vip1", origin, "proposition")
    page = p.page
    try:
        eid = create(p, f"{PREFIX} Proposition Victor", 12, [GROUP_BOTS], submit_label=None)
        save_state(c6_e2=eid)
        p.log(f"E2 = {eid} statut {ev(eid).get('status') if eid else None}")
        p.expect_or_flag(page.get_by_text("En attente de validation").first, "le badge « En attente de validation »")
        go_list(p)
        tab(p, "En attente")
        p.shot("onglet-en-attente")
        if not in_list(p, "Proposition Victor"):
            p.flag("🟠", "proposition : absente de l'onglet « En attente » de son auteur")
    finally:
        p.close()
    eid = load_state()["c6_e2"]
    n = notes(eid, since)
    print("notifications de proposition :", n, "quarantaine :", held(eid))
    if not any(x["kind"] == "proposal" and x["who"] in ("Bot Ada", "Bot Côme") for x in n):
        anomaly("vip1", "🟠", "proposition : ni Bot Ada ni Bot Côme ne reçoivent « Nouvelle proposition »", str(n))
    # Côme refuse avec motif depuis la page d'administration (bannière de la liste)
    since = db_now()
    p = phone(browser, "coadmin", origin, "refuser")
    page = p.page
    try:
        go_list(p)
        banner = page.get_by_role("link", name=re.compile("attend.*ta validation"))
        if p.see(banner.first, "la bannière « propositions à valider »", 8000):
            p.log(f"bannière : {banner.first.inner_text()}")
            p.tap(banner.first, "bannière propositions")
        else:
            p.flag("🟠", "co-admin : pas de bannière « proposition attend ta validation » dans la liste")
            p.goto("/events/admin")
        page.wait_for_timeout(3000)
        p.shot("admin-propositions", full=True)
        card = page.get_by_text(f"{PREFIX} Proposition Victor").first
        with p.step("Refuser avec motif"):
            card.scroll_into_view_if_needed()
            # Une seule proposition à l'écran : boutons de la page (le conteneur filtré sur « Refuser » disparaît une fois ouvert)
            p.tap(btn(p, "Refuser").first, "Refuser")
            p.tap(btn(p, "Annuler").first, "Annuler (le refus)")
            page.wait_for_timeout(800)
            p.shot("refus-annule")
            p.tap(btn(p, "Refuser").first, "Refuser")
            fld = page.get_by_placeholder("Message pour l’organisateur (optionnel)")
            p.type(fld, "Date trop proche du Nouvel An, propose une autre date", "le motif")
            p.shot("motif")
            p.tap(page.get_by_role("button", name="Confirmer le refus"), "Confirmer le refus")
            page.wait_for_timeout(3000)
            p.shot("apres-refus")
        row = ev(eid)
        p.log(f"base : status={row['status']} motif={row['rejection_reason']}")
        if row["status"] != "rejected" or not row["rejection_reason"]:
            p.flag("🔴", "refus avec motif non enregistré", str(row.get("status")))
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications de refus :", n)
    if not any(x["kind"] == "rejected" and x["who"] == "Bot Victor" and "Nouvel An" in (x["body"] or "") for x in n):
        anomaly("coadmin", "🟠", "refus : Bot Victor ne reçoit pas la notification avec le motif", str(n))
    # Victor : Brouillons, fiche avec motif, renvoi
    p = phone(browser, "vip1", origin, "renvoyer")
    page = p.page
    try:
        go_list(p)
        tab(p, "Brouillons")
        p.shot("brouillons")
        if not in_list(p, "Proposition Victor"):
            p.flag("🟠", "proposition refusée : absente de l'onglet Brouillons")
        open_event(p, eid)
        p.shot("fiche-refusee", full=True)
        p.expect_or_flag(page.get_by_text("Motif du refus", exact=False).first, "le motif du refus sur la fiche")
        with p.step("corriger et renvoyer"):
            open_edit(p, eid)
            f.set_date(p, "Début", f.day(20), "19:30")
            label = "Envoyer pour validation" if btn(p, "Envoyer pour validation").count() else "Publier"
            p.log(f"bouton : {label}")
            save(p, label)
        p.log(f"base : {ev(eid)['status']} motif={ev(eid)['rejection_reason']}")
        if ev(eid)["status"] != "pending":
            p.flag("🔴", f"renvoi après refus : statut {ev(eid)['status']}")
    finally:
        p.close()
    # Ada approuve depuis la fiche
    since = db_now()
    p = phone(browser, "admin", origin, "approuver")
    page = p.page
    try:
        open_event(p, eid)
        p.shot("fiche-proposition")
        p.log(f"Refuser sur la fiche : pas de champ motif (bouton direct) = {btn(p, 'Refuser').count()}")
        with p.step("Approuver depuis la fiche"):
            p.tap(btn(p, "Approuver"), "Approuver")
            page.wait_for_timeout(3000)
            p.shot("approuvee")
        if ev(eid)["status"] != "published":
            p.flag("🔴", "Approuver depuis la fiche ne publie pas")
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications d'approbation :", n, "quarantaine :", held(eid))
    if not any(x["kind"] == "approved" and x["who"] == "Bot Victor" for x in n):
        anomaly("admin", "🟠", "approbation : Bot Victor n'est pas prévenu", str(n))



# ── Bug 8 : refus depuis la fiche ─────────────────────────────────────────────────────────────────────────────

def phase_refus_fiche(browser, origin):
    p = phone(browser, "vip2", origin, "proposition2")
    try:
        eid = create(p, f"{PREFIX} Proposition Vera", 14, [GROUP_BOTS], submit_label=None)
        save_state(c6_e3=eid)
    finally:
        p.close()
    eid = load_state()["c6_e3"]
    since = db_now()
    p = phone(browser, "admin", origin, "refus-fiche")
    page = p.page
    try:
        open_event(p, eid)
        with p.step("Refuser depuis la fiche : un toucher ne refuse pas"):
            p.tap(btn(p, "Refuser"), "Refuser")
            page.wait_for_timeout(2500)
            p.shot("refuser-ouvert")
            if ev(eid)["status"] == "rejected":
                p.flag("🟡", "fiche : « Refuser » refuse encore en un toucher, sans confirmation ni motif")
        with p.step("Annuler puis Refuser + motif + Confirmer"):
            p.tap(btn(p, "Annuler"), "Annuler (le refus)")
            page.wait_for_timeout(600)
            if ev(eid)["status"] != "pending":
                p.flag("🔴", "« Annuler » du refus a changé le statut")
            p.tap(btn(p, "Refuser"), "Refuser")
            p.type(page.get_by_label("Motif du refus (optionnel)"), "Lieu à préciser, merci", "le motif")
            p.tap(btn(p, "Confirmer le refus"), "Confirmer le refus")
            page.wait_for_timeout(3000)
            p.shot("refusee-fiche", full=True)
        row = ev(eid)
        p.log(f"base : {row['status']} motif={row['rejection_reason']!r}")
        if row["status"] != "rejected" or row["rejection_reason"] != "Lieu à préciser, merci":
            p.flag("🔴", "refus depuis la fiche : statut / motif non enregistrés", str(row.get("rejection_reason")))
        p.expect_or_flag(page.get_by_text("Lieu à préciser", exact=False).first, "le motif sur la fiche")
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications de refus (fiche) :", n)
    if not any(x["kind"] == "rejected" and x["who"] == "Bot Vera" and "Lieu à préciser" in (x["body"] or "") for x in n):
        anomaly("admin", "🟠", "refus depuis la fiche : Vera ne reçoit pas le motif", str(n))
    p = phone(browser, "vip2", origin, "supprimer-proposition")
    page = p.page
    try:
        open_event(p, eid)
        p.shot("fiche-refusee")
        with p.step("Supprimer la proposition"):
            p.tap(btn(p, "Supprimer la proposition"), "Supprimer la proposition")
            p.tap(btn(p, "Oui, supprimer"), "Oui, supprimer")
            page.wait_for_timeout(3000)
        if ev(eid):
            p.flag("🔴", "Supprimer la proposition : toujours en base")
    finally:
        p.close()


# ── Bug 4 : événement passé ──────────────────────────────────────────────────────────────────────────────────

def phase_passe(browser, origin):
    eid = load_state().get("c6_e4")
    if not eid or not ev(eid):
        p = phone(browser, "orga2", origin, "passe")
        try:
            save_state(c6_e4=create(p, f"{PREFIX} Passé", 3, [GROUP_BOTS]))
        finally:
            p.close()
    eid = load_state()["c6_e4"]
    sql(f"update public.events set starts_at = now() - interval '2 days', ends_at = now() - interval '2 days' + interval '3 hours' where id = '{eid}'")
    victor = uid("vip1")
    sql(f"delete from public.rsvps where event_id = '{eid}' and user_id = '{victor}'")
    p = phone(browser, "vip1", origin, "passe")
    page = p.page
    try:
        go_list(p)
        a_venir = in_list(p, f"{PREFIX} Passé")
        tab(p, "Passés")
        p.shot("onglet-passes")
        passes = in_list(p, f"{PREFIX} Passé")
        p.log(f"À venir={a_venir} Passés={passes}")
        if not passes:
            p.flag("🟠", "événement passé : absent de l'onglet « Passés »")
        if a_venir:
            p.flag("🟡", "événement passé : encore dans « À venir »")
        open_event(p, eid)
        p.shot("fiche-passee", full=True)
        radio = page.get_by_role("radiogroup").get_by_role("button", name="Présent", exact=True)
        p.log(f"boutons de réponse : {radio.count()}")
        if radio.count():
            p.log(f"« Présent » désactivé : {radio.first.is_disabled()} aria-disabled={radio.first.get_attribute('aria-disabled')}")
            box = radio.first.bounding_box()
            if box:
                page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.wait_for_timeout(3000)
                p.shot("passe-apres-toucher")
        r = sql(f"select status from public.rsvps where event_id = '{eid}' and user_id = '{victor}'")
        p.log(f"base après toucher : {r}")
        if r:
            p.flag("🟠", "événement passé : l'écran enregistre encore une réponse", str(r))
    finally:
        p.close()
    s = Session(BY_KEY["vip1"].phone)
    resp = httpx.post(f"{TEST_URL}/rest/v1/rsvps", headers={**s.headers, "Prefer": "return=minimal"},
                      json={"event_id": eid, "user_id": s.uid, "status": "yes"}, timeout=30)
    r = sql(f"select status from public.rsvps where event_id = '{eid}' and user_id = '{victor}'")
    print("API : réponse à un événement passé :", resp.status_code, resp.text[:200], "base :", r)
    if r:
        anomaly("vip1", "🟡", "événement passé : la base (API) accepte encore une réponse « Présent » (guard_rsvp)",
                f"HTTP {resp.status_code} ; base {r}")
        sql(f"delete from public.rsvps where event_id = '{eid}' and user_id = '{victor}'")
    p = phone(browser, "orga2", origin, "passe")
    try:
        open_event(p, eid)
        p.shot("fiche-passee-orga", full=True)
        p.log(f"orga : Modifier={btn(p, 'Modifier').count()} Annuler={btn(p, 'Annuler l’événement').count()}")
    finally:
        p.close()


def phase_modeles(browser, origin):
    eid = load_state()["c6_e4"]
    p = phone(browser, "orga2", origin, "modeles")
    page = p.page
    try:
        with p.step("Enregistrer comme modèle (perso)"):
            open_edit(p, eid)
            p.tap(btn(p, "Enregistrer comme modèle"), "Enregistrer comme modèle")
            f.fill(p, "Nom du modèle", f"{PREFIX} Modèle")
            p.tap(btn(p, "Enregistrer le modèle"), "Enregistrer le modèle")
            p.expect_or_flag(page.get_by_text(f"Modèle « {PREFIX} Modèle » enregistré").or_(
                page.get_by_text("Le modèle n’a pas pu être enregistré", exact=False)), "la réponse à « Enregistrer le modèle »",
                timeout=60000)
            p.shot("modele-reponse")
        rows = sql(f"select id from public.event_templates where name = {q(PREFIX + ' Modèle')}")
        p.log(f"base : {len(rows)} modèle(s)")
        with p.step("quitter Modifier après le modèle (aucun changement de l'événement)"):
            back_nav(page)
            page.wait_for_timeout(1500)
            if page.get_by_text("Abandonner les changements ?").count():
                p.log("question « Abandonner » après avoir seulement enregistré un modèle")
                p.tap(btn(p, "Abandonner"), "Abandonner")
                page.wait_for_timeout(1500)
        with p.step("Nouvel événement depuis le modèle"):
            p.goto("/events/event/new")
            page.wait_for_timeout(3000)
            p.tap(page.get_by_role("button", name=f"Remplir avec le modèle {PREFIX} Modèle"), "le modèle")
            page.wait_for_timeout(800)
            p.shot("modele-applique", full=True)
            t = page.get_by_label("Titre", exact=True).input_value()
            p.log(f"après modèle : titre={t!r} lieu={page.get_by_label('Lieu', exact=True).input_value()!r}")
            if t != f"{PREFIX} Passé":
                p.flag("🟠", f"modèle appliqué : titre {t!r}")
            vip = f.chip(p, "👥 Vendredi Party")
            if vip.count() and f.selected(vip.first):
                p.flag("🟠", "modèle appliqué : « Vendredi Party » coché")
            p.log("date du modèle : " + str(page.get_by_label("Début").first.input_value() if page.get_by_label("Début").count() else None))
        with p.step("Supprimer le modèle (🗑 → Supprimer ?)"):
            p.tap(page.get_by_role("button", name="🗑").first, "🗑")
            p.tap(btn(p, "Supprimer ?"), "Supprimer ?")
            page.wait_for_timeout(2000)
        left = sql(f"select count(*) n from public.event_templates where name = {q(PREFIX + ' Modèle')}")[0]["n"]
        if left:
            p.flag("🟠", "modèle : la suppression n'a pas eu lieu")
        with p.step("quitter le formulaire rempli par le modèle"):
            p.tap(page.get_by_role("button", name=re.compile("Annuler$|Retour")).first, "Annuler (en-tête)")
            page.wait_for_timeout(1500)
            p.shot("quitter-apres-modele")
            if page.get_by_text("Abandonner les changements ?").count():
                p.tap(btn(p, "Abandonner"), "Abandonner")
                page.wait_for_timeout(2500)
        drafts = sql(f"select id, status from public.events where title = {q(PREFIX + ' Passé')} and id <> '{eid}'")
        p.log(f"brouillons laissés par le modèle : {drafts}")
        if drafts:
            p.flag("🟡", "modèle puis Abandonner : un brouillon reste en base", str(drafts))
    finally:
        p.close()


def phase_annule_liste(browser, origin):
    eid = load_state()["c6_e5"]
    p = phone(browser, "orga2", origin, "annule-liste")
    try:
        open_event(p, eid)
        if ev(eid)["status"] != "cancelled":
            p.tap(btn(p, "Annuler l’événement"), "Annuler l'événement")
            p.tap(btn(p, "Oui, annuler"), "Oui, annuler")
        for _ in range(30):
            if ev(eid)["status"] == "cancelled":
                break
            p.page.wait_for_timeout(2000)
    finally:
        p.close()
    for key in ("orga2", "vip1"):
        p = phone(browser, key, origin, "annule-liste")
        try:
            go_list(p)
            found = {}
            for t in ("À venir", "Sondages", "En attente", "Brouillons", "Passés"):
                tab(p, t)
                found[t] = in_list(p, "Liste Zygomatique")
                if t == "À venir":
                    card = p.page.get_by_role("link", name=re.compile("Liste Zygomatique"))
                    p.log(f"carte lue : {card.first.get_attribute('aria-label') if card.count() else None}")
                    p.shot("a-venir-annule")
            p.log(f"annulé visible dans : {found}")
            if not found.get("À venir"):
                p.flag("🟠", "événement à venir annulé : absent de « À venir »", str(found))
        finally:
            p.close()


def phase_menage(browser, origin):
    rows = sql(f"select id, title from public.events where title like {q(PREFIX + '%')}")
    print("à supprimer :", rows)
    sql(f"delete from public.events where title like {q(PREFIX + '%')}")
    sql(f"delete from public.event_templates where name like {q(PREFIX + '%')}")
    if not load_state().get("r6_block_had"):
        sql(f"delete from public.direct_blocks where user_id = '{uid('orga1')}' and blocked_id = '{uid('guest1')}'")
    print("restants :", sql(f"select count(*) n from public.events where title like {q(PREFIX + '%')}"))


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
