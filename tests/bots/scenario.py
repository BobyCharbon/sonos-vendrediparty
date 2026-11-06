"""Scénario complet d'un événement de test, joué par les 15 bots (organisateur → invités → membres → sans l'app).

Chaque phase est relançable seule (les identifiants des événements sont dans state.json). Toute erreur d'une étape
devient une anomalie (capture + journal) et la suite continue."""
from __future__ import annotations

import re

import httpx

from tests.bots import flows as f
from tests.bots.bench import load_state, phone, save_state
from tests.bots.common import BY_KEY, GROUP_BOTS, GROUP_BOTS_2, TEST_URL, Session, publishable_key, sql

FULL_TITLE = "Bot Soirée complète (avancé)"
POLL_TITLE = "Bot Sondage de dates"


def _open(p, key: str) -> None:
    p.goto(f"/events/event/{load_state()[key]}")
    p.page.wait_for_timeout(2500)


def _check_screen(p, what: str) -> None:
    """Chaque écran : défilement au doigt jusqu'en bas, textes coupés, capture."""
    p.scroll_to_bottom(what)
    cut = p.check_texts_cut(what)
    if cut:
        p.flag("🟡", f"{what} : textes coupés ou hors écran", "; ".join(cut))


# ── 1. Création (formulaire avancé, sondage de dates, droits) ──────────────────────────────────────────────────

def create_full(p) -> str | None:
    page = p.page
    p.goto("/events/event/new")
    p.see(page.get_by_label("Titre", exact=True), "le formulaire")
    p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
    f.fill(p, "Titre", FULL_TITLE)
    f.fill(p, "Description", "Soirée de test des bots : prix, places limitées, liste d'attente, billets QR. Ignorer.")
    p.tap(f.chip(p, "Soirée", exact=True).first, "catégorie Soirée")
    f.set_date(p, "Début", f.day(9), "20:00")
    f.set_date(p, "Fin (optionnel)", f.day(9), "23:30")
    f.fill(p, "Lieu", "Chez les bots")
    f.fill(p, "Adresse", "Rue du Lac 12, 1800 Vevey")
    f.fill(p, "Lien (site, carte…)", "https://www.google.com/maps/search/?api=1&query=Rue%20du%20Lac%2012%20Vevey")
    f.fill(p, "Prix / pers. (CHF)", "15")
    f.fill(p, "Paiement", "TWINT 079 000 01 03")
    f.toggle(p, "Billets QR", True)
    f.audience_invite_groups(p, [GROUP_BOTS])
    f.fill(p, "Nombre de places (vide = illimité)", "4")
    f.toggle(p, "Liste d’attente", True)
    f.toggle(p, "Réponse « Peut-être » autorisée", True)
    f.toggle(p, "Accompagnants (+1)", True)
    f.fill(p, "Accompagnants max par personne (vide = illimité)", "1")
    f.set_date(p, "Date limite de réponse (optionnel)", f.day(8), "12:00")
    # Co-organisateur : Bot Oscar (organisateur)
    p.tap(f.chip(p, "Bot Oscar", exact=True).first, "co-organisateur Bot Oscar")
    f.toggle(p, "Pot commun", True)
    with p.step("mini-sondage"):
        p.tap(page.get_by_role("button", name="+ Ajouter un sondage"), "+ Ajouter un sondage")
        f.fill(p, "Question du sondage 1", "Raclette ou fondue ?")
        page.get_by_label("Sondage 1, option 1", exact=True).fill("Raclette")
        page.get_by_label("Sondage 1, option 2", exact=True).fill("Fondue")
    with p.step("qui amène quoi"):
        p.tap(page.get_by_role("button", name="+ Ajouter un objet"), "+ Ajouter un objet")
        page.get_by_placeholder("Fromage, pain…").last.fill("Pain")
    f.toggle(p, "Forum de l’événement", True)
    f.toggle(p, "Prévenir le groupe à la publication", True)
    p.shot("avance-rempli")
    _check_screen(p, "formulaire avancé")
    p.shot("avance-bas")
    return f.submit(p, "Publier")


def create_poll(p) -> str | None:
    page = p.page
    p.goto("/events/event/new")
    p.see(page.get_by_label("Titre", exact=True), "le formulaire")
    p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
    f.fill(p, "Titre", POLL_TITLE)
    p.tap(page.get_by_role("tab", name="Date à définir"), "Date à définir")
    for i, offset in enumerate((12, 13, 14), start=1):
        if i > 1:
            p.tap(page.get_by_role("button", name="+ Ajouter un créneau"), "+ Ajouter un créneau")
        with p.step(f"créneau {i}"):
            f.set_date(p, f"Créneau {i}", f.day(offset), "19:00")
    f.set_date(p, "Fin du vote (optionnel)", f.day(10), "20:00")
    f.toggle(p, "Les membres peuvent proposer des dates", True)
    f.fill(p, "Lieu", "Bar des bots")
    f.audience_invite_groups(p, [GROUP_BOTS])
    p.shot("sondage-rempli")
    _check_screen(p, "formulaire sondage de dates")
    return f.submit(p, "Publier")


def phase_creation(browser, origin, only):
    p = phone(browser, "orga1", origin, "creation")
    try:
        with p.step("créer l'événement complet (avancé)"):
            eid = create_full(p)
            if eid:
                save_state(e_full=eid)
                p.shot("fiche-complete")
                _check_screen(p, "fiche organisateur")
                p.dump("fiche-organisateur")
    finally:
        p.close()
    p = phone(browser, "orga2", origin, "creation")
    try:
        with p.step("créer le sondage de dates"):
            eid = create_poll(p)
            if eid:
                save_state(e_poll=eid)
                p.shot("fiche-sondage")
                _check_screen(p, "fiche sondage")
    finally:
        p.close()


