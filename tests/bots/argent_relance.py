"""Relance de la campagne 2, domaine « Argent et entrée » : vérifie les corrections des bugs de l'ancien rapport 05
qui ne sont pas couverts par tests/bots/argent.py (blocage et groupe, « C'est noté » pendant l'enregistrement,
erreurs en anglais, paiements sans recharger, pot commun d'un événement supprimé).

Usage : BOTS_OUT=<dossier> ARGENT_PREFIX="[R-05]" .venv/bin/python -m tests.bots.argent_relance <phase…>
Base de TEST uniquement ; serveur du banc lancé ; événements de argent.py déjà créés (phase prep)."""
from __future__ import annotations

import json
import re
import sys
import time
import traceback

import httpx
from playwright.sync_api import sync_playwright

from tests.bots import argent as a
from tests.bots import flows as f
from tests.bots.bench import anomaly, load_state, phone, save_state
from tests.bots.common import GROUP_BOTS, TEST_URL, q, sql

SLOW_MS = 6000
POLL_WAIT_MS = 45000   # la fiche relit les paiements toutes les 20 s (fix-D)


# ── Bug 1 : Olga a bloqué Gus ; elle publie « Sur invitation · Bots » ────────────────────────────────────────

def _block(blocker: str, blocked: str, on: bool) -> int:
    s = a.session(blocker)
    r = s.rpc("set_block", target=a.uid(blocked), blocked=on)   # même fonction que l'app (lib/moderation.ts)
    print(f"blocage {blocker}→{blocked} {'posé' if on else 'retiré'} : {r.status_code} {r.text[:160]}", flush=True)
    return r.status_code


def phase_blocage(browser, origin, only):
    title = f"{a.PREFIX} Sur invitation bloqué"
    existed = bool(sql(f"""select 1 from public.direct_blocks where user_id = {q(a.uid('orga1'))}
                           and blocked_id = {q(a.uid('guest1'))}"""))   # posé par un autre agent : on le laisse
    if not existed:
        _block("orga1", "guest1", True)
    p = phone(browser, "orga1", origin, "relance-blocage")
    page = p.page
    try:
        a.signed_in(p)
        p.goto("/events/event/new")
        p.see(page.get_by_label("Titre", exact=True), "le formulaire")
        p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
        f.fill(p, "Titre", title)
        f.set_date(p, "Début", f.day(8), "20:00")
        f.fill(p, "Lieu", "Chez les bots")
        f.fill(p, "Prix / pers. (CHF)", "10")
        f.audience_invite_groups(p, [GROUP_BOTS])
        if page.get_by_label("Prévenir le groupe", exact=True).count():
            f.toggle(p, "Prévenir le groupe", False)
        new = f.submit(p, "Publier")
        p.shot("apres-publier")
        p.log(f"événement : {new}")
        rows = sql(f"select id, status from public.events where title = {q(title)}")
        p.log(f"base : {rows}")
        a.check(p, len(rows) == 1 and rows[0]["status"] == "published", "🔴",
                "blocage : l'événement de groupe est publié (un seul, pas de brouillon laissé)", str(rows))
        if rows:
            save_state(e_block=rows[0]["id"])
            inv = sql(f"""select p.display_name from public.event_invites i join public.profiles p on p.id = i.user_id
                          where i.event_id = {q(rows[0]['id'])} order by 1""")
            names = [r["display_name"] for r in inv]
            p.log(f"invités : {names}")
            a.check(p, "Bot Gus" not in names and len(names) >= 3, "🔴", "blocage : Gus sauté, les autres invités", str(names))
    finally:
        p.close()
        if not existed:
            _block("orga1", "guest1", False)
    # Gus, débloqué, ouvre l'événement : il n'y est pas invité (attendu), aucune erreur technique
    p = phone(browser, "guest1", origin, "relance-blocage")
    try:
        e = load_state().get("e_block")
        if e:
            a.signed_in(p)
            p.goto(f"/events/event/{e}")
            a.settle(p)
            p.shot("gus-voit")
            tree = p.dump("gus-voit")
            a.check(p, not re.search(r"blocked|statement|PGRST|Cannot coerce", tree), "🟡",
                    "Gus : pas de message technique sur la fiche", tree[:200])
    finally:
        p.close()


