"""Campagne 2, agent 04 : réponses des participants (Présent / Peut-être / Absent, accompagnants, liste d'attente,
date limite, sondage de dates, mini-sondages, qui amène quoi, forum, agenda .ics, pastille, « Qui vient ? »).

Base de TEST seulement, groupes et comptes « Bot … » seulement. Les événements sont créés par Bot Olga avec SON jeton
(API REST, mêmes règles que l'app), titres préfixés « [C2-04] » ; tout le reste se fait au doigt dans de vrais écrans.

  BOTS_OUT=<dossier 04> .venv/bin/python -m tests.bots.reponses_c2 setup login reponses ...
  (phases : voir PHASES en bas du fichier ; « cleanup » supprime les événements [C2-04] et seulement eux)"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

import httpx
from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots.bench import anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, TEST_URL, Session, q, sql

from tests.bots.bench import Phone

# Machine et base de TEST saturées pendant la campagne (charge > 300) : délais du banc allongés pour ce module seulement.
Phone.tap.__defaults__ = (60000,)
Phone.see.__defaults__ = (45000,)
Phone.expect_or_flag.__defaults__ = ("🟠", 45000)

PREFIX = "[C2-04]"
NOTE = f"Salut Olga, j'amène mon cousin 🙂 n°{int(time.time()) % 1000}"
TZ = timezone.utc


# ── Comptes et API (jeton du bot : mêmes droits que dans l'app) ─────────────────────────────────────────────────

class Api:
    """Jeton REST d'un bot, gardé dans state.json (une heure) pour ne pas redemander un code à chaque phase."""

    def __init__(self, key: str):
        tokens = load_state().get("tokens", {})
        cached = tokens.get(key)
        stored = _browser_session(key)
        if cached and cached["exp"] > time.time() + 300:
            self.uid, self.token = cached["uid"], cached["token"]
        elif stored:
            self.uid, self.token = stored
        else:
            s = Session(BY_KEY[key].phone)
            self.uid, self.token = s.uid, s.token
            save_state(tokens={**load_state().get("tokens", {}),
                               key: {"uid": self.uid, "token": self.token, "exp": time.time() + 3300}})
        from tests.bots.common import publishable_key
        self.h = {"apikey": publishable_key(), "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def post(self, table: str, body, prefer: str = "return=representation") -> httpx.Response:
        return httpx.post(f"{TEST_URL}/rest/v1/{table}", headers={**self.h, "Prefer": prefer}, json=body, timeout=90)

    def patch(self, path: str, body) -> httpx.Response:
        return httpx.patch(f"{TEST_URL}/rest/v1/{path}", headers={**self.h, "Prefer": "return=representation"}, json=body, timeout=90)

    def get(self, path: str) -> httpx.Response:
        return httpx.get(f"{TEST_URL}/rest/v1/{path}", headers=self.h, timeout=90)

    def rpc(self, name: str, **args) -> httpx.Response:
        return httpx.post(f"{TEST_URL}/rest/v1/rpc/{name}", headers=self.h, json=args, timeout=90)


def _browser_session(key: str) -> tuple[str, str] | None:
    """Session déjà ouverte dans le navigateur du bot (storage.json) : évite un nouveau code SMS de test."""
    from tests.bots.bench import OUT
    path = OUT / key / "storage.json"
    if not path.exists():
        return None
    for origin in json.loads(path.read_text()).get("origins", []):
        for item in origin.get("localStorage", []):
            if "auth-token" in item["name"]:
                v = json.loads(item["value"])
                if v.get("expires_at", 0) > time.time() + 300:
                    return v["user"]["id"], v["access_token"]
    return None


_apis: dict[str, Api] = {}


def api(key: str) -> Api:
    if key not in _apis:
        _apis[key] = Api(key)
    return _apis[key]


def uid(key: str) -> str:
    return sql(f"select id from public.profiles where phone = {q(BY_KEY[key].phone)}")[0]["id"]


def iso(days: float, hour: int = 20) -> str:
    d = (datetime.now(TZ) + timedelta(days=days)).replace(hour=hour - 1, minute=0, second=0, microsecond=0)
    return d.isoformat()


def ev(key: str) -> str:
    return load_state()["c2"][key]


# ── Vérités de la base ──────────────────────────────────────────────────────────────────────────────────────────

def rows(event_key: str) -> list[dict]:
    return sql(f"""select p.display_name name, r.status, r.waitlisted, r.plus_ones, r.plus_ones_waitlisted pw, r.note,
                          r.updated_at, r.set_by
                   from public.rsvps r join public.profiles p on p.id = r.user_id
                   where r.event_id = '{ev(event_key)}' order by r.updated_at""")


def heads(event_key: str) -> int:
    return sum(1 + r["plus_ones"] for r in rows(event_key) if r["status"] == "yes" and not r["waitlisted"])


def mine(event_key: str, key: str) -> dict | None:
    for r in rows(event_key):
        if r["name"] == BY_KEY[key].nickname:
            return r
    return None


def mine_until(event_key: str, key: str, ok, tries: int = 8) -> dict | None:
    """La base de TEST est lente pendant la campagne : relit jusqu'à ~16 s avant de conclure."""
    r = mine(event_key, key)
    for _ in range(tries):
        if r and ok(r):
            break
        time.sleep(2)
        r = mine(event_key, key)
    return r


# ── Création des événements de test (Bot Olga, son jeton) ──────────────────────────────────────────────────────

INVITED = ["orga2", "vip1", "vip2", "vip3", "vip4", "membre1", "membre2", "membre3", "guest2", "coadmin"]

EVENTS = {
    # Places limitées : 4 places, liste d'attente, peut-être, 2 accompagnants max, forum, sondage, objets.
    "places": dict(title="Places limitées", max_participants=4, waitlist_enabled=True, allow_maybe=True, allow_plus_ones=True,
                   max_plus_ones=2, rsvp_deadline_days=6, forum_enabled=True, show_participants=True),
    # Complet, liste d'attente fermée.
    "sans_attente": dict(title="Complet sans liste d'attente", max_participants=2, waitlist_enabled=False, allow_maybe=False,
                         allow_plus_ones=False, max_plus_ones=0, show_participants=True),
    # Date limite passée (fixée à demain, puis reculée dans la base de TEST pour simuler le temps qui passe).
    "limite": dict(title="Date limite passée", max_participants=None, waitlist_enabled=True, allow_maybe=True,
                   allow_plus_ones=True, max_plus_ones=1, rsvp_deadline_days=1, show_participants=True),
    # Participants cachés.
    "cache": dict(title="Participants cachés", max_participants=10, waitlist_enabled=True, allow_maybe=True,
                  allow_plus_ones=True, max_plus_ones=1, show_participants=False),
    # Dernière place : 3 places, 2 prises d'avance ; 3 bots touchent Présent en même temps.
    "course": dict(title="Course à la dernière place", max_participants=3, waitlist_enabled=True, allow_maybe=True,
                   allow_plus_ones=False, max_plus_ones=0, show_participants=True),
}


def _event_body(olga: str, spec: dict, offset: int) -> dict:
    body = {"title": f"{PREFIX} {spec['title']}", "description": "Recette campagne 2 (agent 04, bots). Ignorer.",
            "created_by": olga, "status": "published", "date_mode": "fixed", "starts_at": iso(offset),
            "ends_at": iso(offset, 23), "location_name": "Salle des bots", "location_address": "Rue du Lac 12, 1800 Vevey",
            "visibility": "invited", "notify_on_publish": False, "public_link": False,
            "max_participants": spec.get("max_participants"), "waitlist_enabled": spec.get("waitlist_enabled", True),
            "allow_maybe": spec.get("allow_maybe", True), "allow_plus_ones": spec.get("allow_plus_ones", False),
            "max_plus_ones": spec.get("max_plus_ones", 0), "show_participants": spec.get("show_participants", True),
            "forum_enabled": spec.get("forum_enabled", False)}
    if spec.get("rsvp_deadline_days"):
        body["rsvp_deadline"] = iso(spec["rsvp_deadline_days"], 12)
    return body


def _invite(o: Api, eid: str, keys: list[str]) -> None:
    r = o.post("event_invites", [{"event_id": eid, "user_id": uid(k)} for k in keys], prefer="return=minimal")
    print("invitations", eid, r.status_code, r.text[:200], flush=True)


def phase_setup(browser, origin, only):
    o = api("orga1")
    created = {}
    for i, (key, spec) in enumerate(EVENTS.items()):
        r = o.post("events", _event_body(o.uid, spec, 7 + i))
        print("événement", key, r.status_code, r.text[:300], flush=True)
        if r.status_code >= 300:
            anomaly("orga1", "🟠", f"création « {spec['title']} » refusée (API, jeton de Bot Olga)", r.text[:400])
            continue
        created[key] = r.json()[0]["id"]
        _invite(o, created[key], INVITED)
    # Co-organisateur : Bot Oscar sur « Places limitées ».
    r = o.post("event_organizers", {"event_id": created["places"], "user_id": uid("orga2")}, prefer="return=minimal")
    print("co-organisateur", r.status_code, r.text[:200], flush=True)
    # Mini-sondage (1 choix) et objets (un simple, un à partager : 6 bouteilles).
    p = o.post("polls", {"event_id": created["places"], "question": "Raclette ou fondue ?", "created_by": o.uid,
                         "members_can_add_options": True})
    print("sondage", p.status_code, p.text[:200], flush=True)
    if p.status_code < 300:
        pid = p.json()[0]["id"]
        o.post("poll_options", [{"poll_id": pid, "label": "Raclette", "sort": 0, "created_by": o.uid},
                                {"poll_id": pid, "label": "Fondue", "sort": 1, "created_by": o.uid}], prefer="return=minimal")
    b = o.post("bring_items", [{"event_id": created["places"], "label": "Pain", "sort": 1, "quantity": None},
                               {"event_id": created["places"], "label": "Bouteilles de jus", "sort": 2, "quantity": 6}],
               prefer="return=minimal")
    print("objets", b.status_code, b.text[:200], flush=True)
    # Sondages de dates : « Si besoin » sans Peut-être (allow_maybe = false), et un normal.
    for key, maybe in (("dates_sans_peutetre", False), ("dates", True)):
        body = {**_event_body(o.uid, {"title": f"Sondage de dates{'' if maybe else ' (sans Peut-être)'}", "allow_maybe": maybe,
                                      "max_participants": 3, "show_participants": True}, 20),
                "date_mode": "poll", "starts_at": None, "ends_at": None, "members_can_propose_dates": True,
                "poll_deadline": iso(5, 22)}
        r = o.post("events", body)
        print("sondage de dates", key, r.status_code, r.text[:300], flush=True)
        if r.status_code >= 300:
            anomaly("orga1", "🟠", f"création du sondage de dates {key} refusée", r.text[:400])
            continue
        created[key] = r.json()[0]["id"]
        o.post("date_options", [{"event_id": created[key], "starts_at": iso(d)} for d in (21, 22, 23)], prefer="return=minimal")
        _invite(o, created[key], INVITED)
    # Deux bots déjà présents sur « Course » (2 places prises sur 3).
    for k in ("orga2", "coadmin"):
        r = api(k).post("rsvps", {"event_id": created["course"], "user_id": api(k).uid, "status": "yes"}, prefer="return=minimal")
        print("présent d'avance", k, r.status_code, r.text[:200], flush=True)
    save_state(c2=created)
    print(json.dumps(created, indent=2), flush=True)


def phase_cleanup(browser, origin, only):
    gone = sql(f"delete from public.events where title like {q(PREFIX + '%')} returning id, title")
    print("supprimés :", gone, flush=True)


# ── Gestes communs ───────────────────────────────────────────────────────────────────────────────────────────────

def wait_ready(p) -> None:
    """Fiche chargée. Pendant la campagne (10 agents, machine et base de TEST saturées) : jusqu'à 90 s, puis un
    rechargement ; le temps d'ouverture est noté au journal."""
    t = time.time()
    for attempt in range(2):
        try:
            p.page.get_by_text("À propos", exact=True).first.wait_for(timeout=90000)
            break
        except Exception:
            if attempt:
                raise
            p.log("fiche toujours en chargement après 90 s : rechargement")
            p.shot("chargement-long")
            p.page.reload(wait_until="domcontentloaded")
    p.log(f"fiche chargée en {time.time() - t:.1f} s")
    p.page.wait_for_timeout(1500)


def open_event(p, key: str) -> None:
    p.goto(f"/events/event/{ev(key)}")
    wait_ready(p)


def wait_saved(p, timeout_ms: int = 20000) -> None:
    """Attend la fin de l'enregistrement (plus aucun choix « occupé »)."""
    busy = p.page.locator('[role="radiogroup"] [aria-busy="true"]')
    waited = 0
    while busy.count() and waited < timeout_ms:
        p.page.wait_for_timeout(250)
        waited += 250
    if waited:
        p.log(f"enregistrement : {waited} ms")


def tap_rsvp(p, choice: str, double: bool = False) -> None:
    btn = p.page.get_by_role("radiogroup").first.get_by_role("button", name=choice, exact=True)
    p.tap(btn, choice)
    if double:
        p.page.wait_for_timeout(60)
        try:
            btn.tap(timeout=1500, force=True)
            p.log(f"second toucher rapide sur « {choice} »")
        except Exception as e:  # bouton occupé (désactivé pendant l'enregistrement) : attendu
            p.log(f"second toucher refusé ({type(e).__name__})")
    p.page.wait_for_timeout(400)
    wait_saved(p)
    if f.accept_terms_if_asked(p):
        p.page.wait_for_timeout(2000)
        wait_saved(p)
    err = p.page.get_by_text(re.compile("connexion a échoué|statement timeout|Réessaie|erreur", re.I))
    if err.count():
        p.log(f"message d'erreur à l'écran : {err.first.inner_text()[:200]}")
    p.page.wait_for_timeout(1200)


def ui_counts(p) -> dict:
    """Ce que l'écran affiche : ligne « Places », jauge de « Qui vient ? », pastille."""
    page = p.page
    out = {}
    places = page.get_by_text(re.compile(r"^\d+ / \d+$")).first
    out["places"] = places.inner_text() if places.count() else None
    meter = page.get_by_label(re.compile(r"^\d+ sur \d+ places prises$")).first
    out["meter"] = meter.get_attribute("aria-label") if meter.count() else None
    badge = page.get_by_role("button", name=re.compile(r"présents? ou peut-être")).first
    out["badge"] = badge.get_attribute("aria-label") if badge.count() else None
    who = page.get_by_text(re.compile(r"^PRÉSENTS · \d+$")).first
    out["presents"] = who.inner_text() if who.count() else None
    wl = page.get_by_text(re.compile(r"^LISTE D’ATTENTE · \d+$")).first
    out["attente"] = wl.inner_text() if wl.count() else None
    p.log(f"compteurs à l'écran : {out}")
    return out


def check_counts(p, event_key: str, what: str, tries: int = 3) -> None:
    """Compare l'écran à la base ; la base de TEST est lente : on laisse au temps réel 3 essais de 4 s."""
    for attempt in range(tries):
        if _counts_match(p, event_key, what, flag=attempt == tries - 1):
            return
        p.page.wait_for_timeout(4000)


def _counts_match(p, event_key: str, what: str, flag: bool) -> bool:
    db = rows(event_key)
    h = sum(1 + r["plus_ones"] for r in db if r["status"] == "yes" and not r["waitlisted"])
    maybe = sum(1 for r in db if r["status"] == "maybe")
    ui = ui_counts(p)
    p.log(f"base ({what}) : présents (accompagnants compris) {h}, peut-être {maybe} ; réponses {db}")
    problems = []
    if ui["places"] and int(ui["places"].split(" / ")[0]) != h:
        problems.append(f"Places {ui['places']} ≠ base {h}")
    if ui["meter"] and int(ui["meter"].split(" ")[0]) != h:
        problems.append(f"jauge {ui['meter']} ≠ base {h}")
    if ui["presents"] and int(ui["presents"].split("· ")[1]) != h:
        problems.append(f"{ui['presents']} ≠ base {h}")
    if ui["badge"]:
        n = int(ui["badge"].split(" ")[0])
        if n != h + maybe:
            problems.append(f"pastille « {ui['badge']} » ≠ base {h} présents + {maybe} peut-être")
    if problems and flag:
        p.flag("🟠", f"compteurs faux ({what})", " ; ".join(problems))
    return not problems


def note_box(p):
    return p.page.get_by_label("Un petit mot perso pour l’organisateur")


# ── Phases ──────────────────────────────────────────────────────────────────────────────────────────────────────

LOGIN = ["orga1", "orga2", "coadmin", "vip1", "vip2", "vip3", "vip4", "membre1", "membre2", "membre3", "guest2"]


def phase_login(browser, origin, only):
    for key in LOGIN:
        if only and key not in only:
            continue
        p = phone(browser, key, origin, "c2-connexion")
        try:
            with p.step("connexion"):
                p.sign_in()
                p.see(p.page.get_by_label("Rechercher un événement"), "la liste des événements", 30000)
                f.accept_terms_if_asked(p)
        finally:
            p.close()


def phase_reponses(browser, origin, only):
    """Présent / Peut-être / Absent, changements d'avis répétés, double toucher, petit mot, accompagnants +/−."""
    p = phone(browser, "vip1", origin, "c2-reponses")
    page = p.page
    try:
        open_event(p, "places")
        p.shot("fiche-avant")
        p.dump("fiche-avant")
        check_counts(p, "places", "ouverture")
        for choice, expected in (("Présent", "yes"), ("Peut-être", "maybe"), ("Absent", "no"), ("Présent", "yes"),
                                 ("Absent", "no"), ("Peut-être", "maybe"), ("Présent", "yes")):
            with p.step(f"répondre « {choice} »"):
                tap_rsvp(p, choice)
                r = mine_until("places", "vip1", lambda x: x["status"] == expected)
                p.log(f"base : {r}")
                if not r or r["status"] != expected:
                    p.flag("🔴", f"« {choice} » pas enregistré en base", str(r))
                sel = page.get_by_role("radiogroup").first.get_by_role("button", name=choice, exact=True)
                if sel.get_attribute("aria-selected") != "true" and sel.get_attribute("aria-pressed") != "true":
                    p.log(f"attributs du choix : selected={sel.get_attribute('aria-selected')} pressed={sel.get_attribute('aria-pressed')}")
        p.shot("apres-changements")
        with p.step("double toucher sur Absent puis Présent"):
            tap_rsvp(p, "Absent", double=True)
            tap_rsvp(p, "Présent", double=True)
            r = mine_until("places", "vip1", lambda x: x["status"] == "yes")
            p.log(f"base après double toucher : {r}")
            if not r or r["status"] != "yes":
                p.flag("🔴", "double toucher : réponse finale fausse en base", str(r))
        with p.step("accompagnants + + + puis −"):
            plus = page.get_by_label("Ajouter un accompagnant")
            minus = page.get_by_label("Retirer un accompagnant")
            for n in (1, 2):
                p.tap(plus, f"+ accompagnant ({n})")
                mine_until("places", "vip1", lambda x, n=n: x["plus_ones"] + x["pw"] == n)
                page.wait_for_timeout(2500)
            p.shot("deux-accompagnants")
            disabled = plus.is_disabled() or plus.get_attribute("aria-disabled") == "true"
            p.log(f"« + » au maximum (2) désactivé : {disabled}")
            if not disabled:
                p.flag("🟠", "accompagnants : « + » reste actif au maximum (2)")
            r = mine_until("places", "vip1", lambda x: x["plus_ones"] + x["pw"] == 2)
            if not r or r["plus_ones"] + r["pw"] != 2:
                p.flag("🔴", "accompagnants : 2 demandés, base différente", str(r))
            p.tap(minus, "− accompagnant")
            page.wait_for_timeout(2500)
            r = mine_until("places", "vip1", lambda x: x["plus_ones"] + x["pw"] == 1)
            p.log(f"base après − : {r}")
            if not r or r["plus_ones"] + r["pw"] != 1:
                p.flag("🔴", "accompagnants : retrait non enregistré", str(r))
            check_counts(p, "places", "Victor +1")
        with p.step("deux touchers rapides sur « + » (0 → 2 attendu)"):
            p.tap(minus, "− (retour à 0)")
            mine_until("places", "vip1", lambda x: x["plus_ones"] + x["pw"] == 0)
            page.wait_for_timeout(2500)
            plus.tap()
            page.wait_for_timeout(120)
            plus.tap()
            p.log("deux touchers rapides sur « + »")
            r = mine_until("places", "vip1", lambda x: x["plus_ones"] + x["pw"] == 2, tries=5)
            page.wait_for_timeout(2000)
            shown = page.get_by_text(re.compile(r"^\+\d$")).first.inner_text()
            p.log(f"base : {r} ; écran : {shown}")
            p.shot("double-plus")
            if r and r["plus_ones"] + r["pw"] != 2:
                p.flag("🟡", "accompagnants : deux touchers rapides sur « + » n'en ajoutent qu'un (le bouton reste actif pendant l'enregistrement)",
                       f"base {r['plus_ones'] + r['pw']}, écran {shown}")
            p.tap(minus, "− (retour à 1)")
            mine_until("places", "vip1", lambda x: x["plus_ones"] + x["pw"] == 1)
            page.wait_for_timeout(2500)
        with p.step("petit mot à l'organisateur"):
            box = note_box(p)
            box.fill("")
            page.wait_for_timeout(300)
            p.type(box, NOTE, "le petit mot")
            p.shot("mot-saisi")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True), "Envoyer le mot")
            page.wait_for_timeout(2000)
            r = mine_until("places", "vip1", lambda x: x["note"] == NOTE)
            if not r or r["note"] != NOTE:
                p.flag("🔴", "petit mot pas enregistré", str(r))
            still = page.get_by_role("button", name="Envoyer", exact=True).count()
            p.log(f"bouton Envoyer encore là après envoi : {bool(still)}")
            p.shot("mot-envoye")
        with p.step("rechargement : réponse, accompagnant et mot conservés"):
            page.reload(wait_until="domcontentloaded")
            wait_ready(p)
            v = note_box(p).input_value() if note_box(p).count() else None
            p.log(f"mot relu à l'écran : {v!r}")
            if v != NOTE:
                p.flag("🟠", "petit mot : pas relu après rechargement", repr(v))
            p.expect_or_flag(page.get_by_text("+1", exact=True).first, "« +1 » accompagnant après rechargement")
        with p.step("Absent retire l'accompagnant ; retour à Présent sans accompagnant"):
            tap_rsvp(p, "Absent")
            r = mine_until("places", "vip1", lambda x: x["status"] == "no")
            p.log(f"base : {r}")
            if r and r["plus_ones"]:
                p.flag("🟠", "Absent : l'accompagnant reste compté", str(r))
            tap_rsvp(p, "Présent")
            p.shot("retour-present")
        with p.step("perte réseau : toucher Peut-être hors ligne"):
            p.ctx.set_offline(True)
            p.tap(page.get_by_role("radiogroup").first.get_by_role("button", name="Peut-être", exact=True), "Peut-être (hors ligne)")
            page.wait_for_timeout(6000)
            p.shot("hors-ligne")
            sel = page.get_by_role("radiogroup").first.get_by_role("button", name="Peut-être", exact=True)
            p.log(f"hors ligne : Peut-être sélectionné à l'écran : {sel.get_attribute('aria-selected')} ; "
                  f"texte : {page.get_by_role('radiogroup').first.locator('xpath=..').inner_text()[:300]!r}")
            err = page.get_by_text(re.compile("connexion|réseau|Réessaie|Failed to fetch", re.I)).count()
            if not err:
                p.flag("🟠", "perte réseau : aucun message d'erreur après un toucher « Peut-être » hors ligne")
            if sel.get_attribute("aria-selected") == "true":
                p.flag("🟠", "perte réseau : « Peut-être » reste affiché comme choisi alors que rien n'est enregistré")
            p.ctx.set_offline(False)
            page.wait_for_timeout(1500)
            r = mine("places", "vip1")
            p.log(f"base après retour du réseau : {r}")
        check_counts(p, "places", "après aller-retours")
        f_cut = p.check_texts_cut("fiche invité")
        if f_cut:
            p.flag("🟡", "fiche invité : textes coupés", "; ".join(f_cut))
        p.scroll_to_bottom("fiche invité")
    finally:
        p.close()