def phase_droits_creation(browser, origin, only):
    """Membre VIP, Membre et Guest essaient de créer : ce que chacun voit (Publier / Envoyer pour validation / refus)."""
    for key in ("vip1", "membre1", "guest1"):
        p = phone(browser, key, origin, "droits-creation")
        try:
            with p.step("ouvrir « Proposer »"):
                p.goto("/events/")
                p.page.wait_for_timeout(2500)
                propose = p.page.get_by_role("button", name=re.compile("Proposer"))
                p.log(f"bouton « Proposer » visible : {propose.count() > 0}")
                p.goto("/events/event/new")
                p.page.wait_for_timeout(3000)
                p.shot("formulaire")
                buttons = [b for b in ("Publier", "Envoyer pour validation") if p.page.get_by_role("button", name=b, exact=True).count()]
                p.log(f"bouton d'envoi : {buttons or 'aucun'}")
                (p.dir / "droits.txt").write_text(f"Proposer visible={propose.count() > 0} ; envoi={buttons}\n")
            with p.step("créer un événement"):
                title = f"Bot proposition de {BY_KEY[key].nickname}"
                eid = f.create_simple(p, title, 6, [GROUP_BOTS], submit_label=None)
                if eid:
                    save_state(**{f"e_{key}": eid})
                    p.shot("fiche")
                    status = p.page.get_by_text("En attente de validation").count()
                    p.log(f"statut affiché « En attente de validation » : {bool(status)}")
        finally:
            p.close()


# ── 2. Assistant IA : brouillon injecté (sans clé Anthropic), puis vrai serveur ─────────────────────────────────

AI_DRAFT = {"status": "ready", "questions": [], "description": "Raclette des bots, chacun amène une salade.",
            "end": "", "place_query": "Rue du Lac 12, Vevey", "place_name": "Chez les bots", "place_broad": "",
            "address_complete": True, "price_chf": 0, "max_participants": 0, "category": "Soirée", "audience": "",
            "invitees": ["Bot Max"], "not_understood": [], "pot": False, "bring": ["Salade"],
            "summary": "Raclette des bots"}


def ai_save_draft(token: str, origin: str, title: str, offset: int) -> dict:
    """Comme l'app iPhone après « Oui, continuer » : POST /api/account/ai/event/draft/save (vrai serveur, vraie base)."""
    start = f"{f.day(offset)}T19:00"
    r = httpx.post(f"{origin}/api/account/ai/event/draft/save", timeout=60,
                   json={"token": token, "draft": {**AI_DRAFT, "title": title, "start": start},
                         "place": {"name": "Chez les bots", "address": "Rue du Lac 12, 1800 Vevey", "url": ""}})
    return {"status": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}


def phase_ia(browser, origin, only):
    """3 brouillons IA de Bot Oscar ; étape 2 « Qui est invité » : Sur invitation, un groupe, Public."""
    s = Session(BY_KEY["orga2"].phone)
    # Comme l'app : l'accord « IA » (envoi à Anthropic) est demandé avant le premier usage ; le bot l'accepte.
    consent = httpx.post(f"{origin}/api/account/ai/consent", json={"token": s.token, "accept": True}, timeout=30)
    print("accord IA", consent.status_code, consent.text[:200], flush=True)
    choices = [("invite", "Sur invitation"), ("group", GROUP_BOTS), ("public", "Public")]
    for i, (kind, _) in enumerate(choices):
        out = ai_save_draft(s.token, origin, f"Bot IA ({kind})", 15 + i)
        print("brouillon IA", kind, out, flush=True)
        if out["status"] != 200:
            p = phone(browser, "orga2", origin, f"ia-{kind}")
            p.flag("🔴", f"IA : enregistrement du brouillon refusé ({kind})", str(out)[:400])
            p.close()
            continue
        eid = out["body"]["id"]
        save_state(**{f"ai_{kind}": eid})
        p = phone(browser, "orga2", origin, f"ia-{kind}")
        try:
            members = s.get(f"profiles?select=id&display_name=eq.Bot%20Max").json()
            suggested = members[0]["id"] if members else ""
            p.goto(f"/events/event/{eid}/invite?suggested={suggested}")
            p.page.wait_for_timeout(3000)
            p.expect_or_flag(p.page.get_by_role("progressbar", name=re.compile("Étape 2 sur 3")), "l'étape 2 « Qui est invité »", "🔴")
            p.shot("etape2")
            p.dump("etape2")
            _check_screen(p, f"étape 2 IA ({kind})")
            with p.step(f"choix « {kind} »"):
                page = p.page
                if kind == "invite":  # Sur invitation seulement → Publier → feuille Inviter avec le lien
                    p.tap(page.get_by_role("radio", name=re.compile("Sur invitation seulement")), "✉️ Sur invitation seulement")
                    p.shot("sur-invitation")
                    p.tap(page.get_by_role("button", name="Publier", exact=True), "Publier")
                elif kind == "group":  # Un groupe → Bots → « Publier sans inviter pour l'instant »
                    p.tap(page.get_by_role("radio", name=re.compile("Un groupe")), "👥 Un groupe")
                    page.wait_for_timeout(800)
                    p.dump("un-groupe")
                    c = f.chip(p, f"{GROUP_BOTS} · ").first
                    if f.selected(c):
                        p.log(f"groupe {GROUP_BOTS} déjà coché d'office")
                    else:
                        p.tap(c, f"groupe {GROUP_BOTS}")
                    p.shot("groupe-choisi")
                    p.tap(page.get_by_role("button", name="Publier sans inviter pour l’instant"), "Publier sans inviter pour l'instant")
                else:  # Public (par défaut) → « Ouvrir l'événement (finir à la main) » puis publier depuis la fiche
                    p.tap(page.get_by_role("button", name="Ouvrir l’événement (finir à la main)"), "Ouvrir l'événement (finir à la main)")
                    page.wait_for_timeout(3000)
                    p.shot("fiche-brouillon")
                    p.dump("fiche-brouillon")
                    publish = page.get_by_role("button", name=re.compile("^(Inviter et publier|Publier)"))
                    if publish.count():
                        p.tap(publish.first, publish.first.inner_text())
                        page.wait_for_timeout(3000)
                        again = page.get_by_role("button", name="Publier", exact=True)
                        if again.count():  # « Inviter et publier » ramène à l'étape 2 : on y publie
                            p.shot("retour-etape2")
                            p.tap(again.first, "Publier (étape 2)")
                    else:
                        p.flag("🟠", "IA « finir à la main » : aucun bouton pour publier depuis la fiche du brouillon")
                page.wait_for_timeout(2500)
                if f.accept_terms_if_asked(p):
                    page.wait_for_timeout(3000)
                p.shot("apres-choix")
                p.dump("apres-choix")
                if kind == "invite":
                    sheet = page.get_by_label(re.compile("^Inviter à "))
                    if p.see(sheet, "la feuille « Inviter » avec le lien", 10000):
                        box = sheet.bounding_box()
                        p.scroll_to_bottom("feuille Inviter (étape 3 IA)", x=box["x"] + box["width"] / 2, y=min(box["y"] + box["height"] - 60, 700))
                        p.shot("feuille-bas")
                        p.expect_or_flag(sheet.get_by_role("button", name=re.compile("Retirer Bot Max")), "Bot Max proposé par l'IA coché", "🟡", 5000)
                    else:
                        p.flag("🟠", "IA « Sur invitation » : la feuille Inviter avec le lien ne s'ouvre pas après Publier")
            status = sql(f"select status, visibility, public_link from public.events where id = '{eid}'")
            p.log(f"base : {status}")
            if not status or status[0]["status"] != "published":
                p.flag("🔴", f"IA ({kind}) : l'événement n'est pas publié après le choix", str(status))
        finally:
            p.close()


