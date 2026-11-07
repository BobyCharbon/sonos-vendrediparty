"""Campagne 2, agent 07 : annonces de groupe et notifications (base de TEST seulement, groupes « Bots » / « Bots 2 »).

Complète tests/bots/annonces.py : chaque point de la décision de l'admin du 06.11 (spec « annonces-groupe ») par les vrais
écrans (Playwright tactile 390×844), puis vérifié dans la base ; l'API REST avec le jeton des bots pour les contournements ;
chaque interrupteur de Réglages › Notifications (écran → colonne → private.web_push_allowed), pause et heures de silence.
Titres préfixés « [C2-07] ». Usage :
  BOTS_OUT=<dossier 07> .venv/bin/python -m tests.bots.annonces_c2 <phase…>   (phases : voir PHASES en bas)"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import traceback

import httpx
from playwright.sync_api import sync_playwright

from tests.bots.annonces import REQUEST_SENTENCE, announcement, told, uid
from tests.bots.bench import anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, TEST_URL, Session, q, sql
from tests.bots.flows import accept_terms_if_asked, audience_invite_groups, chip, day, fill, selected, set_date, submit, toggle

P = os.environ.get("C2_PREFIX", "[C2-07] ")  # relance : C2_PREFIX="[R-07] "
# Demandeur : Bot Oscar (simple membre de « Bots »). Bot Olga a bloqué Bot Gus (autre agent) : elle ne peut plus publier pour
# « Bots » (bug relevé au rapport). « Bots 2 » : Bot Valentin (membre).
ORG = "orga2"
ORG2 = "orga1"  # Bot Olga : son blocage de Bot Gus ne touche pas « Bots 2 »
OFF_SENTENCE = "Le groupe voit l’événement dans Party, sans notification."
DIRECT_SENTENCE = "Le groupe reçoit une notification dès la publication."


class Cached(Session):
    """Session d'un bot reprise du navigateur du banc (jeton rafraîchi), sans nouveau code SMS (base de TEST surchargée)."""

    def __init__(self, key: str):  # noqa: D107 — pas d'appel au constructeur parent (il redemande un code)
        from tests.bots.bench import OUT
        from tests.bots.common import publishable_key
        store = json.loads((OUT / key / "storage.json").read_text())
        raw = next(i["value"] for o in store["origins"] for i in o["localStorage"] if i["name"].endswith("-auth-token"))
        base = {"apikey": publishable_key(), "Content-Type": "application/json"}
        r = httpx.post(f"{TEST_URL}/auth/v1/token?grant_type=refresh_token", headers=base,
                       json={"refresh_token": json.loads(raw)["refresh_token"]}, timeout=90)
        data = r.json() if r.status_code == 200 else json.loads(raw)
        self.uid, self.token = data["user"]["id"], data["access_token"]
        self.headers = {**base, "Authorization": f"Bearer {self.token}"}

    def rpc(self, name: str, **args) -> httpx.Response:
        return httpx.post(f"{TEST_URL}/rest/v1/rpc/{name}", headers=self.headers, json=args, timeout=90)


def ids() -> dict:
    return dict(load_state().get("c2", {}))


def keep(key: str, eid: str) -> None:
    s = ids()
    s[key] = eid
    save_state(c2=s)


def group_id(name: str) -> str:
    return sql(f"select id from public.member_groups where name = {q(name)}")[0]["id"]


def requests_to(eid: str, key: str) -> int:
    return sql(f"""select count(*) n from public.notifications where user_id = {q(uid(key))} and kind = 'announce_request'
                   and data->>'target_event' = {q(eid)}""")[0]["n"]


def announcements(eid: str) -> list:
    return sql(f"""select (select name from public.member_groups where id = a.group_id) grp, a.status, a.sent_at is not null sent,
                   (select display_name from public.profiles where id = a.answered_by) answered_by
                   from public.event_announcements a where a.event_id = {q(eid)} order by 1""") or []


def report(bot: str, ok: bool, sev: str, title: str, detail) -> None:
    print(f"{'OK ' if ok else 'KO '} {title} : {detail}", flush=True)
    if not ok:
        anomaly(bot, sev, title, str(detail)[:600])


# ── Formulaire ───────────────────────────────────────────────────────────────────────────────────────────────────

def new_event(p, title: str, offset: int, *, groups=("Bots",), announce=False, public=False, check_toggle=True) -> str | None:
    """Formulaire « Proposer » : groupes (ou public / sur invitation sans groupe), « Prévenir le groupe », Publier."""
    page = p.page
    p.goto("/events/event/new")
    p.see(page.get_by_label("Titre", exact=True), "le formulaire", 30000)
    fill(p, "Titre", P + title)
    fill(p, "Description", "Événement de test des bots (campagne 2, agent 07, annonces). Ignorer.")
    set_date(p, "Début", day(offset), "19:30")
    fill(p, "Lieu", "Salle des bots, Vevey")
    sw = page.get_by_label("Prévenir le groupe", exact=True)
    if public:
        p.tap(page.get_by_role("button", name="Publique + lien"), "Publique + lien")
        page.wait_for_timeout(800)
        if sw.count():
            p.flag("🔴", "« Prévenir le groupe » proposé pour un événement public")
        return submit(p, "Publier")
    audience_invite_groups(p, list(groups))
    page.wait_for_timeout(800)
    if not groups:
        if sw.count():
            p.flag("🟠", "« Prévenir le groupe » proposé sans aucun groupe (sur invitation seulement)")
        return submit(p, "Publier")
    if not p.see(sw, "l'interrupteur « Prévenir le groupe »"):
        p.flag("🔴", "« Prévenir le groupe » absent pour un événement de groupe")
        return None
    if check_toggle:
        if sw.is_checked():
            p.flag("🔴", "« Prévenir le groupe » allumé par défaut")
        p.expect_or_flag(page.get_by_text(OFF_SENTENCE, exact=True), "la phrase « sans notification » (éteint)", "🟡")
    if announce:
        toggle(p, "Prévenir le groupe", True)
        page.wait_for_timeout(600)
    p.shot(f"formulaire-{'annonce' if announce else 'sans-annonce'}")
    return submit(p, "Publier")


def phase_formulaire(browser, origin, only):
    """Olga (simple membre de « Bots ») : public sans interrupteur, sur invitation sans groupe, puis six événements de groupe."""
    s = ids()
    p = phone(browser, ORG, origin, "c2-formulaire")
    try:
        p.sign_in()
        accept_terms_if_asked(p)
        # Aller-retour de l'interrupteur et ses phrases, puis public (il disparaît), puis groupe (il revient éteint ?).
        with p.step("aller-retour de « Prévenir le groupe »"):
            page = p.page
            p.goto("/events/event/new")
            p.see(page.get_by_label("Titre", exact=True), "le formulaire", 30000)
            audience_invite_groups(p, ["Bots"])
            toggle(p, "Prévenir le groupe", True)
            p.expect_or_flag(page.get_by_text(REQUEST_SENTENCE, exact=True), "phrase « Ta demande sera envoyée… » (Olga, Bots)", "🔴")
            p.shot("interrupteur-allume")
            toggle(p, "Prévenir le groupe", False)
            p.expect_or_flag(page.get_by_text(OFF_SENTENCE, exact=True), "phrase « sans notification » après extinction", "🟡")
            toggle(p, "Prévenir le groupe", True)
            p.tap(page.get_by_role("button", name="Publique + lien"), "Publique + lien (interrupteur allumé)")
            page.wait_for_timeout(800)
            if page.get_by_label("Prévenir le groupe", exact=True).count():
                p.flag("🔴", "public : « Prévenir le groupe » encore là")
            p.shot("public-sans-interrupteur")
            audience_invite_groups(p, ["Bots"])
            page.wait_for_timeout(800)
            sw = page.get_by_label("Prévenir le groupe", exact=True)
            p.log(f"retour à « Bots » : interrupteur {'allumé' if sw.count() and sw.is_checked() else 'éteint'}")
            p.shot("retour-groupe")
        plan = [("accept", "Annonce acceptée", 30, True), ("race", "Deux valideurs en même temps", 31, True),
                ("refuse", "Annonce refusée", 32, True), ("silence", "Sans réponse 48 h", 33, True),
                ("late", "Prévenir depuis la fiche", 34, False), ("sheet", "Prévenir depuis Inviter", 35, False),
                ("onoff", "Interrupteur coupé puis rallumé", 36, True), ("prefs", "Interrupteur Annonce à valider", 37, False)]
        for key, title, offset, announce in plan:
            if key in s:
                continue
            with p.step(f"créer « {title} »"):
                eid = new_event(p, title, offset, announce=announce)
                if eid:
                    keep(key, eid)
                    s[key] = eid
                    p.page.wait_for_timeout(1500)
                    want = "Annonce en attente" if announce else None
                    if want:
                        p.expect_or_flag(p.page.get_by_text(want, exact=False).first, f"« {want} » sur la fiche ({title})", "🔴")
                    p.shot(f"fiche-{key}")
        if "public" not in s:
            with p.step("créer un public"):
                eid = new_event(p, "Public sans annonce", 38, public=True)
                if eid:
                    keep("public", eid)
        if "invite_only" not in s:
            with p.step("créer « sur invitation » sans groupe"):
                eid = new_event(p, "Sur invitation sans groupe", 39, groups=())
                if eid:
                    keep("invite_only", eid)
    finally:
        p.close()
    s = ids()
    for key in ("accept", "race", "refuse", "silence", "onoff"):
        if key in s:
            a = announcements(s[key])
            ok = [x["status"] for x in a] == ["pending"] and told(s[key], "vip1", "private_invite") == 0
            report(ORG, ok, "🔴", f"demande ouverte, membres non prévenus ({key})", a)
            n_ada, n_come = requests_to(s[key], "admin"), requests_to(s[key], "coadmin")
            report(ORG, n_ada == 1 and n_come == 1, "🔴", f"Ada et Côme reçoivent « Annonce à valider » ({key})", (n_ada, n_come))
    for key in ("late", "sheet", "prefs", "public"):
        if key in s:
            report(ORG, not announcements(s[key]), "🔴", f"aucune annonce sans l'interrupteur ({key})", announcements(s[key]))


