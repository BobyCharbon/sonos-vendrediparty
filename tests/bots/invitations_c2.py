"""Campagne 2, domaine INVITATIONS (v2 allumées) : carte « Invités », feuille « Inviter », relances, retraits, liens
arrêtés, et le parcours complet de l'invité SANS L'APP (carte sans compte, prénom + numéro + code, confirmation,
calendrier, itinéraire, Installer Party, changer d'avis, liens expiré / plein / arrêté, aperçu WhatsApp).

Usage (serveur du banc lancé, BOTS_OUT / BOTS_PORT réglés) :
  .venv/bin/python -m tests.bots.invitations_c2 <phase> [<phase>…]
Phases : setup carte feuille groupes sans_app limites relances retrait_puis_lien orga_son_lien meta nettoyage
Titres des événements préfixés « [C2-03] » ; seulement les groupes Bots / Bots 2 et les comptes « Bot … »."""
from __future__ import annotations

import re
import sys
import traceback
from datetime import date, timedelta

import httpx
from playwright.sync_api import sync_playwright

from tests.bots import flows as f
from tests.bots.bench import anomaly, load_state, phone, save_state
from tests.bots.common import BY_KEY, GROUP_BOTS, GROUP_BOTS_2, TEST_URL, Session, q, sql

PREFIX = "[C2-03]"
E1_TITLE = f"{PREFIX} Invitations"
E2_TITLE = f"{PREFIX} Limites"
E3_TITLE = f"{PREFIX} Oscar"
# Olga a bloqué Bot Gus (autre agent, « signaler ») : E1 invite Bots 2 (sans Gus) ; Bots est ajouté depuis la feuille.
E1_GROUP = GROUP_BOTS_2
OTHER_GROUP = GROUP_BOTS
TOKEN_RE = re.compile(r"/events/invite/([0-9a-f-]{36})")
# Toutes les ouvertures (window.open, location) sont notées dans window.__opened (sans quitter la page).
RECORD_OPENS = """
window.__opened = [];
const _open = window.open;
window.open = function (url, target, features) { window.__opened.push(String(url)); return null; };
"""


# ── Gestes ───────────────────────────────────────────────────────────────────────────────────────────────────────

def touch_drag(p, x: float, y0: float, y1: float, steps: int = 12) -> None:
    """Vrai glissé du doigt (événements tactiles CDP) de (x, y0) à (x, y1)."""
    cdp = p.ctx.new_cdp_session(p.page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y0}]})
    for i in range(1, steps + 1):
        y = y0 + (y1 - y0) * i / steps
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y}]})
        p.page.wait_for_timeout(16)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    p.log(f"glisse le doigt ({x:.0f}, {y0:.0f}) → ({x:.0f}, {y1:.0f})")
    p.page.wait_for_timeout(700)


def swipe_left(p, locator, what: str) -> None:
    """Glisse une ligne vers la gauche (défilement horizontal natif, geste tactile Chrome)."""
    locator.scroll_into_view_if_needed()
    box = locator.bounding_box()
    cdp = p.ctx.new_cdp_session(p.page)
    cdp.send("Input.synthesizeScrollGesture", {"x": box["x"] + box["width"] * 0.7, "y": box["y"] + box["height"] / 2,
                                               "xDistance": -260, "yDistance": 0, "gestureSourceType": "touch",
                                               "speed": 900})
    cdp.detach()
    p.log(f"glisse vers la gauche : {what}")
    p.page.wait_for_timeout(900)


def action_near(p, name, target, exact: bool = True):
    """Le bouton d'action révélé sur la ligne glissée (même hauteur que la ligne, dans l'écran)."""
    tb = target.bounding_box()
    loc = p.page.get_by_role("button", name=name, exact=exact) if isinstance(name, str) else p.page.get_by_role("button", name=name)
    for b in loc.all():
        bb = b.bounding_box()
        if bb and bb["x"] < 390 and bb["x"] + bb["width"] > 0 and abs((bb["y"] + bb["height"] / 2) - (tb["y"] + tb["height"] / 2)) < 40:
            return b
    return None


def opened(p) -> list[str]:
    return p.page.evaluate("window.__opened || []")


def sheet_of(p):
    s = p.page.get_by_label(re.compile("^Inviter à "))
    s.wait_for(state="visible", timeout=10000)
    return s


def sheet_visible(p) -> bool:
    s = p.page.get_by_label(re.compile("^Inviter à "))
    return bool(s.count()) and s.first.is_visible()


def open_sheet(p, how: str = "plus"):
    page = p.page
    if how == "plus":
        p.tap(page.get_by_role("button", name="Inviter", exact=True), "＋ (Inviter)")
    else:
        p.tap(page.get_by_role("button", name="＋ Inviter d’autres personnes"), "＋ Inviter d’autres personnes")
    page.wait_for_timeout(900)
    return sheet_of(p)


def links_of(event_id: str) -> list[dict]:
    return sql(f"""select token, label, max_uses, uses, expires_at, revoked_at, opened_at, used_by, created_at
                   from private.invite_links where kind = 'event' and target = '{event_id}' order by created_at""") or []


def copy_link(p, sheet) -> str:
    """Copier, puis attend que le presse-papiers change (la base peut être lente : jusqu'à 20 s)."""
    p.page.evaluate("navigator.clipboard.writeText('(vide)')")
    p.tap(sheet.get_by_role("button", name="Copier", exact=True), "Copier")
    text = ""
    for _ in range(40):
        p.page.wait_for_timeout(500)
        text = p.page.evaluate("navigator.clipboard.readText()")
        if text != "(vide)":
            break
    m = TOKEN_RE.search(text or "")
    p.log(f"presse-papiers : {text!r}")
    return m.group(1) if m else ""


def tap_until_disabled(p, locator, times: int, what: str) -> int:
    """Touche jusqu'à `times` fois ; s'arrête quand le bouton devient inactif (borne). Renvoie le nombre de touchers."""
    n = 0
    for _ in range(times):
        if locator.get_attribute("aria-disabled") == "true":
            break
        locator.tap()
        p.page.wait_for_timeout(60)
        n += 1
    p.log(f"{what} : {n} toucher(s)")
    return n


def open_event(p, key: str = "e1") -> None:
    for attempt in range(3):
        p.goto(f"/events/event/{load_state()[key]}")
        try:
            p.page.get_by_text(re.compile("^Invités · ")).first.wait_for(timeout=45000)
            break
        except Exception:
            p.log(f"carte Invités pas chargée (essai {attempt + 1}) : base lente ?")
    p.page.wait_for_timeout(1200)


def tile(p, label: str):
    return p.page.get_by_role("tab", name=re.compile(rf"^\d+ {re.escape(label)}$"))


def tile_count(p, label: str) -> int:
    name = tile(p, label).first.get_attribute("aria-label") or "-1"
    return int(name.split(" ")[0])


def guest_list(event_id: str, phone_number: str) -> dict:
    s = Session(phone_number)
    for _ in range(4):
        try:
            r = s.rpc("event_guest_list", e=event_id)
            if r.status_code == 200:
                return r.json()
        except httpx.HTTPError:
            pass
    raise RuntimeError("event_guest_list illisible (base lente)")


TOASTS = re.compile(r"Lien copié|Message copié|Copie impossible|invités|Déjà invités|rappel|Rappel|relancé|Relancé|"
                    r"Lien arrêté|ne fait plus partie|Personne à relancer|sans l’app|n’a pas pu|Trop de")


def toast(p, what: str, timeout: int = 6000) -> str:
    """Texte du toast (messages connus), vide sinon."""
    loc = p.page.locator('[role="alert"]')
    try:
        loc.last.wait_for(state="visible", timeout=timeout)
        text = loc.last.inner_text().strip()
    except Exception:
        text = ""
    p.log(f"toast {what} : {text!r}")
    return text


def check_cut(p, what: str) -> None:
    cut = p.check_texts_cut(what)
    if cut:
        p.flag("🟡", f"{what} : textes coupés ou hors écran", "; ".join(cut))


def fresh_phone(browser, key: str, origin: str, phase: str):
    """Téléphone neuf (aucune session gardée) qui note les ouvertures de liens."""
    p0 = phone(browser, key, origin, "x")
    p0.close()
    (p0.dir / "storage.json").unlink(missing_ok=True)  # après close (qui sauve la session)
    p = phone(browser, key, origin, phase)
    p.ctx.add_init_script(RECORD_OPENS)
    p.page.close()
    p.page = p.ctx.new_page()
    _wire(p)
    return p


def _wire(p) -> None:
    p.page.on("pageerror", lambda e: p._problem("exception JS", str(e)))
    p.page.on("console", p._console)
    p.page.on("response", p._response)
    p.page.on("dialog", p._dialog)


def signed_phone(browser, key: str, origin: str, phase: str):
    p = phone(browser, key, origin, phase)
    p.ctx.add_init_script(RECORD_OPENS)
    p.page.close()
    p.page = p.ctx.new_page()
    _wire(p)
    p.sign_in()
    return p


# ── Phases ───────────────────────────────────────────────────────────────────────────────────────────────────────

def phase_setup(browser, origin):
    """Olga (organisatrice, iPhone) crée E1 (Bots) et E2 ; Oscar (Android) crée E3 (Bots)."""
    p = signed_phone(browser, "orga1", origin, "setup")
    try:
        if not load_state().get("e1"):
            e1 = f.create_simple(p, E1_TITLE, 6, [E1_GROUP])
            save_state(e1=e1)
        if not load_state().get("e2"):
            e2 = f.create_simple(p, E2_TITLE, 9, [E1_GROUP])
            save_state(e2=e2)
    finally:
        p.close()
    p = signed_phone(browser, "orga2", origin, "setup")
    try:
        if not load_state().get("e3"):
            save_state(e3=f.create_simple(p, E3_TITLE, 8, [GROUP_BOTS]))
    finally:
        p.close()
    st = load_state()
    print("événements :", st.get("e1"), st.get("e2"), st.get("e3"), flush=True)
    # Adresse exacte (cachée sur la carte sans compte, montrée après la réponse)
    for k in ("e1", "e2"):
        if st.get(k):
            sql(f"update public.events set location_address = 'Rue des Bots 3, 1800 Vevey' where id = '{st[k]}'")


