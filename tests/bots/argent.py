"""Campagne 2, domaine « Argent et entrée » : événement payant, « Payer l'organisateur », « J'ai payé », « Reçu ✓ »,
« Pas reçu », billets QR (option, remise, retrait, remise à tous, renouvellement), scan à l'entrée, Apple Wallet
(refus côté serveur), pot commun (Tricount) de l'événement.

Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.argent <phase…>   (serveur du banc lancé, state.json)
Base de TEST uniquement ; événements préfixés « [C2-05] »."""
from __future__ import annotations

import base64
import re
import sys
import traceback

import httpx
from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots.bench import anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, GROUP_BOTS, TEST_URL, Session, q, sql

PREFIX = "[C2-05]"
PAID_TITLE = f"{PREFIX} Soirée payante"
FREE_TITLE = f"{PREFIX} Soirée gratuite"
PRICE = 20
PRESENT = ("vip1", "membre1", "vip2", "guest1")   # Victor (iPhone), Marc (iPhone), Vera (Android), Gus (Android)
_SESSIONS: dict[str, Session] = {}


class _Login(Session):
    """Session d'un bot qui garde aussi la réponse complète (pour la poser dans le navigateur, sans écran de code :
    les autres agents de la campagne se partagent les mêmes numéros et la limite d'un code par minute)."""

    def __init__(self, phone_number: str):
        import time
        from tests.bots.common import OTP, publishable_key
        base = {"apikey": publishable_key(), "Content-Type": "application/json"}
        r = None
        for _ in range(8):
            sent = httpx.post(f"{TEST_URL}/auth/v1/otp", headers=base, json={"phone": phone_number}, timeout=30)
            if sent.status_code == 200:
                r = httpx.post(f"{TEST_URL}/auth/v1/verify", headers=base,
                               json={"type": "sms", "phone": phone_number, "token": OTP}, timeout=30)
                if r.status_code == 200:
                    break
            time.sleep(20)
        if r is None or r.status_code != 200:
            raise RuntimeError(f"Connexion {phone_number} impossible")
        self.raw = r.json()
        self.uid = self.raw["user"]["id"]
        self.token = self.raw["access_token"]
        self.headers = {**base, "Authorization": f"Bearer {self.token}"}


def session(key: str) -> _Login:
    if key not in _SESSIONS:
        _SESSIONS[key] = _Login(BY_KEY[key].phone)
    return _SESSIONS[key]


STORAGE_KEY = "sb-ewromqfsmcqsthftyhzm-auth-token"


def signed_in(p) -> None:
    """Le bot est connecté : session gardée (storage.json) ou posée dans le stockage du navigateur."""
    import json
    p.goto("/events/")
    try:
        p.page.get_by_label("Ton numéro de téléphone", exact=True).wait_for(state="visible", timeout=6000)
    except Exception:
        p.log("déjà connecté")
        return
    s = session(p.bot.key)
    p.page.evaluate("([k, v]) => localStorage.setItem(k, v)", [STORAGE_KEY, json.dumps(s.raw)])
    p.log("session posée (code fixe obtenu par l'API)")
    p.page.reload()
    settle(p)


def eid(name: str = "e_paid") -> str:
    return load_state()[name]


def uid(key: str) -> str:
    return sql(f"select id from public.profiles where phone = {q(BY_KEY[key].phone)}")[0]["id"]


def ticket(key: str, event: str | None = None) -> dict:
    rows = sql(f"""select t.paid, t.pay_declared_at, t.issued_at, t.issued_by_payment, t.checked_in_at, t.code, t.token
                   from public.event_tickets t join public.profiles p on p.id = t.user_id
                   where t.event_id = {q(event or eid())} and p.phone = {q(BY_KEY[key].phone)}""")
    return rows[0] if rows else {}


def notifs(kind: str, key: str, event: str | None = None) -> list:
    return sql(f"""select n.body, n.created_at from public.notifications n join public.profiles p on p.id = n.user_id
                   where n.kind = {q(kind)} and n.event_id = {q(event or eid())} and p.phone = {q(BY_KEY[key].phone)}
                   order by n.created_at""")


def open_event(p, name: str = "e_paid") -> None:
    import time
    signed_in(p)
    start = time.time()
    p.goto(f"/events/event/{eid(name)}")
    title = PAID_TITLE if name == "e_paid" else FREE_TITLE
    try:
        p.page.get_by_text(title).first.wait_for(state="visible", timeout=60000)
    except Exception:
        p.flag("🟠", f"fiche « {title} » pas chargée en 60 s")
    took = time.time() - start
    p.log(f"fiche chargée en {took:.1f} s")
    if took > 8:
        anomaly(p.bot.key, "🟡", "fiche d'événement lente à charger", f"{took:.1f} s")
    p.page.wait_for_timeout(1500)


def settle(p, timeout: int = 90000) -> None:
    """Attend la fin des requêtes (base de TEST chargée par la campagne : parfois 20 à 60 s)."""
    import time
    start = time.time()
    p.page.wait_for_timeout(800)
    try:
        p.page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        p.log("réseau toujours occupé après 90 s")
    took = time.time() - start
    if took > 10:
        p.log(f"(attente réseau {took:.0f} s)")


def btn(p, name: str, exact: bool = True):
    return p.page.get_by_role("button", name=name, exact=exact)


def row_button(p, person: str, label: str):
    """Bouton « label » sur la ligne de « person » (le plus petit bloc qui contient les deux)."""
    page = p.page
    return page.locator("div").filter(has_text=person).filter(has=page.get_by_role("button", name=label, exact=True)) \
        .last.get_by_role("button", name=label, exact=True).first


def check(p, ok: bool, severity: str, title: str, detail: str = "") -> None:
    if ok:
        p.log(f"✓ {title}")
    else:
        p.flag(severity, title, detail)


def text_on_screen(p, pattern: str, timeout: int = 8000) -> bool:
    return p.see(p.page.get_by_text(re.compile(pattern)).first, f"« {pattern} »", timeout)


# ── 0. Préparation : profil de paiement de l'organisatrice, événement payant (vrai formulaire) ─────────────────

def phase_prep(browser, origin, only):
    olga = session("orga2")  # organisateur principal : Oscar (Olga a bloqué Bot Gus, voir RAPPORT)
    r = httpx.post(f"{origin}/api/account/tricount/payment/save", timeout=30, json={
        "token": olga.token, "iban": "CH93 0076 2011 6238 5295 7", "holder": "Bot Oscar Orga",
        "links": {"twint": "079 000 01 04", "revolut": "botoscar"}, "note": "Merci les bots !"})
    print("profil de paiement :", r.status_code, r.text[:300], flush=True)
    bad = httpx.post(f"{origin}/api/account/tricount/payment/save", timeout=30, json={
        "token": olga.token, "iban": "CH00 1234", "holder": "", "links": {}, "note": ""})
    print("IBAN invalide :", bad.status_code, bad.text[:200], flush=True)
    if bad.status_code < 400:
        anomaly("orga1", "🟠", "profil de paiement : IBAN invalide accepté", bad.text[:200])
        httpx.post(f"{origin}/api/account/tricount/payment/save", timeout=30, json={
            "token": olga.token, "iban": "CH93 0076 2011 6238 5295 7", "holder": "Bot Oscar Orga",
            "links": {"twint": "079 000 01 04", "revolut": "botoscar"}, "note": "Merci les bots !"})

    p = phone(browser, "orga2", origin, "argent-creation")
    page = p.page
    try:
        signed_in(p)
        p.goto("/events/event/new")
        p.see(page.get_by_label("Titre", exact=True), "le formulaire")
        p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
        f.fill(p, "Titre", PAID_TITLE)
        f.fill(p, "Description", "Banc des bots, domaine argent et entrée. Ignorer.")
        f.set_date(p, "Début", f.day(6), "20:00")
        f.fill(p, "Lieu", "Caisse des bots")
        with p.step("prix invalide refusé"):
            f.fill(p, "Prix / pers. (CHF)", "-5")
            p.tap(btn(p, "Publier").last, "Publier (prix -5)")
            page.wait_for_timeout(1500)
            check(p, text_on_screen(p, "montant positif"), "🟠", "prix négatif : message « montant positif » affiché")
            p.shot("prix-negatif")
        f.fill(p, "Prix / pers. (CHF)", "20")
        f.fill(p, "Paiement", "TWINT 079 000 01 04 ou espèces à l'entrée")
        f.toggle(p, "Billets QR", False)
        f.audience_invite_groups(p, [GROUP_BOTS])
        p.tap(f.chip(p, "Bot Olga", exact=True).first, "co-organisatrice Bot Olga")
        f.toggle(p, "Pot commun", True)
        if page.get_by_label("Prévenir le groupe", exact=True).count():
            f.toggle(p, "Prévenir le groupe", False)
        p.shot("formulaire-rempli")
        new = f.submit(p, "Publier")
        p.log(f"événement payant : {new}")
        if new:
            save_state(e_paid=new)
            row = sql(f"select price_chf, payment_info, tickets_enabled, pot_enabled, status from public.events where id = {q(new)}")[0]
            p.log(f"base : {row}")
            check(p, float(row["price_chf"]) == PRICE and not row["tickets_enabled"] and row["pot_enabled"], "🔴",
                  "base : prix 20, billets QR éteints, pot commun actif", str(row))
            pot = sql(f"select id, archived, (select count(*) from public.tc_members m where m.group_id = g.id) n from public.tc_groups g where event_id = {q(new)}")
            p.log(f"pot commun : {pot}")
            check(p, bool(pot) and not pot[0]["archived"], "🔴", "pot commun créé avec l'événement", str(pot))
            p.shot("fiche-organisatrice")
            p.dump("fiche-organisatrice")
        # Événement gratuit, billets QR allumés dès le formulaire
        p.goto("/events/event/new")
        p.see(page.get_by_label("Titre", exact=True), "le formulaire")
        p.tap(page.get_by_role("tab", name="Avancé"), "Avancé")
        f.fill(p, "Titre", FREE_TITLE)
        f.set_date(p, "Début", f.day(7), "19:00")
        f.fill(p, "Lieu", "Entrée libre des bots")
        f.toggle(p, "Billets QR", True)
        f.audience_invite_groups(p, [GROUP_BOTS])
        if page.get_by_label("Prévenir le groupe", exact=True).count():
            f.toggle(p, "Prévenir le groupe", False)
        free = f.submit(p, "Publier")
        p.log(f"événement gratuit : {free}")
        if free:
            save_state(e_free=free)
            row = sql(f"select price_chf, tickets_enabled from public.events where id = {q(free)}")[0]
            check(p, row["tickets_enabled"] and row["price_chf"] is None, "🔴", "base : gratuit, billets QR allumés", str(row))
    finally:
        p.close()


