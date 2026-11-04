"""Mes amis dans Party et invitations dans l'app (avis 84fab3987f68) : relais fixes, jamais de numéro ni de rôle,
liens validés avant la base, aperçu sans session, interrupteurs des deux nouvelles notifications."""
import json

import httpx
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main
from app.app_invites import AppInvites, invite_url
from app.contact_names import ContactNames
from tests.test_notify_prefs import FakeAccounts

LEA = "11111111-1111-1111-1111-111111111111"
TOKEN = "22222222-2222-4222-8222-222222222222"


def fake(reply: dict | None = None, status: int = 200):
    """Base simulée : chaque fonction répond ce qu'on lui donne ; on garde ce qui a été envoyé."""
    seen = []

    def handler(request: httpx.Request):
        seen.append((request.url.path, request.content, request.headers.get("authorization")))
        if request.url.path == "/auth/v1/user":
            return httpx.Response(200, json={"id": "u-me"})
        if request.url.path == "/storage/v1/object/sign/profile-photos":
            paths = json.loads(request.content)["paths"]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/profile-photos/{p}?token=t"} for p in paths])
        name = request.url.path.rsplit("/", 1)[-1]
        if status != 200:
            return httpx.Response(status, json={"message": "self: C'est ton propre lien d'invitation."})
        return httpx.Response(200, content=json.dumps((reply or {}).get(name)).encode(),
                              headers={"content-type": "application/json"})

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    return acc, seen


def test_friends_relay_only_the_asked_accounts_without_number_or_role():
    acc, seen = fake({"contacts_friends": [
        {"id": LEA, "display_name": "Léa", "avatar_url": f"{LEA}/a.jpg", "joined_at": "2026-11-01T10:00:00Z",
         "common_groups": ["Vendredi Party", 3], "phone": "41790000001", "role": "admin"},
        {"id": "33333333-3333-3333-3333-333333333333", "display_name": "Pas demandé"}]})
    friends = ContactNames(acc).friends("tok", [LEA.upper(), LEA])
    assert friends == [{"id": LEA, "display_name": "Léa",
                        "photo": f"{accounts_mod.SUPABASE_URL}/storage/v1/object/sign/profile-photos/{LEA}/a.jpg?token=t",
                        "joined_at": "2026-11-01T10:00:00Z", "common_groups": ["Vendredi Party"]}]
    body = json.loads(next(c for p, c, _ in seen if p.endswith("/contacts_friends")))
    assert body == {"ids": [LEA]}  # dédoublonnés, en minuscules


def test_friends_refuse_bad_ids_before_the_base_and_skip_an_empty_list():
    acc, seen = fake()
    names = ContactNames(acc)
    assert names.friends("tok", []) == []
    try:
        names.friends("tok", ["pas-un-uuid"])
        raise AssertionError("aurait dû être refusé")
    except accounts_mod.AccountError:
        pass
    assert not any(p.endswith("/contacts_friends") for p, _, _ in seen)


def test_my_link_points_to_the_join_page_of_the_site():
    acc, _ = fake({"my_app_invite": {"token": TOKEN, "joined": 2, "created_at": "x"}})
    invites = AppInvites(acc, lambda: "https://partytest.bobycharbon.ch")
    assert invites.mine("tok") == {"token": TOKEN, "url": f"https://partytest.bobycharbon.ch/events/join/{TOKEN}", "joined": 2}
    assert invite_url("https://party.bobycharbon.ch/", TOKEN) == f"https://party.bobycharbon.ch/events/join/{TOKEN}"


def test_preview_is_read_without_a_member_session():
    acc, seen = fake({"app_invite_preview": {"inviter": "Ludo", "avatar_url": None, "phone": "41790000001"}})
    invites = AppInvites(acc, lambda: "https://party.bobycharbon.ch")
    assert invites.preview(TOKEN) == {"inviter": "Ludo"}  # rien d'autre, même si la base en disait plus
    assert invites.preview("pas-un-lien") is None
    path, _, auth = seen[-1]
    assert path.endswith("/app_invite_preview") and auth == f"Bearer {accounts_mod.SUPABASE_ANON_KEY}"
    assert not any(p == "/auth/v1/user" for p, _, _ in seen)


