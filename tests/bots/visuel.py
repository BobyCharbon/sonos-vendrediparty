"""Campagne 2, domaine « visuel, gestes et accessibilité » du module Événements (agent 09).

Chaque écran du module à 360 / 390 / 430 px (iPhone et Android), tablette 820, bureau 1280, thème sombre et clair,
texte agrandi (130 %) : débordements, textes coupés, cibles < 44 px, contrôles sans nom, éléments masqués mais
activables, contrastes (axe-core), contenu sous la barre d'onglets. Puis les vrais gestes : défilement au doigt,
feuilles fermées au glisser / ✕ / fond, retour arrière (bouton du navigateur et bord gauche), liens profonds.

Sessions des bots obtenues par l'API (code fixe, base de TEST) et posées dans le stockage du navigateur.
Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.run visuel_prepare visuel_ecrans visuel_gestes visuel_liens
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import httpx
from playwright.sync_api import Browser

from tests.bots.bench import OUT, PHONES, Phone, anomaly, load_state, save_state
from tests.bots.common import BY_KEY, OTP, TEST_REF, TEST_URL, publishable_key, q, sql
from tests.bots.flows import create_simple

PREFIX = os.environ.get("VISUEL_PREFIX", "[C2-09]")  # relance : VISUEL_PREFIX="[R-09]"
LONG_TITLE = f"{PREFIX} 🎉🍕 Très longue soirée raclette-fondue au bord du lac Léman avec un titre interminable 🥂✨"
STORAGE_KEY = f"sb-{TEST_REF}-auth-token"
AXE = Path(os.environ.get("AXE_JS", OUT.parent / "axe" / "package" / "axe.min.js"))
SIZES = {
    "360": {"width": 360, "height": 780}, "390": {"width": 390, "height": 844}, "430": {"width": 430, "height": 932},
    "820": {"width": 820, "height": 1180}, "1280": {"width": 1280, "height": 800},
}
MIN_TARGET = 44


# ── Sessions ─────────────────────────────────────────────────────────────────────────────────────────────────────

def api_session(key: str) -> dict:
    """Session Supabase complète d'un bot (gardée tant qu'elle vaut encore 10 min)."""
    cache = OUT / key / "session.json"
    if cache.exists():
        s = json.loads(cache.read_text())
        if s.get("expires_at", 0) - time.time() > 600:
            return s
    base = {"apikey": publishable_key(), "Content-Type": "application/json"}
    phone = BY_KEY[key].phone
    for _ in range(6):
        if httpx.post(f"{TEST_URL}/auth/v1/otp", headers=base, json={"phone": phone}, timeout=30).status_code == 200:
            r = httpx.post(f"{TEST_URL}/auth/v1/verify", headers=base, json={"type": "sms", "phone": phone, "token": OTP}, timeout=30)
            if r.status_code == 200:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(r.text)
                return r.json()
        time.sleep(31)
    raise RuntimeError(f"session de {key} impossible")


def storage_for(key: str | None, origin: str) -> dict:
    items = [{"name": "vp_install_dismissed", "value": "1"}]
    if key:
        items.append({"name": STORAGE_KEY, "value": json.dumps(api_session(key))})
    return {"cookies": [], "origins": [{"origin": origin, "localStorage": items}]}


def rpc(key: str, name: str, **args):
    s = api_session(key)
    h = {"apikey": publishable_key(), "Authorization": f"Bearer {s['access_token']}", "Content-Type": "application/json"}
    r = httpx.post(f"{TEST_URL}/rest/v1/rpc/{name}", headers=h, json=args, timeout=30)
    r.raise_for_status()
    return r.json()


# ── Téléphone à la taille voulue ─────────────────────────────────────────────────────────────────────────────────

class VPhone(Phone):
    """Phone du banc, mais taille, thème, appareil et compte au choix ; vidéo seulement si demandée."""

    def __init__(self, browser: Browser, key: str, origin: str, phase: str, size: str = "390", device: str = "iphone",
                 scheme: str = "dark", who: str | None = "same", video: bool = False):
        self.bot, self.origin, self.phase = BY_KEY[key], origin, phase
        self.dir = OUT / f"{key}-{device}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (self.dir / "journal.log").open("a")
        self.shots = 0
        vp = SIZES[size]
        opts = {**PHONES[device], "viewport": vp}
        if int(size) >= 820:  # tablette / bureau : pas un téléphone
            opts = {"viewport": vp, "device_scale_factor": 2, "is_mobile": size == "820", "has_touch": size == "820"}
        video_opts = {"record_video_dir": str(self.dir / "video-tmp"), "record_video_size": vp} if video else {}
        account = key if who == "same" else who
        self.ctx = browser.new_context(base_url=origin, locale="fr-CH", timezone_id="Europe/Zurich", color_scheme=scheme,
                                       storage_state=storage_for(account, origin), **video_opts, **opts)
        self.ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
        self.page = self.ctx.new_page()
        self.page.on("pageerror", lambda e: self._problem("exception JS", str(e)))
        self.page.on("console", self._console)
        self.page.on("response", self._response)
        self.page.on("dialog", self._dialog)
        self.log(f"── {phase} ({self.bot.nickname}, compte {account}, {device}, {size}px, {scheme}) ──")

    def save_session(self) -> None:  # les sessions viennent de l'API : rien à garder
        return None

    def tap(self, locator, what: str, timeout: int = 60000) -> None:  # machine chargée : on attend plus longtemps
        super().tap(locator, what, timeout)


# ── Audit d'un écran ─────────────────────────────────────────────────────────────────────────────────────────────

AUDIT_JS = r"""(minTarget) => {
  const INTER = 'button,a[href],[role=button],[role=link],[role=switch],[role=checkbox],[role=radio],[role=tab],input,select,textarea';
  const vw = innerWidth, vh = innerHeight;
  const visible = (el) => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05; };
  const name = (el) => (el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder') ||
    (el.getAttribute('aria-labelledby') && document.getElementById(el.getAttribute('aria-labelledby'))?.textContent) ||
    el.textContent || el.querySelector('img[alt]')?.alt || '').trim();
  const label = (el) => (name(el) || el.outerHTML.slice(0, 80)).slice(0, 70);
  const hiddenAncestor = (el) => el.closest('[aria-hidden="true"]');
  const out = { overflowX: document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth,
                offRight: [], small: [], unnamed: [], hiddenActive: [], underBar: [] };
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || getComputedStyle(el).position === 'fixed') continue;
    let a = el.parentElement, h = false;
    while (a) { const o = getComputedStyle(a).overflowX; if (/(auto|scroll|hidden)/.test(o) && a !== document.body && a !== document.documentElement) { h = true; break; } a = a.parentElement; }
    if (!h && r.right > vw + 2 && !el.children.length) out.offRight.push((el.textContent || el.tagName).trim().slice(0, 50));
  }
  const bars = [...document.querySelectorAll('[role=navigation],[role=tablist]')].filter(visible)
    .map((b) => b.getBoundingClientRect()).filter((r) => r.bottom >= vh - 2 && r.height < 140);
  for (const el of document.querySelectorAll(INTER)) {
    const r = el.getBoundingClientRect();
    const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true';
    if (hiddenAncestor(el) && !disabled && el.tabIndex >= 0 && !el.closest('[inert]')) out.hiddenActive.push(label(el) + ' (aria-hidden)');
    if (!visible(el)) {
      if (!hiddenAncestor(el) && !disabled && el.tabIndex >= 0 && r.width > 0 && getComputedStyle(el).display !== 'none'
          && +getComputedStyle(el).opacity <= 0.05) out.hiddenActive.push(label(el) + ' (transparent)');
      continue;
    }
    if (hiddenAncestor(el)) continue;
    if (!name(el) && el.type !== 'hidden') out.unnamed.push(el.outerHTML.slice(0, 120));
    if (r.bottom < 0 || r.top > vh) continue;
    if (el.tagName === 'INPUT' && /checkbox|radio|range/.test(el.type)) continue;
    if ((r.width < minTarget || r.height < minTarget) && !el.closest('[role=navigation]'))
      out.small.push(`${label(el)} ${Math.round(r.width)}×${Math.round(r.height)}`);
    for (const b of bars) if (r.top < b.top && r.bottom > b.top + 4 && !el.closest('[role=navigation],[role=tablist]'))
      out.underBar.push(label(el));
  }
  // Boutons / liens qui se chevauchent (texte agrandi, petits écrans), hors éléments imbriqués.
  out.overlap = [];
  const boxes = [...document.querySelectorAll(INTER)].filter((el) => visible(el) && !hiddenAncestor(el))
    .map((el) => [el, el.getBoundingClientRect()]).filter(([, r]) => r.bottom > 0 && r.top < vh);
  for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
    const [a, ra] = boxes[i], [b, rb] = boxes[j];
    if (a.contains(b) || b.contains(a)) continue;
    const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left), h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
    if (w > 4 && h > 4) out.overlap.push(`${label(a)} ⟷ ${label(b)}`);
  }
  for (const k of ['offRight', 'small', 'unnamed', 'hiddenActive', 'underBar', 'overlap']) out[k] = [...new Set(out[k])].slice(0, 25);
  return out; }"""

BIG_TEXT_JS = """() => {
  const grow = (root) => { for (const el of root.querySelectorAll ? root.querySelectorAll('*') : []) {
      if (el.dataset.big) continue; el.dataset.big = 1; const cs = getComputedStyle(el);
      el.style.fontSize = (parseFloat(cs.fontSize) * 1.3) + 'px';
      if (cs.lineHeight.endsWith('px')) el.style.lineHeight = (parseFloat(cs.lineHeight) * 1.3) + 'px'; } };
  grow(document.body);
  new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => n.nodeType === 1 && grow(n.parentElement || n))))
    .observe(document.body, { childList: true, subtree: true }); }"""


def axe(p: Phone) -> list[dict]:
    if not AXE.exists():
        return []
    p.page.add_script_tag(path=str(AXE))
    res = p.page.evaluate("""async () => { const r = await axe.run(document, { resultTypes: ['violations'],
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'best-practice'] } });
      return r.violations.map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length,
        nodes: v.nodes.slice(0, 5).map(n => (n.target.join(' ') + ' | ' + (n.failureSummary || '').split('\\n').slice(1, 2).join('')
               + ' | ' + (n.html || '').slice(0, 90))) })); }""")
    return res


def audit(p: Phone, screen: str, with_axe: bool = True) -> dict:
    """Mesures de l'écran (haut puis bas de page) ; écrites dans audit.jsonl."""
    res = p.page.evaluate(AUDIT_JS, MIN_TARGET)
    res["cut"] = p.check_texts_cut(screen)
    if with_axe:
        res["axe"] = axe(p)
    rec = {"screen": screen, "size": p.page.viewport_size, "device": p.dir.name, **res}
    with (OUT / os.environ.get("AUDIT_FILE", "audit.jsonl")).open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    p.log(f"audit {screen}: overflowX={res['overflowX']} petits={len(res['small'])} sans-nom={len(res['unnamed'])} "
          f"masqués-actifs={len(res['hiddenActive'])} sous-barre={len(res['underBar'])} coupés={len(res['cut'])} "
          f"chevauchements={res['overlap'][:4]} "
          f"axe={[(v['id'], v['n']) for v in res.get('axe', [])]}")
    return res


