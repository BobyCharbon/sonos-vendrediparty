"""Outils des tests de bout en bout : un serveur isolé et des « téléphones » (navigateurs) qui jouent ensemble."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
from playwright.sync_api import Browser, Page, expect

ROOT = Path(__file__).resolve().parents[2]
ADMIN_PIN = "9999"

# Écrans testés : téléphones (tactile) et ordinateur.
DEVICES = {
    "iphone": {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True,
               "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"},
    "android": {"viewport": {"width": 412, "height": 915}, "device_scale_factor": 2.6, "is_mobile": True, "has_touch": True,
                "user_agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"},
    "desktop": {"viewport": {"width": 1280, "height": 800}},
}

# Bruit attendu dans la console : réponses d'erreur volontaires du serveur (409, 403…), ressources externes.
IGNORED_CONSOLE = ("Failed to load resource", "favicon", "fonts.g", "net::ERR")


class FakeSupabase:
    """Supabase local pour les tests navigateur : deux comptes à jeton fixe, un Guest+ (droit « Écrire un avis »)
    et un Guest (sans). Seules les routes lues par Party pour relier un compte et vérifier ses droits répondent."""

    ACCOUNTS = {"jeton-de-test-guest-plus-0001": ("u-plus", "Léa", ["feedback.write", "music.add"]),
                "jeton-de-test-guest-0001": ("u-guest", "Tom", ["music.add"])}

    def __init__(self):
        accounts = self.ACCOUNTS

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _answer(self, status, data):
                body = json.dumps(data).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _route(self):
                body = self.rfile.read(int(self.headers["Content-Length"])) if self.headers.get("Content-Length") else b""
                who = accounts.get(self.headers.get("Authorization", "").removeprefix("Bearer "))
                if who is None:
                    return self._answer(401, {"message": "invalid JWT"})
                uid, name, perms = who
                path = self.path.split("?")[0]
                cards = {u: {"id": u, "display_name": n, "avatar_url": None, "role": "guestplus", "root": False, "me": u == uid,
                             "first_name": None, "last_name": None, "phone": None, "groups": []} for u, n, _ in accounts.values()}
                if path == "/rest/v1/rpc/member_card":
                    return self._answer(200, cards.get(json.loads(body or b"{}").get("target")))
                answers = {"/auth/v1/user": {"id": uid}, "/rest/v1/rpc/my_permissions": perms,
                           "/rest/v1/rpc/get_member_directory": [{"id": uid, "display_name": name, "status": "active"}],
                           "/rest/v1/rpc/is_beta_tester": False}
                return self._answer(200, answers[path]) if path in answers else self._answer(404, {})

            do_GET = do_POST = _route

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def stop(self):
        self.http.shutdown()


class Server:
    """Serveur Vendredi Party sur un port libre, avec ses propres données."""

    def __init__(self, supabase: "FakeSupabase | None" = None):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.url = f"http://127.0.0.1:{self.port}"
        self.data = tempfile.mkdtemp(prefix="vp-e2e-")
        env = {**os.environ, "DATA_DIR": self.data, "ADMIN_PIN": ADMIN_PIN}
        env.pop("SPOTIFY_CLIENT_ID", None)
        if supabase:
            env.update(SUPABASE_URL=supabase.url, SUPABASE_ANON_KEY="cle-publique-de-test")
        self.log = open(Path(self.data) / "server.log", "w")
        self.proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(self.port), "--log-level", "warning"],
                                     cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT)
        for _ in range(300):  # jusqu'à 30 s : sur une machine chargée, le démarrage peut dépasser 10 s
            try:
                if httpx.get(self.url + "/", timeout=1).status_code == 200:
                    return
            except httpx.HTTPError:
                time.sleep(0.1)
        raise RuntimeError("Le serveur de test n'a pas démarré")

    def errors(self) -> str:
        """Erreurs Python survenues côté serveur (une trace = un bug)."""
        self.log.flush()
        text = (Path(self.data) / "server.log").read_text()
        return text if "Traceback" in text else ""

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()


class Phone:
    """Un invité avec son navigateur : il touche les vrais boutons de l'app."""

    def __init__(self, browser: Browser, server: Server, name: str, device: str = "iphone"):
        self.server, self.name = server, name
        self.gid = f"e2e-{name.lower()}-{uuid.uuid4().hex[:10]}"
        self.ctx = browser.new_context(base_url=server.url, locale="fr-CH", **DEVICES[device])
        # Identité posée une seule fois (le reste du stockage vit sa vie comme sur un vrai téléphone).
        self.ctx.add_init_script(f"""
            if (!localStorage.getItem("vp_guest")) {{
              localStorage.setItem("vp_guest", "{self.gid}");
              localStorage.setItem("vp_name", "{name}");
              localStorage.setItem("vp_install_dismissed", "1");
            }}""")
        self.page: Page = self.ctx.new_page()
        self.errors: list[str] = []
        self.token = ""
        self.page.on("pageerror", lambda e: self.errors.append(f"[{name}] exception JS : {e}"))
        self.page.on("console", lambda m: m.type == "error" and not any(x in m.text for x in IGNORED_CONSOLE)
                     and self.errors.append(f"[{name}] console : {m.text}"))
        self.code = ""

    # ── Navigation ──
    def open_games(self):
        """Accueil des jeux (on quitte d'abord la partie en cours sur ce téléphone, s'il y en a une)."""
        self.page.goto("/")
        self.page.evaluate("localStorage.removeItem('vp_game'); localStorage.removeItem('vp_room')")
        self.page.goto("/")
        self.page.locator('button[data-tab="games"]').first.click()
        expect(self.page.locator("#gHome")).to_be_visible()

    def create(self, kind: str, **options) -> str:
        """Crée une partie depuis l'accueil des jeux (carte du jeu → bouton de création)."""
        self.open_games()
        card = self.page.locator(f'#gHome .gcard:has([data-create="{kind}"])')
        for opt, value in options.items():
            toggle = card.locator(f'[data-opt="{opt}"]')
            if toggle.count() and toggle.is_checked() != value:
                toggle.set_checked(value, force=True)
        card.locator(f'[data-create="{kind}"]').click()
        expect(self.page.locator("#gamePlay")).to_be_visible()
        self.code = self.page.locator("#gameCode").inner_text().strip()
        assert self.code.isdigit(), f"code de partie illisible : {self.code!r}"
        return self.code

    def join(self, code: str):
        """Rejoint par le lien du QR code, comme en vrai."""
        self.code = code
        self.page.goto(f"/?game={code}")
        expect(self.page.locator("#gamePlay")).to_be_visible()

    # ── Actions ──
    def tap(self, selector: str, nth: int = 0):
        el = self.page.locator(selector).locator("visible=true").nth(nth)
        el.click()
        return el

    def current(self) -> str:
        """Code de la partie ouverte sur ce téléphone (dans une salle, c'est le jeu lancé, pas la salle)."""
        try:
            return self.page.evaluate("localStorage.getItem('vp_game')") or self.code
        except Exception:
            return self.code

    def act(self, action: str, **extra):
        """Action de jeu envoyée directement (pour les joueurs « figurants » d'une scène)."""
        r = httpx.post(f"{self.server.url}/api/games/{self.current()}",
                       json={"guest_id": self.gid, "name": self.name, "action": action, **extra}, timeout=10)
        return r.json() if r.content else None

    def state(self) -> dict:
        return httpx.get(f"{self.server.url}/api/games/{self.current()}", params={"guest_id": self.gid}, timeout=10).json()

    def pid(self) -> str:
        return (self.state().get("me") or {}).get("pid", "")

    def shot(self, name: str):
        out = Path(os.environ.get("E2E_SHOTS", ROOT / "test-results" / "shots"))
        out.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(out / f"{name}.png"))

    def close(self):
        self.ctx.close()