# ── 3. Invitations (feuille « Inviter ») ────────────────────────────────────────────────────────────────────────

def _sheet(p):
    sheet = p.page.get_by_label(re.compile("^Inviter à "))
    sheet.wait_for(state="visible", timeout=10000)
    return sheet


def _sheet_scroll(p, sheet, what: str) -> str:
    box = sheet.bounding_box()
    return p.scroll_to_bottom(what, x=box["x"] + box["width"] / 2, y=min(box["y"] + box["height"] - 60, 700))


def _copy_link(p, sheet) -> str:
    p.tap(sheet.get_by_role("button", name="Copier"), "Copier le lien")
    p.page.wait_for_timeout(1200)
    text = p.page.evaluate("navigator.clipboard.readText()")
    m = re.search(r"/events/invite/([0-9a-f-]{36})", text or "")
    p.log(f"presse-papiers : {text!r}")
    return m.group(1) if m else ""


def phase_retirer(browser, origin, only):
    """Retirer un invité ajouté à la main (Bot Gina) depuis la carte Invités, puis la réinviter."""
    p = phone(browser, "orga1", origin, "retirer")
    page = p.page
    try:
        _open(p, "e_full")
        page.get_by_text(re.compile("^Invités · ")).first.wait_for(timeout=20000)
        with p.step("retirer Bot Gina"):
            remove = page.get_by_role("button", name=re.compile("Retirer.*Bot Gina"))
            remove.first.scroll_into_view_if_needed()
            p.tap(remove.first, "Retirer Bot Gina")
            page.wait_for_timeout(1200)
            p.shot("confirmer-visible")
            confirm = page.get_by_role("button", name=re.compile("^Confirmer"))
            box = confirm.first.bounding_box() if confirm.count() else None
            p.log(f"bouton Confirmer : {box}")
            if box and box["height"] < 40:
                p.flag("🟠", "Retirer un invité : le bouton « Confirmer » révélé est écrasé / mal placé", str(box))
            p.tap(confirm.first, "Confirmer le retrait")
            page.wait_for_timeout(2500)
            p.shot("apres-retrait")
        rows = sql(f"""select 1 from public.event_invites i join public.profiles p on p.id = i.user_id
                       where i.event_id = '{load_state()['e_full']}' and p.display_name = 'Bot Gina'""")
        p.log(f"Bot Gina encore invitée en base : {bool(rows)}")
        if rows:
            p.flag("🔴", "« Retirer » Bot Gina : elle reste invitée en base")
        with p.step("réinviter Bot Gina"):
            p.tap(page.get_by_role("button", name="Inviter", exact=True), "＋ Inviter")
            sheet = _sheet(p)
            sheet.get_by_label("Chercher une personne ou un groupe").fill("Gina")
            page.wait_for_timeout(1500)
            p.tap(sheet.get_by_role("button", name=re.compile("^Ajouter Bot Gina")).first, "Ajouter Bot Gina")
            p.tap(sheet.get_by_role("button", name=re.compile("^Inviter ")).first, "Inviter")
            page.wait_for_timeout(2500)
            p.shot("gina-reinvitee")
    finally:
        p.close()