def answer(browser, origin, key: str, event_key: str, choice: str, extras: int = 0, phase: str = "c2-attente") -> dict | None:
    p = phone(browser, key, origin, phase)
    try:
        try:
            open_event(p, event_key)
        except Exception as e:  # machine saturée : la réponse passe par l'API (même jeton) pour que le scénario continue
            p.log(f"fiche pas chargée ({type(e).__name__}) : réponse donnée par l'API")
            status = {"Présent": "yes", "Peut-être": "maybe", "Absent": "no"}[choice]
            a = api(key)
            body = {"status": status, "plus_ones": extras}
            r = a.patch(f"rsvps?event_id=eq.{ev(event_key)}&user_id=eq.{a.uid}", body)
            if r.status_code == 200 and r.json() == []:
                r = a.post("rsvps", {"event_id": ev(event_key), "user_id": a.uid, **body})
            p.log(f"API : {r.status_code} {r.text[:200]}")
            return mine(event_key, key)
        with p.step(f"{BY_KEY[key].nickname} : « {choice} » (+{extras})"):
            tap_rsvp(p, choice)
            for _ in range(extras):
                p.tap(p.page.get_by_label("Ajouter un accompagnant"), "Ajouter un accompagnant")
                p.page.wait_for_timeout(1800)
            p.shot(f"{event_key}-{choice}")
        r = mine(event_key, key)
        p.log(f"base : {r}")
        check_counts(p, event_key, f"après {BY_KEY[key].nickname} {choice}")
        return r
    finally:
        p.close()