# ── Bug 3 : « C'est noté » seulement après l'enregistrement ; échec → erreur ─────────────────────────────────

def _rsvp_row(key: str, event: str) -> list:
    return sql(f"""select r.status from public.rsvps r join public.profiles pr on pr.id = r.user_id
                   where r.event_id = {q(event)} and pr.phone = {q(a.BY_KEY[key].phone)}""")


def phase_reponse_lente(browser, origin, only):
    e = a.eid("e_free")
    key = "membre2"   # Mia : pas encore répondu à l'événement gratuit
    sql(f"delete from public.rsvps where event_id = {q(e)} and user_id = {q(a.uid(key))}")
    p = phone(browser, key, origin, "relance-reponse")
    page = p.page

    try:
        a.open_event(p, "e_free")
        # Réseau lent (latence ajoutée par Chrome, sans bloquer le banc : un sleep dans un route() fige tout)
        cdp = page.context.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": SLOW_MS,
                                                       "downloadThroughput": -1, "uploadThroughput": -1})
        with p.step("Présent sur un réseau lent"):
            p.tap(page.get_by_role("radiogroup").get_by_role("button", name="Présent", exact=True).first, "Présent")
            page.wait_for_timeout(1200)
            p.shot("pendant")
            saving = page.get_by_text("Enregistrement…").count() > 0
            early = page.get_by_text(re.compile("C’est noté, tu viens")).count() > 0
            in_db = bool(_rsvp_row(key, e))
            p.log(f"pendant : Enregistrement… {saving}, « C'est noté » {early}, en base {in_db}")
            a.check(p, saving and not early, "🟠", "pendant l'envoi : « Enregistrement… », pas « C'est noté »",
                    f"saving={saving} early={early} in_db={in_db}")
            a.settle(p)
            if f.accept_terms_if_asked(p):
                a.settle(p)
            page.wait_for_timeout(SLOW_MS)
            p.shot("apres")
            done = page.get_by_text(re.compile("C’est noté, tu viens")).count() > 0
            a.check(p, done and bool(_rsvp_row(key, e)), "🟠", "après l'envoi : « C'est noté » et réponse en base",
                    str(_rsvp_row(key, e)))
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0,
                                                       "downloadThroughput": -1, "uploadThroughput": -1})
        with p.step("Absent puis échec réseau : erreur, pas de confirmation"):
            page.route(re.compile(r".*/rest/v1/rsvps.*"),
                       lambda r: r.abort() if r.request.method in ("POST", "PATCH") else r.continue_())
            p.tap(page.get_by_role("radiogroup").get_by_role("button", name="Absent", exact=True).first, "Absent (échec)")
            page.wait_for_timeout(2500)
            p.shot("echec")
            tree = p.dump("echec")
            status = _rsvp_row(key, e)
            p.log(f"base : {status}")
            fake_ok = re.search(r"C’est noté[^\n]*(pas là|absent)|Dommage", tree) is not None
            has_err = re.search(r"connexion|réseau|Réessaie", tree, re.I) is not None
            a.check(p, has_err and not fake_ok, "🟠", "échec : message d'erreur, pas de fausse confirmation",
                    f"err={has_err} fake={fake_ok} base={status}")
            a.check(p, status and status[0]["status"] == "yes", "🔴", "base : la réponse reste « Présent »", str(status))
            page.unroute(re.compile(r".*/rest/v1/rsvps.*"))
            radios = page.get_by_role("radiogroup").get_by_role("button", name="Présent", exact=True).first
            p.log(f"Présent coché après l'échec : {radios.get_attribute('aria-checked') or radios.get_attribute('aria-pressed')}")
    finally:
        p.close()
    sql(f"delete from public.rsvps where event_id = {q(e)} and user_id = {q(a.uid(key))}")