# ── Réponses ─────────────────────────────────────────────────────────────────────────────────────────────────────

def card_of(p, title: str, group: str = "Bots", kind: str = "Annonce"):
    return p.page.get_by_label(f"{kind} à valider : {P}{title}, pour {group}")


def phase_reponses(browser, origin, only):
    s = ids()
    steps = set(os.environ.get("C2_STEPS", "1,2,3,4,5").split(","))
    if "1" in steps:
        # 1. Ada accepte.
        a = phone(browser, "admin", origin, "c2-accepte")
        try:
            a.sign_in()
            a.goto("/events/activity")
            accept_terms_if_asked(a)
            card = card_of(a, "Annonce acceptée")
            if a.expect_or_flag(card, "carte « Annonce à valider » (acceptée)", "🔴", 20000):
                a.expect_or_flag(card.get_by_text("Notification envoyée aux 10 membres :", exact=True), "« Notification envoyée aux 10 membres »", "🟡")
                a.expect_or_flag(card.get_by_text("Sans réponse, l’annonce part d’office", exact=False), "« part d’office … » sur la carte", "🟡")
                a.shot("carte")
                a.tap(card.get_by_role("button", name="Accepter"), "Accepter")
                a.page.wait_for_timeout(2500)
                a.expect_or_flag(a.page.get_by_text("C’est parti : Bots est prévenu.", exact=True), "« C’est parti : Bots est prévenu. »", "🟠")
                a.shot("acceptee")
                # Rechargement : la carte ne revient pas.
                a.page.reload()
                a.page.wait_for_timeout(3000)
                if card_of(a, "Annonce acceptée").count():
                    a.flag("🔴", "la carte acceptée revient après rechargement")
        finally:
            a.close()
        if "accept" in s:
            report("admin", [x["status"] for x in announcements(s["accept"])] == ["accepted"], "🔴", "acceptée en base", announcements(s["accept"]))

    if "2" in steps:
        # 2. Première réponse gagne : Ada et Côme ont la carte ouverte ; Ada accepte, puis Côme refuse sur sa carte périmée.
        a = phone(browser, "admin", origin, "c2-course-ada")
        c = phone(browser, "coadmin", origin, "c2-course-come")
        try:
            for x in (a, c):
                x.sign_in()
                x.goto("/events/activity")
                accept_terms_if_asked(x)
            ca, cc = card_of(a, "Deux valideurs en même temps"), card_of(c, "Deux valideurs en même temps")
            if a.expect_or_flag(ca, "carte (course, Ada)", "🔴", 20000) and c.expect_or_flag(cc, "carte (course, Côme)", "🔴", 20000):
                a.tap(ca.get_by_role("button", name="Accepter"), "Accepter (Ada, la première)")
                a.page.wait_for_timeout(2000)
                c.tap(cc.get_by_role("button", name="Refuser"), "Refuser (Côme, carte périmée)")
                c.page.wait_for_timeout(2500)
                c.expect_or_flag(c.page.get_by_text("Bot Ada a déjà répondu : rien n’a changé.", exact=True), "« Bot Ada a déjà répondu : rien n’a changé. »", "🟠")
                c.shot("deja-repondu")
        finally:
            a.close()
            c.close()
        if "race" in s:
            st = announcements(s["race"])
            report("coadmin", [x["status"] for x in st] == ["accepted"] and st[0]["answered_by"] == "Bot Ada", "🔴", "première réponse gagne (écran)", st)
            report(ORG, told(s["race"], ORG, "announce_refused") == 0, "🔴", "Olga ne reçoit pas de refus après l'acceptation", told(s["race"], ORG, "announce_refused"))

    if "3" in steps:
        # 3. Côme refuse.
        c = phone(browser, "coadmin", origin, "c2-refuse")
        try:
            c.sign_in()
            c.goto("/events/activity")
            card = card_of(c, "Annonce refusée")
            if c.expect_or_flag(card, "carte (refus)", "🔴", 45000):
                c.tap(card.get_by_role("button", name="Refuser"), "Refuser")
                c.page.wait_for_timeout(2500)
                c.expect_or_flag(c.page.get_by_text("Refusé : Bots n’est pas prévenu, l’événement reste visible.", exact=True), "phrase du refus", "🟠")
                c.shot("refusee")
        finally:
            c.close()
        if "refuse" in s:
            st = announcements(s["refuse"])
            report("coadmin", [x["status"] for x in st] == ["refused"], "🔴", "refusée en base", st)
            report("vip1", told(s["refuse"], "vip1", "private_invite") == 0, "🔴", "refusée : Victor non prévenu", told(s["refuse"], "vip1", "private_invite"))

    if "4" in steps:
        # 4. 48 h sans réponse (date reculée dans la base de TEST, puis la tâche planifiée).
        if "silence" in s:
            sql(f"update public.event_announcements set requested_at = now() - interval '49 hours' where event_id = {q(s['silence'])} and status = 'pending'")
            n = sql("select private.auto_accept_announcements() n")[0]["n"]
            st = announcements(s["silence"])
            report("banc", [x["status"] for x in st] == ["auto"] and st[0]["sent"], "🔴", f"48 h : partie d'office (tâche : {n})", st)
            # Une carte périmée après 48 h : la réponse tardive ne change rien.
            sess = Cached("coadmin")
            aid = sql(f"select id from public.event_announcements where event_id = {q(s['silence'])}")[0]["id"]
            r = sess.rpc("answer_announcement", a=aid, accept=False)
            report("coadmin", r.status_code == 200 and r.json().get("already"), "🔴", "réponse après 48 h : déjà partie", r.text[:200])
            job = sql("select schedule, active from cron.job where jobname = 'group-announcements-auto'")
            report("banc", bool(job) and job[0]["active"], "🔴", "tâche planifiée 48 h présente et active", job)

    if "5" in steps:
        # 5. Ce que reçoivent Olga et Victor ; fiche de l'organisatrice.
        expected = {"accept": ("acceptée par Bot Ada", 1, "announce_accepted"), "race": ("refusée par Bot Côme", 0, "announce_refused"),
                    "refuse": ("Annonce refusée par Bot Côme", 0, "announce_refused"), "silence": ("sans réponse en 48 h", 1, "announce_accepted")}
        o = phone(browser, ORG, origin, "c2-statuts")
        try:
            o.sign_in()
            for key, (status, invites, kind) in expected.items():
                if key not in s:
                    continue
                o.goto(f"/events/event/{s[key]}")
                o.expect_or_flag(o.page.get_by_text(status, exact=False).first, f"« {status} » sur la fiche ({key})", "🔴", 45000)
                o.shot(f"statut-{key}")
                got, mine = told(s[key], "vip1", "private_invite"), told(s[key], ORG, kind)
                report(ORG, got == invites and mine == 1, "🔴", f"notifications ({key}) Victor={invites} Olga {kind}=1", (got, mine))
            o.goto("/events/activity")
            for text in ("Ton annonce a été acceptée", "Ton annonce a été refusée", "Ton annonce est partie"):
                o.expect_or_flag(o.page.get_by_text(text, exact=True).first, f"« {text} » dans Activité", "🟠")
            o.shot("activite")
        finally:
            o.close()
        v = phone(browser, "vip1", origin, "c2-membre")
        try:
            v.sign_in()
            if "refuse" in s:
                v.goto(f"/events/event/{s['refuse']}")
                v.expect_or_flag(v.page.get_by_text(P + "Annonce refusée", exact=True).first, "refusée : l'événement reste visible du groupe", "🔴")
                v.shot("refusee-visible")
            v.goto("/events/activity")
            v.shot("activite")
            if "accept" in s:
                v.expect_or_flag(v.page.get_by_text(f"On t’invite à « {P}Annonce acceptée » avec le groupe Bots.", exact=True).first, "Victor : invitation dans Activité", "🟠")
        finally:
            v.close()