def phase_attente(browser, origin, only):
    """Remplir les 4 places, liste d'attente (personnes et accompagnant), désistement, montée, notification, rang."""
    started = sql("select now() t")[0]["t"]
    answer(browser, origin, "vip2", "places", "Présent", 1)     # Victor 1+1 = 2 (si sa réponse est restée) ; Vera 2 → 4
    state = rows("places")
    print("après Vera :", state, flush=True)
    answer(browser, origin, "membre1", "places", "Présent")      # complet → Marc en attente
    answer(browser, origin, "vip3", "places", "Présent")         # Valentin en attente
    save_state(c2_attente_started=started)
    phase_attente_suite(browser, origin, only)


def phase_attente_suite(browser, origin, only):
    """Suite (relançable seule) : Violette +1 en attente, Guest, accompagnant en attente, désistement, montée."""
    started = load_state().get("c2_attente_started") or sql("select now() t")[0]["t"]
    answer(browser, origin, "vip4", "places", "Présent", 1)      # Violette +1 en attente
    answer(browser, origin, "guest2", "places", "Peut-être")
    # Guest : pas d'accompagnant possible (écran) ; par l'API la base remet 0.
    p = phone(browser, "guest2", origin, "c2-attente")
    try:
      with p.step("Guest : Présent, accompagnant impossible"):
        open_event(p, "places")
        tap_rsvp(p, "Présent")
        p.shot("guest-present")
        n = p.page.get_by_label("Ajouter un accompagnant").count()
        p.log(f"Guest : bouton « Ajouter un accompagnant » visible : {bool(n)}")
        if n:
            p.flag("🟠", "Guest : le bouton accompagnant est proposé")
        r = api("guest2").patch(f"rsvps?event_id=eq.{ev('places')}&user_id=eq.{api('guest2').uid}", {"plus_ones": 2})
        p.log(f"API Guest plus_ones=2 : {r.status_code} {r.text[:200]}")
        g = mine("places", "guest2")
        if g and g["plus_ones"] + g["pw"]:
            p.flag("🔴", "Guest : accompagnants acceptés par la base via l'API", str(g))
        tap_rsvp(p, "Peut-être")
    finally:
        p.close()
    # Vera (présente) ajoute un 2e accompagnant alors que c'est complet : elle garde sa place, l'accompagnant attend.
    p = phone(browser, "vip2", origin, "c2-attente")
    try:
      with p.step("Vera : + accompagnant quand c'est complet"):
        open_event(p, "places")
        if True:
            hint = p.page.get_by_text(re.compile("un accompagnant de plus passe en liste d’attente")).count()
            p.log(f"indication « complet : accompagnant en liste d'attente » : {bool(hint)}")
            p.tap(p.page.get_by_label("Ajouter un accompagnant"), "Ajouter un accompagnant (complet)")
            p.page.wait_for_timeout(2500)
            p.shot("accompagnant-en-attente")
            r = mine("places", "vip2")
            p.log(f"base : {r}")
            if not r or r["waitlisted"] or r["pw"] != 1:
                p.flag("🔴", "complet : le 2e accompagnant de Vera n'est pas en liste d'attente (ou elle perd sa place)", str(r))
            p.expect_or_flag(p.page.get_by_text(re.compile("1 en liste d’attente|accompagnant en liste d’attente")).first,
                             "« … en liste d'attente » pour son accompagnant")
        check_counts(p, "places", "complet")
        p.dump("liste-attente")
        p.shot("qui-vient-complet", full=True)
    finally:
        p.close()
    before = rows("places")
    print("avant désistement :", before, flush=True)
    save_state(c2_before_desist=before)
    # Le premier présent se désiste : la tête de file monte.
    first = next((r for r in before if r["status"] == "yes" and not r["waitlisted"]), None)
    leaver = next(k for k in ("vip1", "vip2", "membre1") if first and BY_KEY[k].nickname == first["name"]) if first else "vip1"
    answer(browser, origin, leaver, "places", "Absent", phase="c2-desistement")
    after = rows("places")
    print("après désistement :", after, flush=True)
    save_state(c2_after_desist=after)
    notifs = sql(f"""select p.display_name, n.kind, n.title, n.body, n.created_at from public.notifications n
                     join public.profiles p on p.id = n.user_id
                     where n.event_id = '{ev('places')}' and n.kind = 'waitlist' and n.created_at >= {q(started)}""")
    print("notifications « place libérée » :", notifs, flush=True)
    save_state(c2_waitlist_notifs=notifs)
    # Chaque personne en attente regarde sa fiche : statut + rang.
    for k in ("membre1", "vip3", "vip4"):
        p = phone(browser, k, origin, "c2-montee")
        try:
          with p.step("fiche après désistement"):
            open_event(p, "places")
            p.shot("fiche")
            r = mine("places", k)
            on_wait = p.page.get_by_text(re.compile("tu es sur liste d’attente")).count() > 0
            p.log(f"base : {r} ; écran « liste d'attente » : {on_wait}")
            if r and r["status"] == "yes" and bool(r["waitlisted"]) != on_wait:
                p.flag("🔴", "statut liste d'attente : l'écran ne dit pas ce que dit la base", f"base {r}, écran {on_wait}")
            rank = p.page.get_by_text(re.compile(r"(\d+(e|er|ᵉ)|rang|position)", re.I)).count()
            p.log(f"rang affiché : {bool(rank)}")
            check_counts(p, "places", f"vu par {BY_KEY[k].nickname}")
        finally:
            p.close()