# ── Bug 4 : erreur « statement timeout » de la base → phrase française ──────────────────────────────────────

TIMEOUT_BODY = json.dumps({"code": "57014", "details": None, "hint": None,
                           "message": "canceling statement due to statement timeout"})


def phase_erreurs(browser, origin, only):
    p = phone(browser, "orga1", origin, "relance-erreurs")
    page = p.page
    try:
        a.open_event(p, "e_paid")
        with p.step("Billets QR : la base dépasse son délai"):
            page.route(re.compile(r".*/rest/v1/rpc/set_event_tickets.*"),
                       lambda r: r.fulfill(status=500, content_type="application/json", body=TIMEOUT_BODY))
            sw = page.get_by_label("Billets QR", exact=True).first
            sw.scroll_into_view_if_needed()
            before = sql(f"select tickets_enabled from public.events where id = {q(a.eid())}")[0]["tickets_enabled"]
            p.tap(sw, "Billets QR (délai dépassé)")
            page.wait_for_timeout(2000)
            p.shot("billets-timeout")
            tree = p.dump("billets-timeout")
            a.check(p, "statement timeout" not in tree and "canceling" not in tree, "🟡",
                    "Billets QR : pas de message anglais", re.findall(r"alert[^\n]*", tree)[:3].__str__())
            p.log(f"alertes : {re.findall(r'alert[^\\n]*', tree)[:3]}")
            after = sql(f"select tickets_enabled from public.events where id = {q(a.eid())}")[0]["tickets_enabled"]
            try:
                on_screen = sw.is_checked()
            except Exception:
                on_screen = sw.get_attribute("aria-checked")
            p.log(f"interrupteur à l'écran {on_screen}, base avant {before} après {after}")
            a.check(p, str(on_screen).lower() == str(after).lower(), "🟠",
                    "Billets QR : l'interrupteur revient à l'état de la base après l'échec", f"écran {on_screen} base {after}")
            page.unroute(re.compile(r".*/rest/v1/rpc/set_event_tickets.*"))
        with p.step("Fiche : la lecture de l'événement dépasse son délai"):
            page.route(re.compile(r".*/rest/v1/events\?.*"),
                       lambda r: r.fulfill(status=500, content_type="application/json", body=TIMEOUT_BODY))
            page.reload()
            page.wait_for_timeout(6000)
            p.shot("fiche-timeout")
            tree = p.dump("fiche-timeout")
            a.check(p, "statement timeout" not in tree and "canceling" not in tree, "🟡",
                    "fiche : pas de message anglais en pleine page", tree[:300])
            a.check(p, re.search(r"Réessayer", tree) is not None, "🟡", "fiche : « Réessayer » proposé", tree[:300])
            page.unroute(re.compile(r".*/rest/v1/events\?.*"))
    finally:
        p.close()


# ── Bug 5 : « J'ai payé » et « Reçu ✓ » apparaissent sans recharger (relecture toutes les 20 s) ─────────────

def phase_sans_recharger(browser, origin, only):
    e = a.eid()
    vic = a.uid("vip1")
    sql(f"update public.event_tickets set paid = false, pay_declared_at = null where event_id = {q(e)} and user_id = {q(vic)}")
    org = phone(browser, "orga2", origin, "relance-tempsreel")
    v = phone(browser, "vip1", origin, "relance-tempsreel")
    try:
        a.open_event(org, "e_paid")
        a.open_event(v, "e_paid")
        org.shot("avant")
        r = a.as_user("vip1", f"public.declare_ticket_payment({q(e)}, true)")
        org.log(f"Victor déclare depuis un autre téléphone : {r[:60]}")
        t0 = time.time()
        seen = org.see(org.page.get_by_text(re.compile("Dit avoir payé")).first, "déclaration de Victor", POLL_WAIT_MS)
        org.log(f"vue après {time.time() - t0:.0f} s")
        org.shot("apres-declaration")
        a.check(org, seen, "🟡", "organisateur : « J'ai payé » de Victor visible sans recharger (≤ 45 s)")
        a.as_user("orga2", f"public.confirm_ticket_payment({q(e)}, {q(vic)}, true)")
        t0 = time.time()
        ok = v.see(v.page.get_by_text(re.compile("Place payée")).first, "« Place payée » sans recharger", POLL_WAIT_MS)
        v.log(f"vue après {time.time() - t0:.0f} s")
        v.shot("apres-recu")
        a.check(v, ok, "🟡", "invité : « Reçu ✓ » visible sans recharger (≤ 45 s)")
        # page cachée : pas de relecture (économie), puis reprise au retour
        n = {"n": 0}
        v.page.on("request", lambda req: n.__setitem__("n", n["n"] + 1) if "event_pay" in req.url or "event_tickets" in req.url
                  or "my_event_ticket" in req.url else None)
        v.page.wait_for_timeout(25000)
        v.log(f"requêtes de paiement en 25 s (page visible) : {n['n']}")
    finally:
        org.close()
        v.close()


