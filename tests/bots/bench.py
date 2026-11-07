"""Banc des bots : serveur Party local branché sur la base de TEST (réglé comme la prod) et un téléphone par bot
(navigateur Playwright séparé, 390×844 tactile) qui enregistre vidéo, journal horodaté, captures, erreurs JS et
réponses HTTP ≥ 400.

Dossier de sortie : $BOTS_OUT (par défaut <scratchpad>/bots) ; un sous-dossier par bot."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from playwright.sync_api import Browser, BrowserContext, Page, expect

from tests.bots.common import BY_KEY, OTP, PROD_FEATURES_URL, TEST_URL, Bot, publishable_key

REPO = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get("BOTS_OUT") or REPO / "data-local" / "bots")
STATE_FILE = OUT / "state.json"
ANOMALIES = OUT / "anomalies.jsonl"

PHONES = {
    "iphone": {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True,
               "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
                             "Version/18.0 Mobile/15E148 Safari/604.1"},
    "android": {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 2.6, "is_mobile": True, "has_touch": True,
                "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/130.0 Mobile Safari/537.36"},
}
# Bruit sans intérêt : ressources externes (polices, tuiles), favicon.
NOISE = ("favicon", "fonts.g", "net::ERR_ABORTED", "googleapis", "gstatic")


def now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(**changes) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    state = {**load_state(), **changes}
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    return state


def anomaly(bot: str, severity: str, title: str, detail: str = "", shot: str = "") -> None:
    """Une anomalie relevée (gravité 🔴 / 🟠 / 🟡) : reprise dans RAPPORT.md."""
    OUT.mkdir(parents=True, exist_ok=True)
    with ANOMALIES.open("a") as f:
        f.write(json.dumps({"at": now(), "bot": bot, "severity": severity, "title": title, "detail": detail, "shot": shot},
                           ensure_ascii=False) + "\n")


# ── Serveur ──────────────────────────────────────────────────────────────────────────────────────────────────────

def prod_flags() -> dict:
    try:
        return httpx.get(PROD_FEATURES_URL, timeout=10).json()
    except httpx.HTTPError:
        return {"compagnon": False, "discussions": False, "invites_v2": True}  # relevé du 06.11


def start_server(source: Path, dist: Path, data: Path) -> tuple[subprocess.Popen, str]:
    """uvicorn sur un port libre, base de TEST, drapeaux de la prod (lus sur /api/features de la prod)."""
    flags = prod_flags()
    # Port fixe (BOTS_PORT, 8796 par défaut) : les sessions des bots (stockage du navigateur) dépendent de l'origine.
    port = int(os.environ.get("BOTS_PORT") or 0)
    if not port:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
    data.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "DATA_DIR": str(data), "EVENTS_WEB_DIR": str(dist), "EVENTS_ENABLED": "1", "ADMIN_PIN": "8462",
           "SUPABASE_URL": TEST_URL, "SUPABASE_ANON_KEY": publishable_key(), "SPOTIFY_CLIENT_ID": "",
           "COMPAGNON_ENABLED": "1" if flags.get("compagnon") else "0",
           "DISCUSSIONS_ENABLED": "1" if flags.get("discussions") else "0",
           "INVITES_V2_ENABLED": "1" if flags.get("invites_v2") else "0",
           "PARTY_PUBLIC_URL": f"http://127.0.0.1:{port}", "ANTHROPIC_API_KEY": ""}
    log = open(data / "server.log", "a")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)],
                            cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(600):
        try:
            if httpx.get(url + "/", timeout=1).status_code == 200:
                return proc, url
        except httpx.HTTPError:
            time.sleep(0.1)
    raise RuntimeError("Le serveur Party du banc ne démarre pas (voir server.log)")


# ── Téléphone d'un bot ───────────────────────────────────────────────────────────────────────────────────────────

class Phone:
    """Le téléphone d'un bot : contexte séparé, vidéo, journal, captures, erreurs."""

    def __init__(self, browser: Browser, bot: Bot, origin: str, phase: str):
        self.bot, self.origin, self.phase = bot, origin, phase
        self.dir = OUT / bot.key
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (self.dir / "journal.log").open("a")
        self.shots = 0
        storage = self.dir / "storage.json"
        self.ctx: BrowserContext = browser.new_context(
            base_url=origin, locale="fr-CH", timezone_id="Europe/Zurich", color_scheme="dark",
            record_video_dir=str(self.dir / "video-tmp"), record_video_size={"width": 390, "height": 844},
            storage_state=str(storage) if storage.exists() else None, **PHONES[bot.device])
        self.ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
        self.page: Page = self.ctx.new_page()
        self.page.on("pageerror", lambda e: self._problem("exception JS", str(e)))
        self.page.on("console", self._console)
        self.page.on("response", self._response)
        self.page.on("dialog", self._dialog)
        self.log(f"── phase {phase} ({bot.nickname}, {bot.role}, {bot.device}) ──")

    # Journal
    def log(self, text: str) -> None:
        line = f"{now()} [{self.phase}] {text}"
        self.log_file.write(line + "\n")
        self.log_file.flush()
        print(f"{self.bot.key:9} {line}", flush=True)

    def _problem(self, kind: str, text: str) -> None:
        if any(n in text for n in NOISE):
            return
        self.log(f"⚠️ {kind} : {text[:600]}")
        with (self.dir / "errors.log").open("a") as f:
            f.write(f"{now()} [{self.phase}] {kind} : {text}\n")

    def _console(self, msg) -> None:
        if msg.type == "error":
            self._problem("console", msg.text)

    def _response(self, resp) -> None:
        if resp.status >= 400:
            body = ""
            try:
                body = resp.text()[:300]
            except Exception:  # corps illisible (flux, redirection) : l'adresse suffit
                pass
            self._problem(f"HTTP {resp.status}", f"{resp.request.method} {resp.url.split('?')[0]} {body}")

    def _dialog(self, dialog) -> None:
        self.log(f"boîte de dialogue « {dialog.message} » → OK")
        dialog.accept()

    def shot(self, name: str, full: bool = False) -> str:
        self.page.wait_for_timeout(600)
        self.shots += 1
        path = self.dir / f"{self.phase}-{self.shots:02d}-{name}.png"
        self.page.screenshot(path=str(path), full_page=full)
        self.log(f"📸 {path.name}")
        return str(path)

    def dump(self, name: str) -> str:
        """Arbre d'accessibilité de l'écran (ce que le bot « lit »), sans les options d'heure."""
        tree = "\n".join(l for l in self.page.locator("body").aria_snapshot().splitlines() if 'option "' not in l)
        (self.dir / f"{self.phase}-{name}.aria.txt").write_text(tree)
        return tree

    def step(self, what: str):
        """Étape de scénario : une erreur devient une anomalie (capture comprise) et la suite continue."""
        phone = self

        class _Step:
            def __enter__(self):
                phone.log(f"▶ {what}")

            def __exit__(self, kind, exc, tb):
                if exc is None:
                    return False
                phone.flag("🟠", f"étape « {what} » impossible", f"{kind.__name__}: {str(exc).splitlines()[0][:300]}")
                return True
        return _Step()

    def flag(self, severity: str, title: str, detail: str = "") -> None:
        shot = self.shot("anomalie")
        self.log(f"{severity} ANOMALIE : {title} {detail}")
        anomaly(self.bot.key, severity, title, detail, shot)

    # Actions
    def goto(self, path: str) -> None:
        self.log(f"ouvre {path}")
        self.page.goto(self.origin + path, wait_until="domcontentloaded")

    def tap(self, locator, what: str, timeout: int = 15000) -> None:
        """Toucher réel (événements tactiles) ; le bouton doit être visible et dans l'écran après défilement."""
        self.log(f"touche « {what} »")
        locator.wait_for(state="visible", timeout=timeout)
        locator.scroll_into_view_if_needed(timeout=timeout)
        box = locator.bounding_box()
        vp = self.page.viewport_size
        if box and (box["y"] + box["height"] / 2 > vp["height"] or box["y"] + box["height"] / 2 < 0):
            self.flag("🟠", f"« {what} » reste hors de l'écran", f"y={box['y']:.0f}")
        locator.tap(timeout=timeout)

    def type(self, locator, text: str, what: str) -> None:
        self.log(f"écrit « {text} » dans {what}")
        locator.fill(text)

    def see(self, locator, what: str, timeout: int = 15000) -> bool:
        try:
            expect(locator).to_be_visible(timeout=timeout)
            self.log(f"voit {what}")
            return True
        except AssertionError:
            return False

    def expect_or_flag(self, locator, what: str, severity: str = "🟠", timeout: int = 15000) -> bool:
        if self.see(locator, what, timeout):
            return True
        self.flag(severity, f"{what} n'apparaît pas")
        return False

    # Défilement au doigt (geste tactile réel de Chrome, pas de scroll programmé)
    SCROLLERS_AT = """([x, y]) => {
        const out = [];
        let el = document.elementFromPoint(x, y);
        while (el) {
          const cs = getComputedStyle(el);
          const doc = el === document.scrollingElement;
          if (el.scrollHeight > el.clientHeight + 4 && (doc || /(auto|scroll)/.test(cs.overflowY)))
            out.push({top: Math.round(el.scrollTop), room: el.scrollHeight - el.clientHeight});
          el = el.parentElement;
        }
        return out; }"""

    def finger_scroll(self, what: str, x: float | None = None, y: float | None = None, distance: int = -450,
                      flag: bool = True) -> str:
        """Glisse le doigt vers le haut au point (x, y). « moved » : ça a défilé ; « end » : rien (plus) à faire défiler
        sous le doigt ; « blocked » : il restait de quoi défiler mais rien n'a bougé (bug, relevé en anomalie)."""
        vp = self.page.viewport_size
        x = vp["width"] / 2 if x is None else x
        y = vp["height"] * 0.6 if y is None else y
        before = self.page.evaluate(self.SCROLLERS_AT, [x, y])
        if not any(b["top"] < b["room"] - 2 for b in before):
            self.log(f"défilement au doigt {what} : rien de plus à faire défiler")
            return "end"
        cdp = self.ctx.new_cdp_session(self.page)
        cdp.send("Input.synthesizeScrollGesture", {"x": x, "y": y, "yDistance": distance, "gestureSourceType": "touch",
                                                   "speed": 1400})
        cdp.detach()
        self.page.wait_for_timeout(450)
        after = self.page.evaluate(self.SCROLLERS_AT, [x, y])
        moved = [b["top"] for b in before] != [a["top"] for a in after]
        self.log(f"défilement au doigt {what} ({x:.0f},{y:.0f}) : {'OK' if moved else 'BLOQUÉ'} {before} → {after}")
        if not moved and flag:
            self.flag("🔴", f"{what} : ne défile pas au doigt", f"conteneurs sous le doigt : {before}")
        return "moved" if moved else "blocked"

    def scroll_to_bottom(self, what: str, x: float | None = None, y: float | None = None, tries: int = 10) -> str:
        """Fait défiler au doigt jusqu'en bas ; « end » si le bas est atteint."""
        result = "end"
        for _ in range(tries):
            result = self.finger_scroll(what, x, y)
            if result != "moved":
                break
        return result

    def check_texts_cut(self, what: str) -> list[str]:
        """Textes coupés : un élément de texte plus large que son conteneur sans retour à la ligne, ou hors écran à droite."""
        cut = self.page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('div,span,button,a')) {
              if (el.children.length || !el.textContent.trim()) continue;
              const r = el.getBoundingClientRect();
              if (r.width === 0 || r.bottom < 0 || r.top > innerHeight) continue;
              const cs = getComputedStyle(el);
              let a = el.parentElement, hscroll = false;
              while (a) { if (/(auto|scroll)/.test(getComputedStyle(a).overflowX) && a.scrollWidth > a.clientWidth) { hscroll = true; break; } a = a.parentElement; }
              if (hscroll) continue;  // rangée qui défile de côté (filtres, tags) : voulu
              if (r.right > innerWidth + 2 && cs.position !== 'fixed') out.push('hors écran : ' + el.textContent.trim().slice(0, 60));
              else if (el.scrollWidth > el.clientWidth + 2 && cs.overflow !== 'visible' && cs.textOverflow !== 'ellipsis'
                       && cs.webkitLineClamp === 'none') out.push('coupé : ' + el.textContent.trim().slice(0, 60));
            }
            return out.slice(0, 12); }""")
        if cut:
            self.log(f"textes coupés {what} : {cut}")
        return cut

    # Connexion
    def sign_in(self) -> None:
        """Connexion par numéro + code fixe (vrai écran)."""
        page = self.page
        self.goto("/events/")
        field = page.get_by_label("Ton numéro de téléphone", exact=True)
        try:
            field.wait_for(state="visible", timeout=8000)
        except Exception:
            self.log("déjà connecté")
            return
        self.shot("connexion")
        self.type(field, "0" + self.bot.phone[2:], "le numéro")
        self.tap(page.get_by_role("button", name="Recevoir un code par SMS"), "Recevoir un code par SMS")
        code = page.get_by_placeholder("123456", exact=True)
        code.wait_for(state="visible", timeout=60000)
        self.type(code, OTP, "le code")
        self.tap(page.get_by_role("button", name="Se connecter", exact=True), "Se connecter")
        page.wait_for_timeout(2500)

    def save_session(self) -> None:
        self.ctx.storage_state(path=str(self.dir / "storage.json"))

    def close(self) -> None:
        try:
            self.save_session()
        except Exception as e:  # contexte déjà fermé : on garde ce qu'on a
            self.log(f"session non sauvée : {e}")
        video = self.page.video
        self.ctx.close()
        if video:
            target = self.dir / f"video-{self.phase}.webm"
            try:
                Path(video.path()).rename(target)
                self.log(f"🎬 {target.name}")
            except OSError as e:
                self.log(f"vidéo non déplacée : {e}")
        self.log_file.close()


def phone(browser: Browser, key: str, origin: str, phase: str) -> Phone:
    return Phone(browser, BY_KEY[key], origin, phase)