# ── 1. Réponses « Présent » : billets éteints → seulement « Payer l'organisateur » ─────────────────────────────

def phase_reponses(browser, origin, only):
    for key in (only or PRESENT):
        p = phone(browser, key, origin, "argent-reponse")
        page = p.page
        try:
            signed_in(p)
            for name in ("e_paid", "e_free"):
                open_event(p, name)
                with p.step(f"Présent ({name})"):
                    p.tap(page.get_by_role("radiogroup").get_by_role("button", name="Présent", exact=True).first, "Présent")
                    settle(p)
                    if f.accept_terms_if_asked(p):
                        settle(p)
                    p.shot(f"present-{name}")
                    import time
                    start = time.time()
                    while time.time() - start < 120 and not sql(
                            f"""select 1 from public.rsvps r join public.profiles pr on pr.id = r.user_id
                                where r.event_id = {q(eid(name))} and pr.phone = {q(BY_KEY[key].phone)} and r.status = 'yes'"""):
                        page.wait_for_timeout(3000)
                    p.log(f"réponse en base après {time.time() - start:.0f} s")
            open_event(p, "e_paid")
            pay = page.get_by_role("button", name=re.compile(r"^Payer l’organisateur · 20 CHF"))
            check(p, p.see(pay, "« Payer l'organisateur · 20 CHF »"), "🔴", "billets éteints : « Payer l'organisateur · 20 CHF » visible")
            check(p, page.get_by_label("Afficher ton billet à montrer à l’entrée").count() == 0 and
                  page.get_by_test_id("ticket-pending").count() == 0, "🔴", "billets éteints : aucun billet ni attente affiché")
            open_event(p, "e_free")
            check(p, page.get_by_role("button", name=re.compile("^Payer l’organisateur")).count() == 0, "🟠",
                  "événement gratuit : pas de bouton de paiement")
            check(p, p.see(page.get_by_test_id("ticket-pending"), "billet en attente (gratuit, QR allumé)"), "🔴",
                  "gratuit + billets QR : carte « Ton billet arrivera… » affichée")
            p.shot("gratuit-attente")
        finally:
            p.close()
    rows = sql(f"""select p.display_name, r.status, r.waitlisted from public.rsvps r join public.profiles p on p.id = r.user_id
                   where r.event_id = {q(eid())}""")
    print("réponses en base :", rows, flush=True)
    pot = sql(f"""select m.name from public.tc_members m join public.tc_groups g on g.id = m.group_id
                  where g.event_id = {q(eid())} order by m.created_at""")
    print("membres du pot :", pot, flush=True)
    names = {m["name"] for m in pot}
    for key in PRESENT:
        if BY_KEY[key].nickname not in names:
            anomaly(key, "🔴", "pot commun : un présent n'y est pas entré", str(pot))


# ── 2. Payer l'organisateur : feuille, copier, fermer, J'ai payé, Annuler, double toucher, déclarer à nouveau ─

def _open_pay_sheet(p):
    page = p.page
    p.tap(page.get_by_role("button", name=re.compile(r"^Payer l’organisateur")).first, "Payer l'organisateur")
    page.wait_for_timeout(1500)
    return page.get_by_label("Payer l’organisateur", exact=True)


def phase_payer(browser, origin, only):
    # Marc (iPhone) : tout le parcours
    for key in [k for k in ("vip2", "guest1") if only and k in only]:
        _declare(browser, origin, key)
    if only and "membre1" not in only:
        return
    p = phone(browser, "membre1", origin, "argent-payer")
    page = p.page
    try:
        open_event(p, "e_paid")
        with p.step("feuille de paiement : contenu"):
            sheet = _open_pay_sheet(p)
            p.shot("feuille")
            tree = p.dump("feuille")
            for want, what in (("20 CHF", "montant"), ("TWINT 079 000 01 04", "infos de l'événement"),
                               ("Merci les bots", "note du profil"), ("Twint", "Twint"), ("Payer avec Revolut", "Revolut"),
                               ("CH93 0076 2011 6238 5295 7", "IBAN groupé"), ("Party · ", "communication")):
                check(p, want in tree, "🟠", f"feuille de paiement : {what} affiché", want)
            _check_scroll = p.scroll_to_bottom("feuille de paiement")
        with p.step("Copier l'IBAN et la communication"):
            p.tap(page.get_by_role("button", name=re.compile("^Copier Virement")), "Copier l'IBAN")
            page.wait_for_timeout(600)
            clip = page.evaluate("navigator.clipboard.readText()")
            p.log(f"presse-papiers : {clip!r}")
            check(p, clip.replace(" ", "") == "CH9300762011623852957", "🟠", "IBAN copié sans espaces", clip)
            check(p, text_on_screen(p, "Copié ✓"), "🟡", "retour « Copié ✓ » visible")
            p.tap(page.get_by_role("button", name=re.compile("^Copier Communication")), "Copier la communication")
            page.wait_for_timeout(600)
            clip = page.evaluate("navigator.clipboard.readText()")
            check(p, clip == f"Party · {PAID_TITLE}", "🟡", "communication copiée", clip)
            p.tap(page.get_by_role("button", name=re.compile("^Copier Twint")), "Copier Twint")
            page.wait_for_timeout(600)
            clip = page.evaluate("navigator.clipboard.readText()")
            check(p, clip == "0790000104", "🟡", "numéro Twint copié", clip)
        with p.step("Revolut : lien sûr"):
            with page.context.expect_page(timeout=5000) as popup:
                p.tap(btn(p, "Payer avec Revolut"), "Payer avec Revolut")
            url = popup.value.url
            p.log(f"Revolut ouvre {url}")
            check(p, url.startswith("https://revolut.me/botoscar"), "🟠", "Revolut ouvre revolut.me/botoscar", url)
            popup.value.close()
        with p.step("Fermer puis rouvrir"):
            p.tap(btn(p, "Fermer").last, "Fermer")
            page.wait_for_timeout(800)
            check(p, page.get_by_label("Payer l’organisateur", exact=True).count() == 0, "🟠", "« Fermer » ferme la feuille")
            _open_pay_sheet(p)
        with p.step("J'ai payé (double toucher)"):
            b = btn(p, "J’ai payé")
            b.wait_for(state="visible")
            b.tap()
            try:
                b.tap(timeout=800)
                p.log("2e toucher envoyé")
            except Exception:
                p.log("2e toucher impossible (bouton occupé ou fermé) : attendu")
            settle(p)
            p.shot("apres-jai-paye")
            check(p, text_on_screen(p, "Payé · en attente de confirmation"), "🔴", "« Payé · en attente de confirmation » affiché")
            t = ticket("membre1")
            p.log(f"base : {t}")
            check(p, t.get("pay_declared_at") is not None and not t.get("paid"), "🔴", "base : paiement déclaré, pas payé", str(t))
            n_oscar, n_olga = notifs("ticket_pay_declared", "orga2"), notifs("ticket_pay_declared", "orga1")
            p.log(f"notifications organisatrice {len(n_olga)}, co-organisateur {len(n_oscar)}")
            check(p, len(n_oscar) == 1, "🟠", "une seule notification « dit avoir payé » à l'organisateur (double toucher)", str(n_oscar))
            check(p, len(n_olga) == 1, "🟡", "la co-organisatrice est prévenue aussi", str(n_olga))
        with p.step("Annuler la déclaration puis rechargement"):
            p.tap(btn(p, "Annuler"), "Annuler")
            settle(p)
            check(p, ticket("membre1").get("pay_declared_at") is None, "🔴", "base : déclaration annulée")
            page.reload()
            settle(p)
            check(p, p.see(page.get_by_role("button", name=re.compile(r"^Payer l’organisateur")), "Payer de nouveau"), "🔴",
                  "après Annuler + rechargement : « Payer l'organisateur » revient")
        with p.step("redéclarer"):
            _open_pay_sheet(p)
            p.tap(btn(p, "J’ai payé"), "J'ai payé")
            settle(p)
            check(p, text_on_screen(p, "en attente de confirmation"), "🔴", "redéclaration affichée")
            n = notifs("ticket_pay_declared", "orga2")
            p.log(f"notifications organisateur après redéclaration : {len(n)}")
        _check_texts(p, "fiche invité payant")
    finally:
        p.close()
    for key in ("vip2", "guest1"):    # Vera, Gus (Android) : J'ai payé tout de suite
        _declare(browser, origin, key)