def settle(p: Phone, ms: int = 2500) -> None:
    try:
        p.page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:  # le module interroge parfois en continu : on attend juste un peu
        pass
    p.page.wait_for_timeout(ms)
    try:  # écran encore en chargement (roue) : on attend qu'il soit prêt, la machine du banc est très chargée
        # la jauge « N sur M places prises » est aussi un progressbar (fix-C1) : seule une roue compte
        p.page.wait_for_function("() => !document.querySelector('[role=progressbar]:not([aria-label*=\"places\"])')", timeout=60000)
        p.page.wait_for_timeout(800)
    except Exception:
        p.log("⚠️ écran toujours en chargement après 60 s")


def scroll_all_to_end(p: Phone) -> None:
    """Pour l'audit du bas de page seulement (les gestes réels sont testés à part)."""
    p.page.evaluate("""() => { for (const el of document.querySelectorAll('*')) {
        const cs = getComputedStyle(el); if (/(auto|scroll)/.test(cs.overflowY) && el.scrollHeight > el.clientHeight) el.scrollTop = 1e6; }
      document.scrollingElement.scrollTop = 1e6; }""")
    p.page.wait_for_timeout(700)


# ── Préparation ──────────────────────────────────────────────────────────────────────────────────────────────────

def phase_visuel_prepare(browser, origin, only):
    """Événement [C2-09] au titre long (emoji), prix, +1, dans « Bots » ; lien d'invitation ; réponses de bots."""
    p = VPhone(browser, "orga2", origin, "prepare", device="android", video=True)
    try:
        eid = create_simple(p, LONG_TITLE, 9, ["Bots"])
        p.log(f"événement : {eid}")
        if not eid:
            return
        sql(f"""update public.events set price_chf = 15, payment_info = 'TWINT au 079 000 00 00 (test des bots)',
                location_name = 'Salle polyvalente des bots du bord du lac, entrée par la cour arrière (sonner deux fois)',
                allow_plus_ones = true, max_participants = 30,
                description = {q('Description très longue pour les retours à la ligne. ' * 12 + 'Lien : https://example.org/un/tres/long/chemin/sans/espace/pour/voir/si/ca/deborde/du/cadre/de/la/carte')}
                where id = '{eid}'""")
        link = rpc("orga2", "create_event_invite", e=eid, places=3, until=None, label="Ami très très long prénom")
        save_state(v_event=eid, v_token=link["token"])
        for name, ans in (("Bot Vera", "yes"), ("Bot Mia", "maybe"), ("Bot Gus", "no")):
            try:
                sql(f"""insert into public.rsvps (event_id, user_id, status)
                        select '{eid}', id, '{ans}' from public.profiles where display_name = {q(name)}""")
            except Exception as e:  # sans conséquence pour le visuel
                p.log(f"réponse {name} non posée : {str(e)[:160]}")
        p.log(f"lien : /events/invite/{link['token']}")
        short = create_simple(p, f"{PREFIX} Apéro", 12, ["Bots"])
        save_state(v_event_short=short)
    finally:
        p.close()


