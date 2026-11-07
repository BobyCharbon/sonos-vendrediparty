"""Banc des bots : constantes, accès à la base de TEST (jamais la prod) et équipe des 15 bots.

Toute écriture SQL passe par l'API de gestion Supabase sur le projet TEST seulement (jeton dans
~/.config/supabase-claude/token, hors dépôt)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import httpx

TEST_REF = "ewromqfsmcqsthftyhzm"  # Vendrediparty-test : la seule base que ce banc touche
TEST_URL = f"https://{TEST_REF}.supabase.co"
CONFIG = Path.home() / ".config/supabase-claude"
OTP = "123456"
PROD_FEATURES_URL = "https://party.bobycharbon.ch/api/features"


def publishable_key() -> str:
    return (CONFIG / "test-publishable-key").read_text().strip()


def _management(method: str, path: str, body: dict | None = None):
    token = (CONFIG / "token").read_text().strip()
    req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{TEST_REF}/{path}",
                                 data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                          "User-Agent": "party-bots"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                text = r.read().decode()
                return json.loads(text) if text else None
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(5)
                continue
            raise RuntimeError(f"API de gestion {method} {path} : HTTP {e.code} {e.read().decode()[:800]}") from e


def sql(query: str):
    """SQL en écriture sur la base de TEST uniquement."""
    return _management("POST", "database/query", {"query": query})


def auth_config() -> dict:
    return _management("GET", "config/auth")


def patch_auth_config(changes: dict):
    return _management("PATCH", "config/auth", changes)


@dataclass(frozen=True)
class Bot:
    key: str            # dossier des enregistrements
    phone: str          # numéro de test (code fixe 123456)
    first: str
    last: str
    role: str           # clé de la table roles ; "none" = pas de compte au départ (arrive par un lien)
    device: str         # iphone / android
    groups: tuple = ()

    @property
    def nickname(self) -> str:
        return f"Bot {self.first}"

    @property
    def has_account_at_start(self) -> bool:
        return self.role != "none"


GROUP_BOTS = "Bots"
GROUP_BOTS_2 = "Bots 2"

# 15 bots : 1 admin, 1 co-admin, 2 organisateurs, 4 Membres VIP (groupe Vendredi Party), 3 Membres, 2 Guests,
# 2 « sans l'app ». Numéros +41 79 000 01 01 → 15 : jamais attribués (plage de test, comme 079 000 00 01).
BOTS = [
    Bot("admin", "41790000101", "Ada", "Admin", "admin", "iphone", (GROUP_BOTS,)),
    Bot("coadmin", "41790000102", "Côme", "Coadmin", "coadmin", "android", (GROUP_BOTS,)),
    Bot("orga1", "41790000103", "Olga", "Orga", "organizer", "iphone", (GROUP_BOTS, GROUP_BOTS_2)),
    Bot("orga2", "41790000104", "Oscar", "Orga", "organizer", "android", (GROUP_BOTS,)),
    Bot("vip1", "41790000105", "Victor", "Vip", "member", "iphone", (GROUP_BOTS,)),
    Bot("vip2", "41790000106", "Vera", "Vip", "member", "android", (GROUP_BOTS,)),
    Bot("vip3", "41790000107", "Valentin", "Vip", "member", "iphone", (GROUP_BOTS, GROUP_BOTS_2)),
    Bot("vip4", "41790000108", "Violette", "Vip", "member", "android", (GROUP_BOTS_2,)),
    Bot("membre1", "41790000109", "Marc", "Membre", "basic", "iphone", (GROUP_BOTS,)),
    Bot("membre2", "41790000110", "Mia", "Membre", "basic", "android", (GROUP_BOTS,)),
    Bot("membre3", "41790000111", "Max", "Membre", "basic", "iphone", ()),          # hors des groupes : invité « de Party »
    Bot("guest1", "41790000112", "Gus", "Guest", "guest", "android", (GROUP_BOTS,)),
    Bot("guest2", "41790000113", "Gina", "Guest", "guest", "iphone", ()),
    Bot("sansapp1", "41790000114", "Sam", "Sanslapp", "none", "iphone"),
    Bot("sansapp2", "41790000115", "Sara", "Sanslapp", "none", "android"),
]
BY_KEY = {b.key: b for b in BOTS}
BOT_PHONES = tuple(b.phone for b in BOTS)


class Session:
    """Session Supabase d'un bot (code fixe, aucun SMS)."""

    def __init__(self, phone: str):
        base = {"apikey": publishable_key(), "Content-Type": "application/json"}
        r = None
        for _ in range(5):  # un code par minute et par numéro ; un numéro tout juste ajouté met ~1 min à être pris en compte
            sent = httpx.post(f"{TEST_URL}/auth/v1/otp", headers=base, json={"phone": phone}, timeout=30)
            if sent.status_code == 200:
                r = httpx.post(f"{TEST_URL}/auth/v1/verify", headers=base,
                               json={"type": "sms", "phone": phone, "token": OTP}, timeout=30)
                if r.status_code == 200:
                    break
            time.sleep(31)
        if r is None or r.status_code != 200:
            raise RuntimeError(f"Connexion {phone} : {sent.status_code} {sent.text} / {r and r.text}")
        self.uid = r.json()["user"]["id"]
        self.token = r.json()["access_token"]
        self.headers = {**base, "Authorization": f"Bearer {self.token}"}

    def rpc(self, name: str, **args) -> httpx.Response:
        return httpx.post(f"{TEST_URL}/rest/v1/rpc/{name}", headers=self.headers, json=args, timeout=30)

    def get(self, path: str) -> httpx.Response:
        return httpx.get(f"{TEST_URL}/rest/v1/{path}", headers=self.headers, timeout=30)


def q(value: str) -> str:
    """Littéral SQL échappé."""
    return "'" + str(value).replace("'", "''") + "'"


def phones_sql() -> str:
    return "(" + ",".join(q(p) for p in BOT_PHONES) + ")"