def _declare(browser, origin, key):
    if True:
        p = phone(browser, key, origin, "argent-payer")
        page = p.page
        try:
            open_event(p, "e_paid")
            with p.step("J'ai payé"):
                _open_pay_sheet(p)
                btn(p, "J’ai payé").wait_for(state="visible", timeout=60000)
                p.shot("feuille-android")
                p.tap(btn(p, "J’ai payé"), "J'ai payé")
                settle(p)
                check(p, text_on_screen(p, "en attente de confirmation"), "🔴", "« en attente de confirmation » affiché")
        finally:
            p.close()


def _check_texts(p, what: str) -> None:
    cut = p.check_texts_cut(what)
    if cut:
        p.flag("🟡", f"{what} : textes coupés", "; ".join(cut))


# ── 3. L'organisatrice confirme : Reçu ✓ (Marc), Pas reçu (Vera) ; Gus reste en attente ────────────────────────

def phase_confirmer(browser, origin, only):
    if only:
        return _confirmed_views(browser, origin, only)
    p = phone(browser, "orga1", origin, "argent-confirmer")
    page = p.page
    try:
        open_event(p, "e_paid")
        p.dump("paiements")
        with p.step("section Paiements"):
            check(p, text_on_screen(p, r"3 à confirmer · 20 CHF chacun"), "🟠", "« 3 à confirmer · 20 CHF chacun »")
            p.shot("paiements-a-confirmer")
        with p.step("Reçu ✓ pour Bot Marc"):
            p.tap(row_button(p, "Bot Marc", "Reçu ✓"), "Reçu ✓ (Marc)")
            settle(p)
            t = ticket("membre1")
            p.log(f"base Marc : {t}")
            check(p, t.get("paid") and t.get("issued_at") is not None and t.get("issued_by_payment"), "🔴",
                  "base : Marc payé, billet remis PAR LE PAIEMENT (même option éteinte)", str(t))
            check(p, any("bien reçu" in n["body"] for n in notifs("ticket_pay_confirmed", "membre1")), "🟠",
                  "Marc prévenu « a bien reçu ton paiement »")
        with p.step("Pas reçu pour Bot Vera"):
            p.tap(row_button(p, "Bot Vera", "Pas reçu"), "Pas reçu (Vera)")
            settle(p)
            t = ticket("vip2")
            p.log(f"base Vera : {t}")
            check(p, not t.get("paid") and t.get("pay_declared_at") is None and t.get("issued_at") is None, "🔴",
                  "base : Vera remise à « à payer », pas de billet", str(t))
            check(p, any("n'a pas reçu" in n["body"] for n in notifs("ticket_pay_confirmed", "vip2")), "🟠", "Vera prévenue « n'a pas reçu »")
            p.shot("apres-confirmations")
            check(p, text_on_screen(p, r"1 / 4 payé"), "🟡", "compteur « 1 / 4 payé »")
        _check_texts(p, "section paiements")
    finally:
        p.close()
    _confirmed_views(browser, origin, None)


def _confirmed_views(browser, origin, only):
    for key, pattern, what in (("membre1", r"✓ Place payée · 20 CHF", "Marc voit « ✓ Place payée · 20 CHF »"),
                               ("vip2", r"^Payer l’organisateur", "Vera peut payer de nouveau")):
        if only and key not in only:
            continue
        p = phone(browser, key, origin, "argent-confirmer")
        try:
            open_event(p, "e_paid")
            ok = text_on_screen(p, pattern) if key == "membre1" else \
                p.see(p.page.get_by_role("button", name=re.compile(pattern)), what)
            check(p, ok, "🔴", what)
            if key == "membre1":
                check(p, p.page.get_by_label("Afficher ton billet à montrer à l’entrée").count() == 0, "🔴",
                      "option éteinte : Marc n'a pas de QR malgré la place payée")
            p.shot("vu-par-invite")
        finally:
            p.close()


# ── 4. Le co-organisateur allume « Billets QR » après publication ─────────────────────────────────────────────

def phase_billets_on(browser, origin, only):
    p = phone(browser, "orga1", origin, "argent-option")
    page = p.page
    try:
        signed_in(p)
        open_event(p, "e_paid")
        with p.step("allumer Billets QR (co-organisateur)"):
            sw = page.get_by_label("Billets QR", exact=True).first
            sw.scroll_into_view_if_needed()
            p.shot("option-eteinte")
            p.tap(sw, "Billets QR → oui")
            settle(p)
            on = sql(f"select tickets_enabled from public.events where id = {q(eid())}")[0]["tickets_enabled"]
            check(p, on, "🔴", "base : option allumée par le co-organisateur", str(on))
            p.shot("option-allumee")
            check(p, text_on_screen(p, r"1 / 4 remis"), "🟠", "« 1 / 4 remis » (Marc, par le paiement)")
            check(p, p.see(btn(p, "Remettre à tous les présents (3)"), "Remettre à tous (3)"), "🟠", "« Remettre à tous les présents (3) »")
            check(p, len(notifs("ticket_issued", "membre1")) >= 1, "🟠", "Marc prévenu « Ton billet est prêt » à l'allumage")
        _check_texts(p, "billets QR (co-organisateur)")
    finally:
        p.close()
    for key, want in (("membre1", "ok"), ("vip1", "pending")):
        p = phone(browser, key, origin, "argent-option")
        page = p.page
        try:
            open_event(p, "e_paid")
            if want == "ok":
                check(p, p.see(page.get_by_label("Afficher ton billet à montrer à l’entrée"), "son billet QR"), "🔴", "Marc : QR affiché")
            else:
                check(p, p.see(page.get_by_test_id("ticket-pending"), "billet en attente"), "🔴", "Victor : « Ton billet arrivera… »")
                check(p, text_on_screen(p, "Paie ta place : le billet arrive"), "🟡", "Victor : invitation à payer sa place")
            p.shot(f"billet-{want}")
        finally:
            p.close()


# ── 5. Remise : un par un, retirer, remettre à tous ; « payé » décoché retire le billet remis par le paiement ──

def phase_remise(browser, origin, only):
    p = phone(browser, "orga1", origin, "argent-remise")
    page = p.page
    try:
        open_event(p, "e_paid")
        with p.step("Remettre le billet à Bot Victor"):
            p.tap(row_button(p, "Bot Victor", "Remettre le billet"), "Remettre le billet (Victor)")
            settle(p)
            t = ticket("vip1")
            check(p, t.get("issued_at") is not None and not t.get("issued_by_payment"), "🔴", "base : Victor billet remis à la main", str(t))
            check(p, len(notifs("ticket_issued", "vip1")) == 1, "🟠", "Victor prévenu « Ton billet est prêt »")
        with p.step("Retirer le billet de Bot Victor"):
            p.tap(row_button(p, "Bot Victor", "Retirer"), "Retirer (Victor)")
            settle(p)
            check(p, ticket("vip1").get("issued_at") is None, "🔴", "base : billet de Victor retiré")
            p.shot("retire")
        with p.step("Remettre à tous les présents"):
            all_btn = page.get_by_role("button", name=re.compile(r"^Remettre à tous les présents"))
            label = all_btn.first.get_attribute("aria-label")
            p.log(f"bouton : {label}")
            p.tap(all_btn.first, label or "Remettre à tous")
            settle(p)
            check(p, text_on_screen(p, r"3 billets remis : chacun est prévenu"), "🟠", "« 3 billets remis : chacun est prévenu. »")
            check(p, p.see(btn(p, "Tous les présents ont leur billet ✓"), "tous remis"), "🟠", "bouton « Tous les présents ont leur billet ✓ »")
            issued = [k for k in PRESENT if ticket(k).get("issued_at")]
            check(p, len(issued) == 4, "🔴", "base : 4 billets remis", str(issued))
            n = notifs("ticket_issued", "vip1")
            p.log(f"Victor : {len(n)} notification(s) « billet prêt » (remis, retiré, remis)")
            p.shot("tous-remis")
        _check_texts(p, "billets remis")
    finally:
        p.close()
    # Entrée : « Payé ✓ » décoché sur Marc → billet remis par le paiement retiré + message ; puis recoché
    p = phone(browser, "orga1", origin, "argent-entree")
    page = p.page
    try:
        signed_in(p)
        p.goto(f"/events/event/{eid()}/scan")
        settle(p)
        p.shot("entree")
        p.dump("entree")
        with p.step("Payé ✓ décoché (Marc)"):
            p.tap(row_button(p, "Bot Marc", "Payé ✓"), "Payé ✓ (décocher, Marc)")
            settle(p)
            t = ticket("membre1")
            p.log(f"base Marc : {t}")
            check(p, not t.get("paid") and t.get("issued_at") is None, "🔴", "base : paiement annulé → billet retiré", str(t))
            check(p, text_on_screen(p, "Billet retiré : il avait été remis par ce paiement"), "🟠",
                  "message « Billet retiré : il avait été remis par ce paiement… »")
            p.shot("paye-decoche")
        with p.step("Payé ? recoché (Marc)"):
            p.tap(row_button(p, "Bot Marc", "Payé ?"), "Payé ? (Marc)")
            settle(p)
            t = ticket("membre1")
            check(p, t.get("paid") and t.get("issued_at") is not None and t.get("issued_by_payment"), "🔴",
                  "base : payé à nouveau → billet remis par le paiement", str(t))
        with p.step("Reçu ✓ depuis l'entrée (Gus, déclaré)"):
            p.tap(row_button(p, "Bot Gus", "Reçu ✓"), "Reçu ✓ (Gus)")
            settle(p)
            t = ticket("guest1")
            check(p, t.get("paid") and t.get("issued_at") is not None and not t.get("issued_by_payment"), "🔴",
                  "base : Gus payé ; billet déjà remis à la main (pas « par le paiement »)", str(t))
        with p.step("Payé ✓ décoché (Gus, billet remis à la main) : le billet reste"):
            p.tap(row_button(p, "Bot Gus", "Payé ✓"), "Payé ✓ (décocher, Gus)")
            settle(p)
            t = ticket("guest1")
            check(p, not t.get("paid") and t.get("issued_at") is not None, "🔴", "base : billet remis à la main gardé", str(t))
            check(p, page.get_by_text("Billet retiré : il avait été remis").count() == 0, "🟠", "pas de message de retrait (billet à la main)")
            p.tap(row_button(p, "Bot Gus", "Payé ?"), "Payé ? (Gus)")
            settle(p)
        _check_texts(p, "écran d'entrée")
        p.scroll_to_bottom("écran d'entrée")
    finally:
        p.close()