# ── Après la publication : fiche, feuille Inviter, interrupteur coupé ─────────────────────────────────────────────

def phase_apres(browser, origin, only):
    s = ids()
    o = phone(browser, ORG, origin, "c2-apres")
    page = o.page
    try:
        o.sign_in()
        if "late" in s:
            with o.step("fiche : allumer « Prévenir le groupe » après la publication"):
                o.goto(f"/events/event/{s['late']}")
                card = page.get_by_text("Annonce au groupe", exact=True)
                if o.expect_or_flag(card, "carte « Annonce au groupe » sur la fiche", "🔴", 20000):
                    o.shot("carte-annonce")
                    toggle(o, "Prévenir le groupe", True)
                    page.wait_for_timeout(2500)
                    o.expect_or_flag(page.get_by_text("Annonce en attente", exact=False).first, "« Annonce en attente » après l'allumage", "🔴")
                    o.shot("fiche-apres")
            st = announcements(s["late"])
            report(ORG, [x["status"] for x in st] == ["pending"] and requests_to(s["late"], "admin") == 1, "🔴", "fiche : demande ouverte", st)
        if "sheet" in s:
            with o.step("feuille Inviter : ajouter « Bots 2 » avec « Prévenir le groupe »"):
                o.goto(f"/events/event/{s['sheet']}")
                o.tap(page.get_by_role("button", name="Inviter", exact=True), "Inviter")
                sheet = page.get_by_label(re.compile("^Inviter à "))
                o.see(sheet, "la feuille Inviter", 10000)
                field = sheet.get_by_label("Chercher une personne ou un groupe")
                o.type(field, "Bots 2", "recherche")
                page.wait_for_timeout(1200)
                add = sheet.get_by_role("button", name=re.compile("^Ajouter Bots 2"))
                o.tap(add.first, "Ajouter Bots 2")
                page.wait_for_timeout(800)
                sw = sheet.get_by_label("Prévenir le groupe", exact=True)
                if o.expect_or_flag(sw, "« Prévenir le groupe » dans la feuille", "🔴"):
                    if sw.is_checked():
                        o.flag("🔴", "feuille Inviter : « Prévenir le groupe » allumé par défaut")
                    o.tap(sw, "Prévenir le groupe → oui")
                    page.wait_for_timeout(800)
                    o.shot("feuille-annonce")
                    o.tap(sheet.get_by_role("button", name=re.compile("^Inviter ")).first, "Inviter (Bots 2)")
                    page.wait_for_timeout(3000)
                    o.shot("feuille-apres")
            st = announcements(s["sheet"])
            print("feuille Inviter →", st, flush=True)
            report(ORG, [x["grp"] for x in st] == ["Bots 2"], "🟠",
                   "feuille Inviter : seule « Bots 2 » (ajoutée ici) est annoncée, pas « Bots » (déjà là, sans annonce)", st)
        if "onoff" in s:
            with o.step("modifier : couper puis rallumer « Prévenir le groupe »"):
                for on in (False, True):
                    o.goto(f"/events/event/{s['onoff']}/edit")
                    o.see(page.get_by_label("Titre", exact=True), "le formulaire de modification", 20000)
                    toggle(o, "Prévenir le groupe", on)
                    o.shot(f"modifier-{'on' if on else 'off'}")
                    save = page.get_by_role("button", name=re.compile("^Enregistrer")).last
                    o.tap(save, "Enregistrer")
                    page.wait_for_timeout(3000)
                    accept_terms_if_asked(o)
                    if not on:
                        report(ORG, not announcements(s["onoff"]), "🔴", "coupé : la demande en attente tombe", announcements(s["onoff"]))
            st = announcements(s["onoff"])
            n = requests_to(s["onoff"], "admin")
            report(ORG, [x["status"] for x in st] == ["pending"], "🔴", "rallumé : nouvelle demande", st)
            report("admin", n <= 1, "🟡", "couper / rallumer « Prévenir le groupe » renvoie « Annonce à valider » aux valideurs à chaque fois", f"Ada a {n} demandes")
    finally:
        o.close()


# ── Envoi direct (créatrice du groupe), IA étape 2 ────────────────────────────────────────────────────────────────

def phase_direct(browser, origin, only):
    s = ids()
    if "direct" not in s:
        a = phone(browser, "admin", origin, "c2-direct")
        try:
            a.sign_in()
            page = a.page
            page.goto(origin + "/events/event/new")
            a.see(page.get_by_label("Titre", exact=True), "le formulaire", 30000)
            audience_invite_groups(a, ["Bots"])
            toggle(a, "Prévenir le groupe", True)
            a.expect_or_flag(page.get_by_text(DIRECT_SENTENCE, exact=True), "phrase « dès la publication » (créatrice du groupe)", "🟠")
            eid = new_event(a, "Envoi direct (créatrice)", 40, announce=True)
            if eid:
                keep("direct", eid)
                a.expect_or_flag(a.page.get_by_text("Bots · Annonce envoyée", exact=True).first, "« Bots · Annonce envoyée » (direct)", "🟠")
                a.shot("fiche-direct")
        finally:
            a.close()
    s = ids()
    if "direct" in s:
        st = announcements(s["direct"])
        report("admin", [x["status"] for x in st] == ["direct"] and st[0]["sent"], "🔴", "créatrice du groupe : envoi direct", st)
        report("admin", told(s["direct"], "vip1", "private_invite") == 1, "🔴", "direct : Victor prévenu", told(s["direct"], "vip1", "private_invite"))
        n = sql(f"select count(*) n from public.notifications where kind = 'announce_request' and data->>'target_event' = {q(s['direct'])}")[0]["n"]
        report("admin", n == 0, "🔴", "direct : aucune demande à valider", n)


def phase_ia(browser, origin, only):
    """Oscar (membre de « Bots », pas admin du groupe) : brouillon IA, étape 2 « Un groupe » + « Prévenir le groupe »."""
    from tests.bots.scenario import ai_save_draft
    s = ids()
    if "ia" not in s:
        sess = Session(BY_KEY["orga2"].phone)
        httpx.post(f"{origin}/api/account/ai/consent", json={"token": sess.token, "accept": True}, timeout=90)
        out = ai_save_draft(sess.token, origin, P + "IA étape 2 avec annonce", 41)
        print("brouillon IA", out, flush=True)
        if out["status"] != 200:
            anomaly("orga2", "🔴", "IA : brouillon refusé", str(out)[:400])
            return
        keep("ia", out["body"]["id"])
        s = ids()
    eid = s["ia"]
    p = phone(browser, "orga2", origin, "c2-ia")
    page = p.page
    try:
        p.sign_in()
        p.goto(f"/events/event/{eid}/invite")
        p.page.wait_for_timeout(3000)
        accept_terms_if_asked(p)
        p.tap(page.get_by_role("button", name="👥 Un groupe", exact=True), "👥 Un groupe")
        page.wait_for_timeout(800)
        if not selected(chip(p, "Bots · ").first):
            p.tap(chip(p, "Bots · ").first, "groupe Bots")
        all_sw = page.get_by_label(re.compile("^Prévenir "))
        p.log(f"interrupteurs « Prévenir … » à l'étape 2 : {all_sw.count()} "
              f"{[all_sw.nth(i).get_attribute('aria-label') for i in range(all_sw.count())]}")
        old = page.get_by_label("Prévenir le groupe", exact=True).count()
        if old:
            p.flag("🟡", f"IA étape 2 : encore {old} interrupteur(s) au libellé ambigu « Prévenir le groupe »")
        sw = page.get_by_label("Prévenir « Bots »", exact=True)
        if p.expect_or_flag(sw, "« Prévenir le groupe » à l'étape 2 de l'IA", "🔴"):
            if sw.is_checked():
                p.flag("🔴", "IA étape 2 : « Prévenir le groupe » allumé par défaut")
            p.tap(sw, "Prévenir le groupe (carte Un groupe) → oui")
            page.wait_for_timeout(800)
            states = [all_sw.nth(i).is_checked() for i in range(all_sw.count())]
            p.log(f"états des interrupteurs : {states}")
            if sum(states) != 1:
                p.flag("🟡", f"IA étape 2 : allumer « Prévenir « Bots » » change aussi l'autre interrupteur ({states})")
            p.expect_or_flag(page.get_by_text(REQUEST_SENTENCE, exact=True).last, "IA : phrase « Ta demande sera envoyée… »", "🟠")
        # Public : l'interrupteur disparaît.
        pub = page.get_by_role("button", name=re.compile("^🌍"))
        p.shot("etape2-annonce")
        p.dump("etape2-annonce")
        p.tap(page.get_by_role("button", name="Publier pour « Bots »"), "Publier pour « Bots »")
        page.wait_for_timeout(4000)
        p.shot("apres-publication")
        if pub.count():
            p.log("bouton public présent à l'étape 2")
    finally:
        p.close()
    st = announcements(eid)
    report("orga2", [x["status"] for x in st] == ["pending"], "🔴", "IA étape 2 : demande d'annonce ouverte", st)
    report("orga2", requests_to(eid, "admin") == 1, "🔴", "IA étape 2 : Ada prévenue de la demande", requests_to(eid, "admin"))


