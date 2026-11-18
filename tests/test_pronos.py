"""Pronos entre amis (avis f071c5f46e3d, 17.11.2026) : relais de l'app iPhone (liste blanche, photos signées), lien
partagé, toucher des notifications, et les garde-fous de conformité (pour l'honneur : ni argent, ni mise, ni lot).
La base est testée pour de vrai dans tests/supabase_live/test_pronos_live.py ; le web dans test_pronos_browser_live.py."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app import main, pronos

ROOT = Path(__file__).resolve().parents[1]
PRONO = "0a0b0c0d-0000-4000-8000-000000000009"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.fixture
def client():
    return TestClient(main.app)


def test_the_relay_only_calls_prono_functions(client):
    with mock.patch.object(pronos.Db, "call", return_value=(200, [])) as call:
        assert client.post("/api/account/pronos/rpc", json={"token": "t", "fn": "agenda_links"}).status_code == 404
        assert client.post("/api/account/pronos/rpc", json={"token": "t", "fn": "report_content",
                                                            "args": {"p_kind": "profile", "p_target": "x"}}).status_code == 404
        assert call.call_count == 0
        assert client.post("/api/account/pronos/rpc", json={"token": "t", "fn": "prono_list"}).json() == {"result": []}


def test_refusals_of_the_database_keep_their_words(client):
    body = {"message": "content_refused: Les pronos se jouent pour l'honneur : pas d'argent, de mise ni de boisson."}
    with mock.patch.object(pronos.Db, "call", return_value=(400, body)):
        r = client.post("/api/account/pronos/rpc", json={"token": "t", "fn": "prono_create", "args": {"body": {}}})
    assert r.status_code == 400 and r.json()["code"] == "content_refused" and "honneur" in r.json()["detail"]
    with mock.patch.object(pronos.Db, "call", return_value=(400, {"message": "terms_required: Accepte les CGU."})):
        r = client.post("/api/account/pronos/rpc", json={"token": "t", "fn": "prono_answer", "args": {}})
    assert r.status_code == 403 and r.json()["code"] == "terms_required"  # l'app ouvre la feuille des CGU


def test_faces_get_a_signed_photo_for_the_native_screens(client):
    data = {"creator": {"id": "a", "name": "Léa", "avatar_url": "a/p.png"}, "answered": [{"id": "b", "name": "Marc", "avatar_url": None}]}
    signed = mock.Mock(status_code=200, json=lambda: [{"path": "a/p.png", "signedURL": "/object/sign/profile-photos/a/p.png?token=x"}])
    with mock.patch.object(pronos.Db, "call", return_value=(200, data)), mock.patch.object(main.accounts, "_get", return_value=signed):
        out = client.post("/api/account/pronos/rpc", json={"token": "t", "fn": "prono_get", "args": {"id": PRONO}}).json()["result"]
    assert out["creator"]["photo"].endswith("/storage/v1/object/sign/profile-photos/a/p.png?token=x")
    assert out["answered"][0]["photo"] is None


def test_a_shared_link_opens_the_join_page(client):
    r = client.get("/prono/AbCdEfGhIjKlMnOpQrStUvWx", follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "/events/prono-invite/AbCdEfGhIjKlMnOpQrStUvWx"
    assert client.get("/prono/..%2Fadmin", follow_redirects=False).status_code == 404


@pytest.mark.skipif(not shutil.which("node"), reason="Node absent")
def test_a_prono_notification_opens_the_prono():
    shell = ROOT / "app/static/events-shell.js"
    script = ("globalThis.window = { addEventListener() {} }; globalThis.document = { readyState: 'loading', addEventListener() {} }; "
              "import(process.argv[1]).then(() => console.log(JSON.stringify("
              "JSON.parse(process.argv[2]).map((q) => window.PartyEvents.target(new URLSearchParams(q))))))")
    out = subprocess.run(["node", "-e", script, shell.as_uri(), json.dumps([f"tab=events&prono={PRONO}", "tab=events&prono=../x"])],
                         capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == [f"/events/prono/{PRONO}", "/events/"]
    apns = read("supabase/functions/send-push/apns.ts")
    assert "data.kind.startsWith('prono_')" in apns and "return `/?tab=events&prono=${data.prono_id}`" in apns
    sql = read("supabase/migrations/20261117180000_pronos.sql")
    assert "'url', '/?tab=events&prono=' || p.id" in sql  # Web Push suit data.url (chemin du même site)


def test_honour_only_no_stake_no_money_word_on_screen():
    """Revue de conformité du 17.11 : jamais « pari / mise / pot / cagnotte / cote », aucun champ d'enjeu ni de paiement."""
    screens = [read(p) for p in ("web/events/src/app/prono/[id].tsx", "web/events/src/app/prono/new.tsx", "web/events/src/app/pronos.tsx",
                                 "web/events/src/app/group/[id]/pronos.tsx", "web/events/src/app/prono-invite/[token].tsx",
                                 "web/events/src/components/pronos/Bits.tsx", "web/events/src/components/pronos/EventPronos.tsx",
                                 "ios/Party/Pronos/PronoDetailView.swift", "ios/Party/Pronos/PronoNewView.swift",
                                 "ios/Party/Pronos/PronosListView.swift")]
    for text in screens:
        visible = " ".join(re.findall(r"[\"'«`]([^\"'`»]{3,})[\"'»`]", text)).lower()
        for word in ("parier", "pariez", "cagnotte", "pot commun", "jackpot", "cote ", "miser", "enjeu", "twint", "revolut", "payer"):
            assert word not in visible, word
        assert "payment" not in text  # « stake » (patates plantées, v2) est un nom de champ, jamais un mot à l'écran
    sql = read("supabase/migrations/20261117180000_pronos.sql")
    assert "stake" not in sql and "amount" not in sql
    # L'IA, les pièces de Zicou, le bar et le Pot commun ne touchent jamais un prono.
    for path in ("app/ai_events.py", "app/ai_event_edit.py", "app/tricount.py"):
        assert "prono" not in read(path)
    # Le rappel des confettis (v2, 18.11) remplace « aucun argent, aucune mise » (mot interdit) : web (lib) et iPhone (kit).
    assert "Les confettis n'ont aucune valeur" in read("web/events/src/lib/pronos.ts").replace("’", "'")
    assert "aucune valeur" in read("ios/Party/Pronos/PronoKit.swift") or "aucune valeur" in read("ios/Party/Pronos/PronosStore.swift")


def test_the_iphone_opens_pronos_natively():
    bridge = read("ios/Party/NativeBridge.swift")
    assert "pronos: {" in bridge and "PronosHandler(model: model), name: pronosHandler" in bridge
    assert "PronoRoute.parse(body)" in bridge and "AppConfig.isInternal(message.frameInfo.securityOrigin.url)" in bridge
    assert "PronoRoute.requested(in: target)" in read("ios/Party/WebModel.swift")
    assert 'pronosRPC(token: String, fn: String' in read("ios/Party/Music/PartyAPI.swift")
    web = read("web/events/src/lib/pronos.ts")
    assert "PartyNative?: { pronos?" in web
    # Réglages › Autres apps : « Pronos », web et iPhone.
    assert 'label="Pronos"' in read("web/events/src/components/Settings.tsx")
    assert 'title: "Pronos"' in read("ios/Party/Settings/SettingsView.swift")