# ── Écrans ───────────────────────────────────────────────────────────────────────────────────────────────────────

def screens(state: dict) -> list[tuple[str, str, str | None]]:
    """(nom, chemin, compte) ; compte None = déconnecté."""
    e, tok = state["v_event"], state["v_token"]
    oscar = "orga2"
    rows = [("liste", "/events/", oscar), ("activite", "/events/activity", oscar), ("profil", "/events/profile", oscar),
            ("fiche", f"/events/event/{e}", oscar), ("modifier", f"/events/event/{e}/edit", oscar),
            ("inviter-page", f"/events/event/{e}/invite", oscar), ("cadeaux", f"/events/event/{e}/gifts", oscar),
            ("forum", f"/events/event/{e}/chat", oscar), ("scanner", f"/events/event/{e}/scan", oscar),
            ("nouveau", "/events/event/new", oscar), ("groupes", "/events/groups", oscar),
            ("annonces", "/events/announcements", oscar), ("reglages-notifs", "/events/settings/notifications", oscar),
            ("reglages-abos", "/events/settings/subscriptions", oscar), ("reglages-profil", "/events/settings/profile", oscar),
            ("reglages-vie-privee", "/events/settings/privacy", oscar), ("reglages-compte", "/events/settings/account", oscar),
            ("compte", "/events/account", oscar), ("cgu", "/events/terms", oscar), ("confidentialite", "/events/privacy", oscar),
            ("membre", f"/events/member/{sql(q_profile('Bot Vera'))[0]['id']}", oscar),
            ("fiche-invite", f"/events/event/{e}", "vip2"), ("fiche-guest", f"/events/event/{e}", "guest1"),
            ("partage", f"/events/share/{e}", "guest2"), ("invitation-connecte", f"/events/invite/{tok}", "membre3"),
            ("invitation-deconnecte", f"/events/invite/{tok}", None), ("connexion", "/events/", None),
            ("fiche-deconnecte", f"/events/event/{e}", None)]
    for name, path in (("admin", "/events/admin"), ("admin-roles", "/events/admin/roles"),
                       ("admin-signalements", "/events/admin/reports"), ("admin-categories", "/events/admin/taxonomy"),
                       ("admin-membres", "/events/admin/members"), ("admin-comptes", "/events/admin/users"),
                       ("admin-journal", "/events/admin/journal"), ("admin-annonces", "/events/admin/announcements")):
        rows.append((name, path, "admin"))
    return rows