def test_unknown_link_preview_is_null():
    acc, _ = fake({"app_invite_preview": None})
    assert AppInvites(acc, lambda: "").preview(TOKEN) is None


def test_claim_relays_the_readable_reason():
    acc, _ = fake(status=400)
    try:
        AppInvites(acc, lambda: "").claim("tok", TOKEN)
        raise AssertionError("aurait dû être refusé")
    except accounts_mod.AccountError as e:
        assert str(e) == "C'est ton propre lien d'invitation."


def test_routes(monkeypatch):
    acc, _ = fake({"contacts_friends": [{"id": LEA, "display_name": "Léa"}],
                   "my_app_invite": {"token": TOKEN, "joined": 0},
                   "app_invite_preview": {"inviter": "Ludo"},
                   "claim_app_invite": {"new": True},
                   "member_invited_by": [{"inviter": "Ludo", "invited_by": LEA, "via": "group", "target": TOKEN,
                                          "target_name": "Les amis", "at": "2026-11-03T10:00:00Z"},
                                         {"via": "autre"}]})
    monkeypatch.setattr(main, "contact_names", ContactNames(acc))
    monkeypatch.setattr(main, "app_invites", AppInvites(acc, lambda: "https://party.bobycharbon.ch"))
    client = TestClient(main.app)
    assert client.post("/api/account/contacts/friends", json={"token": "t", "ids": [LEA]}).json()["friends"][0]["id"] == LEA
    assert client.post("/api/account/contacts/friends", json={"token": "t", "ids": [LEA] * 2001}).status_code == 422
    assert client.post("/api/account/invite", json={"token": "t"}).json()["url"].endswith(f"/events/join/{TOKEN}")
    assert client.post("/api/account/invite/preview", json={"invite": TOKEN}).json() == {"invite": {"inviter": "Ludo"}}
    assert client.post("/api/account/invite/preview", json={"invite": "x"}).status_code == 422
    assert client.post("/api/account/invite/claim", json={"token": "t", "invite": TOKEN}).json() == {"new": True}
    seen = client.post("/api/account/card/invited-by", json={"token": "t", "id": LEA}).json()["invited_by"]
    assert seen == [{"inviter": "Ludo", "invited_by": LEA, "via": "group", "target": TOKEN, "target_name": "Les amis",
                     "at": "2026-11-03T10:00:00Z"}]  # type inconnu écarté


def test_invited_by_is_null_without_the_right():
    acc, _ = fake({"member_invited_by": None})
    assert AppInvites(acc, lambda: "").invited_by("tok", LEA) is None


def test_both_new_notifications_have_their_switch(monkeypatch):
    monkeypatch.setattr(main, "accounts", FakeAccounts())
    client = TestClient(main.app)
    for key in ("referral_joins", "contact_joins"):
        r = client.post("/api/account/notifications/update", json={"token": "ok", "patch": {key: False}})
        assert r.status_code == 200 and r.json()["prefs"][key] is False, key


def test_join_page_has_a_rich_escaped_preview_for_whatsapp_and_imessage(monkeypatch, tmp_path):
    (tmp_path / "index.html").write_text("<html><head><title>Party</title></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(main, "EVENTS_WEB", tmp_path)
    acc, _ = fake({"app_invite_preview": {"inviter": 'Ludo"><script>alert(1)</script>'}})
    monkeypatch.setattr(main, "app_invites", AppInvites(acc, lambda: "https://party.bobycharbon.ch"))
    page = TestClient(main.app).get(f"/events/join/{TOKEN}").text
    assert 'property="og:title" content="Ludo&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt; t&#x27;invite sur Party"' in page
    assert "<script>alert" not in page
    assert 'property="og:image" content="https://party.bobycharbon.ch/static/icon-512.png"' in page
    assert 'name="twitter:card" content="summary"' in page
    assert f'property="og:url" content="https://party.bobycharbon.ch/events/join/{TOKEN}"' in page
    other = TestClient(main.app).get("/events/groups").text
    assert "og:title" not in other  # seulement la page du lien