def phase_invitations(browser, origin, only):
    p = phone(browser, "orga1", origin, "invitations")
    page = p.page
    try:
        _open(p, "e_full")
        with p.step("ouvrir la feuille Inviter et la faire défiler au doigt"):
            p.tap(page.get_by_role("button", name="Inviter", exact=True), "＋ Inviter")
            sheet = _sheet(p)
            p.shot("feuille")
            result = _sheet_scroll(p, sheet, "feuille Inviter")
            p.shot("feuille-bas")
            last = sheet.get_by_text(re.compile("notification Party")).last
            if last.count() and not last.is_visible():
                p.flag("🔴", "feuille Inviter : le bas de la feuille reste inaccessible au doigt", result)
        with p.step("ajouter le groupe Bots 2"):
            p.tap(sheet.get_by_role("button", name=f"Ajouter {GROUP_BOTS_2}"), f"Ajouter {GROUP_BOTS_2}")
        with p.step("chercher et ajouter Bot Max (hors groupe) et Bot Gina (Guest)"):
            for name in ("Bot Max", "Bot Gina"):
                search = sheet.get_by_label("Chercher une personne ou un groupe")
                p.type(search, name.split()[1], "la recherche")
                page.wait_for_timeout(1500)
                p.shot(f"recherche-{name.split()[1]}")
                p.tap(sheet.get_by_role("button", name=re.compile(rf"^Ajouter {name}")).first, f"Ajouter {name}")
                search.fill("")
            p.shot("personnes-cochees")
            invite = sheet.get_by_role("button", name=re.compile("^Inviter "))
            p.tap(invite.first, "Inviter (personnes cochées)")
            page.wait_for_timeout(2500)
            p.shot("apres-inviter")
        with p.step("lien « Une personne » pour Sam (sans l'app)"):
            if not sheet.is_visible():
                p.tap(page.get_by_role("button", name="Inviter", exact=True), "＋ Inviter")
                sheet = _sheet(p)
            p.tap(sheet.get_by_role("tab", name="Une personne"), "Une personne")
            label = sheet.get_by_label("Pour qui ? (facultatif)")
            if label.count():
                p.type(label, "Sam", "Pour qui ?")
            token = _copy_link(p, sheet)
            p.shot("lien-une-personne")
            if token:
                save_state(link_one=token)
            else:
                p.flag("🔴", "lien « Une personne » : aucun lien copié")
        with p.step("lien « Plusieurs » (3 places) pour Sara"):
            nouveau = sheet.get_by_role("button", name="Nouveau lien (pour quelqu’un d’autre)")
            if nouveau.count():
                p.tap(nouveau, "Nouveau lien")
            p.tap(sheet.get_by_role("tab", name="Plusieurs"), "Plusieurs")
            for _ in range(7):
                p.tap(sheet.get_by_label("Une place de moins"), "une place de moins")
            token = _copy_link(p, sheet)
            p.shot("lien-plusieurs")
            if token:
                save_state(link_many=token)
            else:
                p.flag("🔴", "lien « Plusieurs » : aucun lien copié")
        with p.step("QR code du lien"):
            p.tap(sheet.get_by_role("button", name="QR code"), "QR code")
            page.wait_for_timeout(1200)
            p.expect_or_flag(page.get_by_label(re.compile("QR code du lien")).first, "le QR code du lien", "🟠", 8000)
            p.shot("qr")
            close = page.get_by_role("button", name="Fermer")
            p.tap(close.last, "Fermer")
        with p.step("fermer la feuille"):
            page.wait_for_timeout(800)
            if sheet.is_visible():
                p.tap(sheet.get_by_role("button", name="Fermer").first, "Fermer la feuille")
        _open(p, "e_full")
        p.page.get_by_text(re.compile("^Invités · ")).first.wait_for(timeout=20000)
        p.dump("fiche-apres-invitations")
        with p.step("relancer une personne"):
            p.tap(page.get_by_role("tab", name=re.compile("Pas répondu")), "filtre Pas répondu")
            page.wait_for_timeout(800)
            nudge = page.get_by_role("button", name=re.compile("^Relancer Bot"))
            p.log(f"{nudge.count()} bouton(s) « Relancer … »")
            if nudge.count():
                p.tap(nudge.first, "Relancer (une personne)")
                page.wait_for_timeout(1500)
                p.shot("apres-relance")
        with p.step("retirer Bot Gina puis la réinviter"):
            remove = page.get_by_role("button", name=re.compile("Retirer.*Bot Gina"))
            p.log(f"bouton retirer Gina : {remove.count()}")
            if remove.count():
                p.tap(remove.first, "Retirer Bot Gina")
                page.wait_for_timeout(1000)
                confirm = page.get_by_role("button", name=re.compile("^Confirmer"))
                if confirm.count():
                    box = confirm.first.bounding_box()
                    p.log(f"bouton Confirmer : {box}")
                    if box and box["height"] < 40:
                        p.flag("🟠", "Retirer un invité : le bouton « Confirmer » révélé est écrasé / mal placé", str(box))
                    p.tap(confirm.first, "Confirmer le retrait")
                page.wait_for_timeout(2000)
                p.shot("gina-retiree")
            else:
                p.flag("🟠", "impossible de retirer Bot Gina depuis la carte Invités (bouton introuvable)")
        _check_screen(p, "fiche après invitations")
    finally:
        p.close()
    rows = sql(f"""select p.display_name, i.via_group from public.event_invites i join public.profiles p on p.id = i.user_id
                   where i.event_id = '{load_state()['e_full']}' order by 1""")
    print("invités en base :", rows, flush=True)
    save_state(invites_after=rows)


# ── 4. Réponses des invités (Présent / Peut-être / Absent, accompagnants, liste d'attente) ───────────────────────

def rsvp(p, choice: str) -> None:
    page = p.page
    radio = page.get_by_role("radiogroup").get_by_role("button", name=choice, exact=True).first
    p.tap(radio, choice)
    page.wait_for_timeout(2500)
    if f.accept_terms_if_asked(p):
        page.wait_for_timeout(2500)
    p.shot(f"apres-{choice.lower()}")


def my_rsvp(key: str) -> dict | None:
    rows = sql(f"""select r.status, r.waitlisted, r.plus_ones from public.rsvps r join public.profiles p on p.id = r.user_id
                   where r.event_id = '{load_state()['e_full']}' and p.phone = '{BY_KEY[key].phone}'""")
    return rows[0] if rows else None


def _waitlisted(row) -> bool:
    return bool(row and row.get("waitlisted"))


def phase_reponses(browser, origin, only):
    plan = [("vip1", "Présent", 1), ("vip2", "Peut-être", 0), ("vip3", "Absent", 0), ("membre1", "Présent", 0),
            ("vip3", "Présent", 0), ("membre3", "Présent", 0), ("guest2", "Présent", 0)]
    for key, choice, extras in plan:
        p = phone(browser, key, origin, "reponses")
        page = p.page
        try:
            _open(p, "e_full")
            with p.step(f"répondre « {choice} »"):
                rsvp(p, choice)
                for _ in range(extras):
                    p.tap(page.get_by_label("Ajouter un accompagnant"), "Ajouter un accompagnant")
                    page.wait_for_timeout(1500)
                if extras:
                    p.shot("accompagnant")
                note = page.get_by_label("Un petit mot perso pour l’organisateur")
                if note.count() and choice == "Présent":
                    p.type(note, f"Salut, ici {BY_KEY[key].nickname} !", "le petit mot")
                    send = page.get_by_role("button", name="Envoyer", exact=True)
                    if send.count():
                        p.tap(send.first, "Envoyer le petit mot")
                page.wait_for_timeout(1500)
                row = my_rsvp(key)
                p.log(f"base : {row}")
                expected = {"Présent": "yes", "Peut-être": "maybe", "Absent": "no"}[choice]
                if not row or row["status"] != expected:
                    p.flag("🔴", f"réponse « {choice} » pas enregistrée en base", str(row))
                if extras and row and row.get("plus_ones") != extras:
                    p.flag("🟠", f"accompagnants : {extras} demandé(s), base {row.get('plus_ones')}")
                if _waitlisted(row):
                    p.expect_or_flag(page.get_by_text(re.compile("liste d.attente", re.I)).first, "le statut « liste d'attente » à l'écran")
            if key == "vip1":
                with p.step("mini-sondage et « Je prends »"):
                    p.tap(page.get_by_role("button", name=re.compile("^Raclette")).first, "vote Raclette")
                    p.tap(page.get_by_role("button", name="Je prends").first, "Je prends (Pain)")
                    page.wait_for_timeout(1500)
                    p.shot("sondage-et-pain")
            _check_screen(p, f"fiche invité ({choice})")
        finally:
            p.close()
    # Victor (2 places avec son accompagnant) se désiste : la liste d'attente doit monter.
    before = {k: my_rsvp(k) for k in ("membre3", "guest2")}
    p = phone(browser, "vip1", origin, "reponses-desistement")
    try:
        _open(p, "e_full")
        with p.step("changer d'avis : Absent"):
            rsvp(p, "Absent")
    finally:
        p.close()
    after = {k: my_rsvp(k) for k in ("membre3", "guest2")}
    save_state(waitlist_before=before, waitlist_after=after)
    print("liste d'attente avant/après désistement :", before, after, flush=True)
    for k in ("membre3", "guest2"):
        p = phone(browser, k, origin, "reponses-montee")
        try:
            _open(p, "e_full")
            p.shot("apres-desistement")
            if _waitlisted(before[k]) and _waitlisted(after[k]):
                p.flag("🔴", "liste d'attente : une place libérée (désistement de 2 places) mais le bot reste en attente",
                       f"avant {before[k]} après {after[k]}")
        finally:
            p.close()