# ── Bug 6 : supprimer un événement ne laisse plus de pot actif ─────────────────────────────────────────────

def _create_with_pot(s, title: str) -> str:
    r = httpx.post(f"{TEST_URL}/rest/v1/events", headers={**s.headers, "Prefer": "return=representation"}, timeout=30,
                   json={"title": title, "starts_at": f"{f.day(9)}T19:00:00+01:00", "status": "draft", "pot_enabled": True,
                         "visibility": "invited", "created_by": s.uid})
    print(f"création « {title} » : {r.status_code} {r.text[:200]}", flush=True)
    return r.json()[0]["id"] if r.status_code < 300 else ""


def phase_pot_suppression(browser, origin, only):
    oscar = a.session("orga2")
    for with_expense in (False, True):
        title = f"{a.PREFIX} Pot {'avec' if with_expense else 'sans'} dépense"
        e = _create_with_pot(oscar, title)
        if not e:
            anomaly("orga2", "🟠", "création brouillon avec pot impossible (API)", title)
            continue
        grp = sql(f"select id from public.tc_groups where event_id = {q(e)}")
        print("pot :", grp, flush=True)
        if not grp:
            anomaly("orga2", "🟠", "brouillon avec pot : pas de pot créé", title)
            continue
        g = grp[0]["id"]
        if with_expense:
            st = a._tc(origin, "/open", token=oscar.token, group_id=g).json()
            me = st.get("me")
            r = a._tc(origin, "/expense", token=oscar.token, group_id=g, expense={
                "title": f"Courses {a.PREFIX}", "amount_cents": 3000, "currency": "CHF", "paid_by": me, "split_mode": "equal",
                "spent_on": f.day(0), "category": "food", "shares": [{"member_id": me, "weight": 1}]})
            print("dépense :", r.status_code, flush=True)
        d = httpx.delete(f"{TEST_URL}/rest/v1/events?id=eq.{e}", headers={**oscar.headers, "Prefer": "return=minimal"}, timeout=30)
        print(f"suppression par Oscar : {d.status_code} {d.text[:160]}", flush=True)
        left = sql(f"select archived, event_id from public.tc_groups where id = {q(g)}")
        print("pot après suppression :", left, flush=True)
        ok = (left and left[0]["archived"]) if with_expense else not left
        if not ok:
            anomaly("orga2", "🟡", f"pot {'avec' if with_expense else 'sans'} dépense après suppression de l'événement", str(left))
        lst = a._tc(origin, "", token=oscar.token).json().get("tricounts", [])
        mine = [t for t in lst if t["id"] == g]
        print("dans la liste du pot commun d'Oscar :", mine[:1], flush=True)


PHASES = ("blocage", "reponse_lente", "erreurs", "sans_recharger", "pot_suppression")


def main(argv: list[str]) -> None:
    origin = load_state()["origin"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv or PHASES:
            print(f"════ phase {name} ════", flush=True)
            try:
                globals()[f"phase_{name}"](browser, origin, None)
            except Exception as e:  # une phase cassée devient une anomalie, les suivantes continuent
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