# ── Réglages du groupe « Bots 2 » ─────────────────────────────────────────────────────────────────────────────────

def set_rules_ui(p, group: str, approval: str, mode: str) -> None:
    page = p.page
    p.goto("/events/groups")
    p.page.wait_for_timeout(2500)
    card = page.get_by_text(group, exact=True).first
    p.see(card, f"le groupe {group}", 60000)
    # Jamais le panneau de Vendredi Party (vrais membres) : la plus petite carte qui contient le nom du groupe ET « Modifier ».
    cards = page.locator("div").filter(has=page.get_by_text(group, exact=True)).filter(
        has=page.get_by_role("button", name=re.compile("^(Modifier|Fermer)$")))
    own_card = cards.last
    if own_card.get_by_role("button", name="Modifier", exact=True).count():
        p.tap(own_card.get_by_role("button", name="Modifier", exact=True), f"Modifier ({group})")
        page.wait_for_timeout(1500)
    cards = page.locator("div").filter(has=page.get_by_text(group, exact=True)).filter(
        has=page.get_by_label("Réglages des événements du groupe"))
    rules = cards.last.get_by_label("Réglages des événements du groupe").filter(has_text="Les membres créent")
    if rules.count() != 1 or not p.see(rules, "réglages des événements du groupe", 8000):
        p.flag("🔴", f"réglages des événements du groupe {group} introuvables")
        return
    for label in (approval, mode):
        b = rules.get_by_role("tab", name=label, exact=True)
        if b.first.get_attribute("aria-selected") == "true":
            p.log(f"« {label} » déjà choisi")
            continue
        p.tap(b.first, label, timeout=40000)
        page.wait_for_timeout(5000)
    p.shot(f"regles-{approval}-{mode}".replace(" ", "-"))


def phase_regles(browser, origin, only):
    s = ids()
    gid = group_id("Bots 2")
    was = {"events_need_approval": False, "announce_mode": "request"}  # état d'origine relevé au début de la campagne
    try:
        # Olga (membre, pas créatrice) ne voit pas les réglages et ne peut pas les changer par l'API.
        o = phone(browser, ORG, origin, "c2-regles-olga")
        try:
            o.sign_in()
            o.goto("/events/groups")
            o.page.wait_for_timeout(3000)
            if o.page.get_by_label("Réglages des événements du groupe").count():
                o.flag("🔴", "Olga (simple membre) voit les réglages des événements d'un groupe")
            o.shot("groupes-olga")
        finally:
            o.close()
        r = Cached(ORG).rpc("set_group_event_rules", grp=gid, need_approval=True, mode="free")
        report(ORG, r.status_code >= 400, "🔴", "Olga ne change pas les réglages de « Bots 2 » (API)", f"{r.status_code} {r.text[:160]}")

        # Ada (créatrice) : avec validation + sur demande, par l'écran.
        a = phone(browser, "admin", origin, "c2-regles-ada")
        try:
            a.sign_in()
            set_rules_ui(a, "Bots 2", "Avec validation", "Sur demande")
        finally:
            a.close()
        now = sql(f"select events_need_approval, announce_mode from public.member_groups where id = {q(gid)}")[0]
        report("admin", now == {"events_need_approval": True, "announce_mode": "request"}, "🔴", "réglages enregistrés (avec validation, sur demande)", now)

        o = phone(browser, ORG2, origin, "c2-regles-propose")
        try:
            o.sign_in()
            for key, title, off in (("prop_ok", "Bots 2 à valider (accepté)", 42), ("prop_no", "Bots 2 à valider (refusé)", 43)):
                if key in s:
                    continue
                eid = new_event(o, title, off, groups=("Bots 2",), announce=True)
                if eid:
                    keep(key, eid)
                    o.expect_or_flag(o.page.get_by_text("En attente de validation du groupe", exact=False).first, f"« En attente de validation du groupe » ({key})", "🟠")
                    o.shot(f"fiche-{key}")
        finally:
            o.close()
        s = ids()
        for key in ("prop_ok", "prop_no"):
            if key in s:
                st = sql(f"select status from public.event_groups where event_id = {q(s[key])}")
                inv = sql(f"select count(*) n from public.event_invites where event_id = {q(s[key])} and user_id = {q(uid('vip4'))}")[0]["n"]
                gr = sql(f"select count(*) n from public.notifications where kind = 'group_event_request' and data->>'target_event' = {q(s[key])} and user_id = {q(uid('admin'))}")[0]["n"]
                report(ORG2, st == [{"status": "pending"}] and inv == 0 and gr == 1, "🔴",
                       f"proposé à « Bots 2 » : en attente, invisible pour Violette, Ada prévenue ({key})", (st, inv, gr))
        a = phone(browser, "admin", origin, "c2-regles-valide")
        try:
            a.sign_in()
            a.goto("/events/activity")
            for key, accept in (("prop_ok", True), ("prop_no", False)):
                title = "Bots 2 à valider (accepté)" if accept else "Bots 2 à valider (refusé)"
                card = card_of(a, title, "Bots 2", "Événement")
                if a.expect_or_flag(card, f"carte « Événement à valider » ({key})", "🔴", 20000):
                    a.shot(f"carte-{key}")
                    a.dump(f"carte-{key}")
                    a.tap(card.get_by_role("button", name="Accepter" if accept else "Refuser"), "Accepter" if accept else "Refuser")
                    a.page.wait_for_timeout(2500)
                    a.shot(f"repondu-{key}")
        finally:
            a.close()
        if "prop_ok" in s:
            e = s["prop_ok"]
            st, ann = sql(f"select status from public.event_groups where event_id = {q(e)}"), announcements(e)
            report("admin", st == [{"status": "approved"}] and [x["status"] for x in ann] == ["accepted"] and told(e, "vip4", "private_invite") == 1,
                   "🔴", "accepter l'événement accepte aussi l'annonce (Violette prévenue une fois)", (st, ann, told(e, "vip4", "private_invite")))
            report(ORG2, told(e, ORG2, "group_event_accepted") == 1, "🟠", "Olga : « Événement accepté par le groupe »", told(e, ORG2, "group_event_accepted"))
        if "prop_no" in s:
            e = s["prop_no"]
            st, ann = sql(f"select status from public.event_groups where event_id = {q(e)}"), announcements(e)
            inv = sql(f"select count(*) n from public.event_invites where event_id = {q(e)} and user_id = {q(uid('vip4'))}")[0]["n"]
            report("admin", st == [{"status": "refused"}] and not ann and told(e, "vip4", "private_invite") == 0 and inv == 0,
                   "🔴", "refuser l'événement : rien n'est envoyé, invisible", (st, ann, inv))
            report(ORG2, told(e, ORG2, "group_event_refused") == 1, "🟠", "Olga : « Événement refusé par le groupe »", told(e, ORG2, "group_event_refused"))

        # Ada : sans validation + libres → Olga prévient directement.
        a = phone(browser, "admin", origin, "c2-regles-libres")
        try:
            a.sign_in()
            set_rules_ui(a, "Bots 2", "Sans validation", "Libres")
        finally:
            a.close()
        now = sql(f"select events_need_approval, announce_mode from public.member_groups where id = {q(gid)}")[0]
        report("admin", now == {"events_need_approval": False, "announce_mode": "free"}, "🔴", "réglages enregistrés (sans validation, libres)", now)
        if "free" not in s:
            o = phone(browser, ORG2, origin, "c2-regles-libre-olga")
            try:
                o.sign_in()
                o.goto("/events/event/new")
                o.see(o.page.get_by_label("Titre", exact=True), "le formulaire", 30000)
                audience_invite_groups(o, ["Bots 2"])
                toggle(o, "Prévenir le groupe", True)
                o.expect_or_flag(o.page.get_by_text(DIRECT_SENTENCE, exact=True), "groupe « libre » : phrase « dès la publication »", "🟠")
                eid = new_event(o, "Bots 2 notifications libres", 44, groups=("Bots 2",), announce=True)
                if eid:
                    keep("free", eid)
            finally:
                o.close()
        s = ids()
        if "free" in s:
            st = announcements(s["free"])
            report(ORG2, [x["status"] for x in st] == ["direct"] and told(s["free"], "vip4", "private_invite") == 1, "🔴",
                   "groupe « libre » : Olga prévient directement", (st, told(s["free"], "vip4", "private_invite")))
        # Côme (Co-admin du site, pas créateur de « Bots 2 ») : la spécification dit « décidés par le créateur du groupe ».
        r = Cached("coadmin").rpc("set_group_event_rules", grp=gid, need_approval=False, mode="free")
        print(f"Côme (Co-admin, pas créateur) set_group_event_rules : {r.status_code} {r.text[:120]}", flush=True)
    finally:
        sql(f"update public.member_groups set events_need_approval = {str(was['events_need_approval']).lower()}, "
            f"announce_mode = {q(was['announce_mode'])} where id = {q(gid)}")
        print("Bots 2 remis :", sql(f"select events_need_approval, announce_mode from public.member_groups where id = {q(gid)}"), flush=True)