def phase_sondage_dates(browser, origin, only):
    votes = {"vip2": ("Oui", "Non", "Si besoin"), "membre1": ("Oui", "Oui", "Non"), "membre2": ("Non", "Oui", "Oui"),
             "guest1": ("Oui", "Si besoin", "Non")}
    for key, answers in votes.items():
        p = phone(browser, key, origin, "sondage-dates")
        page = p.page
        try:
            _open(p, "e_poll")
            with p.step("voter sur chaque créneau"):
                labels = page.get_by_role("button", name=re.compile(r"^Oui : ")).all()
                slots = [b.get_attribute("aria-label").split(" : ", 1)[1] for b in labels]
                for slot, answer in zip(slots, answers):
                    p.tap(page.get_by_role("button", name=f"{answer} : {slot}"), f"{answer} pour {slot}")
                    page.wait_for_timeout(1200)
                    if f.accept_terms_if_asked(p):
                        page.wait_for_timeout(1500)
                p.shot("votes")
            if key == "vip2":
                with p.step("proposer une date"):
                    f.set_date(p, "Proposer une date", f.day(16), "20:00")
                    p.tap(page.get_by_role("button", name="Ajouter", exact=True).first, "Ajouter la date")
                    page.wait_for_timeout(2000)
                    p.shot("date-proposee")
            _check_screen(p, "fiche sondage de dates (invité)")
        finally:
            p.close()
    n = sql(f"""select count(*) n from public.date_votes v join public.date_options o on o.id = v.option_id
                where o.event_id = '{load_state()['e_poll']}'""")
    print("votes en base :", n, flush=True)
    p = phone(browser, "orga2", origin, "sondage-fixer")
    page = p.page
    try:
        _open(p, "e_poll")
        p.shot("resultats")
        with p.step("fixer la date la plus votée"):
            p.tap(page.get_by_role("button", name="Fixer cette date").first, "Fixer cette date")
            page.wait_for_timeout(1200)
            confirm = page.get_by_role("button", name=re.compile("^Oui|Confirmer|Fixer"))
            p.dump("fixer")
            if confirm.count() > 1:
                p.tap(confirm.last, "confirmer")
            page.wait_for_timeout(3000)
            p.shot("date-fixee")
        mode = sql(f"select date_mode, starts_at from public.events where id = '{load_state()['e_poll']}'")
        p.log(f"base : {mode}")
        if not mode or mode[0]["date_mode"] != "fixed":
            p.flag("🔴", "« Fixer cette date » : l'événement reste en sondage", str(mode))
    finally:
        p.close()


def phase_forum(browser, origin, only):
    for key, text in (("vip3", "Je ramène la musique 🎶"), ("orga1", "Super, merci @Bot Valentin !"), ("guest1", "Moi aussi je viens ?")):
        p = phone(browser, key, origin, "forum")
        page = p.page
        try:
            p.goto(f"/events/event/{load_state()['e_full']}/chat")
            page.wait_for_timeout(3000)
            with p.step("écrire dans la discussion"):
                box = page.get_by_label("Message", exact=True)
                p.type(box, text, "le message")
                p.tap(page.get_by_role("button", name="Envoyer", exact=True), "Envoyer")
                page.wait_for_timeout(2500)
                if f.accept_terms_if_asked(p):
                    page.wait_for_timeout(2500)
                p.expect_or_flag(page.get_by_text(text.split(" @")[0]).last, f"son message « {text} »", "🔴", 8000)
                p.shot("message")
            _check_screen(p, "discussion")
        finally:
            p.close()


def phase_paiements(browser, origin, only):
    """« Payer l'organisateur » → « J'ai payé » ; l'organisateur : « Reçu ✓ » et « Pas reçu »."""
    for key in ("membre1", "vip3"):
        p = phone(browser, key, origin, "paiement")
        page = p.page
        try:
            _open(p, "e_full")
            with p.step("payer l'organisateur"):
                p.tap(page.get_by_role("button", name=re.compile("^Payer l’organisateur")).first, "Payer l'organisateur")
                page.wait_for_timeout(1500)
                p.shot("feuille-paiement")
                p.dump("feuille-paiement")
                p.tap(page.get_by_role("button", name="J’ai payé"), "J'ai payé")
                page.wait_for_timeout(2500)
                p.shot("apres-jai-paye")
        finally:
            p.close()
    p = phone(browser, "orga1", origin, "paiement-orga")
    page = p.page
    try:
        _open(p, "e_full")
        p.dump("fiche-paiements")
        with p.step("Reçu ✓ (Bot Marc) et Pas reçu (Bot Valentin)"):
            received = page.get_by_role("button", name="Reçu ✓")
            p.log(f"{received.count()} paiement(s) en attente")
            if not received.count():
                p.flag("🔴", "paiements déclarés invisibles pour l'organisateur (aucun « Reçu ✓ »)")
            else:
                p.tap(received.first, "Reçu ✓")
                page.wait_for_timeout(2500)
                p.tap(page.get_by_role("button", name="Pas reçu").first, "Pas reçu")
                page.wait_for_timeout(2500)
                p.shot("apres-confirmations")
    finally:
        p.close()
    rows = sql(f"""select p.display_name, t.* from public.event_tickets t join public.profiles p on p.id = t.user_id
                   where t.event_id = '{load_state()['e_full']}'""")
    print("billets en base :", rows, flush=True)
    save_state(tickets_after_pay=[{k: str(v) for k, v in r.items()} for r in rows])