def q_profile(name: str) -> str:
    return f"select id from public.profiles where display_name = {q(name)}"


def visit(p: Phone, path: str) -> None:
    p.goto(path)
    settle(p)


def run_screen(browser, origin, name, path, who, size, device, scheme="dark", big=False, deep=True) -> None:
    owner = who or "sansapp1"
    tag = f"{size}-{device}-{scheme}{'-grand' if big else ''}"
    p = VPhone(browser, owner, origin, f"ecran-{tag}", size=size, device=device, scheme=scheme, who=who)
    try:
        visit(p, path)
        if big:
            p.page.evaluate(BIG_TEXT_JS)
            p.page.wait_for_timeout(800)
        p.shot(f"{name}-haut")
        res = audit(p, f"{name} {tag} haut", with_axe=deep)
        if res["overflowX"] > 2:
            p.flag("🟠", f"{name} ({tag}) : la page déborde à droite de {res['overflowX']} px", str(res["offRight"][:5]))
        if deep:
            scroll_all_to_end(p)
            p.shot(f"{name}-bas")
            audit(p, f"{name} {tag} bas", with_axe=False)
    except Exception as e:  # un écran cassé n'arrête pas les autres
        anomaly(p.dir.name, "🟠", f"écran {name} ({tag}) : audit impossible", f"{type(e).__name__}: {str(e)[:200]}")
    finally:
        p.close()