def phase_carte(browser, origin):
    """Carte « Invités » : compteurs comparés à la base, groupe replié, filtres (aller-retour), ouvertures de la feuille."""
    p = signed_phone(browser, "orga1", origin, "carte")
    page = p.page
    e1 = load_state()["e1"]
    try:
        open_event(p)
        p.shot("carte")
        p.dump("carte")
        gl = guest_list(e1, BY_KEY["orga1"].phone)
        people = gl.get("people", [])
        p.log(f"base : {len(people)} personnes, groupes {[g['name'] for g in gl.get('groups', [])]}, {len(gl.get('links', []))} liens")
        head = page.get_by_text(re.compile(r"^Invités · \d+")).first.inner_text()
        p.log(f"en-tête : {head}")
        with p.step("compteurs = base"):
            expected = {"Viennent": sum(1 for x in people if x["status"] == "yes"),
                        "Peut-être": sum(1 for x in people if x["status"] == "maybe"),
                        "Absents": sum(1 for x in people if x["status"] == "no")}
            for label, n in expected.items():
                shown = tile_count(p, label)
                if shown != n:
                    p.flag("🔴", f"compteur « {label} » faux", f"écran {shown}, base {n}")
        with p.step("groupe replié puis déplié"):
            grp = page.get_by_role("button", name=re.compile(rf"^Groupe {E1_GROUP}, \d+ personnes"))
            p.expect_or_flag(grp.first, "la ligne repliée du groupe Bots")
            n_members = int(re.search(r", (\d+) personnes", grp.first.get_attribute("aria-label")).group(1))
            db_members = sql(f"""select count(*) n from public.member_group_members m join public.member_groups g on g.id = m.group_id
                                 join public.profiles p on p.id = m.user_id
                                 where g.name = {q(E1_GROUP)} and p.display_name <> 'Bot Olga' and p.status = 'active'""")[0]["n"]
            p.log(f"groupe {E1_GROUP} : écran {n_members}, base {db_members}")
            if n_members != db_members:
                p.flag("🟠", "nombre de personnes du groupe faux", f"écran {n_members}, base {db_members}")
            p.tap(grp.first, "déplier le groupe")
            p.see(page.get_by_text("Bot Valentin", exact=True).first, "Bot Valentin dans le groupe déplié", 5000)
            p.shot("groupe-deplie")
            p.tap(grp.first, "replier le groupe")
            page.wait_for_timeout(500)
            if page.get_by_text("Bot Valentin", exact=True).first.is_visible():
                p.flag("🟡", "le groupe ne se replie pas")
        with p.step("filtres : chaque compteur, puis second toucher = tout"):
            for label in ("Viennent", "Peut-être", "Absents", "Pas répondu", "Lien pas ouvert"):
                t = tile(p, label).first
                p.tap(t, f"filtre {label}")
                page.wait_for_timeout(500)
                sel = t.get_attribute("aria-selected")
                p.shot(f"filtre-{label.replace(' ', '-').lower()}")
                if sel != "true":
                    p.flag("🟡", f"filtre « {label} » : pas marqué choisi", f"aria-selected={sel}")
                p.tap(t, f"filtre {label} (retour à tout)")
                page.wait_for_timeout(400)
                if not page.get_by_role("button", name=re.compile(rf"^Groupe {E1_GROUP}")).first.is_visible():
                    p.flag("🟠", f"second toucher sur « {label} » ne revient pas à la liste complète")
        with p.step("feuille : ouvrir par « + », fermer par ✕"):
            sheet = open_sheet(p, "plus")
            p.shot("feuille-ouverte")
            p.tap(sheet.get_by_role("button", name="Fermer").first, "✕")
            page.wait_for_timeout(800)
            if sheet_visible(p):
                p.flag("🔴", "✕ ne ferme pas la feuille Inviter")
        with p.step("feuille : ouvrir par « ＋ Inviter d’autres personnes », fermer en touchant le fond"):
            sheet = open_sheet(p, "more")
            box = sheet.bounding_box()
            p.log(f"feuille : y={box['y']:.0f} h={box['height']:.0f}")
            if box["y"] < 12:
                p.flag("🟡", "feuille Inviter : aucun fond visible au-dessus (fermer en touchant le fond impossible)", str(box))
            else:
                page.touchscreen.tap(195, max(4, box["y"] / 2))
                page.wait_for_timeout(900)
                if sheet_visible(p):
                    p.flag("🟠", "toucher le fond ne ferme pas la feuille Inviter", str(box))
        with p.step("feuille : fermer en glissant la poignée vers le bas"):
            if not sheet_visible(p):
                sheet = open_sheet(p, "plus")
            box = sheet.bounding_box()
            touch_drag(p, 195, box["y"] + 8, box["y"] + 420)
            page.wait_for_timeout(600)
            if sheet_visible(p):
                p.flag("🔴", "glisser la feuille Inviter vers le bas ne la ferme pas")
            p.shot("apres-glisse")
        with p.step("feuille : petit glissé (60 px) → la feuille revient"):
            sheet = open_sheet(p, "plus")
            box = sheet.bounding_box()
            touch_drag(p, 195, box["y"] + 8, box["y"] + 60, steps=20)
            page.wait_for_timeout(700)
            if not sheet_visible(p):
                p.flag("🟡", "un petit glissé de 60 px ferme déjà la feuille")
            else:
                nb = sheet.bounding_box()
                if abs(nb["y"] - box["y"]) > 4:
                    p.flag("🟠", "après un petit glissé, la feuille ne revient pas en place", f"{box['y']} → {nb['y']}")
                p.tap(sheet.get_by_role("button", name="Fermer").first, "✕")
        with p.step("feuille : glisser le contenu défilé vers le bas le fait défiler (pas fermer)"):
            sheet = open_sheet(p, "plus")
            box = sheet.bounding_box()
            p.finger_scroll("feuille Inviter", x=195, y=min(box["y"] + box["height"] - 80, 760), flag=True)
            page.wait_for_timeout(300)
            touch_drag(p, 195, 500, 700)
            if not sheet_visible(p):
                p.flag("🟠", "feuille défilée : redescendre le contenu au doigt ferme la feuille au lieu de remonter le contenu")
            elif sheet_visible(p):
                p.tap(sheet_of(p).get_by_role("button", name="Fermer").first, "✕")
        check_cut(p, "carte Invités")
    finally:
        p.close()