def phase_billets(browser, origin, only):
    """Billet remis par l'organisateur, QR chez l'invité, scan à l'entrée par code, Wallet (réponse du serveur)."""
    p = phone(browser, "orga1", origin, "billets")
    page = p.page
    try:
        _open(p, "e_full")
        with p.step("remettre le billet à Bot Max"):
            give = page.get_by_role("button", name="Remettre le billet")
            p.log(f"{give.count()} bouton(s) « Remettre le billet »")
            p.dump("fiche-billets")
            p.tap(give.first, "Remettre le billet")
            page.wait_for_timeout(2500)
            p.shot("billet-remis")
    finally:
        p.close()
    code = ""
    for key in ("membre3", "membre1"):
        p = phone(browser, key, origin, "billets")
        page = p.page
        try:
            _open(p, "e_full")
            with p.step("voir son billet QR"):
                ticket = page.get_by_label("Ton billet")
                if p.see(ticket, "son billet", 8000):
                    p.tap(ticket.first, "Ton billet")
                    page.wait_for_timeout(1500)
                    p.shot("billet-qr")
                    label = page.get_by_label(re.compile("^Code ")).first.get_attribute("aria-label") or ""
                    code = code or label.removeprefix("Code ").replace(" ", "")
                    p.log(f"code du billet : {code}")
                else:
                    p.log("pas de billet visible")
                    p.shot("sans-billet")
            with p.step("Wallet : réponse du serveur"):
                s = Session(BY_KEY[key].phone)
                st = httpx.get(f"{origin}/api/wallet/status", timeout=30).json()
                r = httpx.post(f"{origin}/api/wallet/ticket", json={"token": s.token, "event_id": load_state()["e_full"]}, timeout=30)
                p.log(f"Wallet status={st} ticket → {r.status_code} {r.text[:200]}")
                button = page.get_by_label("Ajouter à l’app Cartes Apple").count()
                p.log(f"bouton Wallet affiché : {bool(button)}")
                if button and not st.get("enabled"):
                    p.flag("🟠", "bouton Apple Wallet affiché alors que le serveur n'a pas Wallet (503)")
        finally:
            p.close()
    save_state(ticket_code=code)
    p = phone(browser, "orga1", origin, "scan")
    page = p.page
    try:
        p.goto(f"/events/event/{load_state()['e_full']}/scan")
        page.wait_for_timeout(3000)
        p.shot("scanner")
        p.dump("scanner")
        with p.step("valider le billet par son code"):
            if not code:
                raise RuntimeError("aucun code de billet relevé")
            p.type(page.get_by_label("Code du billet"), code, "le code du billet")
            p.tap(page.get_by_role("button", name="Valider"), "Valider")
            page.wait_for_timeout(2500)
            p.shot("billet-valide")
            p.dump("billet-valide")
        with p.step("le même billet une 2e fois"):
            nxt = page.get_by_role("button", name="Billet suivant")
            if nxt.count():
                p.tap(nxt, "Billet suivant")
            p.type(page.get_by_label("Code du billet"), code, "le même code")
            p.tap(page.get_by_role("button", name="Valider"), "Valider")
            page.wait_for_timeout(2500)
            p.shot("billet-deja-scanne")
        _check_screen(p, "scanner")
    finally:
        p.close()
    p = phone(browser, "guest1", origin, "scan-interdit")
    try:
        p.goto(f"/events/event/{load_state()['e_full']}/scan")
        p.page.wait_for_timeout(3000)
        p.shot("scanner-guest")
        p.dump("scanner-guest")
    finally:
        p.close()


# ── 5. « Sans l'app » : arrivée par le lien (prénom + numéro + code) ───────────────────────────────────────────

def phase_sans_app(browser, origin, only):
    """Sam (lien « une personne ») et Sara (lien « plusieurs ») n'ont aucun compte : navigateur vierge, lien reçu."""
    for key, link_key, answer in (("sansapp1", "link_one", "Je viens !"), ("sansapp2", "link_many", "Peut-être")):
        storage = phone(browser, key, origin, "x").dir / "storage.json"
        storage.unlink(missing_ok=True)  # aucune session : un vrai nouveau téléphone
        p = phone(browser, key, origin, "sans-app")
        page = p.page
        bot = BY_KEY[key]
        try:
            token = load_state().get(link_key)
            if not token:
                p.flag("🔴", f"pas de lien {link_key} à ouvrir (phase invitations)")
                continue
            p.goto(f"/events/invite/{token}")
            page.wait_for_timeout(4000)
            p.shot("carte-invitation")
            p.dump("carte-invitation")
            _check_screen(p, "carte d'invitation (sans compte)")
            with p.step(f"répondre « {answer} » sans l'app"):
                p.tap(page.get_by_role("button", name=answer, exact=True).first, answer)
                page.wait_for_timeout(1500)
                p.shot("identite")
                p.type(page.get_by_label("Prénom", exact=True), bot.first, "le prénom")
                p.type(page.get_by_label("Numéro de portable"), "0" + bot.phone[2:], "le numéro")
                p.tap(page.get_by_role("button", name="Recevoir mon code par SMS"), "Recevoir mon code par SMS")
                code = page.get_by_placeholder("123456")
                code.wait_for(state="visible", timeout=60000)
                p.type(code, "123456", "le code")
                p.tap(page.get_by_role("button", name="Confirmer").last, "Confirmer")
                page.wait_for_timeout(4000)
                if f.accept_terms_if_asked(p):
                    page.wait_for_timeout(3000)
                p.shot("confirmation")
                p.dump("confirmation")
                _check_screen(p, "confirmation (sans l'app)")
            rows = sql(f"""select r.status, p.display_name from public.rsvps r join public.profiles p on p.id = r.user_id
                           where r.event_id = '{load_state()['e_full']}' and p.phone = '{bot.phone}'""")
            p.log(f"base : {rows}")
            if not rows:
                p.flag("🔴", f"« {answer} » par le lien : aucune réponse enregistrée", "")
            with p.step("rouvrir le lien (déjà répondu)"):
                p.goto(f"/events/invite/{token}")
                page.wait_for_timeout(3500)
                p.shot("lien-rouvert")
        finally:
            p.close()


# ── 6. Signaler, bloquer ────────────────────────────────────────────────────────────────────────────────────

