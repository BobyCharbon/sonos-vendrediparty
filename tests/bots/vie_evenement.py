"""Campagne 2, agent 06 : vie de l'événement côté organisation (base de TEST, bots seulement).

Modifier après publication (champs, erreurs, double toucher, retour arrière), co-organisateurs, groupe ↔ public,
annuler / rouvrir / supprimer, proposition → refus (motif) → nouvel envoi → validation, événements passés, modèles,
liste (onglets, recherche, filtres, badges) et onglet Activité. Chaque phase vérifie la base et les notifications.

Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.vie_evenement <phase> [<phase>…]
Titre des événements : « [C2-06] … » (supprimés par la phase « menage »)."""
from __future__ import annotations

import re
import sys
import traceback

from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots.bench import Phone, anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, GROUP_BOTS, q, sql

# Base de TEST chargée par 10 agents en parallèle (requêtes de 10 à 30 s) : on attend plus longtemps chaque bouton.
Phone.tap.__defaults__ = (45000,)

PREFIX = "[C2-06]"
EDIT_URL = re.compile(r"/edit")
FICHE_URL = re.compile(r"/event/[0-9a-f-]{36}$")


def create(p, title: str, offset: int, groups: list[str], submit_label: str | None = "Publier") -> str | None:
    """flows.create_simple, plus patient : sous la charge de la campagne, l'enregistrement prend souvent > 15 s."""
    p.goto("/events/event/new")
    for _ in range(4):
        title_field, retry = p.page.get_by_label("Titre", exact=True), p.page.get_by_role("button", name="Réessayer", exact=True)
        title_field.or_(retry).first.wait_for(timeout=90000)
        if not retry.count():
            break
        p.log(f"formulaire en erreur : « {p.page.locator('body').inner_text()[:160]} » → Réessayer")
        p.shot("formulaire-erreur")
        retry.tap()
        p.page.wait_for_timeout(3000)
    eid = f.create_simple(p, title, offset, groups, submit_label)
    if eid:
        return eid
    try:
        p.page.wait_for_url(f.EVENT_URL, timeout=90000)
        p.page.wait_for_timeout(2000)
        p.log("la fiche s'est finalement ouverte (base lente)")
        return f.event_id(p)
    except Exception:
        return None


def uid(key: str) -> str:
    return sql(f"select id from public.profiles where phone = {q(BY_KEY[key].phone)}")[0]["id"]


def ev(eid: str) -> dict:
    rows = sql(f"select * from public.events where id = '{eid}'")
    return rows[0] if rows else {}


def notes(eid: str, since: str | None = None) -> list:
    extra = f"and n.created_at >= '{since}'" if since else ""
    return sql(f"""select p.display_name who, n.kind, n.title, n.body from public.notifications n
                   join public.profiles p on p.id = n.user_id where n.event_id = '{eid}' {extra} order by n.created_at""") or []


def held(eid: str) -> list:
    return sql(f"select kind, count(*) n from private.bots_quarantine_log where event_id = '{eid}' group by 1") or []


def db_now() -> str:
    return sql("select now() t")[0]["t"]


def open_event(p, eid: str) -> None:
    """Ouvre la fiche et attend la fin du chargement (fiche fantôme) : la base de TEST est lente sous 10 agents."""
    p.goto(f"/events/event/{eid}")
    p.page.wait_for_timeout(1500)
    for _ in range(4):  # base surchargée : la fiche affiche l'erreur brute et « Réessayer »
        retry = p.page.get_by_role("button", name="Réessayer", exact=True)
        try:
            p.page.get_by_role("heading", level=1).or_(retry).first.wait_for(state="visible", timeout=60000)
        except Exception:
            break
        if not retry.count():
            break
        p.log(f"fiche en erreur : « {p.page.locator('body').inner_text()[:120]} » → Réessayer")
        retry.tap()
        p.page.wait_for_timeout(3000)
    try:
        p.page.get_by_role("heading", level=1).first.wait_for(state="visible", timeout=60000)
        p.page.get_by_role("progressbar", name="Chargement de l’événement…").wait_for(state="detached", timeout=60000)
    except Exception:
        p.log("fiche encore en chargement après 60 s")
    p.page.wait_for_timeout(1000)


def btn(p, name: str, exact: bool = True):
    return p.page.get_by_role("button", name=name, exact=exact)


def open_edit(p, eid: str) -> None:
    open_event(p, eid)
    p.tap(btn(p, "Modifier"), "Modifier")
    p.page.wait_for_url(EDIT_URL, timeout=30000)
    p.page.get_by_label("Titre", exact=True).wait_for(timeout=60000)
    p.page.wait_for_timeout(800)


def advanced(p) -> None:
    tab = p.page.get_by_role("tablist").get_by_text("Avancé", exact=True).first
    p.tap(tab, "Avancé")
    p.page.wait_for_timeout(500)


def save(p, label: str = "Enregistrer") -> bool:
    p.tap(btn(p, label).last, label)
    try:
        p.page.wait_for_url(FICHE_URL, timeout=45000)
        p.page.wait_for_timeout(2500)
        return True
    except Exception:
        return False