# ── 6. Le QR chez l'invité : afficher, code, nouveau QR ─────────────────────────────────────────────────────

def _read_code(p) -> str:
    page = p.page
    p.tap(page.get_by_label("Afficher ton billet à montrer à l’entrée").first, "Afficher ton billet")
    page.wait_for_timeout(1500)
    label = page.get_by_label(re.compile(r"^Code [A-Z0-9 ]+$")).first.get_attribute("aria-label") or ""
    return label.removeprefix("Code ").replace(" ", "")


def phase_qr(browser, origin, only):
    codes = {}
    for key in PRESENT:
        p = phone(browser, key, origin, "argent-qr")
        page = p.page
        try:
            open_event(p, "e_paid")
            with p.step("afficher son billet"):
                code = _read_code(p)
                p.log(f"code affiché {code} ; base {ticket(key).get('code')}")
                check(p, code == ticket(key).get("code"), "🔴", "code affiché = code en base", code)
                check(p, page.get_by_label("QR code de ton billet").count() == 1, "🔴", "QR affiché en grand")
                codes[key] = code
                p.shot("billet-grand")
                check(p, page.get_by_label("Ajouter à l’app Cartes Apple").count() == 0, "🟠",
                      "bouton Wallet masqué (serveur sans certificats)")
            if key == "vip1":
                with p.step("Nouveau QR → Garder, puis Oui"):
                    p.tap(btn(p, "Nouveau QR (l’ancien ne marchera plus)"), "Nouveau QR")
                    p.tap(btn(p, "Garder"), "Garder")
                    check(p, ticket(key).get("code") == code, "🔴", "« Garder » ne change rien")
                    p.tap(btn(p, "Nouveau QR (l’ancien ne marchera plus)"), "Nouveau QR")
                    p.tap(btn(p, "Oui, changer (Cartes se met à jour)"), "Oui, changer")
                    settle(p)
                    page.get_by_label(re.compile(rf"^Code (?!{' '.join(code)}$)[A-Z0-9 ]+$")).first.wait_for(timeout=30000)
                    new = page.get_by_label(re.compile(r"^Code [A-Z0-9 ]+$")).first.get_attribute("aria-label") or ""
                    new = new.removeprefix("Code ").replace(" ", "")
                    p.log(f"nouveau code {new}")
                    check(p, new and new != code and new == ticket(key).get("code"), "🔴", "nouveau code affiché et en base", new)
                    save_state(old_code_victor=code)
                    codes[key] = new
                    p.shot("nouveau-qr")
            with p.step("Fermer"):
                p.tap(btn(p, "Fermer").last, "Fermer")
                page.wait_for_timeout(800)
            _check_texts(p, "fiche avec billet")
        finally:
            p.close()
    save_state(codes=codes)
    print("codes :", codes, flush=True)


# ── 7. Scan à l'entrée ──────────────────────────────────────────────────────────────────────────────────────

def _scan(p, code: str, expect: str, what: str, severity: str = "🔴") -> str:
    page = p.page
    nxt = btn(p, "Billet suivant")
    if nxt.count():
        p.tap(nxt.first, "Billet suivant")
        page.wait_for_timeout(500)
    p.type(page.get_by_label("Code du billet"), code, "le code")
    p.tap(btn(p, "Valider"), "Valider")
    settle(p)
    alert = page.get_by_role("alert")
    label = alert.first.get_attribute("aria-label") if alert.count() else ""
    p.log(f"verdict : {label}")
    check(p, bool(label) and label.startswith(expect), severity, what, str(label))
    return label or ""


def phase_scan(browser, origin, only):
    st = load_state()
    codes = st["codes"]
    p = phone(browser, "orga1", origin, "argent-scan")
    page = p.page
    try:
        signed_in(p)
        p.goto(f"/events/event/{eid()}/scan")
        settle(p)
        check(p, btn(p, "Valider").is_disabled(), "🟡", "« Valider » grisé sans code")
        _scan(p, codes["vip1"], "Bienvenue", "nouveau code de Victor → « Bienvenue ! »")
        p.shot("bienvenue")
        t = ticket("vip1")
        check(p, t.get("checked_in_at") is not None, "🔴", "base : arrivée de Victor enregistrée", str(t))
        _scan(p, codes["vip1"], "Déjà scanné", "même code → « Déjà scanné »")
        p.shot("deja")
        _scan(p, st["old_code_victor"], "Billet inconnu", "ancien code de Victor → « inconnu ou remplacé »")
        _scan(p, codes["membre1"].lower(), "Bienvenue", "code en minuscules (Marc) → accepté")
        _scan(p, f"{codes['guest1'][:3]}-{codes['guest1'][3:]}", "Bienvenue", "code avec tiret (Gus) → accepté")
        _scan(p, "ABC", "Ce QR n’est pas un billet Party", "« ABC » → pas un billet Party", "🟡")
        _scan(p, "ZZZZZZ", "Billet inconnu", "code inexistant → inconnu", "🟠")
        free_code = sql(f"select code from public.event_tickets where event_id = {q(eid('e_free'))} limit 1")
        token_free = sql(f"select token from public.event_tickets where event_id = {q(eid('e_free'))} limit 1")
        if token_free:
            _scan(p, f"http://x/?tab=events&event={eid('e_free')}&ticket={token_free[0]['token']}", "Billet d’un autre événement",
                  "QR (lien) d'un autre événement → « autre événement »")
        else:
            p.log(f"pas de billet sur l'événement gratuit pour tester « autre événement » ({free_code})")
        # Billet non remis : Vera (retiré par l'organisatrice), puis « Remettre le billet » depuis le verdict
        with p.step("billet non remis puis remis sur place (Vera)"):
            p.tap(btn(p, "Billet suivant"), "Billet suivant")
            p.tap(row_button(p, "Bot Vera", "Retirer"), "Retirer (Vera)")
            settle(p)
            _scan(p, codes["vip2"], "Billet pas encore remis", "billet retiré → « Billet pas encore remis »")
            p.shot("non-remis")
            p.tap(btn(p, "Remettre le billet").first, "Remettre le billet (verdict)")
            settle(p)
            label = page.get_by_role("alert").first.get_attribute("aria-label") or ""
            p.log(f"verdict après remise : {label}")
            check(p, label.startswith("Bienvenue"), "🟠", "remise sur place → QR repasse → « Bienvenue ! »", label)
            check(p, ticket("vip2").get("checked_in_at") is not None, "🟠", "base : arrivée de Vera notée")
        with p.step("verdict : Marquer payé / Annuler « payé » (Victor)"):
            _scan(p, codes["vip1"], "Déjà scanné", "Victor de nouveau → « Déjà scanné »")
            p.tap(btn(p, "Marquer payé"), "Marquer payé")
            settle(p)
            check(p, ticket("vip1").get("paid"), "🔴", "base : Victor payé depuis le verdict")
            check(p, p.see(btn(p, "Annuler « payé »"), "Annuler « payé »"), "🟠", "le verdict se met à jour (« Annuler « payé » »)")
            p.tap(btn(p, "Annuler « payé »"), "Annuler « payé »")
            settle(p)
            t = ticket("vip1")
            check(p, not t.get("paid") and t.get("issued_at") is not None, "🔴", "Victor : payé annulé, billet (remis à la main) gardé", str(t))
        with p.step("arrivée manuelle (Annuler / Arrivé) sur Marc"):
            p.tap(btn(p, "Billet suivant"), "Billet suivant")
            p.tap(row_button(p, "Bot Marc", "Annuler"), "Annuler l'arrivée (Marc)")
            settle(p)
            check(p, ticket("membre1").get("checked_in_at") is None, "🔴", "base : arrivée de Marc annulée")
            p.tap(row_button(p, "Bot Marc", "Arrivé"), "Arrivé (Marc)")
            settle(p)
            check(p, ticket("membre1").get("checked_in_at") is not None, "🔴", "base : arrivée manuelle de Marc")
        with p.step("Gus répond Absent → son code : « Pas inscrit·e »"):
            gus = session("guest1")
            r = httpx.patch(f"{TEST_URL}/rest/v1/rsvps?event_id=eq.{eid()}&user_id=eq.{gus.uid}",
                            headers={**gus.headers, "Prefer": "return=representation"}, json={"status": "no"}, timeout=30)
            p.log(f"Gus Absent (API) : {r.status_code} {r.text[:160]}")
            _scan(p, codes["guest1"], "Pas inscrit", "absent → « Pas inscrit·e comme présent·e »")
            p.shot("pas-inscrit")
        p.scroll_to_bottom("écran d'entrée")
        _check_texts(p, "verdicts")
        heads = page.get_by_text(re.compile(r"\d+ / \d+ personnes")).first.inner_text()
        p.log(f"compteur des arrivées : {heads}")
    finally:
        p.close()
    # Un invité sur l'écran du billet ouvert par l'appareil photo (lien /scan/<jeton>) : refus
    p = phone(browser, "membre1", origin, "argent-scan-invite")
    page = p.page
    try:
        tok = ticket("vip1").get("token")
        p.goto(f"/events/event/{eid()}/scan/{tok}")
        settle(p)
        p.shot("invite-sur-scan")
        p.dump("invite-sur-scan")
        check(p, page.get_by_label("Code du billet").count() == 0, "🔴", "un invité n'a pas de champ de scan")
        t = ticket("vip1")
        p.log(f"Victor après la visite de Marc : {t}")
    finally:
        p.close()