# ── Contournements (API REST avec le jeton des bots) ───────────────────────────────────────────────────────────────

def phase_contournements(browser, origin, only):
    s = ids()
    olga, victor = Cached(ORG), Cached("vip1")
    H = lambda sess: {**sess.headers, "Prefer": "return=representation"}
    bots = group_id("Bots")
    out = []
    # 1. Public : announce_group forcé par l'API → aucune annonce.
    if "public" in s:
        r = httpx.patch(f"{TEST_URL}/rest/v1/events?id=eq.{s['public']}", headers=H(olga), json={"announce_group": True}, timeout=90)
        out.append(("public : announce_group forcé", r.status_code, r.text[:120]))
        report(ORG, not announcements(s["public"]), "🔴", "public : jamais d'annonce, même forcée par l'API", announcements(s["public"]))
    # 2. Olga écrit elle-même une annonce « direct » (contourner la validation).
    if "prefs" in s:
        r = httpx.post(f"{TEST_URL}/rest/v1/event_announcements", headers=H(olga),
                       json={"event_id": s["prefs"], "group_id": bots, "status": "direct"}, timeout=90)
        report(ORG, r.status_code >= 400 and not announcements(s["prefs"]), "🔴", "Olga ne crée pas d'annonce « direct » (API)", f"{r.status_code} {r.text[:160]}")
    # 3. Olga passe sa demande en attente à « accepted ».
    if "onoff" in s:
        r = httpx.patch(f"{TEST_URL}/rest/v1/event_announcements?event_id=eq.{s['onoff']}", headers=H(olga), json={"status": "accepted"}, timeout=90)
        report(ORG, [x["status"] for x in announcements(s["onoff"])] == ["pending"], "🔴", "Olga ne valide pas sa propre demande (UPDATE)", f"{r.status_code} {r.text[:160]}")
        aid = sql(f"select id from public.event_announcements where event_id = {q(s['onoff'])}")[0]["id"]
        r = olga.rpc("answer_announcement", a=aid, accept=True)
        report(ORG, r.status_code >= 400, "🔴", "Olga ne répond pas à sa propre demande (RPC)", f"{r.status_code} {r.text[:160]}")
        r = victor.rpc("answer_announcement", a=aid, accept=True)
        report("vip1", r.status_code >= 400, "🔴", "Victor (membre) ne répond pas à une demande (RPC)", f"{r.status_code} {r.text[:160]}")
        r = httpx.get(f"{TEST_URL}/rest/v1/event_announcements?event_id=eq.{s['onoff']}", headers=victor.headers, timeout=90)
        report("vip1", r.status_code == 200 and r.json() == [], "🟠", "Victor ne lit pas les demandes d'annonce", r.text[:160])
        r = victor.rpc("my_group_requests")
        report("vip1", r.status_code == 200 and r.json() == [], "🟠", "Victor : my_group_requests vide", r.text[:160])
    # 4. Olga change les réglages de « Bots » par la table (garde).
    was = sql(f"select events_need_approval, announce_mode from public.member_groups where id = {q(bots)}")[0]
    r = httpx.patch(f"{TEST_URL}/rest/v1/member_groups?id=eq.{bots}", headers=H(olga), json={"announce_mode": "free"}, timeout=90)
    now = sql(f"select events_need_approval, announce_mode from public.member_groups where id = {q(bots)}")[0]
    report(ORG, now == was, "🔴", "Olga ne passe pas « Bots » en notifications libres (table)", f"{r.status_code} {now}")
    if now != was:
        sql(f"update public.member_groups set announce_mode = {q(was['announce_mode'])} where id = {q(bots)}")
    # 5. Olga met une annonce directe en allumant announce_group sur un événement d'un autre (Oscar) : refus.
    # 6. Annonce « Vendredi Party » demandée par Olga ? (vip) : non testé ici (vrais membres).
    print(json.dumps(out, ensure_ascii=False), flush=True)


# ── Interrupteurs « Annonce à valider » / « Réponse du groupe » ───────────────────────────────────────────────────

def pref(key: str, col: str):
    return sql(f"select {col} v from public.notification_prefs where user_id = {q(uid(key))}")[0]["v"]


def set_pref_ui(p, label: str, on: bool, col: str) -> bool:
    p.goto("/events/settings/notifications")
    p.see(p.page.get_by_label(label, exact=True), f"l'interrupteur « {label} »", 20000)
    toggle(p, label, on)
    p.page.wait_for_timeout(2000)
    return pref(p.bot.key, col) == on


def phase_interrupteurs_annonce(browser, origin, only):
    """Ada coupe « Annonce à valider » : Olga demande → Ada n'est pas prévenue (Côme oui). Olga coupe « Réponse du groupe »
    → Côme refuse → Olga n'est pas prévenue. Puis tout est rallumé."""
    s = ids()
    a = phone(browser, "admin", origin, "c2-pref-ada")
    try:
        a.sign_in()
        report("admin", set_pref_ui(a, "Annonce à valider", False, "announce_requests"), "🔴", "« Annonce à valider » éteint → colonne", pref("admin", "announce_requests"))
        a.shot("annonce-a-valider-off")
    finally:
        a.close()
    o = phone(browser, ORG, origin, "c2-pref-olga")
    try:
        o.sign_in()
        report(ORG, set_pref_ui(o, "Réponse du groupe à mes demandes", False, "announce_results"), "🔴", "« Réponse du groupe » éteint → colonne", pref(ORG, "announce_results"))
        if "prefs" in s:
            o.goto(f"/events/event/{s['prefs']}")
            toggle(o, "Prévenir le groupe", True)
            o.page.wait_for_timeout(2500)
            o.shot("demande-prefs")
    finally:
        o.close()
    if "prefs" in s:
        e = s["prefs"]
        report("admin", requests_to(e, "admin") == 0 and requests_to(e, "coadmin") == 1, "🔴",
               "Ada (interrupteur éteint) non prévenue, Côme prévenu", (requests_to(e, "admin"), requests_to(e, "coadmin")))
        aid = sql(f"select id from public.event_announcements where event_id = {q(e)}")[0]["id"]
        r = Cached("coadmin").rpc("answer_announcement", a=aid, accept=False)
        report(ORG, r.status_code == 200 and told(e, ORG, "announce_refused") == 0, "🔴", "Olga (interrupteur éteint) : pas de « refusée »",
               (r.status_code, told(e, ORG, "announce_refused")))
    # Rallumer par l'écran.
    for key, label, col in (("admin", "Annonce à valider", "announce_requests"), (ORG, "Réponse du groupe à mes demandes", "announce_results")):
        p = phone(browser, key, origin, "c2-pref-rallume")
        try:
            p.sign_in()
            report(key, set_pref_ui(p, label, True, col), "🔴", f"« {label} » rallumé", pref(key, col))
        finally:
            p.close()


# ── Tous les interrupteurs de Réglages › Notifications (écran → colonne → web_push_allowed) ─────────────────────────