def error_shown(p, text: str) -> bool:
    return p.see(p.page.get_by_text(text, exact=False).first, f"le message « {text} »", 4000)


def go_list(p) -> None:
    """Liste chargée (plus de cartes fantômes) ; erreur de la base → « Réessayer »."""
    p.goto("/events/")
    page = p.page
    page.get_by_label("Rechercher un événement").wait_for(timeout=90000)
    for _ in range(4):
        page.wait_for_timeout(1500)
        try:
            page.get_by_role("progressbar", name="Chargement des événements…").wait_for(state="detached", timeout=90000)
        except Exception:
            p.log("liste encore en chargement après 90 s")
        retry = page.get_by_role("button", name="Réessayer", exact=True)
        if not retry.count():
            break
        p.log("liste en erreur → Réessayer")
        retry.tap()
    page.wait_for_timeout(1000)


def tab(p, name: str) -> None:
    p.tap(p.page.get_by_role("tablist").get_by_text(name, exact=True).first, f"onglet {name}")
    p.page.wait_for_timeout(1200)


def in_list(p, title: str) -> bool:
    return p.page.get_by_text(title, exact=False).count() > 0


# ── 0. Connexions ──────────────────────────────────────────────────────────────────────────────────────────────

CAST = ["orga2", "orga1", "admin", "coadmin", "vip1", "vip2", "membre1"]


def phase_connexion(browser, origin):
    for key in CAST:
        p = phone(browser, key, origin, "connexion")
        try:
            p.sign_in()
            f.accept_terms_if_asked(p)
            p.see(p.page.get_by_label("Rechercher un événement"), "la liste", 30000)
        finally:
            p.close()


# ── 1. Création + réponses (pour avoir un public à prévenir) ───────────────────────────────────────────────────

def phase_preparer(browser, origin):
    p = phone(browser, "orga2", origin, "preparer")
    try:
        eid = create(p, f"{PREFIX} Vie A", 7, [GROUP_BOTS])
        p.log(f"E1 = {eid}")
        save_state(c6_e1=eid)
        row = ev(eid)
        p.log(f"base : status={row.get('status')} visibility={row.get('visibility')} public_link={row.get('public_link')}")
    finally:
        p.close()
    for key, choice in (("vip1", "Présent"), ("vip2", "Peut-être")):
        p = phone(browser, key, origin, "preparer")
        try:
            open_event(p, load_state()["c6_e1"])
            from tests.bots.scenario import rsvp
            rsvp(p, choice)
        finally:
            p.close()
    r = sql(f"""select p.display_name, r.status from public.rsvps r join public.profiles p on p.id = r.user_id
                where r.event_id = '{load_state()['c6_e1']}'""")
    print("réponses :", r)


# ── 2. Modifier après publication ───────────────────────────────────────────────────────────────────────────────