# ── 8. Option éteinte puis rallumée (co-organisateur), scan refusé ─────────────────────────────────────────

def phase_option_off(browser, origin, only):
    codes = load_state()["codes"]
    p = phone(browser, "orga2", origin, "argent-option-off")
    page = p.page
    try:
        signed_in(p)
        p.goto(f"/events/event/{eid()}/scan")
        settle(p)
        with p.step("éteindre Billets QR depuis l'entrée"):
            p.tap(page.get_by_label("Billets QR", exact=True).first, "Billets QR → non")
            settle(p)
            off = sql(f"select tickets_enabled from public.events where id = {q(eid())}")[0]["tickets_enabled"]
            check(p, not off, "🔴", "base : option éteinte par le co-organisateur")
            p.shot("option-off")
            _scan(p, codes["membre1"], "Billets QR désactivés", "option éteinte → « Billets QR désactivés »")
            check(p, page.get_by_role("button", name=re.compile("Remettre")).count() == 0, "🟡", "pas de bouton de remise option éteinte")
    finally:
        p.close()
    p = phone(browser, "vip1", origin, "argent-option-off")
    try:
        open_event(p, "e_paid")
        check(p, p.page.get_by_label("Afficher ton billet à montrer à l’entrée").count() == 0, "🔴", "option éteinte : QR caché chez Victor")
        check(p, p.see(p.page.get_by_role("button", name=re.compile(r"^Payer l’organisateur")), "payer"), "🟠",
              "option éteinte : Victor (pas payé) garde « Payer l'organisateur »")
        p.shot("victor-option-off")
        r = session("vip1").rpc("my_event_ticket", e=eid())
        check(p, "token" not in r.text, "🔴", "API : aucun jeton rendu option éteinte", r.text[:200])
    finally:
        p.close()
    p = phone(browser, "orga2", origin, "argent-option-off")
    try:
        open_event(p, "e_paid")
        p.tap(p.page.get_by_label("Billets QR", exact=True).first, "Billets QR → oui")
        settle(p)
        on = sql(f"select tickets_enabled from public.events where id = {q(eid())}")[0]["tickets_enabled"]
        check(p, on, "🔴", "base : option rallumée")
        n = notifs("ticket_issued", "vip1")
        p.log(f"Victor : {len(n)} notification(s) « billet prêt » après le rallumage : {[x['created_at'] for x in n]}")
        p.shot("option-rallumee")
    finally:
        p.close()


# ── 9. Droits (API avec le jeton du bot) ────────────────────────────────────────────────────────────────────

def phase_droits(browser, origin, only):
    e, victor, marc = eid(), session("vip1"), uid("membre1")
    for name, args in (("issue_event_ticket", {"e": e, "member": marc, "issued": False}),
                       ("issue_all_event_tickets", {"e": e}),
                       ("set_event_tickets", {"e": e, "enabled": False}),
                       ("confirm_ticket_payment", {"e": e, "member": marc, "received": False}),
                       ("set_ticket_paid", {"e": e, "member": marc, "is_paid": False}),
                       ("set_ticket_arrival", {"e": e, "member": marc, "arrived": False}),
                       ("check_in_ticket", {"e": e, "scanned": load_state()["codes"]["membre1"]}),
                       ("event_checkins", {"e": e}),
                       ("renew_event_ticket", {"e": e, "member": marc})):
        r = victor.rpc(name, **args)
        print(f"Victor (invité) {name} → {r.status_code} {r.text[:120]}", flush=True)
        if r.status_code < 400:
            anomaly("vip1", "🔴", f"un invité peut appeler {name}", r.text[:200])
    # Déclarer sur un événement gratuit, ou sans être présent
    r = victor.rpc("declare_ticket_payment", e=eid("e_free"), declared=True)
    print("déclarer sur gratuit :", r.status_code, r.text[:160], flush=True)
    if r.status_code < 400:
        anomaly("vip1", "🟠", "« J'ai payé » accepté sur un événement gratuit", r.text[:200])
    r = session("orga1").rpc("event_pay_info", e=eid("e_free"))
    print("event_pay_info gratuit :", r.status_code, r.text[:120], flush=True)
    # Un membre non invité ne lit pas les infos de paiement
    r = session("membre3").rpc("event_pay_info", e=e)
    print("Max (pas invité) event_pay_info :", r.status_code, r.text[:200], flush=True)
    if r.status_code < 400 and r.text not in ("null", ""):
        anomaly("membre3", "🔴", "infos de paiement lues par un non-invité", r.text[:200])
    # Invité non présent (Peut-être) : pas d'IBAN
    gus = session("guest1")
    r = gus.rpc("event_pay_info", e=e)
    print("Gus (Absent) event_pay_info :", r.status_code, r.text[:200], flush=True)
    if r.status_code < 400 and "iban" in r.text:
        anomaly("guest1", "🟠", "un invité non présent lit l'IBAN de l'organisatrice", r.text[:200])
    # Écran d'entrée ouvert par un Guest (Gus) : refus visible
    p = phone(browser, "guest1", origin, "argent-droits")
    try:
        p.goto(f"/events/event/{e}/scan")
        settle(p)
        p.shot("guest-entree")
        tree = p.dump("guest-entree")
        check(p, "Code du billet" not in tree, "🔴", "Guest : pas de champ de scan")
        check(p, "Seuls les organisateurs" in tree or "Introuvable" in tree or "Entrée" in tree, "🟡",
              "Guest : message clair à l'entrée", tree[:300])
    finally:
        p.close()


# ── 10. Apple Wallet : 503 sans certificats ; logique de refus (base) ─────────────────────────────────────────

def phase_wallet(browser, origin, only):
    st = httpx.get(f"{origin}/api/wallet/status", timeout=30).json()
    print("wallet/status :", st, flush=True)
    marc = session("membre1")
    r = httpx.post(f"{origin}/api/wallet/ticket", json={"token": marc.token, "event_id": eid()}, timeout=30)
    print("wallet/ticket (Marc) :", r.status_code, r.text[:200], flush=True)
    if r.status_code != 503:
        anomaly("membre1", "🟠", "wallet/ticket sans certificats ne rend pas 503", f"{r.status_code} {r.text[:200]}")
    r = httpx.post(f"{origin}/api/wallet/ticket", json={"token": "x", "event_id": "pas-un-id"}, timeout=30)
    print("wallet/ticket mauvais id :", r.status_code, r.text[:200], flush=True)
    r = httpx.post(f"{origin}/api/wallet/notify", json={"token": marc.token, "event_id": eid(), "member": None}, timeout=30)
    print("wallet/notify :", r.status_code, r.text[:200], flush=True)
    # Logique de refus côté base : billet remis → pass ; billet retiré → refus ; gratuit sans billet → refus
    ok = marc.rpc("wallet_pass_issue", e=eid())
    print("wallet_pass_issue (Marc, billet remis) :", ok.status_code, ok.text[:200], flush=True)
    if ok.status_code >= 400 or '"valid": true' not in ok.text.replace('":true', '": true'):
        anomaly("membre1", "🔴", "pass Wallet refusé à un billet remis", ok.text[:200])
    if '"token"' in ok.text:
        print("(le pass contient le jeton du billet : attendu pour le QR du pass)", flush=True)
    vic = session("vip1")
    no = vic.rpc("wallet_pass_issue", e=eid("e_free"))
    print("wallet_pass_issue (Victor, gratuit, billet non remis) :", no.status_code, no.text[:200], flush=True)
    if no.status_code < 400:
        anomaly("vip1", "🔴", "pass Wallet accordé sans billet remis", no.text[:200])
    max_ = session("membre3").rpc("wallet_pass_issue", e=eid())
    print("wallet_pass_issue (Max, pas invité) :", max_.status_code, max_.text[:200], flush=True)
    if max_.status_code < 400:
        anomaly("membre3", "🔴", "pass Wallet accordé à un non-invité", max_.text[:200])
    # Billet retiré : le pass déjà émis devient non valable
    org = session("orga1")
    org.rpc("issue_event_ticket", e=eid(), member=marc.uid, issued=False)
    w = sql(f"""select private.wallet_payload({q(eid())}, {q(marc.uid)}) ->> 'valid' v""")
    print("pass de Marc après retrait du billet, valid =", w, flush=True)
    if w and w[0]["v"] == "true":
        anomaly("membre1", "🔴", "pass Wallet toujours valable après retrait du billet", str(w))
    org.rpc("issue_event_ticket", e=eid(), member=marc.uid, issued=True)


