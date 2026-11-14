"""Cas limites de l'inscription (campagne du 14.11.2026), hors base : le surnom de 12 caractères au plus côté serveur
(Réglages natifs › Mon profil) et côté web (surnom de jeu pré-rempli). La base et le vrai navigateur sont testés dans
tests/supabase_live/test_inscription_cas_limites_*_browser_live.py."""
import json
import re
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main

ROOT = Path(__file__).resolve().parents[1]
ROW = {"id": "u-7", "display_name": "Un surnom d'avant", "first_name": "Ludo", "last_name": "T", "phone": "+41765550000",
       "avatar_url": None, "role": "guest", "status": "active"}


def accounts_refusing_long_nicknames():
    """Comme guard_profile (migration 20261114090000) : un surnom NOUVEAU de plus de 12 caractères est refusé, l'ancien reste."""
    seen = []

    def handler(request: httpx.Request):
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-7"})
        if request.url.path == "/rest/v1/rpc/get_member_directory":
            return httpx.Response(200, json=[ROW])
        if request.url.path == "/rest/v1/profiles" and request.method == "PATCH":
            name = json.loads(request.content)["display_name"]
            seen.append(name)
            if name != ROW["display_name"] and len(name) > 12:
                return httpx.Response(400, json={"code": "23514", "message": "nickname_too_long: le surnom est limité à 12 caractères"})
            return httpx.Response(204)
        return httpx.Response(404)

    return accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler))), seen


def test_the_server_says_the_twelve_characters_rule_in_plain_words_and_keeps_an_older_long_nickname(monkeypatch):
    acc, seen = accounts_refusing_long_nicknames()
    monkeypatch.setattr(main, "accounts", acc)
    client = TestClient(main.app)
    body = {"token": "t" * 40, "first_name": "Ludo", "last_name": "T", "photo": ""}
    refused = client.post("/api/account/profile/update", json={**body, "display_name": "Treize carac."})
    assert refused.status_code == 400 and refused.json()["detail"] == "Le surnom est limité à 12 caractères"
    # L'ancien surnom de 17 caractères, renvoyé tel quel avec un autre nom : accepté.
    kept = client.post("/api/account/profile/update", json={**body, "last_name": "Testeur", "display_name": ROW["display_name"]})
    assert kept.status_code == 200, kept.text
    assert seen == ["Treize carac.", ROW["display_name"]]


def test_a_long_game_name_never_prefills_a_nickname_longer_than_the_limit():
    """Nom de jeu (30 caractères au plus, index.html) : coupé à NICKNAME_MAX avant de pré-remplir le surnom ; sinon la
    base le refusait au premier « Continuer » (après les CGU)."""
    form = (ROOT / "web/events/src/components/IdentityForm.tsx").read_text()
    prefill = re.search(r"function gameNickname\(\)[^}]*}", form, re.S).group(0)
    assert "slice(0, NICKNAME_MAX)" in prefill and "slice(0, 30)" not in prefill