LABELS = {  # libellé de l'écran → colonne de notification_prefs, kind de notification
    "Recevoir mes alertes": ("push_enabled", None),
    "Événement modifié ou annulé": ("event_changed", "event_changed"),
    "Nouveau sondage": ("poll_new", "poll_new"),
    "Date choisie": ("date_fixed", "date_fixed"),
    "Un organisateur répond pour moi": ("rsvp_set", "rsvp_set"),
    "Invitation à un événement privé": ("invites", "private_invite"),
    "Rappel pour voter": ("poll_nudge", "poll_nudge"),
    "Place libérée": ("waitlist", "waitlist"),
    "Paiement de ma place confirmé": ("ticket_pay_confirmed", "ticket_pay_confirmed"),
    "Billet prêt": ("ticket_issued", "ticket_issued"),
    "Réponses à mes événements": ("rsvp_mine", "rsvp"),
    "Quelqu’un rejoint par le lien": ("link_join", "link_join"),
    "Quelqu’un dit avoir payé": ("ticket_pay_declared", "ticket_pay_declared"),
    "Ma proposition validée ou refusée": ("proposal_result", "approved"),
    "Réponse du groupe à mes demandes": ("announce_results", "announce_accepted"),
    "Annonce à valider": ("announce_requests", "announce_request"),
    "Événement à valider pour mon groupe": ("group_event_requests", "group_event_request"),
    "Proposition à valider": ("proposals", "proposal"),
}


def allowed(user: str, kind: str, eid: str | None) -> bool:
    """private.web_push_allowed sur une notification fictive (jamais insérée) du bot."""
    rec = {"id": "00000000-0000-0000-0000-000000000001", "user_id": uid(user), "kind": kind, "event_id": eid, "title": "t",
           "body": "b", "data": {}, "dedupe_key": "x:x:1d" if kind == "reminder" else None, "skipped": False}
    return sql(f"""select private.web_push_allowed(jsonb_populate_record(null::public.notifications, {q(json.dumps(rec))}::jsonb)) v""")[0]["v"]


def notification_columns() -> list:
    return [r["column_name"] for r in sql("""select column_name from information_schema.columns where table_schema = 'public'
              and table_name = 'notifications' order by ordinal_position""")]


def phase_reglages(browser, origin, only):
    """Victor (Membre VIP, Android) et Marc (Membre, iPhone) : chaque interrupteur des événements, éteint puis rallumé ;
    colonne en base, puis private.web_push_allowed (éteint → refusé, allumé → permis) ; état remis à la fin."""
    s = ids()
    print("colonnes notifications :", notification_columns(), flush=True)
    eid = s.get("accept")
    for key in ("vip1", "membre1"):
        before = sql(f"select * from public.notification_prefs where user_id = {q(uid(key))}")[0]
        save_state(**{f"prefs_{key}": before})
        p = phone(browser, key, origin, "c2-reglages")
        page = p.page
        try:
            p.sign_in()
            p.goto("/events/settings/notifications")
            p.see(page.get_by_label("Recevoir mes alertes", exact=True), "Réglages › Notifications", 20000)
            p.shot("haut", full=True)
            p.dump("reglages")
            shown = [l for l in LABELS if page.get_by_label(l, exact=True).count()]
            p.log(f"interrupteurs affichés : {shown}")
            for label in shown:
                col, kind = LABELS[label]
                with p.step(f"interrupteur « {label} »"):
                    toggle(p, label, False)
                    page.wait_for_timeout(1500)
                    off_db = pref(key, col)
                    off_push = None  # web_push_allowed : matrice à part (matrice-push.txt), pour ménager l'API de gestion
                    toggle(p, label, True)
                    page.wait_for_timeout(1500)
                    on_db = pref(key, col)
                    on_push = None
                    line = f"{key} « {label} » : colonne {col} off={off_db} on={on_db} ; web_push_allowed({kind}) off={off_push} on={on_push}"
                    p.log(line)
                    with open(f"{load_state().get('out', '')}reglages.txt" if False else str(p.dir.parent / "reglages.txt"), "a") as f:
                        f.write(line + "\n")
                    if off_db is not False or on_db is not True:
                        p.flag("🔴", f"« {label} » mal enregistré", line)
                    elif kind and off_push:
                        p.flag("🔴", f"« {label} » éteint : la notification part quand même", line)
                    elif kind and on_push is False:
                        p.flag("🟠", f"« {label} » allumé : la notification ne part pas ({key}, {BY_KEY[key].role})", line)
            # Rechargement : l'état tient.
            page.reload()
            p.page.wait_for_timeout(3000)
            p.shot("apres-rechargement")
        finally:
            p.close()
            sql(f"""update public.notification_prefs set (push_enabled, event_changed, poll_new, date_fixed, rsvp_set, invites, poll_nudge,
                    waitlist, ticket_pay_confirmed, ticket_issued, rsvp_mine, link_join, ticket_pay_declared, proposal_result,
                    announce_results, announce_requests, group_event_requests, proposals) =
                    (select push_enabled, event_changed, poll_new, date_fixed, rsvp_set, invites, poll_nudge, waitlist, ticket_pay_confirmed,
                     ticket_issued, rsvp_mine, link_join, ticket_pay_declared, proposal_result, announce_results, announce_requests,
                     group_event_requests, proposals from jsonb_populate_record(null::public.notification_prefs, {q(json.dumps(before, default=str))}::jsonb))
                    where user_id = {q(uid(key))}""")


def phase_pause(browser, origin, only):
    """Lune (pause) et heures de silence par l'écran ; private.push_paused / push_is_quiet en base ; remis à la fin."""
    key = "vip1"
    before = sql(f"select push_enabled, quiet_start, quiet_end, muted_until from public.notification_prefs where user_id = {q(uid(key))}")[0]
    p = phone(browser, key, origin, "c2-pause")
    page = p.page
    try:
        p.sign_in()
        p.goto("/events/profile")  # la lune est en haut de « Mon profil » (racine des Réglages)
        moon = page.get_by_role("button", name=re.compile("^(Mettre les notifications en pause|Notifications en pause)"))
        if p.expect_or_flag(moon, "la lune des Réglages", "🔴", 20000):
            p.tap(moon.first, "lune")
            p.tap(page.get_by_role("menuitem", name="1 heure", exact=True), "1 heure")
            page.wait_for_timeout(2000)
            p.expect_or_flag(page.get_by_text("Notifications en pause jusqu’à", exact=False).first, "bandeau de pause", "🟠")
            p.shot("pause")
            r = sql(f"select muted_until > now() + interval '55 minutes' and muted_until < now() + interval '65 minutes' ok, private.push_paused({q(uid(key))}, 'private_invite') paused, private.push_paused({q(uid(key))}, 'push_test') test from public.notification_prefs where user_id = {q(uid(key))}")[0]
            report(key, r["ok"] and r["paused"] and not r["test"], "🔴", "pause 1 h : muted_until et push_paused", r)
            p.tap(page.get_by_role("button", name="Réactiver les notifications").first, "Réactiver")
            page.wait_for_timeout(2000)
            r = sql(f"select muted_until, private.push_paused({q(uid(key))}, 'private_invite') paused from public.notification_prefs where user_id = {q(uid(key))}")[0]
            report(key, r["paused"] is False, "🔴", "pause retirée", r)
            p.shot("pause-retiree")
        p.goto("/events/settings/notifications")
        p.see(page.get_by_label("Heures de silence", exact=True), "Heures de silence", 20000)
        toggle(p, "Heures de silence", False)
        page.wait_for_timeout(1500)
        r = sql(f"select quiet_start, quiet_end from public.notification_prefs where user_id = {q(uid(key))}")[0]
        report(key, r["quiet_start"] is None and r["quiet_end"] is None, "🔴", "heures de silence coupées → null", r)
        toggle(p, "Heures de silence", True)
        page.wait_for_timeout(1500)
        # Plage qui couvre maintenant (heure de Zurich) : de h-1 à h+1.
        hour = int(sql("select extract(hour from now() at time zone 'Europe/Zurich')::int h")[0]["h"])
        start, end = f"{(hour - 1) % 24:02d}:00", f"{(hour + 1) % 24:02d}:00"
        for lab, val in (("Début (HH:MM)", start), ("Fin (HH:MM)", end)):
            f = page.get_by_label(lab, exact=True)
            f.fill(val)
            f.press("Tab")
            page.wait_for_timeout(1500)
        p.shot("silence")
        r = sql(f"select quiet_start, quiet_end, private.push_is_quiet(quiet_start, quiet_end) quiet from public.notification_prefs where user_id = {q(uid(key))}")[0]
        report(key, str(r["quiet_start"]).startswith(start) and str(r["quiet_end"]).startswith(end) and r["quiet"], "🔴", f"heures de silence {start}–{end} enregistrées et actives", r)
        # Saisie invalide.
        f = page.get_by_label("Début (HH:MM)", exact=True)
        f.fill("25:99")
        f.press("Tab")
        page.wait_for_timeout(1000)
        p.expect_or_flag(page.get_by_text("Saisis une heure entre 00:00 et 23:59", exact=False), "message d'heure invalide", "🟡")
        f = page.get_by_label("Début (HH:MM)", exact=True)
        f.fill(end)
        f.press("Tab")
        page.wait_for_timeout(1000)
        p.expect_or_flag(page.get_by_text("Le début et la fin des heures de silence doivent être différents.", exact=True), "message début = fin", "🟡")
        p.shot("silence-erreurs")
        # Entrée + saisie libre « 7h » (fix-D) : Fin = 07:00.
        f = page.get_by_label("Fin (HH:MM)", exact=True)
        f.fill("7h")
        f.press("Enter")
        page.wait_for_timeout(2000)
        r = sql(f"select quiet_end from public.notification_prefs where user_id = {q(uid(key))}")[0]
        report(key, str(r["quiet_end"]).startswith("07:00"), "🟠", "« 7h » + Entrée → Fin 07:00", r)
        p.shot("silence-7h")
        # « Recevoir mes alertes » éteint : tout refusé (sauf l'essai).
        toggle(p, "Recevoir mes alertes", False)
        page.wait_for_timeout(1500)
        s = ids()
        r = (allowed(key, "private_invite", s.get("accept")), allowed(key, "event_changed", s.get("accept")), allowed(key, "push_test", None))
        report(key, r == (False, False, True), "🔴", "« Recevoir mes alertes » éteint : rien ne part (sauf l'essai)", r)
        toggle(p, "Recevoir mes alertes", True)
        page.wait_for_timeout(1500)
    finally:
        p.close()
        sql(f"""update public.notification_prefs set push_enabled = {str(before['push_enabled']).lower()},
                quiet_start = {q(before['quiet_start']) if before['quiet_start'] else 'null'},
                quiet_end = {q(before['quiet_end']) if before['quiet_end'] else 'null'}, muted_until = null where user_id = {q(uid(key))}""")