def phase_sans_attente(browser, origin, only):
    """2 places, liste d'attente FERMÉE : le 3e Présent doit être refusé (pas mis en attente)."""
    for k in ("vip1", "vip2"):
        answer(browser, origin, k, "sans_attente", "Présent", phase="c2-sans-attente")
    p = phone(browser, "membre1", origin, "c2-sans-attente")
    try:
        open_event(p, "sans_attente")
        p.shot("complet-avant")
        p.dump("complet-avant")
        with p.step("3e Présent quand c'est complet, sans liste d'attente"):
            tap_rsvp(p, "Présent")
            p.shot("complet-apres")
            r = mine("sans_attente", "membre1")
            p.log(f"base : {r}")
            if r and r["status"] == "yes":
                p.flag("🔴", "liste d'attente désactivée : un Présent est quand même accepté (mis en liste d'attente)",
                       f"base {r} ; l'écran : {p.page.get_by_role('radiogroup').first.inner_text()[:80]}")
        check_counts(p, "sans_attente", "complet sans attente")
    finally:
        p.close()


def phase_limite(browser, origin, only):
    """Date limite dépassée : boutons fermés, API refusée, l'organisateur peut encore noter."""
    answer(browser, origin, "vip1", "limite", "Présent", phase="c2-limite")
    sql(f"update public.events set rsvp_deadline = now() - interval '1 hour' where id = '{ev('limite')}'")
    p = phone(browser, "vip1", origin, "c2-limite")
    try:
        open_event(p, "limite")
        p.shot("limite-passee")
        p.dump("limite-passee")
        p.expect_or_flag(p.page.get_by_text("Les réponses sont closes."), "« Les réponses sont closes. »")
        btn = p.page.get_by_role("radiogroup").first.get_by_role("button", name="Absent", exact=True)
        p.log(f"Absent désactivé : {btn.is_disabled() or btn.get_attribute('aria-disabled')}")
        n = note_box(p).count()
        if n:
            p.flag("🟡", "date limite passée : le champ « petit mot » reste proposé")
        r = api("vip1").patch(f"rsvps?event_id=eq.{ev('limite')}&user_id=eq.{api('vip1').uid}", {"status": "no"})
        p.log(f"API après la limite : {r.status_code} {r.text[:200]}")
        if r.status_code < 300:
            p.flag("🔴", "date limite passée : la base accepte encore un changement de réponse", r.text[:200])
        plus = p.page.get_by_label("Ajouter un accompagnant")
        if plus.count() and not (plus.is_disabled() or plus.get_attribute("aria-disabled") == "true"):
            p.flag("🟠", "date limite passée : « + accompagnant » reste actif")
    finally:
        p.close()
    p = phone(browser, "vip2", origin, "c2-limite")
    try:
        open_event(p, "limite")
        p.shot("limite-sans-reponse")
        p.expect_or_flag(p.page.get_by_text(re.compile("Les réponses sont closes : tu n’as pas répondu")), "« tu n'as pas répondu »")
    finally:
        p.close()
    r = api("orga1").rpc("set_rsvp_for", event=ev("limite"), member=api("vip2").uid, answer="yes")
    print("organisateur note Vera après la limite :", r.status_code, r.text[:200], flush=True)