def phase_erreurs(browser, origin):
    """Messages d'erreur du formulaire de modification ; rien ne doit être enregistré."""
    eid = load_state()["c6_e1"]
    before = ev(eid)
    p = phone(browser, "orga2", origin, "erreurs")
    page = p.page
    try:
        open_edit(p, eid)
        advanced(p)
        cases = [
            ("Titre", "", "Il manque un titre"),
            ("Prix / pers. (CHF)", "-5", "Le prix doit être un montant positif"),
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
                if not EDIT_URL.search(page.url):
                    p.flag("🔴", f"modification : enregistré malgré « {value} » dans {label}")
                    open_edit(p, eid)
                    advanced(p)
                f.fill(p, label, original[label])
        with p.step("fin avant le début"):
            f.set_date(p, "Début", f.day(7), "19:30")
            f.set_date(p, "Fin (optionnel)", f.day(6), "18:00")
            p.tap(btn(p, "Enregistrer").last, "Enregistrer")
            page.wait_for_timeout(1200)
            p.shot("fin-avant-debut")
            if not error_shown(p, "La fin doit être après le début"):
                p.flag("🟠", "fin avant le début : pas de message")
        with p.step("retour arrière sans enregistrer"):
            f.fill(p, "Titre", f"{PREFIX} NE PAS ENREGISTRER")
            page.go_back()
            page.wait_for_timeout(2500)
            p.shot("apres-retour")
            p.log(f"URL après retour : {page.url}")
            if ev(eid)["title"] != before["title"]:
                p.flag("🔴", "retour arrière : la modification a été enregistrée quand même")
            else:
                p.log("retour arrière : rien d'enregistré, aucune question « abandonner les modifications ? »")
    finally:
        p.close()


def phase_modifier(browser, origin):
    eid = load_state()["c6_e1"]
    since = db_now()
    p = phone(browser, "orga2", origin, "modifier")
    page = p.page
    try:
        with p.step("modifier tous les champs essentiels + double toucher sur Enregistrer"):
            open_edit(p, eid)
            p.shot("formulaire")
            advanced(p)
            f.fill(p, "Titre", f"{PREFIX} Vie A (modifié)")
            f.fill(p, "Description", "Description modifiée par Bot Oscar (campagne 2, agent 06).")
            f.set_date(p, "Début", f.day(9), "20:30")
            f.set_date(p, "Fin (optionnel)", f.day(9), "23:30")
            f.fill(p, "Lieu", "Salle modifiée des bots, Montreux")
            f.fill(p, "Adresse", "Grand-Rue 1, 1820 Montreux")
            f.fill(p, "Lien (site, carte…)", "https://example.org/salle")
            f.fill(p, "Prix / pers. (CHF)", "12.50")
            f.fill(p, "Paiement", "TWINT")
            f.fill(p, "Nombre de places (vide = illimité)", "8")
            f.toggle(p, "Réponse « Peut-être » autorisée", True)
            p.shot("formulaire-modifie", full=True)
            b = btn(p, "Enregistrer").last
            b.scroll_into_view_if_needed()
            box = b.bounding_box()
            p.log("double toucher sur Enregistrer")
            page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_url(FICHE_URL, timeout=45000)
            page.wait_for_timeout(2500)
            p.shot("fiche-modifiee", full=True)
        row = ev(eid)
        p.log(f"base : title={row['title']} starts_at={row['starts_at']} loc={row['location_name']} price={row['price_chf']} "
              f"max={row['max_participants']} status={row['status']}")
        expect = {"title": f"{PREFIX} Vie A (modifié)", "location_name": "Salle modifiée des bots, Montreux",
                  "max_participants": 8, "status": "published"}
        for k, v in expect.items():
            if row.get(k) != v:
                p.flag("🔴", f"modification : {k} vaut {row.get(k)!r} au lieu de {v!r}")
        if float(row.get("price_chf") or 0) != 12.5:
            p.flag("🔴", f"modification : prix {row.get('price_chf')}")
        p.expect_or_flag(page.get_by_text("Salle modifiée des bots, Montreux").first, "le nouveau lieu sur la fiche")
        p.expect_or_flag(page.get_by_text("12.50", exact=False).first, "le prix sur la fiche", "🟡")
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications après modification :", n)
    save_state(c6_notes_modif=n)
    kinds = {(x["who"], x["kind"]) for x in n}
    for who in ("Bot Victor", "Bot Vera"):
        if (who, "event_changed") not in kinds:
            anomaly("orga2", "🟠", f"modification : {who} (a répondu) n'a pas reçu « Événement modifié »", str(n))
    dup = [x for x in n if x["kind"] == "event_changed"]
    if len(dup) > 2:
        anomaly("orga2", "🟡", f"modification : {len(dup)} notifications « modifié » pour 2 participants (doublons ?)", str(dup))
    print("quarantaine :", held(eid))
    # Le participant voit la modification + la notification dans Activité
    p = phone(browser, "vip2", origin, "modifier-vu")
    try:
        p.goto("/events/activity")
        p.page.wait_for_timeout(3000)
        p.shot("activite")
        item = p.page.get_by_role("button", name=re.compile("Événement modifié.*Vie A")).first
        if p.see(item, "la notification « Événement modifié »", 8000):
            p.tap(item, "notification Événement modifié")
            p.page.wait_for_url(FICHE_URL, timeout=45000)
            p.page.wait_for_timeout(2500)
            p.shot("fiche-depuis-activite")
            p.expect_or_flag(p.page.get_by_text("Salle modifiée des bots, Montreux").first, "le nouveau lieu (invitée)")
        else:
            p.flag("🟠", "Activité : la notification « Événement modifié » n'apparaît pas")
    finally:
        p.close()


# ── 3. Co-organisateurs ─────────────────────────────────────────────────────────────────────────────────────────

def organizers(eid: str) -> list:
    return sorted(r["display_name"] for r in sql(f"""select p.display_name from public.event_organizers o
                  join public.profiles p on p.id = o.user_id where o.event_id = '{eid}'""") or [])


def phase_coorga(browser, origin):
    eid = load_state()["c6_e1"]
    since = db_now()
    p = phone(browser, "orga2", origin, "coorga")
    try:
        with p.step("ajouter Bot Olga et Bot Marc comme co-organisateurs"):
            open_edit(p, eid)
            advanced(p)
            for name in ("Bot Olga", "Bot Marc"):
                c = f.chip(p, name, exact=True).first
                if not f.selected(c):
                    p.tap(c, name)
            p.shot("coorga-choisis")
            if not save(p):
                p.flag("🔴", "co-organisateurs : Enregistrer ne revient pas à la fiche")
        orgs = organizers(eid)
        p.log(f"base : co-organisateurs {orgs}")
        if orgs != ["Bot Marc", "Bot Olga"]:
            p.flag("🔴", f"co-organisateurs enregistrés : {orgs}")
    finally:
        p.close()
    n = [x for x in notes(eid, since) if x["who"] in ("Bot Olga", "Bot Marc")]
    print("notifications aux nouveaux co-organisateurs :", n)
    if not n:
        anomaly("orga2", "🟡", "co-organisateur ajouté : aucune notification (Bot Olga / Bot Marc ne sont pas prévenus)")
    # Olga (organisatrice) modifie le lieu en co-organisateur
    p = phone(browser, "orga1", origin, "coorga")
    page = p.page
    try:
        open_event(p, eid)
        p.shot("fiche-coorga")
        p.log(f"Modifier : {btn(p, 'Modifier').count()} · Annuler l'événement : {btn(p, 'Annuler l’événement').count()}")
        with p.step("co-organisateur Oscar : modifier le lieu et retirer Marc"):
            open_edit(p, eid)
            f.fill(p, "Lieu", "Salle d'Olga, Vevey")
            advanced(p)
            c = f.chip(p, "Bot Marc", exact=True).first
            if f.selected(c):
                p.tap(c, "retirer Bot Marc")
            if not save(p):
                p.flag("🔴", "co-organisateur : Enregistrer ne revient pas à la fiche", page.url)
        row = ev(eid)
        orgs = organizers(eid)
        p.log(f"base : lieu={row['location_name']} créateur={row['created_by']} co-orgas={orgs}")
        if row["location_name"] != "Salle d'Olga, Vevey":
            p.flag("🔴", "co-organisateur : lieu non enregistré")
        if orgs != ["Bot Olga"]:
            p.flag("🔴", f"co-organisateur Oscar retire Marc : co-organisateurs = {orgs}")
        if row["created_by"] != uid("orga2"):
            p.flag("🔴", "co-organisateur : le créateur a changé")
    finally:
        p.close()
    phase_coorga_membre(browser, origin)


def phase_coorga_membre(browser, origin):
    """Bot Marc (Membre, sans « modifier le publié ») remis co-organisateur : ce qu'il peut faire."""
    eid = load_state()["c6_e1"]
    p = phone(browser, "orga2", origin, "coorga")
    try:
        with p.step("remettre Bot Marc (Membre) co-organisateur"):
            open_edit(p, eid)
            advanced(p)
            c = f.chip(p, "Bot Marc", exact=True).first
            if not f.selected(c):
                p.tap(c, "Bot Marc")
            save(p)
        p.log(f"co-orgas : {organizers(eid)}")
    finally:
        p.close()
    p = phone(browser, "membre1", origin, "coorga")
    page = p.page
    try:
        open_event(p, eid)
        p.shot("fiche-coorga-membre", full=True)
        has_edit = btn(p, "Modifier").count()
        has_cancel = btn(p, "Annuler l’événement").count()
        p.log(f"Marc (Membre co-organisateur) : Modifier={has_edit} Annuler={has_cancel}")
        if not has_edit and has_cancel:
            p.flag("🟡", "co-organisateur Membre : ne peut pas modifier, mais peut annuler l'événement (zone organisateur)")
        p.goto(f"/events/event/{eid}/edit")
        page.wait_for_timeout(3000)
        p.shot("edit-direct-membre")
    finally:
        p.close()


# ── 4. Groupe ↔ public ─────────────────────────────────────────────────────────────────────────────────────────

def groups_of(eid: str) -> list:
    return sql(f"""select g.name, eg.status from public.event_groups eg join public.member_groups g on g.id = eg.group_id
                   where eg.event_id = '{eid}'""") or []


def phase_visibilite(browser, origin):
    eid = load_state()["c6_e1"]
    since = db_now()
    p = phone(browser, "orga2", origin, "visibilite")
    page = p.page
    try:
        p.log(f"avant : groupes={groups_of(eid)} invites={sql(f'select count(*) n from public.event_invites where event_id = {q(eid)}')}")
        with p.step("groupe → public"):
            open_edit(p, eid)
            p.tap(f.chip(p, "Publique + lien", exact=True).first, "Publique + lien")
            p.shot("public-choisi")
            if not save(p):
                p.flag("🔴", "groupe → public : Enregistrer ne revient pas à la fiche", page.url)
            p.shot("fiche-publique")
        row = ev(eid)
        p.log(f"base : visibility={row['visibility']} public_link={row['public_link']} notify={row['notify_on_publish']} "
              f"groupes={groups_of(eid)} invites={sql(f'select count(*) n from public.event_invites where event_id = {q(eid)}')}")
        if not (row["visibility"] == "all" and row["public_link"]):
            p.flag("🔴", "groupe → public : la base n'est pas publique", str(row))
        p.expect_or_flag(page.get_by_text("Publique", exact=False).first, "la mention « Publique » sur la fiche")
        with p.step("public → groupe Bots"):
            open_edit(p, eid)
            f.audience_invite_groups(p, [GROUP_BOTS])
            p.shot("retour-groupe")
            if not save(p):
                p.flag("🔴", "public → groupe : Enregistrer ne revient pas à la fiche", page.url)
        row = ev(eid)
        p.log(f"base : visibility={row['visibility']} public_link={row['public_link']} groupes={groups_of(eid)}")
        if row["visibility"] != "invited" or row["public_link"] or not groups_of(eid):
            p.flag("🔴", "public → groupe : la base n'a pas suivi", f"{row['visibility']} {row['public_link']} {groups_of(eid)}")
        rs = sql(f"select count(*) n from public.rsvps where event_id = '{eid}'")
        p.log(f"réponses gardées : {rs}")
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications groupe ↔ public :", n, "quarantaine :", held(eid))
    save_state(c6_notes_visib=n)


# ── 5. Annuler / rouvrir / supprimer ───────────────────────────────────────────────────────────────────────────

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
            p.shot("confirmation")
            p.tap(btn(p, "Garder"), "Garder")
            page.wait_for_timeout(800)
            if ev(eid)["status"] != "published":
                p.flag("🔴", "« Garder » a annulé l'événement")
        with p.step("Annuler → Oui, annuler"):
            p.tap(btn(p, "Annuler l’événement"), "Annuler l'événement")
            p.tap(btn(p, "Oui, annuler"), "Oui, annuler")
            page.wait_for_timeout(3000)
            p.shot("annule", full=True)
            p.expect_or_flag(page.get_by_text("Cet événement a été annulé."), "le bandeau « annulé »")
        st = ev(eid)["status"]
        p.log(f"base : {st}")
        if st != "cancelled":
            p.flag("🔴", f"annuler : statut {st}")
        p.log(f"créatrice : Rouvrir={btn(p, 'Rouvrir l’événement').count()} Supprimer={btn(p, 'Supprimer l’événement').count()}")
        with p.step("liste après annulation"):
            go_list(p)
            p.shot("liste-a-venir")
            found = {}
            for t in ("À venir", "Sondages", "En attente", "Brouillons", "Passés"):
                tab(p, t)
                found[t] = in_list(p, title)
            p.log(f"événement annulé (date future) visible dans : {found}")
            if not any(found.values()):
                p.flag("🟠", "événement annulé (date à venir) : introuvable dans la liste (aucun onglet) — "
                       "ni l'organisateur ni les invités ne le retrouvent pour le supprimer / le voir", str(found))
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
    who = {x["who"] for x in n if x["title"] == "Événement annulé"}
    for w in ("Bot Victor", "Bot Vera", "Bot Olga", "Bot Marc"):
        if w not in who:
            anomaly("orga2", "🟠", f"annulation : {w} n'a pas reçu « Événement annulé »", str(n))
    # Vera : la fiche annulée
    p = phone(browser, "vip2", origin, "annuler-vu")
    try:
        open_event(p, eid)
        p.shot("fiche-annulee-invitee", full=True)
        if p.page.get_by_role("radiogroup").count():
            p.flag("🟠", "événement annulé : l'invitée peut encore répondre")
    finally:
        p.close()
    # Ada rouvre
    since = db_now()
    p = phone(browser, "admin", origin, "rouvrir")
    page = p.page
    try:
        open_event(p, eid)
        with p.step("Rouvrir (admin)"):
            p.tap(btn(p, "Rouvrir l’événement"), "Rouvrir l'événement")
            p.tap(btn(p, "Oui, rouvrir"), "Oui, rouvrir")
            page.wait_for_timeout(3000)
            p.shot("rouvert")
        p.log(f"base : {ev(eid)['status']}")
        if ev(eid)["status"] != "published":
            p.flag("🔴", "rouvrir : pas republié")
    finally:
        p.close()
    n = notes(eid, since)
    print("notifications après réouverture :", n)
    save_state(c6_notes_rouvrir=n)
    if any(x["kind"] == "approved" for x in n):
        anomaly("admin", "🟠", "rouvrir un événement annulé envoie « Proposition validée » à la créatrice", str(n))
    if not any(x["who"] in ("Bot Victor", "Bot Vera") for x in n):
        anomaly("admin", "🟠", "rouvrir : les participants (qui ont reçu « annulé ») ne sont pas prévenus du retour", str(n))
    # Olga : annule de nouveau puis supprime
    p = phone(browser, "orga2", origin, "supprimer")
    page = p.page
    try:
        open_event(p, eid)
        p.tap(btn(p, "Annuler l’événement"), "Annuler l'événement")
        p.tap(btn(p, "Oui, annuler"), "Oui, annuler")
        page.wait_for_timeout(2500)
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
        else:
            p.log("base : supprimé")
        with p.step("ouvrir le lien d'un événement supprimé"):
            open_event(p, eid)
            page.wait_for_timeout(2000)
            p.shot("lien-supprime")
            p.log(p.page.locator("body").inner_text()[:300])
    finally:
        p.close()


# ── 6. Proposition → refus motivé → nouvel envoi → validation ─────────────────────────────────────────────────

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
            container = page.locator("div").filter(has=page.get_by_text(f"{PREFIX} Proposition Victor", exact=True)).filter(
                has=page.get_by_role("button", name="Refuser")).last
            p.tap(container.get_by_role("button", name="Refuser", exact=True), "Refuser")
            p.tap(container.get_by_role("button", name="Annuler", exact=True), "Annuler (le refus)")
            p.tap(container.get_by_role("button", name="Refuser", exact=True), "Refuser")
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


def phase_refus_fiche(browser, origin):
    """Proposition refusée depuis la fiche (« Refuser ») : pas de motif possible ; puis suppression par l'auteur."""
    p = phone(browser, "vip2", origin, "proposition2")
    try:
        eid = create(p, f"{PREFIX} Proposition Vera", 14, [GROUP_BOTS], submit_label=None)
        save_state(c6_e3=eid)
    finally:
        p.close()
    eid = load_state()["c6_e3"]
    p = phone(browser, "admin", origin, "refus-fiche")
    page = p.page
    try:
        open_event(p, eid)
        with p.step("Refuser depuis la fiche"):
            p.tap(btn(p, "Refuser"), "Refuser")
            page.wait_for_timeout(2500)
            p.shot("refusee-fiche")
        row = ev(eid)
        p.log(f"base : {row['status']} motif={row['rejection_reason']!r}")
        if row["status"] == "rejected":
            p.flag("🟡", "fiche d'une proposition : « Refuser » refuse en un toucher, sans confirmation ni motif "
                   "(la page Administration, elle, demande un motif)")
    finally:
        p.close()
    p = phone(browser, "vip2", origin, "supprimer-proposition")
    page = p.page
    try:
        open_event(p, eid)
        p.shot("fiche-refusee")
        with p.step("Supprimer la proposition"):
            p.tap(btn(p, "Supprimer la proposition"), "Supprimer la proposition")
            p.tap(btn(p, "Oui, supprimer"), "Oui, supprimer")
            page.wait_for_timeout(3000)
            p.shot("apres-suppression")
        if ev(eid):
            p.flag("🔴", "Supprimer la proposition : toujours en base")
    finally:
        p.close()


# ── 7. Événements passés ───────────────────────────────────────────────────────────────────────────────────────

def phase_passe(browser, origin):
    eid = load_state().get("c6_e4")
    if not eid or not ev(eid):
        p = phone(browser, "orga2", origin, "passe")
        try:
            save_state(c6_e4=create(p, f"{PREFIX} Passé", 3, [GROUP_BOTS]))
        finally:
            p.close()
    eid = load_state()["c6_e4"]
    # Recule l'événement à avant-hier (base de TEST, notre propre événement ; service : pas de garde)
    sql(f"update public.events set starts_at = now() - interval '2 days', ends_at = now() - interval '2 days' + interval '3 hours' where id = '{eid}'")
    p = phone(browser, "vip1", origin, "passe")
    page = p.page
    try:
        go_list(p)
        a_venir = in_list(p, "Passé")
        tab(p, "Passés")
        p.shot("onglet-passes")
        passes = in_list(p, f"{PREFIX} Passé")
        p.log(f"À venir={a_venir} Passés={passes}")
        if not passes:
            p.flag("🟠", "événement passé : absent de l'onglet « Passés »")
        open_event(p, eid)
        p.shot("fiche-passee", full=True)
        radios = page.get_by_role("radiogroup")
        p.log(f"boutons de réponse sur un événement passé : {radios.count()}")
        if radios.count():
            from tests.bots.scenario import rsvp
            with p.step("répondre à un événement passé"):
                rsvp(p, "Présent")
            r = sql(f"select status from public.rsvps where event_id = '{eid}' and user_id = '{uid('vip1')}'")
            p.log(f"base : {r}")
            if r:
                p.flag("🟠", "événement passé (archives) : on peut encore répondre « Présent » (écran et base acceptent)", str(r))
    finally:
        p.close()
    p = phone(browser, "orga2", origin, "passe")
    try:
        open_event(p, eid)
        p.shot("fiche-passee-orga", full=True)
        p.log(f"orga : Modifier={btn(p, 'Modifier').count()} Annuler={btn(p, 'Annuler l’événement').count()} "
              f"Scanner={p.page.get_by_role('button', name=re.compile('Scanner')).count()}")
    finally:
        p.close()


# ── 8. Modèles (duplication) ───────────────────────────────────────────────────────────────────────────────────

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
            page.wait_for_timeout(2000)
            p.expect_or_flag(page.get_by_text("Modèle « [C2-06] Modèle » enregistré").or_(
                page.get_by_text("Le modèle n’a pas pu être enregistré", exact=False)), "la réponse à « Enregistrer le modèle »", timeout=60000)
            p.shot("modele-reponse")
        rows = sql(f"select id, name, shared, data from public.event_templates where name = {q(PREFIX + ' Modèle')}")
        p.log(f"base : {len(rows)} modèle(s)")
        if rows:
            p.log(f"data du modèle : titre={rows[0]['data'].get('title')} who={rows[0]['data'].get('who')}")
        with p.step("Nouvel événement depuis le modèle"):
            p.goto("/events/event/new")
            page.wait_for_timeout(3000)
            m = page.get_by_role("button", name=f"Remplir avec le modèle {PREFIX} Modèle")
            p.tap(m, "le modèle")
            page.wait_for_timeout(800)
            p.shot("modele-applique", full=True)
            t = page.get_by_label("Titre", exact=True).input_value()
            lieu = page.get_by_label("Lieu", exact=True).input_value()
            p.log(f"après modèle : titre={t!r} lieu={lieu!r}")
            if t != f"{PREFIX} Passé":
                p.flag("🟠", f"modèle appliqué : titre {t!r}")
            vip = f.chip(p, "👥 Vendredi Party")
            if vip.count() and f.selected(vip.first):
                p.flag("🟠", "modèle appliqué : « Vendredi Party » coché")
        with p.step("Supprimer le modèle (🗑 → Supprimer ?)"):
            row = page.get_by_role("button", name="🗑")
            p.tap(row.first, "🗑")
            p.tap(btn(p, "Supprimer ?"), "Supprimer ?")
            page.wait_for_timeout(2000)
        left = sql(f"select count(*) n from public.event_templates where name = {q(PREFIX + ' Modèle')}")[0]["n"]
        p.log(f"modèles restants : {left}")
        if left:
            p.flag("🟠", "modèle : la suppression n'a pas eu lieu")
    finally:
        p.close()


# ── 9. Liste, recherche, filtres, badges, Activité ─────────────────────────────────────────────────────────────

def phase_liste(browser, origin):
    p = phone(browser, "orga2", origin, "liste")
    try:
        eid = create(p, f"{PREFIX} Liste Zygomatique", 4, [GROUP_BOTS])
        save_state(c6_e5=eid)
    finally:
        p.close()
    for key in ("vip1", "vip2"):
        p = phone(browser, key, origin, "liste")
        page = p.page
        try:
            go_list(p)
            bar = page.get_by_role("link", name=re.compile("^Événements"))
            p.log(f"onglet de la barre : {bar.first.get_attribute('aria-label')}")
            p.shot("liste")
            if not page.get_by_text("Liste Zygomatique").count():
                p.flag("🟠", "nouvel événement du groupe absent de « À venir »")
            with p.step("recherche par titre, lieu, sans résultat"):
                s = page.get_by_label("Rechercher un événement")
                p.type(s, "zygomatique", "la recherche")
                page.wait_for_timeout(800)
                p.shot("recherche-titre")
                if not in_list(p, "Liste Zygomatique"):
                    p.flag("🟠", "recherche (minuscules) : l'événement n'est pas trouvé")
                p.type(s, "Salle des bots", "la recherche")
                page.wait_for_timeout(800)
                if not in_list(p, "Liste Zygomatique"):
                    p.flag("🟠", "recherche par lieu : rien")
                p.type(s, "zzzz introuvable", "la recherche")
                page.wait_for_timeout(800)
                p.expect_or_flag(page.get_by_text("Aucun événement ne correspond à ta recherche."), "le message « aucun résultat »")
                p.tap(btn(p, "Effacer la recherche et les filtres"), "Effacer la recherche")
                page.wait_for_timeout(800)
                if s.input_value():
                    p.flag("🟡", "« Effacer » ne vide pas la recherche")
                p.type(s, "zygomatique", "la recherche")
                page.wait_for_timeout(500)
                tab(p, "Passés")
                p.log(f"recherche gardée en changeant d'onglet : {s.input_value()!r}")
                p.type(s, "", "la recherche")
                tab(p, "À venir")
            with p.step("filtres : Mes abonnements, une catégorie"):
                p.tap(btn(p, "Mes abonnements", exact=False).first, "Mes abonnements")
                page.wait_for_timeout(800)
                p.shot("filtre-abonnements")
                p.tap(btn(p, "Tout", exact=False).first, "Tout")
                cats = sql("select name from public.categories where not archived order by sort limit 1")
                if cats:
                    p.tap(btn(p, cats[0]["name"], exact=False).first, f"catégorie {cats[0]['name']}")
                    page.wait_for_timeout(800)
                    p.shot("filtre-categorie")
                    p.tap(btn(p, cats[0]["name"], exact=False).first, "désélectionner la catégorie")
            with p.step("répondre depuis la carte (réponse rapide) puis « TU Y VAS »"):
                if key == "vip1":
                    card = page.locator("div").filter(has=page.get_by_text(f"{PREFIX} Liste Zygomatique")).filter(
                        has=page.get_by_role("button", name=re.compile("Présent|Oui|J.y vais"))).last
                    if card.count():
                        p.tap(card.get_by_role("button", name=re.compile("Présent|Oui|J.y vais")).first, "Présent (carte)")
                        page.wait_for_timeout(2500)
                        f.accept_terms_if_asked(p)
                        p.shot("tu-y-vas")
                        p.expect_or_flag(page.get_by_text("TU Y VAS"), "la section « TU Y VAS »", "🟡")
                    else:
                        p.log("pas de réponse rapide sur la carte")
            p.finger_scroll("liste")
            p.check_texts_cut("liste")
        finally:
            p.close()
    # Activité : notification → fiche, tout marquer lu
    p = phone(browser, "vip2", origin, "activite")
    page = p.page
    try:
        p.goto("/events/activity")
        page.wait_for_timeout(3000)
        p.shot("activite", full=True)
        unread = sql(f"select count(*) n from public.notifications where user_id = '{uid('vip2')}' and read_at is null")[0]["n"]
        p.log(f"non lues en base : {unread}")
        item = page.get_by_role("button", name=re.compile("Liste Zygomatique")).first
        if p.see(item, "la notification de l'événement du groupe", 6000):
            p.tap(item, "notification")
            page.wait_for_url(FICHE_URL, timeout=45000)
            p.shot("fiche-depuis-activite")
            page.go_back()
            page.wait_for_timeout(2500)
        else:
            p.log("pas de notification pour l'événement de groupe (Prévenir le groupe éteint par défaut)")
        with p.step("Tout marquer lu"):
            mark = btn(p, "Tout marquer lu")
            if mark.count():
                p.tap(mark, "Tout marquer lu")
                page.wait_for_timeout(2500)
                left = sql(f"select count(*) n from public.notifications where user_id = '{uid('vip2')}' and read_at is null")[0]["n"]
                p.log(f"non lues après : {left}")
                if left:
                    p.flag("🟠", f"« Tout marquer lu » : {left} encore non lues en base")
                p.shot("tout-lu")
        p.scroll_to_bottom("Activité")
        p.check_texts_cut("Activité")
    finally:
        p.close()


# ── 10. Perte réseau pendant l'enregistrement ─────────────────────────────────────────────────────────────────

def phase_reseau(browser, origin):
    eid = load_state()["c6_e5"]
    p = phone(browser, "orga2", origin, "reseau")
    page = p.page
    try:
        open_edit(p, eid)
        f.fill(p, "Lieu", "Lieu hors ligne")
        with p.step("Enregistrer hors ligne"):
            p.ctx.set_offline(True)
            p.tap(btn(p, "Enregistrer").last, "Enregistrer (hors ligne)")
            for i in range(12):
                page.wait_for_timeout(5000)
                if page.get_by_text(re.compile("connexion|réseau|fetch|Réessaie", re.I)).count():
                    break
                p.log(f"hors ligne depuis {5 * (i + 1)} s : toujours rien à l'écran")
            p.shot("hors-ligne")
            msg = page.get_by_text(re.compile("connexion|réseau|Failed to fetch|fetch", re.I)).first
            p.log(f"message affiché : {msg.inner_text() if msg.count() else '(aucun)'}")
            if msg.count() and "fetch" in msg.inner_text().lower():
                p.flag("🟡", "hors ligne : message technique « Failed to fetch » au lieu d'une phrase claire", msg.inner_text())
            elif not msg.count():
                p.flag("🟠", "hors ligne : Enregistrer ne dit rien")
            p.ctx.set_offline(False)
            page.wait_for_timeout(1000)
            spinning = btn(p, "Enregistrer").count() == 0
            p.log(f"retour du réseau : bouton Enregistrer {'encore en chargement' if spinning else 'disponible'}")
            if spinning:
                p.flag("🟠", "hors ligne : Enregistrer reste en chargement (roue) sans message ; il faut quitter l'écran")
                page.wait_for_timeout(30000)
            ok = save(p)
            p.log(f"retour réseau, Enregistrer : {ok} ; base lieu={ev(eid)['location_name']}")
            if ev(eid)["location_name"] != "Lieu hors ligne":
                p.flag("🟠", "retour du réseau : nouvel essai d'Enregistrer sans effet")
    finally:
        p.close()


def phase_annule_liste(browser, origin):
    """Contre-épreuve : un événement à venir annulé disparaît-il de tous les onglets (organisateur et invité) ?"""
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
        p.log(f"base : {ev(eid)['status']}")
    finally:
        p.close()
    for key in ("orga2", "vip1"):
        p = phone(browser, key, origin, "annule-liste")
        try:
            go_list(p)
            control = in_list(p, "Proposition Victor")
            p.log(f"témoin « Proposition Victor » (publié, à venir) visible : {control}")
            found = {}
            for t in ("À venir", "Sondages", "En attente", "Brouillons", "Passés"):
                tab(p, t)
                p.page.wait_for_timeout(1000)
                found[t] = in_list(p, "Liste Zygomatique")
            p.shot("onglets-apres-annulation")
            p.log(f"annulé visible dans : {found}")
            if not any(found.values()):
                p.flag("🟠", "événement à venir annulé : introuvable dans tous les onglets de la liste", str(found))
        finally:
            p.close()


# ── Ménage ─────────────────────────────────────────────────────────────────────────────────────────────────────

def phase_menage(browser, origin):
    rows = sql(f"select id, title from public.events where title like {q(PREFIX + '%')}")
    print("à supprimer :", rows)
    sql(f"delete from public.events where title like {q(PREFIX + '%')}")
    sql(f"delete from public.event_templates where name like {q(PREFIX + '%')}")
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