def act_selector(action: str, target: str | None = None, guess: str | None = None) -> str:
    sel = f'[data-gact="{action}"]'
    if target is not None:
        sel += f'[data-target="{target}"]'
    if guess is not None:
        sel += f'[data-guess="{guess}"]'
    return sel


def tap_act(phone: "Phone", action: str, target: str | None = None, guess: str | None = None):
    """Touche le bouton d'action visible sur ce téléphone (échoue s'il n'apparaît pas)."""
    el = phone.page.locator(act_selector(action, target, guess)).locator("visible=true").first
    expect(el).to_be_enabled()
    el.click()


def wait_state(phone: "Phone", check, timeout: float = 8.0) -> dict:
    """Attend que l'état de la partie (vu par ce téléphone) remplisse une condition."""
    end = time.monotonic() + timeout
    while True:
        s = phone.state()
        if check(s):
            return s
        if time.monotonic() > end:
            raise AssertionError(f"État attendu non atteint (phase={s.get('phase')})")
        time.sleep(0.15)


def sign_in(phone: "Phone", token: str):
    """Compte connecté comme le ferait le module Événements (session dans le localStorage du site), puis relié."""
    phone.token = token
    session = json.dumps({"access_token": token, "refresh_token": "r", "expires_at": int(time.time()) + 3600})
    phone.page.evaluate(f"localStorage.setItem('sb-e2e-auth-token', {json.dumps(session)})")
    phone.page.evaluate("linkAccount()")