def phase_cache(browser, origin, only):
    """« Montrer les participants » éteint : qui voit qui ; pastille ; le petit mot."""
    answer(browser, origin, "vip1", "cache", "Présent", phase="c2-cache")
    p = phone(browser, "vip1", origin, "c2-cache")
    try:
        open_event(p, "cache")
        p.type(note_box(p), f"Mot secret pour l'orga n°{int(time.time()) % 1000}", "le petit mot")
        p.tap(p.page.get_by_role("button", name="Envoyer", exact=True), "Envoyer")
        p.page.wait_for_timeout(2000)
    finally:
        p.close()
    answer(browser, origin, "vip2", "cache", "Présent", phase="c2-cache")
    r = api("orga1").patch(f"events?id=eq.{ev('cache')}", {"max_participants": 2})
    print("Olga passe « Participants cachés » à 2 places :", r.status_code, flush=True)
    p = phone(browser, "vip3", origin, "c2-cache")
    try:
        open_event(p, "cache")
        p.shot("cache-vu-par-valentin")
        full_info = p.page.get_by_text("Complet · liste d’attente ouverte").count()
        warn = p.page.get_by_text(re.compile("L’événement est complet : en répondant Présent")).count()
        p.log(f"participants cachés, complet : ligne Places « Complet » {bool(full_info)} ; avertissement sur la carte Réponse {bool(warn)}")
        if full_info and not warn:
            p.flag("🟡", "participants cachés et complet : la carte « Tu viens ? » ne prévient pas qu'un Présent part en liste d'attente",
                   "RsvpCard compte les présents avec les seules réponses lisibles (la sienne) au lieu des totaux event_attendance")
        tree = p.dump("cache-vu-par-valentin")
        if "Bot Victor" in tree or "Bot Vera" in tree:
            p.flag("🔴", "participants cachés : un invité voit les noms des présents")
        if "Mot secret" in tree:
            p.flag("🔴", "participants cachés : le petit mot d'un autre est visible")
        r = api("vip3").get(f"rsvps?event_id=eq.{ev('cache')}&select=user_id,status,note")
        p.log(f"API rsvps vue par Valentin : {r.status_code} {r.text[:300]}")
        if r.status_code == 200 and len(r.json()) > 0:
            p.flag("🔴", "participants cachés : l'API donne les réponses des autres", r.text[:300])
        check_counts(p, "cache", "participants cachés")
        a = api("vip3").rpc("event_attendance", ids=[ev("cache")])
        p.log(f"event_attendance : {a.text[:300]}")
    finally:
        p.close()
    # Événement visible (« Places limitées ») : le mot de Victor, « pour l'organisateur », est-il montré aux autres ?
    p = phone(browser, "vip3", origin, "c2-mot-visible")
    try:
        open_event(p, "places")
        tree = p.dump("places-vu-par-valentin")
        r = api("vip3").get(f"rsvps?event_id=eq.{ev('places')}&select=user_id,note&note=not.is.null")
        p.log(f"mots lisibles par Valentin (API) : {r.text[:300]}")
        if "Salut Olga" in tree:
            p.shot("mot-visible-par-tous")
            p.flag("🟠", "« Un petit mot perso pour l'organisateur » est affiché à tous les invités dans « Qui vient ? »",
                   "le champ promet un mot pour l'organisateur ; Bot Valentin lit le mot de Bot Victor")
    finally:
        p.close()


PHASES = {}  # rempli en bas (après les autres modules)


def main(argv: list[str]) -> None:
    from tests.bots import reponses_c2_more as more
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        only = set(argv[i + 1].split(","))
        argv = argv[:i] + argv[i + 2:]
    origin = load_state()["origin"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv:
            step = globals().get(f"phase_{name}") or getattr(more, f"phase_{name}")
            print(f"════ phase {name} ════", flush=True)
            try:
                step(browser, origin, only)
            except Exception as e:  # une phase cassée n'arrête pas les suivantes
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