# ── 11. Pot commun de l'événement (API du serveur, comme l'app iPhone) ──────────────────────────────────────

def _tc(origin, path: str, **body) -> httpx.Response:
    return httpx.post(f"{origin}/api/account/tricount{path}", json=body, timeout=60)


def phase_pot(browser, origin, only):
    marc, vera, olga = session("membre1"), session("vip2"), session("orga1")
    lst = _tc(origin, "", token=marc.token)
    print("pots de Marc :", lst.status_code, lst.text[:300], flush=True)
    grp = sql(f"select id from public.tc_groups where event_id = {q(eid())}")[0]["id"]
    st = _tc(origin, "/open", token=marc.token, group_id=grp).json()
    members = {m["name"]: m["id"] for m in st.get("members", [])}
    print("membres :", members, flush=True)
    me = st.get("me")
    exp = {"title": "Fromage [C2-05]", "amount_cents": 6000, "currency": "CHF", "paid_by": me, "split_mode": "equal",
           "spent_on": f.day(0), "category": "food",
           "shares": [{"member_id": members[n], "weight": 1} for n in ("Bot Marc", "Bot Vera", "Bot Victor") if n in members]}
    r = _tc(origin, "/expense", token=marc.token, group_id=grp, expense=exp)
    print("dépense 60 CHF ÷ 3 :", r.status_code, r.text[:300], flush=True)
    if r.status_code >= 400:
        anomaly("membre1", "🔴", "pot commun : dépense refusée", r.text[:300])
    bad = _tc(origin, "/expense", token=marc.token, group_id=grp, expense={**exp, "amount_cents": -100})
    print("dépense négative :", bad.status_code, bad.text[:200], flush=True)
    if bad.status_code < 400:
        anomaly("membre1", "🟠", "pot commun : dépense négative acceptée", bad.text[:200])
    st = _tc(origin, "/open", token=vera.token, group_id=grp).json()
    print("soldes (vus par Vera) :", {k: st.get(k) for k in ("balances", "settle", "transfers", "debts") if k in st}, flush=True)
    # Remboursement Vera → Marc 20 CHF
    vera_id = st.get("me")
    r = _tc(origin, "/settle", token=vera.token, group_id=grp, from_id=vera_id, to_id=me, amount_cents=2000)
    print("remboursement Vera → Marc :", r.status_code, r.text[:300], flush=True)
    if r.status_code >= 400:
        anomaly("vip2", "🔴", "pot commun : remboursement refusé", r.text[:300])
    st = _tc(origin, "/open", token=vera.token, group_id=grp).json()
    print("après remboursement :", {k: st.get(k) for k in ("balances", "settle", "transfers", "debts") if k in st}, flush=True)
    # Suppression de la dépense d'un autre par un simple membre : refusée
    exp_id = next((x["id"] for x in st.get("expenses", []) if x.get("title", "").startswith("Fromage")), None)
    if exp_id:
        r = _tc(origin, "/expense/delete", token=vera.token, group_id=grp, expense_id=exp_id)
        print("Vera supprime la dépense de Marc :", r.status_code, r.text[:200], flush=True)
        if r.status_code < 400:
            anomaly("vip2", "🔴", "pot commun : un membre supprime la dépense d'un autre", r.text[:200])
    # Ticket : photo (petit JPEG) puis lecture IA sans clé
    jpg = base64.b64encode(bytes.fromhex(
        "ffd8ffe000104a46494600010100000100010000ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c"
        "20242e2720222c231c1c2837292c30313434341f27393d38323c2e333432ffc0000b080001000101011100ffc4001f00000105010101010101000000"
        "00000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1"
        "082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a7374"
        "75767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1"
        "e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffda0008010100003f00fbd3ffd9")).decode()
    r = _tc(origin, "/receipt", token=marc.token, group_id=grp, photo=jpg)
    print("photo du ticket :", r.status_code, r.text[:300], flush=True)
    s = httpx.post(f"{origin}/api/account/ai/status", json={"token": marc.token}, timeout=30)
    print("IA status :", s.status_code, s.text[:300], flush=True)
    c = httpx.post(f"{origin}/api/account/ai/consent", json={"token": marc.token, "accept": True}, timeout=30)
    print("accord IA :", c.status_code, c.text[:200], flush=True)
    a = httpx.post(f"{origin}/api/account/ai/receipt", json={"token": marc.token, "photo": jpg}, timeout=60)
    print("lecture IA du ticket (sans clé) :", a.status_code, a.text[:300], flush=True)
    if a.status_code >= 500 and a.status_code != 503:
        anomaly("membre1", "🟠", "scan de ticket IA sans clé : erreur serveur", f"{a.status_code} {a.text[:200]}")
    httpx.post(f"{origin}/api/account/ai/consent", json={"token": marc.token, "accept": False}, timeout=30)
    # Max (pas présent) ne lit pas le pot
    r = _tc(origin, "/open", token=session("membre3").token, group_id=grp)
    print("Max ouvre le pot :", r.status_code, r.text[:160], flush=True)
    if r.status_code < 400:
        anomaly("membre3", "🔴", "pot commun lu par un non-membre", r.text[:200])
    # Option désactivée : pot archivé ; dépenses gardées
    olga_view = _tc(origin, "/open", token=olga.token, group_id=grp)
    print("Olga ouvre le pot :", olga_view.status_code, flush=True)
    # Écran web : y a-t-il un accès au pot commun ? (Réglages du module Événements, Android)
    p = phone(browser, "vip2", origin, "argent-pot")
    try:
        p.goto("/events/settings")
        settle(p)
        tree = p.dump("reglages")
        p.shot("reglages")
        check(p, "Pot commun" in tree, "🟠", "Android/web : « Pot commun » introuvable dans Réglages (le formulaire y renvoie)")
    finally:
        p.close()


# ── 12. Réseau coupé pendant « J'ai payé » (Vera) ────────────────────────────────────────────────────────────

def phase_reseau(browser, origin, only):
    p = phone(browser, "vip2", origin, "argent-reseau")
    page = p.page
    try:
        open_event(p, "e_paid")
        with p.step("J'ai payé hors ligne"):
            pay = page.get_by_role("button", name=re.compile(r"^Payer l’organisateur"))
            if not pay.count():
                p.log("Vera n'a plus de bouton Payer (déjà déclarée ?)")
            _open_pay_sheet(p)
            p.ctx.set_offline(True)
            p.tap(btn(p, "J’ai payé"), "J'ai payé (hors ligne)")
            settle(p)
            p.shot("hors-ligne")
            tree = p.dump("hors-ligne")
            msg = re.findall(r'text: "?([^"\n]*(?:connexion|Failed|fetch|réseau|Réessaie)[^"\n]*)', tree, re.I)
            p.log(f"message : {msg}")
            check(p, any("Failed to fetch" not in m and "TypeError" not in m for m in msg) and msg, "🟡",
                  "hors ligne : message clair (pas « TypeError: Failed to fetch »)", str(msg))
            p.ctx.set_offline(False)
            page.wait_for_timeout(1000)
            p.tap(btn(p, "J’ai payé"), "J'ai payé (réseau revenu)")
            settle(p)
            check(p, text_on_screen(p, "en attente de confirmation"), "🔴", "réseau revenu : déclaration passe")
        with p.step("Pas reçu (organisatrice) → message chez Vera ; billet remis à la main reste"):
            olga = session("orga1")
            r = olga.rpc("confirm_ticket_payment", e=eid(), member=session("vip2").uid, received=False)
            p.log(f"Pas reçu : {r.status_code}")
            page.reload()
            settle(p)
            p.shot("apres-pas-recu")
    finally:
        p.ctx.set_offline(False)
        p.close()


# ── 13. Fin : suppression de MES événements et du profil de paiement créé ─────────────────────────────────────

def phase_nettoyage(browser, origin, only):
    ids = [r["id"] for r in sql(f"select id from public.events where title like {q(PREFIX + '%')}")]
    print("événements à supprimer :", ids, flush=True)
    groups = f"(select id from public.tc_groups where name like {q(PREFIX + '%')})"  # pots orphelins compris
    sql(f"delete from public.tc_expenses where group_id in {groups}")
    sql(f"delete from public.tc_groups where id in {groups}")
    for i in ids:
        sql(f"delete from public.events where id = {q(i)}")
    sql(f"delete from public.tc_payment where user_id = (select id from public.profiles where phone = {q(BY_KEY['orga2'].phone)})")
    print("reste :", sql(f"select count(*) n from public.events where title like {q(PREFIX + '%')}"), flush=True)


ONLY: list[str] | None = None