# ── Nettoyage : seulement mes événements [C2-07] ──────────────────────────────────────────────────────────────────

def phase_menage(browser, origin, only):
    rows = sql(f"select id, title from public.events where title like {q(P + '%')}")
    print("à supprimer :", [r["title"] for r in rows], flush=True)
    if rows:
        idl = ",".join(q(r["id"]) for r in rows)
        sql(f"delete from public.notifications where event_id in ({idl}) or data->>'target_event' in ({idl})")
        sql(f"delete from public.events where id in ({idl})")
    print("reste :", sql(f"select count(*) n from public.events where title like {q(P + '%')}"), flush=True)


# ── Relance : blocage (bug 1), brouillons orphelins (bug 2), interrupteurs masqués (bug 5), suite de la feuille Inviter ──

def drafts_of(title: str) -> list:
    return sql(f"select id, status from public.events where title = {q(P + title)} order by created_at") or []


def phase_blocage(browser, origin, only):
    """Olga bloque Gus (membre de « Bots ») le temps de la phase : elle publie pour « Bots » par le formulaire."""
    s = ids()
    olga, gus = uid("orga1"), uid("guest1")
    sql(f"insert into public.direct_blocks (user_id, blocked_id) values ({q(olga)}, {q(gus)}) on conflict do nothing")
    try:
        if "block" not in s:
            o = phone(browser, "orga1", origin, "r-blocage")
            try:
                o.sign_in()
                accept_terms_if_asked(o)
                eid = new_event(o, "Olga a bloqué Gus", 45, announce=True)
                if eid:
                    keep("block", eid)
                    o.shot("fiche-blocage")
                if o.page.get_by_text("ne peux pas inviter", exact=False).count():
                    o.flag("🔴", "blocage : message « tu ne peux pas inviter » à la publication")
            finally:
                o.close()
        s = ids()
        rows = drafts_of("Olga a bloqué Gus")
        report("orga1", len(rows) == 1 and rows[0]["status"] == "published", "🔴", "blocage : publié, un seul événement (aucun brouillon orphelin)", rows)
        if "block" in s:
            e = s["block"]
            inv = lambda k: sql(f"select count(*) n from public.event_invites where event_id = {q(e)} and user_id = {q(uid(k))}")[0]["n"]
            report("orga1", inv("guest1") == 0 and inv("vip1") == 1, "🔴", "blocage : Gus sauté, Victor invité", (inv("guest1"), inv("vip1")))
            st = announcements(e)
            report("orga1", [x["status"] for x in st] == ["pending"], "🔴", "blocage : demande d'annonce ouverte", st)
            # Ada accepte : Gus ne doit rien recevoir.
            aid = sql(f"select id from public.event_announcements where event_id = {q(e)}")[0]["id"]
            r = Cached("admin").rpc("answer_announcement", a=aid, accept=True)
            report("admin", r.status_code == 200, "🔴", "blocage : Ada accepte", r.text[:160])
            report("guest1", told(e, "guest1", "private_invite") == 0 and told(e, "vip1", "private_invite") == 1, "🔴",
                   "blocage : annonce acceptée, Gus jamais prévenu, Victor oui", (told(e, "guest1", "private_invite"), told(e, "vip1", "private_invite")))
    finally:
        sql(f"delete from public.direct_blocks where user_id = {q(olga)} and blocked_id = {q(gus)}")
        print("blocage retiré :", sql(f"select count(*) n from public.direct_blocks where user_id = {q(olga)}"), flush=True)


HIDDEN_FOR_MEMBERS = ("Nouveau sondage", "Rappel pour voter", "Un organisateur répond pour moi", "Paiement de ma place confirmé",
                      "Billet prêt", "Réponses à mes événements", "Ma proposition validée ou refusée", "Quelqu’un dit avoir payé",
                      "Proposition à valider")


def phase_masques(browser, origin, only):
    """Marc (Membre), Gus (Guest) : les 9 interrupteurs refusés par may_receive_push sont masqués ; Victor (VIP) les garde."""
    for key, want_hidden in (("membre1", True), ("guest1", True), ("vip1", False)):
        p = phone(browser, key, origin, "r-masques")
        page = p.page
        try:
            p.sign_in()
            p.goto("/events/settings/notifications")
            p.see(page.get_by_label("Recevoir mes alertes", exact=True), "Réglages › Notifications", 30000)
            page.wait_for_timeout(2500)
            p.shot("reglages", full=True)
            shown = [l for l in LABELS if page.get_by_label(l, exact=True).count()]
            bad = [l for l in HIDDEN_FOR_MEMBERS if (l in shown) == want_hidden]
            sections = {t: page.get_by_text(t, exact=False).count() for t in ("Nouveaux événements", "Messages des discussions")}
            p.log(f"affichés : {shown} ; sections : {sections}")
            report(key, not bad, "🟠", f"interrupteurs {'masqués' if want_hidden else 'présents'} ({BY_KEY[key].role})", {"en trop/manquants": bad, "sections": sections})
            for l in shown:  # chaque interrupteur affiché à un non-VIP doit pouvoir partir
                col, kind = LABELS[l]
                if kind and want_hidden and kind not in ("announce_request", "group_event_request", "announce_accepted"):
                    ok = allowed(key, kind, None)
                    if not ok:
                        report(key, False, "🟡", f"« {l} » affiché à un {BY_KEY[key].role} mais web_push_allowed({kind}) = false", kind)
        finally:
            p.close()