def phase_visuel_ecrans(browser, origin, only):
    """Tous les écrans : audit complet à 390 (iPhone + Android) ; tailles, thème clair et texte agrandi en plus."""
    state = load_state()
    rows = [r for r in screens(state) if not only or r[0] in only]
    for name, path, who in rows:
        run_screen(browser, origin, name, path, who, "390", "iphone")
        run_screen(browser, origin, name, path, who, "390", "android", deep=False)
        for size in ("360", "430", "820", "1280"):
            run_screen(browser, origin, name, path, who, size, "iphone" if size != "360" else "android", deep=False)
        run_screen(browser, origin, name, path, who, "390", "iphone", scheme="light", deep=False)
        run_screen(browser, origin, name, path, who, "360", "android", big=True, deep=False)


# ── Gestes ───────────────────────────────────────────────────────────────────────────────────────────────────────

def touch_drag(p: Phone, x0: float, y0: float, x1: float, y1: float, steps: int = 12, ms: int = 16) -> None:
    """Vrai glissement du doigt (événements tactiles CDP), de (x0, y0) à (x1, y1)."""
    cdp = p.ctx.new_cdp_session(p.page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
    for i in range(1, steps + 1):
        p.page.wait_for_timeout(ms)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [
            {"x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps}]})
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    p.page.wait_for_timeout(700)


def by_label(p: Phone, label):
    return p.page.get_by_label(label, exact=True) if isinstance(label, str) else p.page.get_by_label(label)


def sheet_open(p: Phone, label) -> bool:
    try:
        by_label(p, label).first.wait_for(state="visible", timeout=8000)
        return True
    except Exception:
        return False


def stable_box(p: Phone, locator) -> dict:
    """Cadre de la feuille une fois son animation d'entrée finie."""
    box = locator.bounding_box()
    for _ in range(20):
        p.page.wait_for_timeout(150)
        nb = locator.bounding_box()
        if nb and box and abs(nb["y"] - box["y"]) < 1:
            return nb
        box = nb
    return box


def check_sheet(p: Phone, what: str, opener, label, scroll: bool = False) -> None:
    """Feuille : en entier dans l'écran, défile au doigt, se ferme par ✕, par le fond et en glissant vers le bas."""
    page = p.page
    for how in ("croix", "fond", "glisser", "glisser-court"):
        with p.step(f"{what} : ouvrir puis fermer ({how})"):
            p.tap(opener(), f"ouvrir {what}")
            if not sheet_open(p, label) and not sheet_open(p, label):
                p.flag("🔴", f"{what} : la feuille ne s'ouvre pas")
                return
            sheet = by_label(p, label).first
            box = stable_box(p, sheet)
            vp = page.viewport_size
            p.shot(f"{what}-ouverte-{how}")
            if how == "croix":
                p.dump(f"{what}-feuille")
                if box["y"] < 0 or box["y"] + box["height"] > vp["height"] + 1:
                    p.flag("🟠", f"{what} : la feuille sort de l'écran (haut sous la barre d'état ou bas coupé)", str(box))
                if scroll:
                    p.scroll_to_bottom(f"{what} (contenu)", x=box["x"] + box["width"] / 2,
                                       y=min(box["y"] + box["height"] - 80, vp["height"] - 80), tries=6)
                    p.shot(f"{what}-bas")
                close = sheet.get_by_role("button", name=re.compile("^Fermer"))
                if not close.count():
                    close = page.get_by_role("button", name=re.compile("^Fermer")).last
                p.tap(close.first if close.count() else close, "✕ Fermer")
            elif how == "fond":
                p.log("touche le fond assombri au-dessus de la feuille")
                if box["y"] > 60:
                    page.touchscreen.tap(vp["width"] / 2, max(10, box["y"] / 2))
                else:
                    p.log("pas de fond visible au-dessus (feuille plein écran)")
            elif how == "glisser":
                touch_drag(p, box["x"] + box["width"] / 2, box["y"] + 14, box["x"] + box["width"] / 2,
                           box["y"] + 14 + max(260, box["height"] * 0.45), steps=14)
            else:  # petit glissement : la feuille doit revenir, pas se fermer
                touch_drag(p, box["x"] + box["width"] / 2, box["y"] + 14, box["x"] + box["width"] / 2, box["y"] + 60,
                           steps=6, ms=60)
            page.wait_for_timeout(700)
            still = sheet_open(p, label)
            p.shot(f"{what}-apres-{how}")
            if how == "glisser-court":
                if not still:
                    p.flag("🟡", f"{what} : un petit glissement (45 px, lent) ferme la feuille")
                else:
                    nb = by_label(p, label).first.bounding_box()
                    if nb and abs(nb["y"] - box["y"]) > 4:
                        p.flag("🟠", f"{what} : après un petit glissement la feuille ne revient pas en place",
                               f"{box['y']:.0f} → {nb['y']:.0f}")
                    close = page.get_by_role("button", name=re.compile("^Fermer")).last
                    p.tap(close, "✕ Fermer")
                    page.wait_for_timeout(600)
            elif still:
                p.flag("🟠", f"{what} : ne se ferme pas ({how})")
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
                if sheet_open(p, label):
                    page.get_by_role("button", name=re.compile("^Fermer")).last.tap()
                    page.wait_for_timeout(500)
    with p.step(f"{what} : double toucher sur le bouton d'ouverture"):
        o = opener()
        o.wait_for(state="visible")
        o.scroll_into_view_if_needed()
        b = o.bounding_box()
        page.touchscreen.tap(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        page.touchscreen.tap(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
        page.wait_for_timeout(1200)
        n = by_label(p, label).count()
        p.shot(f"{what}-double-toucher")
        if n > 1:
            p.flag("🟠", f"{what} : un double toucher ouvre {n} feuilles")
        if sheet_open(p, label):
            page.get_by_role("button", name=re.compile("^Fermer")).last.tap()
            page.wait_for_timeout(700)


def phase_visuel_gestes(browser, origin, only):
    state = load_state()
    e = state["v_event"]
    for device in ("iphone", "android"):
        if only and device not in only:
            continue
        # Organisateur : défilement des écrans longs, feuille Inviter, QR, retour arrière.
        p = VPhone(browser, "orga2", origin, f"gestes-{device}", device=device, video=True)
        page = p.page
        try:
            visit(p, "/events/")
            with p.step("liste : défilement au doigt posé sur une carte"):
                card = page.get_by_role("link", name=re.compile(re.escape(PREFIX))).first
                if not card.count():
                    card = page.get_by_text(re.compile(re.escape(PREFIX))).first
                cb = card.bounding_box() if card.count() else None
                p.finger_scroll("liste (doigt sur une carte)", y=(cb["y"] + cb["height"] / 2) if cb and cb["y"] < 760 else None)
                p.scroll_to_bottom("liste")
                p.shot("liste-bas")
            with p.step("liste → fiche → retour (bouton du navigateur)"):
                page.evaluate("document.scrollingElement.scrollTop = 0")
                visit(p, "/events/")
                link = page.get_by_text(re.compile(r"Très longue soirée")).first
                p.tap(link, "carte de l'événement au titre long")
                page.wait_for_url(re.compile(e), timeout=15000)
                settle(p, 1500)
                p.shot("fiche-depuis-liste")
                page.go_back()
                settle(p, 1500)
                p.shot("retour-navigateur")
                if "/event/" in page.url:
                    p.flag("🟠", "retour du navigateur : reste sur la fiche", page.url)
            with p.step("fiche : retour par glissement depuis le bord gauche"):
                visit(p, "/events/")
                p.tap(page.get_by_text(re.compile(r"Très longue soirée")).first, "carte")
                page.wait_for_url(re.compile(e), timeout=15000)
                settle(p, 1500)
                touch_drag(p, 3, 420, 300, 430, steps=16)
                settle(p, 1200)
                p.shot("apres-bord-gauche")
                if "/event/" in page.url:
                    p.flag("🟡" if device == "android" else "🟠", f"fiche : le glissement depuis le bord gauche ne revient pas ({device})", page.url)
            with p.step("fiche (organisateur) : jusqu'en bas au doigt"):
                visit(p, f"/events/event/{e}")
                p.shot("fiche-haut")
                if p.scroll_to_bottom("fiche organisateur", tries=15) != "end":
                    p.flag("🔴", "fiche : le bas n'est pas atteint au doigt")
                p.shot("fiche-bas")
            with p.step("fiche : rechargement"):
                page.reload()
                settle(p)
                p.shot("fiche-rechargee")
                if not p.see(page.get_by_role("heading", name=re.compile("Très longue soirée")), "la fiche rechargée", 60000):
                    p.flag("🔴", "fiche : vide après rechargement (60 s)")
            visit(p, f"/events/event/{e}")
            check_sheet(p, "Inviter", lambda: page.get_by_role("button", name="Inviter", exact=True).first,
                        re.compile("^Inviter à "), scroll=True)
            with p.step("Inviter : QR code"):
                p.tap(page.get_by_role("button", name="Inviter", exact=True).first, "Inviter")
                sheet_open(p, re.compile("^Inviter à "))
                qr = page.get_by_role("button", name=re.compile("QR"))
                if qr.count():
                    p.tap(qr.first, "QR code")
                    page.wait_for_timeout(1200)
                    p.shot("qr")
                    p.dump("qr")
                    page.get_by_role("button", name="Fermer").last.tap()
                    page.wait_for_timeout(800)
                    p.shot("qr-ferme")
                else:
                    p.log("pas de bouton QR visible (lien pas encore créé)")
                if sheet_open(p, re.compile("^Inviter à ")):
                    page.get_by_role("button", name=re.compile("^Fermer")).last.tap()
            for path, what in ((f"/events/event/{e}/edit", "formulaire Modifier"), ("/events/event/new", "formulaire Proposer"),
                               ("/events/settings/notifications", "Réglages notifications"), ("/events/activity", "Activité"),
                               ("/events/profile", "Mon profil"), (f"/events/event/{e}/invite", "page Inviter")):
                with p.step(f"{what} : jusqu'en bas au doigt"):
                    visit(p, path)
                    r = p.scroll_to_bottom(what, tries=15)
                    p.shot(f"{what.replace(' ', '-')}-bas")
                    if r == "blocked":
                        p.flag("🔴", f"{what} : bloqué au doigt")
            with p.step("perte du réseau : ouvrir la fiche hors ligne"):
                visit(p, "/events/")
                p.ctx.set_offline(True)
                p.tap(page.get_by_text(re.compile(r"Très longue soirée")).first, "carte (hors ligne)")
                page.wait_for_timeout(4000)
                p.shot("fiche-hors-ligne")
                body = page.locator("body").inner_text()
                p.log(f"hors ligne, texte : {body[:300]!r}")
                p.ctx.set_offline(False)
                page.wait_for_timeout(4000)
                p.shot("fiche-reseau-revenu")
        finally:
            p.close()
        # Invitée : Signaler, Payer, réponses ; défilement de la fiche vue par une invitée.
        p = VPhone(browser, "vip2", origin, f"gestes-{device}", device=device, video=True)
        page = p.page
        try:
            visit(p, f"/events/event/{e}")
            p.shot("fiche-invitee")
            if p.scroll_to_bottom("fiche invitée", tries=15) == "blocked":
                p.flag("🔴", "fiche (invitée) : bloquée au doigt")
            p.shot("fiche-invitee-bas")
            check_sheet(p, "Signaler", lambda: page.get_by_role("button", name="Signaler cet événement").first, "Signaler")
            visit(p, f"/events/event/{e}")
            pay = page.get_by_role("button", name=re.compile("Payer"))
            if pay.count():
                check_sheet(p, "Payer", lambda: page.get_by_role("button", name=re.compile("Payer")).first,
                            "Payer l’organisateur", scroll=True)
            else:
                p.log("pas de bouton Payer sur la fiche (prix sans paiement entre amis)")
        finally:
            p.close()


# ── Liens profonds et page Party autour du module ────────────────────────────────────────────────────────────────

def phase_visuel_liens(browser, origin, only):
    state = load_state()
    e, tok = state["v_event"], state["v_token"]
    zero = "00000000-0000-0000-0000-000000000000"
    cases = [("fiche-connecte", f"/events/event/{e}", "orga2"), ("fiche-non-invite", f"/events/event/{e}", "guest2"),
             ("fiche-deconnecte", f"/events/event/{e}", None), ("fiche-inexistante", f"/events/event/{zero}", "orga2"),
             ("invitation-deconnecte", f"/events/invite/{tok}", None), ("invitation-connecte", f"/events/invite/{tok}", "membre3"),
             ("invitation-organisateur", f"/events/invite/{tok}", "orga2"), ("invitation-inexistante", f"/events/invite/{zero}", None),
             ("page-inconnue", "/events/nimportequoi", "orga2"), ("modifier-par-invite", f"/events/event/{e}/edit", "vip2")]
    for name, path, who in cases:
        if only and name not in only:
            continue
        p = VPhone(browser, who or "sansapp1", origin, f"lien-{name}", who=who)
        try:
            visit(p, path)
            p.page.wait_for_timeout(2000)
            p.shot(name)
            p.log(f"{name} : adresse finale {p.page.url} ; texte : {p.page.locator('body').inner_text()[:240]!r}")
            audit(p, f"lien {name}", with_axe=False)
            p.dump(name)
        finally:
            p.close()
    # Page Party (onglet Événements) : le module dans son cadre, au-dessus de la barre d'onglets de Party.
    for device in ("iphone", "android"):
        p = VPhone(browser, "orga2", origin, f"party-{device}", device=device)
        try:
            p.page.add_init_script("localStorage.setItem('vp_tab','events');localStorage.setItem('vp_name','Bot Oscar')")
            visit(p, "/")
            p.page.wait_for_timeout(4000)
            p.shot("party-onglet-evenements")
            geo = p.page.evaluate("""() => { const f = document.getElementById('eventsFrame'); const t = document.getElementById('tabs');
                const r = (x) => x ? (({top, bottom, height}) => ({top, bottom, height}))(x.getBoundingClientRect()) : null;
                return { frame: r(f), tabs: r(t), tabsVisible: t ? getComputedStyle(t).display !== 'none' : false,
                         scrollH: document.scrollingElement.scrollHeight, vh: innerHeight }; }""")
            p.log(f"Party : {geo}")
            frame = p.page.frame_locator("#eventsFrame")
            card = frame.get_by_text(re.compile("Très longue soirée")).first
            card.wait_for(timeout=20000)
            card.tap()
            p.page.wait_for_timeout(3000)
            p.shot("party-fiche")
            fr = p.page.frames[1] if len(p.page.frames) > 1 else None
            if fr:
                p.page.evaluate("""() => { const d = document.getElementById('eventsFrame').contentDocument;
                    for (const el of d.querySelectorAll('*')) { const cs = getComputedStyle(el);
                      if (/(auto|scroll)/.test(cs.overflowY) && el.scrollHeight > el.clientHeight) el.scrollTop = 1e6; }
                    d.scrollingElement.scrollTop = 1e6; }""")
                p.page.wait_for_timeout(800)
                p.shot("party-fiche-bas")
                last = fr.evaluate("""() => { const b = [...document.querySelectorAll('[role=button],button')].filter(x => x.getBoundingClientRect().height > 0);
                    const l = b[b.length - 1]; const r = l.getBoundingClientRect(); return { label: l.getAttribute('aria-label') || l.textContent, top: r.top, bottom: r.bottom, vh: innerHeight }; }""")
                p.log(f"Party fiche, dernier bouton : {last} ; barre Party : {geo['tabs']} ; cadre : {geo['frame']}")
                if geo["tabs"] and geo["frame"] and geo["tabsVisible"]:
                    bottom_on_screen = geo["frame"]["top"] + last["bottom"]
                    if bottom_on_screen > geo["tabs"]["top"] + 2:
                        p.flag("🟠", f"Party ({device}) : le dernier bouton de la fiche finit sous la barre d'onglets",
                               f"{last['label']} bas={bottom_on_screen:.0f} barre={geo['tabs']['top']:.0f}")
        except Exception as ex:
            anomaly(p.dir.name, "🟠", f"page Party ({device}) : test du cadre impossible", str(ex)[:300])
        finally:
            p.close()


def phase_visuel_reprise(browser, origin, only):
    """Reprise après chargement complet (roue disparue) : audit complet 390 iPhone, 360 Android normal et texte agrandi
    (chevauchements compris). Les mesures sont écrites dans audit2.jsonl."""
    rows = [r for r in screens(load_state()) if not only or r[0] in only]
    for name, path, who in rows:
        run_screen(browser, origin, name, path, who, "390", "iphone")
        run_screen(browser, origin, name, path, who, "360", "android", deep=False)
        run_screen(browser, origin, name, path, who, "360", "android", big=True, deep=False)