def phase_feuille(browser, origin):
    """Feuille « Inviter » : modes, places, validité, aperçu, Copier / Partager / WhatsApp / Messages / QR, nouveau lien,
    double toucher, liens pour la suite (Sam, Sara, expiré, arrêté)."""
    p = signed_phone(browser, "orga1", origin, "feuille")
    page = p.page
    e1 = load_state()["e1"]
    try:
        open_event(p)
        sheet = open_sheet(p)
        p.shot("feuille")
        p.dump("feuille")
        check_cut(p, "feuille Inviter")
        with p.step("aperçu du message (Plusieurs, 10 places par défaut)"):
            seg = sheet.get_by_role("tab", name="Plusieurs")
            p.log(f"onglet Plusieurs choisi : {seg.first.get_attribute('aria-selected')}")
            p.see(sheet.get_by_text(re.compile("Les 10 premiers qui répondent")), "10 places par défaut", 3000)
            bubble = sheet.get_by_text(re.compile("^Hello !")).first
            text = bubble.inner_text()
            p.log(f"aperçu : {text!r}")
            if E1_TITLE not in text or "Bot Olga" not in text:
                p.flag("🟠", "aperçu du message : titre ou organisatrice manquant", text)
        with p.step("places : − jusqu'au minimum (2), puis + ; bornes"):
            minus = sheet.get_by_label("Une place de moins")
            tap_until_disabled(p, minus, 12, "une place de moins")
            p.see(sheet.get_by_text(re.compile("Les 2 premiers")), "2 places (minimum)", 3000) or \
                p.flag("🟡", "minimum de places ≠ 2")
            p.shot("places-min")
            plus = sheet.get_by_label("Une place de plus")
            tap_until_disabled(p, plus, 3, "une place de plus")
            p.see(sheet.get_by_text(re.compile("Les 5 premiers")), "5 places", 3000) or p.flag("🟠", "+ ne monte pas à 5")
        with p.step("validité : 3 jours / 7 jours / Après l’événement"):
            for label in ("3 jours", "7 jours", "Après l’événement"):
                r = sheet.get_by_role("radio", name=label)
                p.tap(r.first, label)
                if r.first.get_attribute("aria-checked") != "true":
                    p.flag("🟡", f"validité « {label} » pas marquée choisie")
        n0 = len(links_of(e1))
        with p.step("double toucher sur Copier : un seul lien créé"):
            btn = sheet.get_by_role("button", name="Copier", exact=True)
            btn.scroll_into_view_if_needed()
            b = btn.bounding_box()
            page.touchscreen.tap(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
            page.touchscreen.tap(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
            page.wait_for_timeout(2500)
            n1 = len(links_of(e1))
            p.log(f"liens : {n0} → {n1}")
            if n1 - n0 > 1:
                p.flag("🟠", "double toucher sur « Copier » : deux liens créés", f"{n1 - n0} liens")
            toast(p, "après Copier")
            p.see(sheet.get_by_text(re.compile("✓ Lien prêt")), "✓ Lien prêt", 4000)
            last = links_of(e1)[-1]
            p.log(f"lien en base : {last}")
            if last["max_uses"] != 5:
                p.flag("🔴", "places du lien fausses en base", f"5 attendues, {last['max_uses']}")
        with p.step("le même lien est réutilisé tant qu'on ne change rien (Copier encore)"):
            n2 = len(links_of(e1))
            copy_link(p, sheet)
            if len(links_of(e1)) != n2:
                p.flag("🟡", "Copier une 2e fois crée un nouveau lien alors que rien n'a changé")
        with p.step("Partager le lien… (feuille de partage ou copie)"):
            p.tap(sheet.get_by_role("button", name="Partager le lien…"), "Partager le lien…")
            page.wait_for_timeout(1500)
            t = toast(p, "Partager")
            clip = page.evaluate("navigator.clipboard.readText()")
            p.log(f"presse-papiers après Partager : {clip!r}")
            p.shot("partager")
        with p.step("WhatsApp et Messages"):
            p.tap(sheet.get_by_role("button", name="WhatsApp"), "WhatsApp")
            p.tap(sheet.get_by_role("button", name="Messages"), "Messages")
            page.wait_for_timeout(800)
            urls = opened(p)
            p.log(f"ouvertures : {urls}")
            if not any(u.startswith("https://wa.me/?text=") and "events%2Finvite%2F" in u for u in urls):
                p.flag("🔴", "WhatsApp : pas d'ouverture wa.me avec le lien", str(urls))
            if not any(u.startswith("sms:") and "body=" in u for u in urls):
                p.flag("🔴", "Messages : pas d'ouverture sms: avec le message", str(urls))
        with p.step("QR code : ouvrir, fermer par Fermer, rouvrir, fermer en glissant"):
            p.tap(sheet.get_by_role("button", name="QR code"), "QR code")
            qr = page.get_by_label("QR code du lien d’invitation")
            p.expect_or_flag(qr.first, "le QR code", "🔴", 5000)
            p.see(page.get_by_text("👥 Pour plusieurs · 5 places"), "« Pour plusieurs · 5 places » sous le QR", 3000) or \
                p.flag("🟡", "QR : nombre de places absent ou faux")
            p.shot("qr")
            p.tap(page.get_by_role("button", name="Fermer", exact=True).last, "Fermer (QR)")
            page.wait_for_timeout(600)
            if qr.count() and qr.first.is_visible():
                p.flag("🟠", "QR : « Fermer » ne ferme pas")
            p.tap(sheet.get_by_role("button", name="QR code"), "QR code (encore)")
            page.wait_for_timeout(600)
            card = page.get_by_label("QR code de l’invitation").first
            cb = card.bounding_box()
            p.log(f"fenêtre QR : {cb}")
            img = qr.first.bounding_box()
            touch_drag(p, 195, img["y"] - 60, img["y"] + 360)
            if qr.count() and qr.first.is_visible():
                p.flag("🟡", "QR : glisser vers le bas ne ferme pas la fenêtre")
                p.tap(page.get_by_role("button", name="Fermer", exact=True).last, "Fermer (QR)")
            if not sheet_visible(p):
                p.flag("🟠", "fermer le QR ferme aussi la feuille Inviter")
                sheet = open_sheet(p)
        with p.step("Une personne « Sam » : lien pour une personne"):
            p.tap(sheet.get_by_role("tab", name="Une personne"), "Une personne")
            p.type(sheet.get_by_label("Pour qui ? (facultatif)"), "Sam", "Pour qui ?")
            text = sheet.get_by_text(re.compile("^Hello Sam !")).first.inner_text()
            p.log(f"aperçu : {text}")
            tok = copy_link(p, sheet)
            row = [x for x in links_of(e1) if x["token"] == tok]
            p.log(f"lien Sam : {row}")
            if not tok or not row or row[0]["label"] != "Sam" or row[0]["max_uses"] != 1:
                p.flag("🔴", "lien « Une personne » Sam : faux en base", str(row))
            save_state(link_sam=tok)
        with p.step("Nouveau lien (pour quelqu’un d’autre) : vide le prénom, nouveau jeton"):
            p.tap(sheet.get_by_role("button", name="Nouveau lien (pour quelqu’un d’autre)"), "Nouveau lien")
            val = sheet.get_by_label("Pour qui ? (facultatif)").input_value()
            if val:
                p.flag("🟡", "« Nouveau lien » garde le prénom précédent", val)
            p.type(sheet.get_by_label("Pour qui ? (facultatif)"), "Test orga", "Pour qui ?")
            tok = copy_link(p, sheet)
            if tok == load_state()["link_sam"]:
                p.flag("🔴", "« Nouveau lien » redonne le même lien (Sam)")
            save_state(link_orga=tok)
        with p.step("Plusieurs, 2 places (Sara + 1) → lien plein ensuite"):
            p.tap(sheet.get_by_role("tab", name="Plusieurs"), "Plusieurs")
            tap_until_disabled(p, sheet.get_by_label("Une place de moins"), 12, "une place de moins")
            save_state(link_two=copy_link(p, sheet))
        with p.step("Plusieurs, 3 jours (sera expiré)"):
            tap_until_disabled(p, sheet.get_by_label("Une place de plus"), 2, "une place de plus")
            p.tap(sheet.get_by_role("radio", name="3 jours"), "3 jours")
            tok = copy_link(p, sheet)
            row = [x for x in links_of(e1) if x["token"] == tok]
            p.log(f"lien 3 jours : {row}")
            save_state(link_exp=tok)
        with p.step("Plusieurs, 7 jours (sera arrêté)"):
            p.tap(sheet.get_by_role("radio", name="7 jours"), "7 jours")
            save_state(link_stop=copy_link(p, sheet))
        with p.step("lien pour l'aperçu WhatsApp (jamais ouvert)"):
            p.tap(sheet.get_by_role("radio", name="Après l’événement"), "Après l’événement")
            save_state(link_meta=copy_link(p, sheet))
            ev = sql(f"select starts_at, ends_at from public.events where id = '{e1}'")[0]
            row = [x for x in links_of(e1) if x["token"] == load_state()["link_meta"]]
            p.log(f"événement {ev} ; lien « après l'événement » : {row}")
        p.shot("feuille-fin")
        p.tap(sheet.get_by_role("button", name="Fermer").first, "✕")
        open_event(p)
        p.shot("carte-avec-liens")
        p.dump("carte-avec-liens")
        with p.step("liens envoyés sur la carte"):
            gl = guest_list(e1, BY_KEY["orga1"].phone)
            n_links = len(gl.get("links", []))
            shown = page.get_by_text(re.compile(r"^LIENS ENVOYÉS · \d+")).first.inner_text()
            p.log(f"carte : {shown} ; base {n_links}")
            if str(n_links) not in shown:
                p.flag("🟠", "nombre de liens envoyés faux", f"{shown} / base {n_links}")
            unopened = tile_count(p, "Lien pas ouvert")
            p.log(f"compteur « Lien pas ouvert » : {unopened}")
    finally:
        p.close()


def phase_groupes(browser, origin):
    """Ajouter des gens de Party hors groupe et des groupes : seulement SES groupes ; déjà invité ; introuvable."""
    p = signed_phone(browser, "orga1", origin, "groupes")
    page = p.page
    e1 = load_state()["e1"]
    try:
        open_event(p)
        sheet = open_sheet(p)
        mine = {r["name"] for r in sql(f"""select g.name from public.member_groups g join public.member_group_members m on m.group_id = g.id
                    join public.profiles p on p.id = m.user_id where p.display_name = 'Bot Olga' and g.system_key is null""")}
        with p.step("groupes proposés = ses groupes seulement"):
            search = sheet.get_by_label("Chercher une personne ou un groupe")
            shown = [x.get_attribute("aria-label")[len("Ajouter "):] for x in
                     sheet.get_by_role("button", name=re.compile("^Ajouter ")).all()]
            p.log(f"proposés sans recherche : {shown} ; ses groupes : {mine}")
            for letter in ("a", "e", "o", "i"):
                p.type(search, letter, "la recherche")
                page.wait_for_timeout(700)
                hints = sheet.get_by_text(re.compile(r"^Groupe · \d+ personnes")).all()
                rows = sheet.get_by_role("button", name=re.compile("^Ajouter ")).all()
                groups = [r.get_attribute("aria-label")[len("Ajouter "):] for r in rows
                          if r.get_by_text(re.compile(r"^Groupe · ")).count()]
                strangers = [g for g in groups if g not in mine]
                p.log(f"« {letter} » : groupes {groups}")
                if strangers:
                    p.flag("🔴", "la feuille Inviter propose des groupes dont l'organisatrice n'est pas membre", str(strangers))
                    break
            search.fill("")
        with p.step("ajouter Bots (groupe), Bot Max (hors groupe), Bot Gina (Guest) ; retirer une puce ; Inviter"):
            blocked = sql(f"""select 1 from public.direct_blocks d join public.profiles a on a.id = d.user_id join public.profiles b on b.id = d.blocked_id
                             join public.member_group_members m on m.user_id in (a.id, b.id) join public.member_groups g on g.id = m.group_id
                             where g.name = {q(OTHER_GROUP)} and 'Bot Olga' in (a.display_name, b.display_name)""")
            p.log(f"blocage entre Olga et un membre de {OTHER_GROUP} : {bool(blocked)}")
            p.type(search, OTHER_GROUP, "la recherche")
            page.wait_for_timeout(800)
            p.tap(sheet.get_by_role("button", name=f"Ajouter {OTHER_GROUP}", exact=True), f"Ajouter {OTHER_GROUP}")
            p.see(sheet.get_by_text(re.compile("Prévenir")).first, "l'interrupteur « Prévenir le groupe »", 3000)
            for name in ("Bot Max", "Bot Gina", "Bot Valentin"):
                p.type(search, name.split()[1], "la recherche")
                page.wait_for_timeout(900)
                row = sheet.get_by_role("button", name=re.compile(rf"^Ajouter {name}$")).first
                hint = row.inner_text().replace("\n", " | ")
                p.log(f"{name} : {hint}")
                if name == "Bot Valentin":
                    if "Déjà invité" not in hint:
                        p.flag("🟡", "Bot Valentin (membre du groupe invité) n'est pas marqué « Déjà invité »", hint)
                    continue
                p.tap(row, f"Ajouter {name}")
            search.fill("")
            chips = [c.get_attribute("aria-label") for c in sheet.get_by_role("button", name=re.compile("^Retirer ")).all()]
            p.log(f"puces : {chips}")
            p.shot("puces")
            p.tap(sheet.get_by_role("button", name="Retirer Bot Gina"), "retirer la puce Bot Gina")
            p.type(search, "Gina", "la recherche")
            page.wait_for_timeout(800)
            p.tap(sheet.get_by_role("button", name=re.compile("^Ajouter Bot Gina$")).first, "Ajouter Bot Gina (encore)")
            search.fill("")
            rule = sheet.get_by_text(re.compile(rf"^{E1_GROUP} \+ {OTHER_GROUP}")).first
            p.see(rule, "la règle « Bots 2 + Bots + … »", 3000)
            p.log(f"règle : {rule.inner_text() if rule.count() else '?'}")
            btn = sheet.get_by_role("button", name=re.compile("^Inviter "))
            p.log(f"bouton : {btn.first.inner_text()}")
            p.tap(btn.first, "Inviter (Bots, Bot Max, Bot Gina)")
            page.wait_for_timeout(2500)
            toast(p, "Inviter")
            p.shot("apres-inviter")
            err = sheet.get_by_text(re.compile("inviter cette personne"))
            if err.count():
                p.flag("🔴", "Inviter un groupe où quelqu'un est bloqué par / a bloqué l'organisatrice : TOUT échoue "
                             "(groupe ET personnes), message « tu ne peux pas inviter cette personne » sans dire qui",
                       f"blocage Olga ↔ membre de {OTHER_GROUP} : {bool(blocked)}")
                p.tap(sheet.get_by_role("button", name=f"Retirer 👥 {OTHER_GROUP}"), f"retirer la puce {OTHER_GROUP}")
                p.tap(sheet.get_by_role("button", name=re.compile("^Inviter ")).first, "Inviter (Bot Max, Bot Gina)")
                page.wait_for_timeout(2500)
                toast(p, "Inviter (2e essai)")
                p.shot("apres-inviter-2")
            rows = sql(f"""select p.display_name, i.via_group, i.via_link from public.event_invites i join public.profiles p on p.id = i.user_id
                           where i.event_id = '{e1}' order by 1""")
            groups = sql(f"""select g.name from public.event_groups eg join public.member_groups g on g.id = eg.group_id where eg.event_id = '{e1}'""")
            p.log(f"base : invités {rows} ; groupes {groups}")
            names = {r["display_name"] for r in rows}
            if not {"Bot Max", "Bot Gina"} <= names:
                p.flag("🔴", "Inviter : Bot Max / Bot Gina absents de event_invites", str(rows))
            if not blocked and OTHER_GROUP not in {g["name"] for g in groups}:
                p.flag("🔴", f"Inviter : {OTHER_GROUP} absent de event_groups", str(groups))
            notifs = sql(f"""select p.display_name, n.kind from public.notifications n join public.profiles p on p.id = n.user_id
                             where n.event_id = '{e1}' order by n.created_at""")
            p.log(f"notifications : {notifs}")
        with p.step("« Zorglub » introuvable → lien pour une personne pré-rempli"):
            p.type(search, "Zorglub", "la recherche")
            page.wait_for_timeout(800)
            nf = sheet.get_by_text("« Zorglub » n’est pas sur Party ?")
            p.expect_or_flag(nf, "« Zorglub n'est pas sur Party ? »")
            p.tap(nf, "Envoie-lui un lien pour une personne")
            page.wait_for_timeout(600)
            val = sheet.get_by_label("Pour qui ? (facultatif)").input_value() if sheet.get_by_label("Pour qui ? (facultatif)").count() else ""
            p.log(f"Pour qui ? = {val!r}")
            if val != "Zorglub":
                p.flag("🟠", "« pas sur Party » ne pré-remplit pas le lien pour une personne", val)
            p.shot("zorglub")
            # La feuille reste en bas : le lien (en haut) est-il visible sans défiler ?
            label_box = sheet.get_by_label("Pour qui ? (facultatif)").bounding_box() if val else None
            if label_box and (label_box["y"] < 0 or label_box["y"] > 844):
                p.flag("🟡", "« pas sur Party » : le champ du lien pré-rempli reste hors de l'écran (faut remonter)", str(label_box))
        p.tap(sheet.get_by_role("button", name="Fermer").first, "✕")
        open_event(p)
        with p.step("« en plus » : Bot Max et Bot Gina, avec leur origine"):
            extra = page.get_by_text(re.compile(r"^EN PLUS · \d+")).first
            p.expect_or_flag(extra, "le bloc « En plus »")
            p.log(f"bloc : {extra.inner_text() if extra.count() else '?'}")
            p.see(page.get_by_text("Ajouté par toi").first, "« Ajouté par toi »", 4000) or p.flag("🟡", "origine « Ajouté par toi » absente")
            grp2 = page.get_by_role("button", name=re.compile(rf"^Groupe {E1_GROUP}, \d+ personnes"))
            p.expect_or_flag(grp2.first, "la ligne du groupe")
            p.shot("carte-en-plus")
    finally:
        p.close()
    # Oscar (Android) : son événement E3 ; groupes proposés = les siens ; l'API refuse un groupe dont il n'est pas membre.
    p = signed_phone(browser, "orga2", origin, "groupes-oscar")
    page = p.page
    try:
        e3 = load_state()["e3"]
        open_event(p, "e3")
        sheet = open_sheet(p)
        search = sheet.get_by_label("Chercher une personne ou un groupe")
        with p.step("Oscar : Bots 2 (pas son groupe) n'est pas proposé"):
            p.type(search, "Bots", "la recherche")
            page.wait_for_timeout(900)
            p.shot("oscar-groupes")
            if sheet.get_by_role("button", name=f"Ajouter {GROUP_BOTS_2}").count():
                p.flag("🔴", "Oscar se voit proposer Bots 2 dont il n'est pas membre")
        with p.step("Oscar : l'API refuse Bots 2 et refuse E1 (pas son événement)"):
            s = Session(BY_KEY["orga2"].phone)
            gid = sql(f"select id from public.member_groups where name = {q(GROUP_BOTS_2)}")[0]["id"]
            r = s.rpc("invite_people", e=e3, people=[], groups=[gid])
            p.log(f"invite_people(Bots 2) : {r.status_code} {r.text[:200]}")
            if r.status_code == 200:
                p.flag("🔴", "API : Oscar invite le groupe Bots 2 dont il n'est pas membre")
                sql(f"delete from public.event_groups where event_id = '{e3}' and group_id = '{gid}'")
            for fn, args in (("event_guest_list", {"e": load_state()["e1"]}),
                             ("create_event_invite", {"e": load_state()["e1"], "places": 1}),
                             ("invite_people", {"e": load_state()["e1"], "people": [], "groups": []}),
                             ("nudge_invitees", {"e": load_state()["e1"], "people": []}),
                             ("revoke_invite_link", {"tok": load_state()["link_stop"]})):
                r = s.rpc(fn, **args)
                p.log(f"{fn} sur E1 par Oscar : {r.status_code} {r.text[:160]}")
                if r.status_code == 200:
                    p.flag("🔴", f"API : {fn} accepté sur l'événement d'Olga pour Oscar (pas organisateur)")
            anon = httpx.post(f"{TEST_URL}/rest/v1/rpc/create_event_invite",
                              headers={"apikey": s.headers["apikey"], "Content-Type": "application/json"},
                              json={"e": e3, "places": 1}, timeout=30)
            p.log(f"create_event_invite sans compte : {anon.status_code}")
            if anon.status_code == 200:
                p.flag("🔴", "API : create_event_invite accepté sans compte")
        p.tap(sheet.get_by_role("button", name="Fermer").first, "✕")
        with p.step("Oscar (Android) : lien Copier depuis son événement"):
            sheet = open_sheet(p)
            tok = copy_link(p, sheet)
            p.log(f"lien d'Oscar : {tok}")
            if not tok:
                p.flag("🔴", "Android : Copier ne donne pas de lien")
            p.tap(sheet.get_by_role("button", name="Fermer").first, "✕")
    finally:
        p.close()


def phase_groupes2(browser, origin):
    """Bloquage : ce que voit l'organisatrice (Bots + Max) ; puis Max et Gina seuls ; bloc « En plus »."""
    p = signed_phone(browser, "orga1", origin, "groupes2")
    page = p.page
    e1 = load_state()["e1"]
    try:
        open_event(p)
        sheet = open_sheet(p)
        search = sheet.get_by_label("Chercher une personne ou un groupe")
        with p.step("Bots (Gus bloqué) + Bot Max → Inviter : message vu"):
            p.type(search, OTHER_GROUP, "la recherche")
            page.wait_for_timeout(1200)
            p.tap(sheet.get_by_role("button", name=f"Ajouter {OTHER_GROUP}", exact=True), f"Ajouter {OTHER_GROUP}")
            p.type(search, "Max", "la recherche")
            page.wait_for_timeout(1200)
            p.tap(sheet.get_by_role("button", name=re.compile("^Ajouter Bot Max$")).first, "Ajouter Bot Max")
            search.fill("")
            p.tap(sheet.get_by_role("button", name=re.compile("^Inviter ")).first, "Inviter (Bots, Bot Max)")
            err = sheet.get_by_text(re.compile("inviter cette personne"))
            if p.see(err, "le message d'erreur", 40000):
                p.log(f"message : {err.first.inner_text()!r}")
                p.flag("🔴", "Inviter un groupe où un membre est bloqué : tout échoue (Bot Max non plus n'est pas invité), "
                             "message « tu ne peux pas inviter cette personne » sans dire qui ni quoi faire")
            p.shot("blocage-message")
        with p.step("retirer la puce Bots, Inviter Bot Max + Bot Gina"):
            p.tap(sheet.get_by_role("button", name=f"Retirer 👥 {OTHER_GROUP}"), f"retirer la puce {OTHER_GROUP}")
            p.type(search, "Gina", "la recherche")
            page.wait_for_timeout(1200)
            p.tap(sheet.get_by_role("button", name=re.compile("^Ajouter Bot Gina$")).first, "Ajouter Bot Gina")
            search.fill("")
            p.tap(sheet.get_by_role("button", name=re.compile("^Inviter ")).first, "Inviter (Bot Max, Bot Gina)")
            t = ""
            for _ in range(40):
                page.wait_for_timeout(1000)
                rows = sql(f"""select p.display_name from public.event_invites i join public.profiles p on p.id = i.user_id
                               where i.event_id = '{e1}' and p.display_name in ('Bot Max', 'Bot Gina')""")
                if len(rows) == 2:
                    break
            t = toast(p, "Inviter", 8000)
            p.shot("max-gina-invites")
            p.log(f"base : {rows}")
            if len(rows) != 2:
                p.flag("🔴", "Inviter Bot Max + Bot Gina : pas en base", str(rows))
            if err.count() and err.first.is_visible():
                p.flag("🟡", "l'ancien message d'erreur reste affiché après une invitation réussie")
            notifs = sql(f"""select p.display_name, n.kind from public.notifications n join public.profiles p on p.id = n.user_id
                             where n.event_id = '{e1}' and n.kind = 'private_invite'""")
            p.log(f"notifications private_invite : {notifs}")
            if len(notifs) < 2:
                p.flag("🟠", "Bot Max / Bot Gina invités sans notification « private_invite »", str(notifs))
        p.tap(sheet.get_by_role("button", name="Fermer").first, "✕")
        open_event(p)
        with p.step("« en plus » : Bot Max et Bot Gina, avec leur origine"):
            extra = page.get_by_text(re.compile(r"^EN PLUS · \d+")).first
            p.expect_or_flag(extra, "le bloc « En plus »", "🟠", 30000)
            p.log(f"bloc : {extra.inner_text() if extra.count() else '?'}")
            p.see(page.get_by_text("Ajouté par toi").first, "« Ajouté par toi »", 4000) or p.flag("🟡", "origine « Ajouté par toi » absente")
            p.shot("carte-en-plus", full=True)
            p.log(f"compteur Pas répondu : {tile_count(p, 'Pas répondu')}")
    finally:
        p.close()


def _identify(p, bot, *, wrong_first: bool) -> None:
    page = p.page
    name = page.get_by_label("Prénom", exact=True)
    number = page.get_by_label("Numéro de portable")
    send = page.get_by_role("button", name="Recevoir mon code par SMS")
    p.shot("identite-vide")
    check_cut(p, "identité (sans l'app)")
    if wrong_first:
        disabled = send.get_attribute("aria-disabled")
        p.log(f"« Recevoir » sans rien : aria-disabled={disabled}")
        if disabled != "true":
            p.flag("🟡", "« Recevoir mon code » actif sans prénom ni numéro")
        p.type(name, bot.first, "le prénom")
        p.type(number, "123", "un numéro faux")
        p.tap(send, "Recevoir mon code par SMS (numéro faux)")
        page.wait_for_timeout(800)
        p.expect_or_flag(page.get_by_text(re.compile("Vérifie ton numéro")), "l'erreur « Vérifie ton numéro »")
        p.shot("numero-faux")
        # Perte réseau : l'envoi du code échoue proprement
        p.type(number, "0" + bot.phone[2:], "le numéro")
        p.ctx.set_offline(True)
        p.tap(send, "Recevoir mon code par SMS (hors ligne)")
        page.wait_for_timeout(2500)
        p.shot("hors-ligne")
        err = page.get_by_text(re.compile("Le code n’a pas pu être envoyé"))
        if not err.count():
            p.flag("🟠", "hors ligne : aucun message quand le code ne part pas")
        p.ctx.set_offline(False)
        page.wait_for_timeout(500)
    else:
        p.type(name, bot.first, "le prénom")
        p.type(number, "0" + bot.phone[2:], "le numéro")
    p.tap(send, "Recevoir mon code par SMS")
    code = page.get_by_placeholder("123456")
    code.wait_for(state="visible", timeout=60000)
    p.shot("code")
    p.see(page.get_by_text("En répondant, j’accepte les conditions d’utilisation de Party."), "la phrase des CGU", 3000) or \
        p.flag("🟠", "sans l'app : la phrase des CGU n'est pas au-dessus de Confirmer")
    if wrong_first:
        p.type(code, "000000", "un code faux")
        p.tap(page.get_by_role("button", name="Confirmer").last, "Confirmer (code faux)")
        page.wait_for_timeout(2500)
        p.expect_or_flag(page.get_by_text("Code incorrect ou expiré."), "l'erreur « Code incorrect »")
        p.shot("code-faux")
        code.fill("")
    p.type(code, "123456", "le code")
    p.tap(page.get_by_role("button", name="Confirmer").last, "Confirmer")
    page.wait_for_timeout(4500)


def open_invite(p, tok: str) -> None:
    """Ouvre la carte d'invitation ; base lente : « Lien indisponible » noté (capture) puis nouvel essai."""
    for attempt in range(4):
        p.goto(f"/events/invite/{tok}")
        try:
            p.page.get_by_text(re.compile(re.escape(E1_TITLE) + "|Lien indisponible")).first.wait_for(timeout=45000)
        except Exception:
            continue
        if p.page.get_by_text("Lien indisponible").count():
            body = p.page.locator("body").inner_text()
            p.log(f"carte en erreur (essai {attempt + 1}) : {body[:300]!r}")
            if attempt == 0:
                p.flag("🟠", "base lente / erreur passagère : l'invité lit « Lien indisponible · Ce lien d'invitation n'existe plus » "
                             "(faux : le lien existe), sans bouton Réessayer", body[:200])
            p.page.wait_for_timeout(5000)
            continue
        return
    raise RuntimeError("carte d'invitation jamais chargée")


def _db_guest(event_id: str, phone_number: str) -> dict:
    rows = sql(f"""select p.id, p.display_name, p.first_name, p.role, r.status::text status, r.waitlisted,
                   (select count(*) from private.light_invitees l where l.user_id = p.id) light,
                   (select count(*) from public.terms_acceptances a where a.user_id = p.id) terms,
                   (select row_to_json(i) from public.event_invites i where i.event_id = '{event_id}' and i.user_id = p.id) invite
                   from public.profiles p left join public.rsvps r on r.user_id = p.id and r.event_id = '{event_id}'
                   where p.phone = {q(phone_number)}""")
    return rows[0] if rows else {}


def phase_sans_app(browser, origin):
    """Sam (iPhone, lien « Une personne ») : tout le parcours sans compte ; Sara (Android, lien 2 places) : Absent."""
    st = load_state()
    e1 = st["e1"]
    bot = BY_KEY["sansapp1"]
    if sql(f"select 1 from auth.users where phone = {q(bot.phone)}"):
        anomaly("sansapp1", "🟡", "Sam a déjà un compte : le parcours « sans compte » n'est pas neuf", "")
    p = fresh_phone(browser, "sansapp1", origin, "sans-app")
    page = p.page
    tok = st["link_sam"]
    try:
        open_invite(p, tok)
        p.shot("carte")
        p.dump("carte")
        check_cut(p, "carte d'invitation (sans compte)")
        with p.step("carte lisible sans compte : qui, quoi, quand, où (sans adresse), réponses"):
            for text in ("Bot Olga t’invite, Sam", "Seulement toi, avec ce lien", "Salle des bots, Vevey",
                         "L’adresse exacte après ta réponse", "Pas besoin d’installer l’app."):
                p.see(page.get_by_text(text).first, text, 4000) or p.flag("🟠", f"carte sans compte : « {text} » absent")
            if page.get_by_text("Rue des Bots").count():
                p.flag("🔴", "carte sans compte : l'adresse exacte est montrée avant la réponse")
            for b in ("Je viens !", "Peut-être", "Je ne peux pas"):
                p.see(page.get_by_role("button", name=b).first, b, 3000) or p.flag("🔴", f"bouton « {b} » absent")
            opened_at = [x for x in links_of(e1) if x["token"] == tok][0]["opened_at"]
            p.log(f"opened_at : {opened_at}")
            if not opened_at:
                p.flag("🟠", "ouvrir le lien ne note pas « A ouvert » (opened_at vide)")
            p.scroll_to_bottom("carte d'invitation")
        with p.step("Je viens ! → retour à l'invitation → Je viens ! (aller-retour)"):
            p.tap(page.get_by_role("button", name="Je viens !").first, "Je viens !")
            p.see(page.get_by_text("Super, tu viens ! 🎉"), "Super, tu viens !", 5000)
            p.tap(page.get_by_role("button", name="‹ Retour à l’invitation"), "‹ Retour à l’invitation")
            p.see(page.get_by_role("button", name="Je viens !").first, "la carte de nouveau", 5000) or \
                p.flag("🟠", "« Retour à l'invitation » ne revient pas à la carte")
            p.tap(page.get_by_role("button", name="Je viens !").first, "Je viens !")
        with p.step("prénom + numéro + code (erreurs, hors ligne, code faux, puis bon code)"):
            _identify(p, bot, wrong_first=True)
            f.accept_terms_if_asked(p)
            p.shot("confirmation")
            p.dump("confirmation")
            check_cut(p, "confirmation (sans l'app)")
            if not p.see(page.get_by_text(re.compile("C’est noté, Sam")), "C'est noté, Sam !", 10000):
                p.flag("🔴", "sans l'app : pas d'écran « C'est noté » après le code")
        with p.step("base : compte minimal, CGU, invitation par lien, réponse"):
            g = _db_guest(e1, bot.phone)
            p.log(f"base : {g}")
            if g.get("display_name") != "Sam":
                p.flag("🔴", "compte minimal : prénom pas enregistré", str(g))
            if not g.get("light"):
                p.flag("🟠", "compte minimal pas noté dans light_invitees (purge à 7 jours impossible)", str(g))
            if not g.get("terms"):
                p.flag("🔴", "CGU pas enregistrées pour le compte minimal (le prénom est vu des autres)", str(g))
            if g.get("status") != "yes":
                p.flag("🔴", "« Je viens » pas enregistré", str(g))
            inv = g.get("invite") or {}
            if not inv.get("via_link"):
                p.flag("🔴", "invitation par lien pas notée (event_invites.via_link)", str(inv))
            link = [x for x in links_of(e1) if x["token"] == tok][0]
            p.log(f"lien après réponse : {link}")
            if link["used_by"] != g.get("id") or link["uses"] != 1:
                p.flag("🔴", "lien « une personne » pas marqué utilisé", str(link))
        with p.step("confirmation : adresse, calendrier, itinéraire, Installer Party, Plus tard"):
            p.see(page.get_by_text("Rue des Bots 3, 1800 Vevey").first, "l'adresse exacte après la réponse", 4000) or \
                p.flag("🟠", "confirmation : l'adresse exacte n'apparaît pas après la réponse")
            p.see(page.get_by_text(re.compile("Bot Olga est prévenu")), "« Bot Olga est prévenu »", 3000)
            before = page.url
            p.tap(page.get_by_role("button", name="📍 Itinéraire"), "Itinéraire")
            p.tap(page.get_by_role("button", name="Installer Party"), "Installer Party")
            page.wait_for_timeout(600)
            urls = opened(p)
            p.log(f"ouvertures : {urls}")
            if not any("maps" in u for u in urls):
                p.flag("🟠", "Itinéraire : aucune carte ouverte", str(urls))
            if not any("apple.com" in u for u in urls):
                p.flag("🟠", "Installer Party : rien d'ouvert", str(urls))
            # iPhone : « Ajouter à mon agenda » ouvre le fichier .ics (la page part vers /api/calendar.ics)
            ics = []
            page.on("request", lambda r: ics.append(r.url) if "calendar.ics" in r.url else None)
            p.tap(page.get_by_role("button", name="Ajouter à mon agenda"), "Ajouter à mon agenda")
            page.wait_for_timeout(2500)
            p.log(f"agenda : {ics} ; page {page.url}")
            if ics:
                r = httpx.get(ics[0], timeout=20)
                p.log(f".ics : {r.status_code} {r.headers.get('content-type')} {r.text[:300]!r}")
                if r.status_code != 200 or "BEGIN:VEVENT" not in r.text:
                    p.flag("🔴", "Ajouter à mon agenda : fichier .ics invalide", f"{r.status_code} {r.text[:200]}")
                elif "Rue des Bots" not in r.text:
                    p.flag("🟡", "agenda : l'adresse exacte n'est pas dans le .ics")
            else:
                p.flag("🟠", "Ajouter à mon agenda : aucun .ics demandé")
            if page.url != before:
                p.goto(f"/events/invite/{tok}")
                page.wait_for_timeout(3500)
        with p.step("rouvrir le lien : « Ta réponse : Je viens ! », changer pour Peut-être"):
            open_invite(p, tok)
            page.wait_for_timeout(1500)
            p.shot("lien-rouvert")
            p.see(page.get_by_text(re.compile("Ta réponse : Je viens !")), "« Ta réponse : Je viens ! »", 6000) or \
                p.flag("🔴", "lien rouvert : la réponse donnée n'est pas montrée")
            if page.get_by_text("L’adresse exacte après ta réponse").count():
                p.flag("🟡", "lien rouvert après réponse : encore « L'adresse exacte après ta réponse »")
            p.tap(page.get_by_role("button", name="Peut-être").first, "Peut-être")
            p.see(page.get_by_text(re.compile("C’est noté")), "C'est noté (Peut-être)", 8000) or \
                p.flag("🔴", "changer d'avis : pas de confirmation")
            p.shot("peut-etre")
            if _db_guest(e1, bot.phone).get("status") != "maybe":
                p.flag("🔴", "changer d'avis (Peut-être) pas enregistré")
        with p.step("Plus tard, puis Changer ma réponse → Je ne peux pas"):
            later = page.get_by_role("button", name="Plus tard")
            if later.count():
                p.tap(later, "Plus tard")
                page.wait_for_timeout(500)
                if page.get_by_role("button", name="Installer Party").count():
                    p.flag("🟡", "« Plus tard » ne masque pas la carte « Installer Party »")
            p.tap(page.get_by_role("button", name="Changer ma réponse"), "Changer ma réponse")
            page.wait_for_timeout(2500)
            p.tap(page.get_by_role("button", name="Je ne peux pas").first, "Je ne peux pas")
            p.see(page.get_by_text(re.compile("Tu ne viens pas à")), "« Tu ne viens pas à »", 8000) or \
                p.flag("🔴", "Je ne peux pas : pas de confirmation")
            p.shot("absent")
            if page.get_by_role("button", name="📍 Itinéraire").count():
                p.flag("🟡", "absent : itinéraire encore proposé")
            if _db_guest(e1, bot.phone).get("status") != "no":
                p.flag("🔴", "« Je ne peux pas » pas enregistré")
        with p.step("retour arrière du navigateur et rechargement"):
            page.go_back()
            page.wait_for_timeout(2500)
            p.shot("retour-arriere")
            p.goto(f"/events/invite/{tok}")
            page.reload()
            page.wait_for_timeout(3500)
            p.see(page.get_by_text(re.compile("Ta réponse : Je ne peux pas")), "réponse après rechargement", 6000) or \
                p.flag("🟠", "après rechargement : la réponse n'est pas montrée")
        with p.step("remettre « Je viens ! » (pour la carte de l'organisatrice)"):
            p.tap(page.get_by_role("button", name="Je viens !").first, "Je viens !")
            page.wait_for_timeout(4000)
    finally:
        p.close()

    # Sara (Android) : lien 2 places, « Je ne peux pas » ; « Installer Party » sur Android
    bot = BY_KEY["sansapp2"]
    p = fresh_phone(browser, "sansapp2", origin, "sans-app")
    page = p.page
    tok = st["link_two"]
    try:
        open_invite(p, tok)
        p.shot("carte")
        p.see(page.get_by_text(re.compile("Lien pour plusieurs · reste 2 places")), "« reste 2 places »", 4000) or \
            p.flag("🟠", "lien pour plusieurs : places restantes absentes ou fausses")
        with p.step("Je ne peux pas → prénom + numéro + code"):
            p.tap(page.get_by_role("button", name="Je ne peux pas").first, "Je ne peux pas")
            p.see(page.get_by_text("Dommage !"), "Dommage !", 4000)
            _identify(p, bot, wrong_first=False)
            f.accept_terms_if_asked(p)
            p.shot("confirmation")
            p.see(page.get_by_text(re.compile("C’est noté, Sara")), "C'est noté, Sara", 10000) or \
                p.flag("🔴", "Sara : pas de confirmation")
            g = _db_guest(e1, bot.phone)
            p.log(f"base : {g}")
            if g.get("status") != "no":
                p.flag("🔴", "Sara : « Je ne peux pas » pas enregistré", str(g))
        with p.step("Android : « Installer Party »"):
            inst = page.get_by_role("button", name="Installer Party")
            if inst.count():
                p.tap(inst, "Installer Party")
                page.wait_for_timeout(500)
                urls = opened(p)
                p.log(f"ouvertures : {urls}")
                if any("apple.com" in u for u in urls):
                    p.flag("🟠", "Android : « Installer Party » ouvre l'App Store / TestFlight d'Apple (rien pour Android)",
                           str(urls))
        with p.step("Android : relire le lien → 1 place restante pour les autres"):
            anon = browser.new_context()
            ap = anon.new_page()
            ap.goto(f"{origin}/events/invite/{tok}")
            ap.wait_for_timeout(5000)
            txt = ap.locator("body").inner_text()
            p.log(f"lien vu d'un autre téléphone : {txt[:300]!r}")
            if "reste 1 place" not in txt:
                p.flag("🟠", "après Sara : le lien ne dit pas « reste 1 place »", txt[:200])
            anon.close()
    finally:
        p.close()


def _anon_card(browser, origin, path: str, shot_name: str, key: str = "sansapp2") -> str:
    p = fresh_phone(browser, key, origin, f"anonyme-{shot_name}")
    try:
        p.goto(path)
        try:
            p.page.get_by_text(re.compile(r"\[C2-03\]|Lien indisponible")).first.wait_for(timeout=45000)
        except Exception:
            p.log("carte pas chargée en 45 s")
        p.page.wait_for_timeout(1500)
        p.shot(shot_name)
        text = p.page.locator("body").inner_text()
        p.log(f"{shot_name} : {text[:400]!r}")
        return text
    finally:
        p.close()


def phase_limites(browser, origin):
    """Lien plein (2e place prise par Bot Gus, compte existant, puis un 3e téléphone), expiré, arrêté (glissé),
    invalide, inconnu, événement annulé."""
    st = load_state()
    e1 = st["e1"]
    # 2e place : Bot Gus (Guest, compte avec surnom, Android) → réponse directe sans prénom
    p = signed_phone(browser, "guest1", origin, "lien-plein")
    page = p.page
    acc = []
    page.on("request", lambda r: acc.append(r.url) if "accept_invite" in r.url else None)
    try:
        open_invite(p, st['link_two'])
        p.shot("carte-gus")
        p.see(page.get_by_text(re.compile("reste 1 place")), "« reste 1 place »", 4000)
        with p.step("Gus (compte) : Je viens ! → enregistré tout de suite"):
            p.tap(page.get_by_role("button", name="Je viens !").first, "Je viens !")
            page.wait_for_timeout(5000)
            p.shot("gus-confirmation")
            p.log(f"appels accept_invite : {len(acc)}")
            p.see(page.get_by_text(re.compile("C’est noté")), "C'est noté (Gus)", 6000) or \
                p.flag("🔴", "compte existant : pas de confirmation par le lien")
            g = _db_guest(e1, BY_KEY["guest1"].phone)
            p.log(f"base : {g}")
            if g.get("status") != "yes":
                p.flag("🔴", "Gus : réponse par le lien pas enregistrée", str(g))
            if g.get("display_name") != "Bot Gus":
                p.flag("🔴", "Gus : son surnom a été changé par le lien", str(g))
            blocked = sql("""select 1 from public.direct_blocks d join public.profiles a on a.id = d.user_id join public.profiles b on b.id = d.blocked_id
                             where (a.display_name, b.display_name) in (('Bot Olga', 'Bot Gus'), ('Bot Gus', 'Bot Olga'))""")
            if blocked and g.get("status"):
                p.flag("🟡", "Bot Gus, bloqué par l'organisatrice, entre quand même par un lien pour plusieurs (aucun contrôle du blocage)",
                       "accept_invite n'appelle pas blocked_either")
    finally:
        p.close()
    text = _anon_card(browser, origin, f"/events/invite/{st['link_two']}", "lien-plein")
    if "toutes ses places sont prises" not in text:
        anomaly("sansapp2", "🔴", "lien plein : pas de message « toutes ses places sont prises »", text[:200])
    if "Je viens !" in text:
        anomaly("sansapp2", "🔴", "lien plein : « Je viens ! » encore proposé", "")
    # Expiré : date limite passée (base de TEST)
    sql(f"update private.invite_links set expires_at = now() - interval '1 minute' where token = '{st['link_exp']}'")
    text = _anon_card(browser, origin, f"/events/invite/{st['link_exp']}", "lien-expire")
    if "plus valable" not in text:
        anomaly("sansapp2", "🔴", "lien expiré : pas de message « plus valable »", text[:200])
    # Arrêter le lien 7 jours par un glissé sur la carte de l'organisatrice
    p = signed_phone(browser, "orga1", origin, "arreter-lien")
    page = p.page
    try:
        open_event(p)
        with p.step("glisser « Lien pour plusieurs » (7 jours) : Arrêter → Confirmer"):
            exp7 = sql(f"select expires_at from private.invite_links where token = '{st['link_stop']}'")[0]["expires_at"]
            p.log(f"lien à arrêter : {st['link_stop']} jusqu'au {exp7}")
            rows = page.get_by_role("button", name="Arrêter Lien pour plusieurs").all()
            p.log(f"{len(rows)} lien(s) « pour plusieurs » arrêtables")
            # La ligne à glisser : celle du lien 7 jours (4 places)
            target = page.get_by_text(re.compile(r"^0 sur 4 places · jusqu’au")).first
            p.expect_or_flag(target, "la ligne « 0 sur 4 places » du lien 7 jours")
            p.log(f"ligne : {target.inner_text()}")
            swipe_left(p, target, "lien 7 jours")
            p.shot("lien-glisse")
            stop = page.get_by_role("button", name="Arrêter Lien pour plusieurs")
            visible = [b for b in stop.all() if b.is_visible()]
            if not visible:
                p.flag("🔴", "glisser une ligne de lien ne montre pas « Arrêter »")
            else:
                visible[0].tap()
                page.wait_for_timeout(600)
                conf = [b for b in page.get_by_role("button", name="Confirmer Lien pour plusieurs").all() if b.is_visible()]
                p.shot("lien-confirmer")
                if not conf:
                    p.flag("🔴", "Arrêter un lien : pas de « Confirmer »")
                else:
                    cb = conf[0].bounding_box()
                    p.log(f"Confirmer : {cb}")
                    conf[0].tap()
                    page.wait_for_timeout(2500)
                    toast(p, "Arrêter")
                    p.shot("lien-arrete")
            rev = sql(f"select revoked_at from private.invite_links where token = '{st['link_stop']}'")[0]["revoked_at"]
            p.log(f"revoked_at : {rev}")
            if not rev:
                p.flag("🔴", "Arrêter le lien : pas arrêté en base (ou mauvais lien glissé)")
                all_rev = sql(f"select token, label, max_uses, revoked_at from private.invite_links where target = '{e1}' and revoked_at is not null")
                p.log(f"liens arrêtés : {all_rev}")
            gl = guest_list(e1, BY_KEY["orga1"].phone)
            if any(x["token"] == st["link_stop"] for x in gl["links"]):
                p.log("le lien arrêté (jamais utilisé) reste dans la liste")
            else:
                p.log("le lien arrêté jamais utilisé disparaît de la carte")
    finally:
        p.close()
    text = _anon_card(browser, origin, f"/events/invite/{st['link_stop']}", "lien-arrete")
    if "arrêté ce lien" not in text:
        anomaly("sansapp2", "🔴", "lien arrêté : pas de message « a arrêté ce lien »", text[:200])
    text = _anon_card(browser, origin, "/events/invite/pas-un-jeton", "lien-invalide")
    if "pas complet" not in text:
        anomaly("sansapp2", "🟡", "lien tronqué : pas de message « pas complet »", text[:200])
    text = _anon_card(browser, origin, "/events/invite/00000000-0000-4000-8000-000000000000", "lien-inconnu")
    if "n’existe plus" not in text:
        anomaly("sansapp2", "🟡", "lien inconnu : pas de message « n'existe plus »", text[:200])
    # Événement annulé (E2) : lien créé par l'API d'Olga, puis E2 annulé (base de TEST)
    s = Session(BY_KEY["orga1"].phone)
    r = s.rpc("create_event_invite", e=st["e2"], places=3)
    tok = r.json().get("token") if r.status_code == 200 else None
    print("lien E2 :", r.status_code, r.text[:200], flush=True)
    if tok:
        sql(f"update public.events set status = 'cancelled' where id = '{st['e2']}'")
        text = _anon_card(browser, origin, f"/events/invite/{tok}", "evenement-annule")
        if "annulé" not in text:
            anomaly("sansapp2", "🔴", "événement annulé : la carte du lien ne le dit pas", text[:200])
        if "Je viens !" in text:
            anomaly("sansapp2", "🔴", "événement annulé : « Je viens ! » encore proposé", "")
        save_state(link_e2=tok)


def phase_limites2(browser, origin):
    """Reprise (base lente) : lien plein vu d'un 3e téléphone ; arrêter le lien 7 jours d'un glissé."""
    st = load_state()
    text = _anon_card(browser, origin, f"/events/invite/{st['link_two']}", "lien-plein")
    if "toutes ses places sont prises" not in text:
        anomaly("sansapp2", "🔴", "lien plein : pas de message « toutes ses places sont prises »", text[:300])
    if "Je viens !" in text:
        anomaly("sansapp2", "🔴", "lien plein : « Je viens ! » encore proposé", "")
    if sql(f"select revoked_at from private.invite_links where token = '{st['link_stop']}'")[0]["revoked_at"]:
        p = None
    else:
        p = signed_phone(browser, "orga1", origin, "arreter-lien")
    page = p.page if p else None
    try:
        if not p:
            raise StopIteration
        open_event(p)
        p.shot("carte-liens", full=True)
        with p.step("glisser le lien 7 jours : Arrêter → Confirmer"):
            target = page.get_by_text(re.compile(r"^0 sur 4 places · jusqu’au")).first
            p.expect_or_flag(target, "la ligne « 0 sur 4 places » du lien 7 jours", "🟠", 30000)
            swipe_left(p, target, "lien 7 jours")
            p.shot("lien-glisse")
            visible = [b for b in page.get_by_role("button", name="Arrêter Lien pour plusieurs").all() if b.is_visible()]
            if not visible:
                p.flag("🔴", "glisser une ligne de lien ne montre pas « Arrêter »")
                return
            visible[0].tap()
            page.wait_for_timeout(600)
            conf = [b for b in page.get_by_role("button", name="Confirmer Lien pour plusieurs").all() if b.is_visible()]
            p.shot("lien-confirmer")
            if not conf:
                p.flag("🔴", "Arrêter un lien : pas de « Confirmer »")
                return
            conf[0].tap()
            t = toast(p, "Arrêter", 30000)
            p.shot("lien-arrete")
            rev = None
            for _ in range(20):
                rev = sql(f"select revoked_at from private.invite_links where token = '{st['link_stop']}'")[0]["revoked_at"]
                if rev:
                    break
                page.wait_for_timeout(1000)
            p.log(f"revoked_at : {rev}")
            if not rev:
                arr = sql(f"select token, max_uses, revoked_at from private.invite_links where target = '{st['e1']}' and revoked_at is not null")
                p.flag("🔴", "Arrêter le lien : le lien glissé n'est pas arrêté en base", str(arr))
            page.wait_for_timeout(2000)
            still = page.get_by_text(re.compile(r"^0 sur 4 places · jusqu’au")).count()
            p.log(f"lignes « 0 sur 4 places · jusqu'au » restantes : {still}")
    except StopIteration:
        pass
    finally:
        if p:
            p.close()
    text = _anon_card(browser, origin, f"/events/invite/{st['link_stop']}", "lien-arrete")
    if "arrêté ce lien" not in text:
        anomaly("sansapp2", "🔴", "lien arrêté : pas de message « a arrêté ce lien »", text[:300])


def phase_relances(browser, origin):
    """Relancer une personne, tous, un lien ; une seule fois par jour."""
    st = load_state()
    e1 = st["e1"]
    p = signed_phone(browser, "orga1", origin, "relances")
    page = p.page
    try:
        open_event(p)
        gl0 = guest_list(e1, BY_KEY["orga1"].phone)
        waiting0 = [x["name"] for x in gl0["people"] if not x["status"] and not x["nudged_today"]]
        p.log(f"sans réponse, pas relancés : {waiting0} ; has_app : {[(x['name'], x['has_app']) for x in gl0['people']]}")
        with p.step("Relancer Bot Max (une personne)"):
            p.tap(tile(p, "Pas répondu").first, "filtre Pas répondu")
            page.wait_for_timeout(600)
            p.shot("pas-repondu")
            btn = page.get_by_role("button", name="Relancer Bot Max")
            p.tap(btn, "Relancer Bot Max")
            page.wait_for_timeout(2000)
            t = toast(p, "Relancer Bot Max")
            p.shot("max-relance")
            n = sql(f"""select channel, count(*) n from private.invite_nudges x join public.profiles p on p.id = x.user_id
                        where x.event_id = '{e1}' and p.display_name = 'Bot Max' group by 1""")
            p.log(f"relances de Max en base : {n}")
            if not n:
                p.flag("🔴", "Relancer Bot Max : rien en base")
            p.see(page.get_by_text("Relancé ✓").first, "« Relancé ✓ »", 4000) or p.flag("🟠", "après relance : pas de « Relancé ✓ »")
            if page.get_by_role("button", name="Relancer Bot Max").count():
                p.flag("🟠", "Relancer Bot Max encore proposé le même jour")
        with p.step("Relancer Bot Max encore par l'API : refusé / compté « déjà relancé »"):
            s = Session(BY_KEY["orga1"].phone)
            mx = sql("select id from public.profiles where display_name = 'Bot Max'")[0]["id"]
            r = s.rpc("nudge_invitees", e=e1, people=[mx])
            p.log(f"2e relance : {r.status_code} {r.text}")
            if r.status_code == 200 and r.json().get("skipped") != 1:
                p.flag("🔴", "limite d'une relance par jour non tenue", r.text)
        with p.step("Relancer tous ceux qui n'ont pas répondu"):
            p.tap(tile(p, "Pas répondu").first, "filtre Pas répondu (retour)")
            page.wait_for_timeout(500)
            all_btn = page.get_by_role("button", name=re.compile("^↻ Relancer"))
            p.expect_or_flag(all_btn.first, "« ↻ Relancer les … »")
            label = all_btn.first.inner_text()
            p.log(f"bouton : {label}")
            p.tap(all_btn.first, label)
            page.wait_for_timeout(2500)
            t = toast(p, "Relancer tous")
            p.shot("tous-relances")
            gl = guest_list(e1, BY_KEY["orga1"].phone)
            after = [(x["name"], x["has_app"], x["nudged_today"]) for x in gl["people"] if not x["status"]]
            p.log(f"après « tous » : {after}")
            no_app = [x["name"] for x in gl["people"] if not x["status"] and not x["has_app"]]
            if t and "sans l’app : relance-les une par une" in t:
                still = [n for n in no_app if page.get_by_role("button", name=f"Relancer {n}").count()]
                p.log(f"sans l'app encore relançables une par une : {still}")
                if no_app and not still:
                    p.flag("🟠", "« Relancer tous » dit « relance-les une par une » mais ne laisse plus aucun bouton "
                                 "« Relancer » (comptés relancés sans avoir rien reçu)", f"{t} ; sans l'app : {no_app}")
            if page.get_by_role("button", name=re.compile("^↻ Relancer")).count():
                p.flag("🟡", "« ↻ Relancer » encore proposé juste après avoir relancé tout le monde")
            notifs = sql(f"""select p.display_name, n.kind, n.body from public.notifications n join public.profiles p on p.id = n.user_id
                             where n.event_id = '{e1}' and n.kind = 'private_invite' order by n.created_at""")
            p.log(f"notifications private_invite : {notifs}")
            held = sql("select kind, count(*) n from private.bots_quarantine_log group by 1")
            p.log(f"quarantaine : {held}")
        with p.step("relancer un lien (glissé → ↻ Relancer), puis plus le même jour"):
            target = page.get_by_text(re.compile(r"^Envoyé .* · pas encore ouvert|^Ouvert .* · pas encore de réponse")).first
            if not target.count():
                p.flag("🟡", "aucune ligne de lien « pas encore ouvert » à relancer")
            else:
                p.log(f"ligne : {target.inner_text()}")
                swipe_left(p, target, "lien pas ouvert")
                near = action_near(p, re.compile("^Relancer Lien pour"), target)
                rel = [near] if near else []
                p.shot("lien-relance-glisse")
                if not rel:
                    p.flag("🔴", "glisser un lien ne montre pas « ↻ Relancer »")
                else:
                    who = rel[0].get_attribute("aria-label")
                    rel[0].tap()
                    page.wait_for_timeout(2000)
                    toast(p, "relance du lien")
                    clip = page.evaluate("navigator.clipboard.readText()")
                    p.log(f"presse-papiers : {clip!r}")
                    if "Petit rappel" not in (clip or ""):
                        p.flag("🟠", "relance d'un lien : le message de rappel n'est pas prêt (copie / partage)", clip)
                    n = sql(f"select count(*) n from private.invite_nudges where event_id = '{e1}' and token is not null")[0]["n"]
                    p.log(f"relances de liens en base : {n} ({who})")
                    open_event(p)
                    t2 = page.get_by_text(re.compile(r"^Envoyé .* · pas encore ouvert|^Ouvert .* · pas encore de réponse")).first
                    swipe_left(p, t2, "même lien")
                    p.shot("lien-relance-2")
                    if action_near(p, who, t2):
                        p.flag("🟠", "lien relancé : « ↻ Relancer » encore proposé le même jour", who)
        check_cut(p, "carte après relances")
    finally:
        p.close()


def phase_retrait_puis_lien(browser, origin):
    """Olga retire Sam (venu par le lien) d'un glissé ; Sam rouvre son lien et répond : message clair, pas de boucle."""
    st = load_state()
    e1 = st["e1"]
    p = signed_phone(browser, "orga1", origin, "retirer")
    page = p.page
    try:
        open_event(p)
        with p.step("glisser Sam → Retirer → Confirmer"):
            row = page.get_by_text("Sam", exact=True).first
            p.expect_or_flag(row, "Sam sur la carte")
            p.see(page.get_by_text("SANS L’APP").first, "l'étiquette « SANS L'APP »", 3000) or \
                p.flag("🟡", "Sam (compte minimal) sans étiquette « SANS L'APP »")
            p.see(page.get_by_text(re.compile("Par le lien « Sam »")).first, "« Par le lien « Sam » »", 3000) or \
                p.flag("🟡", "origine « Par le lien « Sam » » absente")
            swipe_left(p, row, "Sam")
            btn = [b for b in page.get_by_role("button", name="Retirer Sam").all() if b.is_visible()]
            p.shot("sam-glisse")
            if not btn:
                p.flag("🔴", "glisser Sam ne montre pas « Retirer »")
                return
            btn[0].tap()
            page.wait_for_timeout(500)
            conf = [b for b in page.get_by_role("button", name="Confirmer Sam").all() if b.is_visible()]
            if not conf:
                p.flag("🔴", "Retirer Sam : pas de « Confirmer »")
                return
            box = conf[0].bounding_box()
            p.log(f"Confirmer : {box}")
            if box["height"] < 40:
                p.flag("🟠", "« Confirmer » écrasé", str(box))
            conf[0].tap()
            page.wait_for_timeout(2500)
            toast(p, "Retirer Sam")
            p.shot("sam-retire")
            g = _db_guest(e1, BY_KEY["sansapp1"].phone)
            p.log(f"base : {g}")
            if g.get("invite") or g.get("status"):
                p.flag("🔴", "Sam retiré : invitation ou réponse encore en base", str(g))
        with p.step("annuler un retrait : Retirer puis glisser en arrière (pas de Confirmer)"):
            row = page.get_by_text("Bot Gina", exact=True).first
            if row.count():
                swipe_left(p, row, "Bot Gina")
                btn = [b for b in page.get_by_role("button", name="Retirer Bot Gina").all() if b.is_visible()]
                if btn:
                    btn[0].tap()
                    page.wait_for_timeout(400)
                    box = row.bounding_box()
                    cdp = p.ctx.new_cdp_session(page)
                    cdp.send("Input.synthesizeScrollGesture", {"x": 60, "y": box["y"] + box["height"] / 2, "xDistance": 300,
                                                               "yDistance": 0, "gestureSourceType": "touch"})
                    cdp.detach()
                    page.wait_for_timeout(800)
                    swipe_left(p, row, "Bot Gina (encore)")
                    again = [b.get_attribute("aria-label") for b in page.get_by_role("button", name=re.compile("Bot Gina$")).all() if b.is_visible()]
                    p.log(f"boutons après ré-ouverture : {again}")
                    p.shot("gina-reouverte")
                    if "Confirmer Bot Gina" in again:
                        p.flag("🟡", "ligne refermée puis rouverte : « Confirmer » reste armé (un toucher retire aussitôt)")
    finally:
        p.close()
    phase_sam_rouvre(browser, origin)


def phase_sam_rouvre(browser, origin):
    """Sam, retiré par l'organisatrice, rouvre son lien et répond : message clair, pas de boucle."""
    st = load_state()
    p = phone(browser, "sansapp1", origin, "retire-rouvre")
    p.ctx.add_init_script(RECORD_OPENS)
    page = p.page
    calls = []
    page.on("request", lambda r: calls.append(r.url) if "rpc/accept_invite" in r.url else None)
    try:
        open_invite(p, st['link_sam'])
        p.shot("carte-apres-retrait")
        text = page.locator("body").inner_text()
        p.log(f"carte : {text[:400]!r}")
        with p.step("Sam retiré tape « Je viens ! »"):
            p.tap(page.get_by_role("button", name="Je viens !").first, "Je viens !")
            page.wait_for_timeout(8000)
            p.shot("apres-je-viens")
            p.log(f"appels accept_invite en 8 s : {len(calls)}")
            body = page.locator("body").inner_text()
            p.log(f"écran : {body[:300]!r}")
            if len(calls) > 3:
                p.flag("🔴", "Sam retiré : « Je viens ! » relance accept_invite en boucle (useEffect sans fin)",
                       f"{len(calls)} appels en 8 s")
            if "retiré" not in body:
                p.flag("🟠", "Sam retiré : pas de message clair", body[:200])
            if _db_guest(st["e1"], BY_KEY["sansapp1"].phone).get("status"):
                p.flag("🔴", "Sam retiré a pu répondre quand même")
    finally:
        p.close()


def phase_orga_son_lien(browser, origin):
    """L'organisatrice ouvre son propre lien « Test orga » et touche « Je viens ! » : le lien d'un invité est-il brûlé ?"""
    st = load_state()
    p = signed_phone(browser, "orga1", origin, "son-lien")
    page = p.page
    try:
        open_invite(p, st['link_orga'])
        p.shot("son-lien")
        row = [x for x in links_of(st["e1"]) if x["token"] == st["link_orga"]][0]
        p.log(f"lien : {row}")
        if row["opened_at"]:
            p.flag("🟡", "l'organisatrice qui ouvre son propre lien le marque « A ouvert »")
        with p.step("Je viens ! sur son propre lien"):
            p.tap(page.get_by_role("button", name="Je viens !").first, "Je viens !")
            page.wait_for_timeout(5000)
            p.shot("son-lien-reponse")
            row = [x for x in links_of(st["e1"]) if x["token"] == st["link_orga"]][0]
            olga = sql("select id from public.profiles where display_name = 'Bot Olga'")[0]["id"]
            p.log(f"lien après : {row}")
            if row["used_by"] == olga:
                p.flag("🟠", "l'organisatrice qui teste son lien « pour une personne » le consomme : l'invité ne peut plus s'en servir",
                       "used_by = organisatrice")
    finally:
        p.close()


def phase_meta(browser, origin):
    """Aperçu WhatsApp : balises Open Graph du lien (robot de WhatsApp, sans compte), sans compter comme une ouverture."""
    st = load_state()
    tok = st["link_meta"]
    ua = {"User-Agent": "WhatsApp/2.24.1 A"}
    r = httpx.get(f"{origin}/events/invite/{tok}", headers=ua, timeout=20)
    tags = dict(re.findall(r'<meta (?:property|name)="([^"]+)" content="([^"]*)"', r.text))
    print("meta lien :", r.status_code, {k: v for k, v in tags.items() if k.startswith(("og:", "twitter:", "description"))}, flush=True)
    title = tags.get("og:title", "")
    if "Bot Olga t&#x27;invite" not in title and "Bot Olga t'invite" not in title:
        anomaly("meta", "🟠", "aperçu WhatsApp : og:title sans « Bot Olga t'invite »", title)
    if E1_TITLE not in title:
        anomaly("meta", "🔴", "aperçu WhatsApp : titre de l'événement absent", title)
    desc = tags.get("og:description", "")
    if "Salle des bots" not in desc or "Rue des Bots" in r.text:
        anomaly("meta", "🟠", "aperçu WhatsApp : lieu absent ou adresse exacte divulguée", desc)
    if not tags.get("og:image", "").startswith("http"):
        anomaly("meta", "🟠", "aperçu WhatsApp : og:image absente ou relative", tags.get("og:image", ""))
    else:
        img = httpx.get(tags["og:image"], timeout=20)
        print("og:image :", img.status_code, img.headers.get("content-type"), flush=True)
        if img.status_code != 200:
            anomaly("meta", "🔴", "aperçu WhatsApp : og:image introuvable", f"{tags['og:image']} → {img.status_code}")
    if not tags.get("og:url", "").endswith(tok):
        anomaly("meta", "🟡", "aperçu WhatsApp : og:url ne pointe pas vers le lien", tags.get("og:url", ""))
    opened_at = [x for x in links_of(st["e1"]) if x["token"] == tok][0]["opened_at"]
    if opened_at:
        anomaly("meta", "🟠", "le robot de WhatsApp compte comme une ouverture (opened_at rempli)", str(opened_at))
    # Titre avec caractères spéciaux : échappement
    sql(f"update public.events set title = {q(E1_TITLE + ' <b>\"&</b>')} where id = '{st['e1']}'")
    r2 = httpx.get(f"{origin}/events/invite/{tok}", headers=ua, timeout=20)
    raw = re.search(r'<meta property="og:title" content="([^"]*)"', r2.text)
    print("og:title échappé :", raw.group(1) if raw else None, flush=True)
    if "<b>" in (raw.group(1) if raw else "") or '<b>"&' in r2.text.split("</head>")[0]:
        anomaly("meta", "🔴", "aperçu WhatsApp : titre non échappé dans les balises", raw.group(1) if raw else "")
    sql(f"update public.events set title = {q(E1_TITLE)} where id = '{st['e1']}'")
    for name, path in (("expiré", st.get("link_exp")), ("annulé", st.get("link_e2")), ("arrêté", st.get("link_stop"))):
        if not path:
            continue
        r3 = httpx.get(f"{origin}/events/invite/{path}", headers=ua, timeout=20)
        t3 = re.search(r'<meta property="og:title" content="([^"]*)"', r3.text)
        d3 = re.search(r'<meta property="og:description" content="([^"]*)"', r3.text)
        print(f"meta lien {name} :", t3.group(1) if t3 else None, "|", d3.group(1) if d3 else None, flush=True)
    r4 = httpx.get(f"{origin}/events/invite/00000000-0000-4000-8000-000000000000", headers=ua, timeout=20)
    t4 = re.search(r'<meta property="og:title" content="([^"]*)"', r4.text)
    print("meta lien inconnu :", r4.status_code, t4.group(1) if t4 else None, flush=True)


def phase_carte_finale(browser, origin):
    """La carte de l'organisatrice reflète les réponses par lien (Gus, Sara) et les liens (plein, expiré, arrêté)."""
    st = load_state()
    p = signed_phone(browser, "orga1", origin, "carte-finale")
    page = p.page
    try:
        open_event(p)
        p.shot("carte-finale", full=True)
        p.dump("carte-finale")
        gl = guest_list(st["e1"], BY_KEY["orga1"].phone)
        p.log(f"base : liens {[(x['label'], x['max_uses'], x['uses'], x['state']) for x in gl['links']]}")
        p.log(f"base : personnes {[(x['name'], x['source'], x['status']) for x in gl['people']]}")
        for label in ("Viennent", "Peut-être", "Absents", "Pas répondu", "Lien pas ouvert"):
            p.log(f"compteur {label} : {tile_count(p, label)}")
        expected = {"Viennent": sum(1 for x in gl["people"] if x["status"] == "yes"),
                    "Absents": sum(1 for x in gl["people"] if x["status"] == "no")}
        for label, n in expected.items():
            if tile_count(p, label) != n:
                p.flag("🔴", f"compteur « {label} » faux", f"écran {tile_count(p, label)}, base {n}")
        for text in ("terminé", "Arrêté", "Terminé", "Plus valable"):
            p.log(f"« {text} » visible : {page.get_by_text(re.compile(text)).count()}")
        p.scroll_to_bottom("fiche (carte finale)")
        check_cut(p, "carte finale")
    finally:
        p.close()


def phase_nettoyage(browser, origin):
    gone = sql(f"delete from public.events where title like {q(PREFIX + '%')} returning id, title")
    print("supprimés :", gone, flush=True)


def main(argv: list[str]) -> None:
    origin = load_state()["origin"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in argv:
            print(f"════ phase {name} ════", flush=True)
            try:
                globals()[f"phase_{name}"](browser, origin)
            except Exception as e:  # une phase cassée devient une anomalie, la suite continue
                traceback.print_exc()
                anomaly("banc", "🟠", f"phase {name} interrompue", f"{type(e).__name__}: {str(e)[:500]}")
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