def phase_feuille_suite(browser, origin, only):
    """Après la feuille Inviter (annonce à « Bots 2 » seulement) : fiche, puis Modifier sans toucher l'interrupteur,
    puis allumer / couper dans Modifier : que deviennent la demande de « Bots 2 » et celle de « Bots » ?"""
    s = ids()
    key, who = ("sheet_olga", "orga1") if "sheet_olga" in s else ("sheet", ORG)
    if key not in s:
        print("pas d'événement « sheet »", flush=True)
        return
    e = s[key]
    o = phone(browser, who, origin, "r-feuille-suite")
    page = o.page
    try:
        o.sign_in()
        o.goto(f"/events/event/{e}")
        page.wait_for_timeout(3000)
        o.shot("fiche-apres-feuille")
        o.dump("fiche-apres-feuille")
        sw = page.get_by_label("Prévenir le groupe", exact=True)
        o.log(f"fiche : interrupteur « Prévenir le groupe » {'allumé' if sw.count() and sw.is_checked() else 'éteint/absent'} ; statuts : "
              f"{[t for t in ('Bots 2 · Annonce en attente', 'Bots · Annonce', 'Annonce en attente') if page.get_by_text(t, exact=False).count()]}")
        before = announcements(e)
        # Modifier : enregistrer sans toucher à l'interrupteur.
        o.goto(f"/events/event/{e}/edit")
        o.see(page.get_by_label("Titre", exact=True), "Modifier", 20000)
        sw = page.get_by_label("Prévenir le groupe", exact=True)
        o.log(f"Modifier : interrupteur {'allumé' if sw.count() and sw.is_checked() else 'éteint/absent'}")
        o.shot("modifier-apres-feuille")
        fill(o, "Description", "Événement de test des bots (relance 07). Modifié sans toucher à l'annonce.")
        o.tap(page.get_by_role("button", name=re.compile("^Enregistrer")).last, "Enregistrer (sans toucher)")
        page.wait_for_timeout(3500)
        accept_terms_if_asked(o)
        after = announcements(e)
        report(who, after == before and bool(after), "🟠", "Modifier sans toucher l'interrupteur : la demande de « Bots 2 » reste", (before, after))
        # Allumer puis couper dans Modifier : constat de ce que deviennent les demandes (Bots et Bots 2).
        for on in (True, False):
            o.goto(f"/events/event/{e}/edit")
            o.see(page.get_by_label("Titre", exact=True), "Modifier", 20000)
            toggle(o, "Prévenir le groupe", on)
            o.shot(f"modifier-{'on' if on else 'off'}-apres-feuille")
            o.tap(page.get_by_role("button", name=re.compile("^Enregistrer")).last, "Enregistrer")
            page.wait_for_timeout(3500)
            accept_terms_if_asked(o)
            print(f"Modifier, interrupteur {'allumé' if on else 'coupé'} →", announcements(e), flush=True)
            o.log(f"Modifier {'on' if on else 'off'} → {announcements(e)}")
    finally:
        o.close()
    report("admin", requests_to(e, "admin") <= 1, "🟡", "feuille + Modifier : une seule « Annonce à valider » pour Ada", requests_to(e, "admin"))


def sheet_add_group(o, eid: str, group: str, announce: bool = True) -> None:
    """Feuille Inviter par l'écran : chercher le groupe, l'ajouter, « Prévenir le groupe », Inviter."""
    page = o.page
    o.goto(f"/events/event/{eid}")
    o.tap(page.get_by_role("button", name="Inviter", exact=True), "Inviter")
    sheet = page.get_by_label(re.compile("^Inviter à "))
    o.see(sheet, "la feuille Inviter", 10000)
    o.type(sheet.get_by_label("Chercher une personne ou un groupe"), group, "recherche")
    page.wait_for_timeout(1500)
    o.tap(sheet.get_by_role("button", name=re.compile(f"^Ajouter {group}")).first, f"Ajouter {group}")
    page.wait_for_timeout(800)
    sw = sheet.get_by_label("Prévenir le groupe", exact=True)
    if o.expect_or_flag(sw, "« Prévenir le groupe » dans la feuille", "🔴"):
        if sw.is_checked():
            o.flag("🔴", "feuille Inviter : « Prévenir le groupe » allumé par défaut")
        if announce:
            o.tap(sw, "Prévenir le groupe → oui")
            page.wait_for_timeout(800)
        o.shot("feuille-annonce")
        o.dump("feuille-annonce")
        o.tap(sheet.get_by_role("button", name=re.compile("^Inviter ")).first, f"Inviter ({group})")
        page.wait_for_timeout(3500)
        o.shot("feuille-apres")


def phase_feuille_olga(browser, origin, only):
    """Bug 3 rejoué par l'écran : Olga (membre de « Bots » ET « Bots 2 », pas créatrice) publie pour « Bots » sans annonce,
    puis feuille Inviter : + « Bots 2 » + « Prévenir le groupe ». Attendu : seule « Bots 2 » est annoncée (demande à Ada)."""
    s = ids()
    o = phone(browser, "orga1", origin, "r-feuille-olga")
    try:
        o.sign_in()
        accept_terms_if_asked(o)
        if "sheet_olga" not in s:
            eid = new_event(o, "Inviter Bots 2 (Olga)", 47, announce=False)
            if not eid:
                return
            keep("sheet_olga", eid)
            s = ids()
        e = s["sheet_olga"]
        if not announcements(e):
            sheet_add_group(o, e, "Bots 2")
        o.goto(f"/events/event/{e}")
        o.page.wait_for_timeout(3000)
        o.shot("fiche-apres-feuille")
        o.dump("fiche-apres-feuille")
    finally:
        o.close()
    st = announcements(e)
    report("orga1", [(x["grp"], x["status"]) for x in st] == [("Bots 2", "pending")], "🟠",
           "feuille Inviter (Olga) : seule « Bots 2 » est annoncée, en attente", st)
    report("vip1", told(e, "vip1", "private_invite") == 0, "🔴", "feuille Inviter : Victor (Bots seulement) pas prévenu", told(e, "vip1", "private_invite"))
    report("admin", requests_to(e, "admin") == 1, "🟠", "feuille Inviter : Ada reçoit une « Annonce à valider »", requests_to(e, "admin"))
    flag = sql(f"select announce_group from public.events where id = {q(e)}")[0]["announce_group"]
    eg = sql(f"select (select name from public.member_groups where id = group_id) g, announce from public.event_groups where event_id = {q(e)} order by 1")
    print("announce_group =", flag, "event_groups =", eg, flush=True)
    report("orga1", flag is False, "🟠", "feuille Inviter : announce_group de l'événement reste éteint", flag)


ENGLISH = ("current transaction is aborted", "statement timeout", "canceling statement", "commands ignored")


def phase_erreurs(browser, origin, only):
    """Bug 9 : erreurs de la base simulées dans le navigateur (réponse 500 de PostgREST, comme sous la charge) :
    la fiche (25P02) et la publication du formulaire (57014) doivent parler français."""
    s = ids()
    v = phone(browser, "vip1", origin, "r-erreurs")
    page = v.page
    try:
        v.sign_in()
        body = json.dumps({"code": "25P02", "details": None, "hint": None,
                           "message": "current transaction is aborted, commands ignored until end of transaction block"})
        page.route(re.compile(r".*/rest/v1/events\?.*"), lambda r: r.fulfill(status=500, content_type="application/json", body=body))
        v.goto(f"/events/event/{s.get('accept', '00000000-0000-0000-0000-000000000000')}")
        page.wait_for_timeout(6000)
        v.shot("fiche-25P02")
        text = page.locator("body").inner_text()
        eng = [w for w in ENGLISH if w in text]
        report("vip1", not eng, "🟡", "fiche : erreur 25P02 en français", eng or text[:200])
        page.unroute(re.compile(r".*/rest/v1/events\?.*"))
        body = json.dumps({"code": "57014", "details": None, "hint": None, "message": "canceling statement due to statement timeout"})
        page.route(re.compile(r".*/rest/v1/events(\?.*)?$"),
                   lambda r: r.fulfill(status=500, content_type="application/json", body=body) if r.request.method == "POST" else r.continue_())
        v.goto("/events/event/new")
        v.see(page.get_by_label("Titre", exact=True), "le formulaire", 30000)
        fill(v, "Titre", P + "Erreur simulée (jamais créé)")
        set_date(v, "Début", day(46), "19:30")
        fill(v, "Lieu", "Salle des bots, Vevey")
        audience_invite_groups(v, ["Bots"])
        v.shot("formulaire-avant")
        v.tap(page.get_by_role("button", name=re.compile("^(Publier|Envoyer pour validation)$")).last, "Publier (POST refusé 57014)")
        page.wait_for_timeout(5000)
        accept_terms_if_asked(v)
        v.shot("formulaire-57014")
        text = page.locator("body").inner_text()
        eng = [w for w in ENGLISH if w in text]
        report("vip1", not eng, "🟡", "formulaire : erreur 57014 en français", eng or "ok")
        m = re.search(r"[^\n]*(délai|lent|répond|Réessaie)[^\n]*", text)
        v.log(f"message affiché : {m.group(0) if m else '(aucun message reconnu)'}")
    finally:
        v.close()


PHASES = {name[6:]: fn for name, fn in globals().items() if name.startswith("phase_")}


def main(argv: list[str]) -> None:
    origin = load_state()["origin"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv:
            print(f"════ phase {name} ════", flush=True)
            try:
                PHASES[name](browser, origin, None)
            except Exception as e:  # une phase cassée n'arrête pas les suivantes
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