def main(argv: list[str]) -> None:
    global ONLY
    if "--only" in argv:
        i = argv.index("--only")
        ONLY = argv[i + 1].split(",")
        argv = argv[:i] + argv[i + 2:]
    origin = load_state()["origin"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv:
            print(f"════ phase {name} ════", flush=True)
            try:
                globals()[f"phase_{name}"](browser, origin, ONLY)
            except Exception as e:  # une phase cassée devient une anomalie, les suivantes continuent
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


# ── Logique de la base, « comme » chaque bot (rôle authenticated + jeton simulé, API de gestion, base de TEST) ──
# Sert quand la passerelle de la base de TEST sature (10 agents en parallèle) : mêmes fonctions que l'app appelle.

def as_user(key: str, expr: str) -> str:
    import json
    claims = json.dumps({"sub": uid(key), "role": "authenticated"})
    try:
        r = sql(f"""begin; set local role authenticated; select set_config('request.jwt.claims', {q(claims)}, true);
                    select ({expr})::text as r; commit;""")
        return (r[-1]["r"] if r else "") or ""
    except RuntimeError as e:
        msg = str(e)
        i = msg.find("ERROR:")
        return "ERREUR " + msg[i:i + 220]


def as_user_do(key: str, statement: str) -> str:
    """Instruction d'écriture « comme » le bot (RLS et gardes appliquées) ; rend le nombre de lignes touchées ou l'erreur."""
    import json
    claims = json.dumps({"sub": uid(key), "role": "authenticated"})
    try:
        r = sql(f"""begin; set local role authenticated; select set_config('request.jwt.claims', {q(claims)}, true);
                    create temp table if not exists _n (n int) on commit drop;
                    with x as ({statement} returning 1) insert into _n select count(*) from x;
                    select n::text as r from _n; commit;""")
        return (r[-1]["r"] if r else "") or ""
    except RuntimeError as e:
        msg = str(e)
        i = msg.find("ERROR:")
        return "ERREUR " + msg[i:i + 220]


def _expect(label: str, got: str, ok: bool, severity: str = "🔴") -> None:
    print(f"{'✓' if ok else '✗'} {label} → {got[:220]}", flush=True)
    if not ok:
        anomaly("logique", severity, label, got[:400])


def phase_logique(browser, origin, only):
    e, free = eid(), eid("e_free")
    u = {k: uid(k) for k in ("orga1", "orga2", "vip1", "vip2", "membre1", "membre3", "guest1")}
    call = lambda who, f_, *a: as_user(who, f"public.{f_}({', '.join(a)})")  # noqa: E731
    E, F = q(e), q(free)
    # Option
    r = call("vip1", "set_event_tickets", E, "true")
    _expect("un invité ne peut pas allumer les billets QR", r, r.startswith("ERREUR"))
    r = call("orga1", "set_event_tickets", E, "true")
    _expect("la co-organisatrice allume les billets QR (après publication)", r, r == "true")
    n = notifs("ticket_issued", "membre1")
    _expect("Marc (billet remis par la place payée) prévenu « billet prêt » à l'allumage", str(len(n)), len(n) == 1, "🟠")
    r = call("membre1", "my_event_ticket", E)
    _expect("Marc : billet « ok » avec jeton", r, '"state": "ok"' in r and '"token"' in r)
    r = call("vip1", "my_event_ticket", E)
    _expect("Victor : billet « pending » sans jeton", r, '"pending"' in r and "token" not in r)
    # Remise
    r = call("orga1", "issue_event_ticket", E, q(u["membre3"]), "true")
    _expect("remettre un billet à un non-présent (Max) refusé", r, r.startswith("ERREUR"), "🟠")
    r = call("vip2", "issue_event_ticket", E, q(u["vip1"]), "true")
    _expect("un invité ne remet pas de billet", r, r.startswith("ERREUR"))
    r = call("orga1", "issue_event_ticket", E, q(u["vip1"]), "true")
    _expect("remettre le billet de Victor", r, '"issued": true' in r and '"issued_by_payment": false' in r)
    r = call("orga1", "issue_event_ticket", E, q(u["vip1"]), "false")
    _expect("retirer le billet de Victor", r, '"issued": false' in r)
    r = call("orga1", "issue_all_event_tickets", E)
    _expect("remettre à tous : 3 (Victor, Vera, Gus)", r, r == "3", "🟠")
    r = call("orga1", "issue_all_event_tickets", E)
    _expect("remettre à tous une 2e fois : 0", r, r == "0", "🟡")
    n = notifs("ticket_issued", "vip1")
    print(f"   Victor a reçu {len(n)} notification(s) « billet prêt » (remis, retiré, remis)", flush=True)
    # Paiement et retrait automatique
    r = call("orga1", "set_ticket_paid", E, q(u["membre1"]), "false")
    _expect("« payé » décoché sur Marc : billet remis par le paiement retiré", r, '"issued": false' in r and '"paid": false' in r)
    r = call("membre1", "my_event_ticket", E)
    _expect("Marc revoit « pending » (plus de QR)", r, '"pending"' in r)
    r = call("orga1", "set_ticket_paid", E, q(u["membre1"]), "true")
    _expect("« payé » recoché : billet remis par le paiement", r, '"issued": true' in r and '"issued_by_payment": true' in r)
    r = call("orga1", "confirm_ticket_payment", E, q(u["membre1"]), "false")
    _expect("« Pas reçu » sur Marc payé : billet retiré", r, '"issued": false' in r and '"paid": false' in r)
    n = notifs("ticket_pay_confirmed", "membre1")
    _expect("Marc prévenu « ton billet est retiré en attendant »", n[-1]["body"] if n else "", bool(n) and "retiré" in n[-1]["body"], "🟠")
    r = call("membre1", "declare_ticket_payment", E, "true")
    _expect("Marc redéclare après « Pas reçu »", r, '"pay_pending": true' in r)
    r = call("orga1", "confirm_ticket_payment", E, q(u["membre1"]), "true")
    _expect("Reçu ✓ : Marc payé et billet remis", r, '"paid": true' in r and '"issued": true' in r)
    r = call("orga1", "confirm_ticket_payment", E, q(u["guest1"]), "true")
    _expect("Reçu ✓ Gus (billet déjà remis à la main)", r, '"paid": true' in r and '"issued_by_payment": false' in r)
    r = call("orga1", "confirm_ticket_payment", E, q(u["guest1"]), "false")
    _expect("« Pas reçu » sur Gus : billet remis à la main gardé", r, '"issued": true' in r and '"paid": false' in r)
    r = call("vip1", "confirm_ticket_payment", E, q(u["guest1"]), "true")
    _expect("un invité ne confirme pas un paiement", r, r.startswith("ERREUR"))
    r = call("vip1", "declare_ticket_payment", F, "true")
    _expect("« J'ai payé » sur un événement gratuit refusé", r, r.startswith("ERREUR"), "🟠")
    r = call("membre3", "declare_ticket_payment", E, "true")
    _expect("« J'ai payé » d'un non-présent refusé", r, r.startswith("ERREUR"), "🟠")
    # Infos de paiement
    r = call("membre3", "event_pay_info", E)
    _expect("infos de paiement : refusées à un non-invité", r, r.startswith("ERREUR") or r in ("", "null"))
    r = call("vip1", "event_pay_info", E)
    _expect("infos de paiement : IBAN de l'organisateur pour un présent", r, "CH9300762011623852957" in r)
    r = call("vip1", "event_pay_info", F)
    _expect("infos de paiement d'un gratuit : rien", r, r in ("", "null"), "🟡")
    # Scan
    codes = {k: ticket(k).get("code") for k in ("membre1", "vip1", "vip2", "guest1")}
    r = call("vip2", "check_in_ticket", E, q(codes["membre1"]))
    _expect("un invité ne scanne pas", r, r.startswith("ERREUR"))
    r = call("orga1", "check_in_ticket", E, q(codes["membre1"]))
    _expect("scan Marc : ok", r, '"result": "ok"' in r)
    r = call("orga1", "check_in_ticket", E, q(codes["membre1"]))
    _expect("scan Marc 2e fois : already", r, '"result": "already"' in r)
    r = call("orga1", "check_in_ticket", E, q(codes["membre1"].lower()))
    _expect("code en minuscules reconnu", r, '"result": "already"' in r, "🟡")
    r = call("orga1", "check_in_ticket", E, "'ZZZZZZ'")
    _expect("code inconnu", r, '"unknown"' in r)
    old = codes["vip1"]
    r = call("vip1", "renew_event_ticket", E)
    new = ticket("vip1").get("code")
    _expect("Victor : nouveau QR (code changé)", f"{old} → {new}", new != old)
    r = call("orga1", "check_in_ticket", E, q(old))
    _expect("ancien code de Victor refusé (unknown)", r, '"unknown"' in r)
    r = call("vip1", "renew_event_ticket", E, q(u["membre1"]))
    _expect("un invité ne renouvelle pas le billet d'un autre", r, r.startswith("ERREUR"))
    r = call("orga1", "issue_event_ticket", E, q(u["vip2"]), "false")
    r = call("orga1", "check_in_ticket", E, q(codes["vip2"]))
    _expect("billet retiré (Vera) : not_issued", r, '"not_issued"' in r)
    r = call("orga1", "issue_event_ticket", E, q(u["vip2"]), "true")
    r = call("orga1", "check_in_ticket", E, q(codes["vip2"]))
    _expect("remis sur place puis rescanné (Vera) : ok", r, '"result": "ok"' in r)
    # Autre événement : billet remis sur le gratuit (Oscar organisateur) puis scanné sur le payant
    call("orga2", "issue_event_ticket", F, q(u["vip1"]), "true")
    tok = sql(f"select token from public.event_tickets where event_id = {F} and user_id = {q(u['vip1'])}")
    if tok:
        r = call("orga1", "check_in_ticket", E, q(tok[0]["token"]))
        _expect("jeton d'un autre événement : other_event", r, '"other_event"' in r)
        r = call("vip2", "check_in_ticket", F, q(tok[0]["token"]))
        _expect("un invité ne scanne pas le gratuit", r, r.startswith("ERREUR"))
    # Arrivée manuelle
    r = call("orga1", "set_ticket_arrival", E, q(u["membre1"]), "false")
    _expect("arrivée de Marc annulée", r, '"checked_in_at": null' in r)
    r = call("orga1", "set_ticket_arrival", E, q(u["membre3"]), "true")
    _expect("arrivée manuelle d'un non-présent refusée", r, r.startswith("ERREUR"), "🟠")
    r = call("orga1", "set_ticket_arrival", E, q(u["membre1"]), "true")
    _expect("arrivée manuelle de Marc", r, '"checked_in_at": "' in r)
    # Wallet (logique de la base)
    r = call("membre1", "wallet_pass_issue", E)
    _expect("Wallet : pass accordé à Marc (billet remis)", r, '"valid": true' in r)
    r = call("membre3", "wallet_pass_issue", E)
    _expect("Wallet : refusé à un non-invité", r, r.startswith("ERREUR"))
    r = call("vip2", "wallet_pass_issue", F)
    _expect("Wallet : refusé sans billet remis (Vera, gratuit)", r, r.startswith("ERREUR") and "remettre" in r, "🟠")
    call("orga1", "issue_event_ticket", E, q(u["membre1"]), "false")
    w = sql(f"select private.wallet_payload({E}, {q(u['membre1'])}) ->> 'valid' v")
    _expect("Wallet : pass de Marc « annulé » après retrait du billet", str(w), bool(w) and w[0]["v"] == "false")
    call("orga1", "issue_event_ticket", E, q(u["membre1"]), "true")
    # Absent → not_registered ; option éteinte → tickets_off ; billets cachés
    r = as_user_do("guest1", f"update public.rsvps set status = 'no', plus_ones = 0 where event_id = {E} and user_id = {q(u['guest1'])}")
    _expect("Gus répond Absent", r, r == "1")
    r = call("orga1", "check_in_ticket", E, q(codes["guest1"]))
    _expect("Gus Absent : not_registered", r, '"not_registered"' in r)
    r = call("orga2", "set_event_tickets", E, "false")
    r = call("orga1", "check_in_ticket", E, q(codes["vip2"]))
    _expect("option éteinte : tickets_off", r, '"tickets_off"' in r)
    r = call("membre1", "my_event_ticket", E)
    _expect("option éteinte : Marc n'a plus de jeton", r, "token" not in r and '"off"' in r)
    w = sql(f"select private.wallet_payload({E}, {q(u['membre1'])}) ->> 'valid' v")
    _expect("option éteinte : pass Wallet « annulé »", str(w), bool(w) and w[0]["v"] == "false")
    r = call("orga1", "issue_all_event_tickets", E)
    _expect("option éteinte : « remettre à tous » refusé", r, r.startswith("ERREUR"), "🟡")
    before = len(notifs("ticket_issued", "vip1"))
    r = call("orga2", "set_event_tickets", E, "true")
    after = len(notifs("ticket_issued", "vip1"))
    print(f"   rallumage : Victor reçoit {after - before} nouvelle(s) notification(s) « billet prêt »", flush=True)
    if after - before:
        anomaly("vip1", "🟡", "éteindre puis rallumer les billets QR renvoie « Ton billet est prêt » à chaque présent",
                f"{after - before} notification(s) en plus")


def phase_scan_victor(browser, origin, only):
    code = ticket("vip1").get("code")
    p = phone(browser, "orga1", origin, "argent-scan-victor")
    page = p.page
    try:
        signed_in(p)
        p.goto(f"/events/event/{eid()}/scan")
        p.page.get_by_label("Code du billet").wait_for(timeout=60000)
        _scan(p, code, "Bienvenue", "nouveau code de Victor → « Bienvenue ! »")
        check(p, ticket("vip1").get("checked_in_at") is not None, "🔴", "base : arrivée de Victor enregistrée")
        _scan(p, code, "Déjà scanné", "même code → « Déjà scanné »")
        p.shot("deja")
        with p.step("verdict : Marquer payé / Annuler « payé » (Victor)"):
            p.tap(btn(p, "Marquer payé"), "Marquer payé")
            settle(p)
            check(p, ticket("vip1").get("paid"), "🔴", "base : Victor payé depuis le verdict")
            check(p, p.see(btn(p, "Annuler « payé »"), "Annuler « payé »"), "🟠", "le verdict se met à jour")
            p.shot("verdict-paye")
            p.tap(btn(p, "Annuler « payé »"), "Annuler « payé »")
            settle(p)
            t = ticket("vip1")
            check(p, not t.get("paid") and t.get("issued_at") is not None, "🔴", "Victor : payé annulé, billet (remis à la main) gardé", str(t))
        p.tap(btn(p, "Billet suivant"), "Billet suivant")
        p.scroll_to_bottom("écran d'entrée")
        p.shot("entree-fin", full=True)
        heads = page.get_by_text(re.compile(r"\d+ / \d+ personnes")).first.inner_text()
        p.log(f"compteur des arrivées : {heads}")
        _check_texts(p, "écran d'entrée (fin)")
    finally:
        p.close()


def phase_remise_a_zero(browser, origin, only):
    """Avant les écrans : billets effacés, Gus Présent et déclaré, Marc payé (billet remis par le paiement), option éteinte."""
    E = q(eid())
    sql(f"delete from public.event_tickets where event_id = {E}")
    sql(f"update public.rsvps set status = 'yes' where event_id = {E} and user_id = {q(uid('guest1'))}")
    sql(f"update public.events set tickets_enabled = false where id = {E}")
    print(as_user("orga1", f"public.set_ticket_paid({E}, {q(uid('membre1'))}, true)")[:80])
    print(as_user("guest1", f"public.declare_ticket_payment({E}, true)")[:80])
    print(sql(f"select p.display_name, t.paid, t.issued_at is not null issued, t.issued_by_payment, t.pay_declared_at is not null declared "
              f"from public.event_tickets t join public.profiles p on p.id = t.user_id where t.event_id = {E}"))


def phase_pot_logique(browser, origin, only):
    e = eid()
    E = q(e)
    grp = sql(f"select id from public.tc_groups where event_id = {E}")[0]["id"]
    G = q(grp)
    mem = {r["name"]: r["id"] for r in sql(f"select id, name from public.tc_members where group_id = {G}")}
    print("membres du pot :", list(mem), flush=True)
    exp = {"title": "Fromage [C2-05]", "amount_cents": 6000, "paid_by": mem["Bot Marc"], "split_mode": "equal",
           "shares": [{"member_id": mem[n]} for n in ("Bot Marc", "Bot Vera", "Bot Victor")]}
    import json
    r = as_user("membre1", f"public.tc_save_expense({G}, {q(json.dumps(exp))}::jsonb)")
    _expect("pot : Marc ajoute 60 CHF ÷ 3", r, not r.startswith("ERREUR"))
    exp_id = r
    r = as_user("membre1", f"public.tc_save_expense({G}, {q(json.dumps({**exp, 'amount_cents': -5}))}::jsonb)")
    _expect("pot : montant négatif refusé (base)", r, r.startswith("ERREUR"), "🟠")
    tr = {"kind": "transfer", "title": "Remboursement", "amount_cents": 2000, "paid_by": mem["Bot Vera"], "split_mode": "equal",
          "shares": [{"member_id": mem["Bot Marc"]}]}
    r = as_user("vip2", f"public.tc_save_expense({G}, {q(json.dumps(tr))}::jsonb)")
    _expect("pot : Vera rembourse 20 CHF à Marc", r, not r.startswith("ERREUR"))
    r = as_user("vip2", f"public.tc_delete_expense({q(exp_id)})")
    _expect("pot : Vera ne supprime pas la dépense de Marc", r, r.startswith("ERREUR"))
    r = as_user("membre3", f"public.tc_state({G})")
    _expect("pot : un non-membre (Max) ne le lit pas", r, r.startswith("ERREUR") or r in ("", "null"))
    st = as_user("vip2", f"public.tc_state({G})")
    _expect("pot : Vera lit le pot (dépense + remboursement)", st[:120], "Fromage" in st and "Remboursement" in st)
    r = as_user("vip2", f"public.tc_remove_member({q(mem['Bot Marc'])})")
    _expect("pot : un membre ne retire pas un autre", r, r.startswith("ERREUR"))
    # Option désactivée puis réactivée par l'organisateur (formulaire = update de la ligne)
    print("   Oscar coupe le pot :", as_user_do("orga2", f"update public.events set pot_enabled = false where id = {E}"), flush=True)
    a = sql(f"select archived from public.tc_groups where id = {G}")[0]["archived"]
    _expect("pot : option coupée → pot archivé", str(a), a is True, "🟠")
    print("   Oscar rallume le pot :", as_user_do("orga2", f"update public.events set pot_enabled = true where id = {E}"), flush=True)
    a = sql(f"select archived, (select count(*) from public.tc_expenses where group_id = {G}) n from public.tc_groups where id = {G}")[0]
    _expect("pot : option rallumée → rouvert, dépenses gardées", str(a), a["archived"] is False and a["n"] >= 2, "🟠")
    # Calcul des soldes (logique Python de l'app)
    from app import tricount_logic as tc
    print("   fonctions du calcul :", [n for n in dir(tc) if not n.startswith("_")][:30], flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