def phase_signaler(browser, origin, only):
    """Bot Gina signale l'événement (les admins réels ne sont pas prévenus : quarantaine), Bot Max bloque Bot Gus."""
    p = phone(browser, "guest2", origin, "signaler")
    page = p.page
    try:
        _open(p, "e_full")
        with p.step("signaler l'événement"):
            p.tap(page.get_by_role("button", name="Signaler cet événement"), "Signaler cet événement")
            page.wait_for_timeout(1200)
            p.shot("feuille-signaler")
            p.dump("feuille-signaler")
            sheet = page.get_by_role("dialog").last
            box = sheet.bounding_box()
            if box:
                p.scroll_to_bottom("feuille Signaler", x=box["x"] + box["width"] / 2, y=min(box["y"] + box["height"] - 60, 700))
            reason = page.get_by_role("radio", name=re.compile("Spam")).first
            if not reason.count():
                reason = page.get_by_role("button", name=re.compile("Spam")).first
            p.tap(reason, "raison Spam")
            p.type(page.get_by_label("Commentaire"), "Test du banc des bots, à ignorer", "le commentaire")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True).last, "Envoyer le signalement")
            page.wait_for_timeout(2500)
            p.shot("apres-signalement")
        rows = sql(f"select reason, status from public.content_reports where target_kind = 'event' and target_id = '{load_state()['e_full']}'")
        p.log(f"base : {rows}")
        if not rows:
            p.flag("🔴", "signalement de l'événement non enregistré")
    finally:
        p.close()
    gus = sql(f"select id from public.profiles where phone = '{BY_KEY['guest1'].phone}'")[0]["id"]
    p = phone(browser, "membre3", origin, "bloquer")
    page = p.page
    try:
        p.goto(f"/events/member/{gus}")
        page.wait_for_timeout(3500)
        p.shot("fiche-membre")
        p.dump("fiche-membre")
        with p.step("bloquer Bot Gus"):
            p.tap(page.get_by_role("button", name=re.compile("^Bloquer")).first, "Bloquer Bot Gus")
            page.wait_for_timeout(800)
            p.tap(page.get_by_role("button", name="Confirmer le blocage"), "Confirmer le blocage")
            page.wait_for_timeout(2500)
            p.shot("bloque")
            p.expect_or_flag(page.get_by_role("button", name=re.compile("^Débloquer")), "« Débloquer » après blocage")
        with p.step("débloquer"):
            p.tap(page.get_by_role("button", name=re.compile("^Débloquer")).first, "Débloquer")
            page.wait_for_timeout(2000)
        _check_screen(p, "fiche membre")
    finally:
        p.close()


# ── 7. Organisateur : modifier, changer la date, annuler, rouvrir (admin), supprimer ────────────────────────

def bot_notifications(kind: str, event_key: str) -> list:
    return sql(f"""select p.display_name, n.kind, n.title from public.notifications n join public.profiles p on p.id = n.user_id
                   where n.event_id = '{load_state()[event_key]}' and n.kind = '{kind}' order by 1""") or []


def phase_modifier(browser, origin, only):
    p = phone(browser, "orga1", origin, "modifier")
    page = p.page
    try:
        _open(p, "e_full")
        with p.step("Modifier : titre et date après publication"):
            p.tap(page.get_by_role("button", name="Modifier", exact=True), "Modifier")
            page.wait_for_url(re.compile(r"/edit"), timeout=15000)
            page.get_by_label("Titre", exact=True).wait_for(timeout=15000)
            p.shot("formulaire-modification")
            f.fill(p, "Titre", FULL_TITLE + " (modifié)")
            f.set_date(p, "Début", f.day(10), "20:30")
            f.set_date(p, "Fin (optionnel)", f.day(10), "23:55")
            _check_screen(p, "formulaire de modification")
            p.tap(page.get_by_role("button", name="Enregistrer", exact=True).last, "Enregistrer")
            page.wait_for_timeout(1500)
            p.dump("apres-enregistrer")
            confirm = page.get_by_role("button", name=re.compile("Prévenir|Enregistrer et|Oui"))
            if confirm.count():
                p.shot("question-prevenir")
                p.tap(confirm.first, confirm.first.inner_text())
            page.wait_for_url(re.compile(r"/event/[0-9a-f-]{36}$"), timeout=15000)
            page.wait_for_timeout(2500)
            p.shot("fiche-modifiee")
        row = sql(f"select title, starts_at from public.events where id = '{load_state()['e_full']}'")
        p.log(f"base : {row}")
        notes = bot_notifications("event_changed", "e_full")
        p.log(f"notifications « modifié » reçues par les bots : {notes}")
        save_state(changed_notifications=notes)
        if row and row[0]["title"].endswith("(modifié)") and not notes:
            p.flag("🟠", "événement modifié (date) : aucun participant prévenu (notification event_changed)")
    finally:
        p.close()
    # Bot Victor (Absent) ou Bot Marc (Présent) voit-il la nouvelle date ?
    p = phone(browser, "membre1", origin, "modifier-vu")
    try:
        _open(p, "e_full")
        p.shot("nouvelle-date")
        p.expect_or_flag(p.page.get_by_text(FULL_TITLE + " (modifié)"), "le nouveau titre côté invité")
        p.goto("/events/activity")
        p.page.wait_for_timeout(3000)
        p.shot("activite")
        p.dump("activite")
        _check_screen(p, "Activité")
    finally:
        p.close()


def phase_annuler(browser, origin, only):
    """Bot Olga annule l'événement simple ; Bot Ada (admin) tente de le rouvrir ; puis suppression."""
    p = phone(browser, "orga1", origin, "annuler")
    page = p.page
    try:
        _open(p, "e_simple")
        with p.step("Annuler l'événement"):
            p.tap(page.get_by_role("button", name="Annuler l’événement"), "Annuler l'événement")
            page.wait_for_timeout(800)
            p.tap(page.get_by_role("button", name="Oui, annuler"), "Oui, annuler")
            page.wait_for_timeout(3000)
            p.shot("annule")
            p.expect_or_flag(page.get_by_text("Cet événement a été annulé."), "le bandeau « annulé »")
        p.dump("fiche-annulee")
    finally:
        p.close()
    p = phone(browser, "admin", origin, "rouvrir")
    page = p.page
    try:
        _open(p, "e_simple")
        p.shot("fiche-annulee-admin")
        p.dump("fiche-annulee-admin")
        with p.step("rouvrir (admin)"):
            reopen = page.get_by_role("button", name=re.compile("Rouvrir|Réouvrir|Republier|Rétablir"))
            if reopen.count():
                p.tap(reopen.first, reopen.first.inner_text())
            else:
                p.flag("🟠", "événement annulé : aucun bouton « Rouvrir » pour l'admin sur la fiche")
                p.tap(page.get_by_role("button", name="Modifier", exact=True), "Modifier")
                page.wait_for_timeout(3000)
                p.shot("modifier-annule")
                p.dump("modifier-annule")
                buttons = [b.inner_text() for b in page.get_by_role("button").all() if b.is_visible()][-4:]
                p.log(f"boutons du bas : {buttons}")
        status = sql(f"select status from public.events where id = '{load_state()['e_simple']}'")
        p.log(f"base : {status}")
        with p.step("supprimer l'événement annulé"):
            _open(p, "e_simple")
            delete = page.get_by_role("button", name=re.compile("Supprimer"))
            if delete.count():
                p.tap(delete.first, delete.first.inner_text())
                page.wait_for_timeout(800)
                p.tap(page.get_by_role("button", name=re.compile("^Oui, supprimer")), "Oui, supprimer")
                page.wait_for_timeout(2500)
            else:
                p.flag("🟠", "événement annulé : aucun moyen de le supprimer depuis l'app (seulement brouillon / proposition)")
    finally:
        p.close()


def phase_valider(browser, origin, only):
    """Bot Côme (co-admin) valide la proposition de Bot Victor (Membre VIP)."""
    eid = load_state().get("e_vip1")
    if not eid:
        return
    p = phone(browser, "coadmin", origin, "valider")
    page = p.page
    try:
        p.goto(f"/events/event/{eid}")
        page.wait_for_timeout(3000)
        p.shot("proposition")
        with p.step("Approuver"):
            p.tap(page.get_by_role("button", name="Approuver"), "Approuver")
            page.wait_for_timeout(3000)
            p.shot("approuvee")
        st = sql(f"select status from public.events where id = '{eid}'")
        p.log(f"base : {st}")
        if not st or st[0]["status"] != "published":
            p.flag("🔴", "co-admin : « Approuver » ne publie pas la proposition", str(st))
    finally:
        p.close()


def phase_droits(browser, origin, only):
    """Guest et Membre sur l'édition d'un événement d'un autre ; co-admin modifie celui d'un organisateur."""
    for key in ("guest1", "membre2", "vip2"):
        p = phone(browser, key, origin, "droits")
        page = p.page
        try:
            _open(p, "e_full")
            has_edit = page.get_by_role("button", name="Modifier", exact=True).count()
            p.log(f"bouton Modifier visible : {bool(has_edit)}")
            if has_edit:
                p.flag("🔴", f"{BY_KEY[key].role} voit « Modifier » sur l'événement d'un autre")
            p.goto(f"/events/event/{load_state()['e_full']}/edit")
            page.wait_for_timeout(3500)
            p.shot("edition-directe")
            p.dump("edition-directe")
            save = page.get_by_role("button", name="Enregistrer", exact=True)
            if save.count():
                p.log("le formulaire d'édition s'ouvre : essai d'enregistrement")
                page.get_by_label("Titre", exact=True).fill("Piraté par un bot")
                p.tap(save.last, "Enregistrer")
                page.wait_for_timeout(3000)
                p.shot("edition-refusee")
                t = sql(f"select title from public.events where id = '{load_state()['e_full']}'")[0]["title"]
                if t == "Piraté par un bot":
                    p.flag("🔴", f"{BY_KEY[key].role} a pu modifier l'événement d'un autre")
                else:
                    p.flag("🟡", f"{BY_KEY[key].role} : l'URL /edit ouvre le formulaire complet d'un événement d'un autre (refus seulement à l'enregistrement)")
        finally:
            p.close()
    p = phone(browser, "coadmin", origin, "droits")
    try:
        _open(p, "e_poll")
        p.log(f"co-admin : Modifier visible sur l'événement d'Oscar : {bool(p.page.get_by_role('button', name='Modifier', exact=True).count())}")
        p.shot("coadmin-fiche")
    finally:
        p.close()


def phase_page_party(browser, origin, only):
    """Comme dans l'app : le module Événements dans la page Party (iframe #eventsFrame), feuille Inviter au doigt."""
    p = phone(browser, "orga1", origin, "page-party")
    page = p.page
    try:
        page.add_init_script("localStorage.setItem('vp_tab','events');localStorage.setItem('vp_install_dismissed','1');"
                             "localStorage.setItem('vp_name','Bot Olga')")
        p.goto("/")
        page.wait_for_timeout(4000)
        frame = page.frame_locator("#eventsFrame")
        with p.step("ouvrir la fiche dans la page Party"):
            card = frame.get_by_text(re.compile("^Bot Soirée complète")).first
            card.wait_for(timeout=30000)
            p.shot("liste-dans-party")
            card.scroll_into_view_if_needed()
            card.tap()
            frame.get_by_role("button", name="Inviter", exact=True).wait_for(timeout=20000)
            p.shot("fiche-dans-party")
        with p.step("feuille Inviter dans la page Party, au doigt"):
            frame.get_by_role("button", name="Inviter", exact=True).tap()
            page.wait_for_timeout(1500)
            p.shot("feuille-dans-party")
            inner = page.frame(url=re.compile(r"/events/"))
            box = page.locator("#eventsFrame").bounding_box()
            sheet = frame.get_by_label(re.compile("^Inviter à ")).bounding_box()
            p.log(f"iframe {box} feuille {sheet}")
            y = min(sheet["y"] + sheet["height"] - 60, 700) if sheet else 650
            before = inner.evaluate(p.SCROLLERS_AT, [195, y - (box["y"] if box else 0)]) if inner else None
            for _ in range(3):  # geste au doigt sur la page Party (le doigt traverse l'iframe comme sur l'iPhone)
                cdp = p.ctx.new_cdp_session(page)
                cdp.send("Input.synthesizeScrollGesture", {"x": 195, "y": y, "yDistance": -400, "gestureSourceType": "touch", "speed": 1400})
                cdp.detach()
                page.wait_for_timeout(500)
            after = inner.evaluate(p.SCROLLERS_AT, [195, y - (box["y"] if box else 0)]) if inner else None
            p.log(f"dans l'iframe : {before} → {after}")
            p.shot("feuille-dans-party-bas")
            if before and after and [b["top"] for b in before] == [a["top"] for a in after] and any(b["top"] < b["room"] - 2 for b in before):
                p.flag("🔴", "feuille Inviter dans la page Party : ne défile pas au doigt", f"{before} → {after}")
    finally:
        p.close()
