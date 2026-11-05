"""Modération commune (Apple 1.2, Google UGC) : filtre de contenu (même algorithme que la base), relais iOS
(Signaler, Personnes bloquées, CGU, écran Signalements), prénoms des invités de Party filtrés."""
import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, group_admin as ga, group_chats as gc, moderation, moderation_api

MIGRATION = Path(__file__).resolve().parents[1] / "supabase/migrations/20261104200000_moderation.sql"
REPORT = "aaaaaaaa-0000-0000-0000-000000000001"
LEA = "bbbbbbbb-0000-0000-0000-000000000002"


@pytest.mark.parametrize("text", ["t'es un connard", "espèce de S@L0PE", "fuck you", "Hurensohn !", "va te faire enculer"])
def test_one_word_insults_are_masked_in_a_message(text):
    v = moderation.check(text, "message")
    assert v.ok and v.category == "insulte" and "•" in v.text and len(v.text) == len(text)


@pytest.mark.parametrize("text, category", [
    ("sale nègre", "haine"), ("niggaz", "haine"), ("heil Hitler", "haine"), ("Schwuchtel", "haine"),
    ("envoie des nudes", "sexuel"), ("p0rn0", "sexuel"), ("s a l o p e", "insulte"), ("s.a.l.o.p.e", "insulte"),
])
def test_hate_sex_and_disguised_insults_are_refused_in_a_message(text, category):
    v = moderation.check(text, "message")
    assert not v.ok and v.category == category and v.message.startswith("Message non envoyé")


@pytest.mark.parametrize("text", [
    "Bitte schön", "vieni con me", "en retard", "cocktail negroni", "salopette", "connexion", "cône", "analyse",
    "spice girls", "Nigeria", "merde, j'ai raté le bus", "putain c'est beau", "on se voit au 079 123 45 67",
    "regarde www.party.ch", "computer dispute",
])
def test_ordinary_words_and_mild_swears_pass_unchanged(text):
    v = moderation.check(text, "message")
    assert v.ok and v.category is None and v.text == text


@pytest.mark.parametrize("text, category", [
    ("saloooope", "insulte"), ("Fotze", "sexuel"), ("lea.com", "lien"), ("https://x.y", "lien"),
    ("079 123 45 67", "numero"), ("conne", "insulte"), ("sal​ope", "insulte"),
])
def test_names_refuse_bad_words_links_and_numbers(text, category):
    v = moderation.check(text, "name")
    assert not v.ok and v.category == category and "Choisis-en un autre" in v.message
    with pytest.raises(moderation.ContentRefused):
        moderation.require_clean(text, "word")


def test_good_names_pass_and_invisible_characters_are_dropped():
    assert moderation.require_clean("Zicou", "name") == "Zicou"
    assert moderation.require_clean("Lé​a", "name") == "Léa"
    with pytest.raises(ValueError):
        moderation.check("x", "inconnu")


def test_normalization_keeps_the_length_so_masks_line_up():
    text = "ÉCOUTE çà, Ŝ@l0pé"
    assert len(moderation.normalize(text)) == len(text)
    assert moderation.merged("t es une s a l o p e") == "t es une salope"


def test_the_migration_holds_exactly_the_python_patterns():
    sql = MIGRATION.read_text()
    assert moderation.sql_values() in sql  # recopier `python -m app.moderation --sql` après un changement de la liste
    # Même normalisation des deux côtés (translate de la base = tables du module).
    froms = re.search(r"translate\(lower\(coalesce\(t, ''\)\),\s*'([^']*)',\s*'([^']*)'\)", sql)
    assert froms.group(1) == moderation.ACCENTS_FROM + moderation.LEET_FROM
    assert froms.group(2) == moderation.ACCENTS_TO + moderation.LEET_TO


def test_party_guest_names_go_through_the_filter():
    from app import main
    with pytest.raises(Exception) as e:
        main.clean_name("Gros connard")
    assert "insulte" in str(e.value.detail)
    assert main.clean_name("  Léa   M ") == "Léa M"


def test_journal_lines_for_moderation_actions():
    entry = {"action": "moderation.suspend", "actor_name": "Boby", "target_name": "Tom", "details": {"days": 3}}
    assert ga.describe(entry) == "Boby a suspendu Tom pour 3 jour(s)"
    assert ga.describe({**entry, "action": "moderation.lift", "details": {}}) == "Boby a réintégré Tom"


def test_database_messages_lose_their_technical_prefix():
    r = httpx.Response(400, json={"message": "content_refused: Message non envoyé : il contient une insulte."})
    assert ga.readable(r, "x") == "Message non envoyé : il contient une insulte."
    assert ga.readable(httpx.Response(400, json={"message": "blocked: tu ne peux pas inviter cette personne"}), "x") \
        == "tu ne peux pas inviter cette personne"


def relay(queue=None, act=None):
    seen = []

    def handler(request: httpx.Request):
        body = json.loads(request.content) if request.content else None
        seen.append((request.method, request.url.path, body))
        path = request.url.path
        if path == "/rest/v1/rpc/report_content":
            if body["p_kind"] == "profile" and body["p_target"] == LEA:
                return httpx.Response(400, json={"message": "rate_limited: tu as fait beaucoup de signalements, réessaie plus tard"})
            return httpx.Response(200, json=REPORT)
        if path == "/rest/v1/rpc/my_blocks":
            return httpx.Response(200, json=[{"id": LEA, "display_name": "Léa", "avatar_url": "lea.jpg", "at": "2026-11-04T10:00:00Z"}])
        if path == "/rest/v1/rpc/moderation_queue":
            return httpx.Response(200, json=queue or [])
        if path == "/rest/v1/rpc/moderation_act":
            return httpx.Response(200, json=act or {"id": REPORT, "status": "actioned"})
        if path == "/rest/v1/rpc/my_terms":
            return httpx.Response(200, json={"version": "2026-11-04", "accepted": False, "contact_email": None, "enforced": False})
        if path == "/rest/v1/rpc/moderation_public_info":
            return httpx.Response(200, json={"terms_version": "2026-11-04", "contact_email": None, "terms_enforced": False})
        if path.startswith("/storage/v1/object/sign/"):
            bucket = path.rsplit("/", 1)[1]
            return httpx.Response(200, json=[{"path": p, "signedURL": f"/object/sign/{bucket}/{p}?t=1"} for p in body["paths"]])
        if path == "/storage/v1/object/profile-photos":
            return httpx.Response(200, json=[])
        if path.startswith("/rest/v1/rpc/"):
            return httpx.Response(204)
        return httpx.Response(404)

    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(handler)))
    admin = ga.GroupAdmin(acc)
    app = FastAPI()
    app.include_router(moderation_api.router(moderation_api.Moderation(admin, gc.GroupChats(admin))))
    return TestClient(app), seen


def test_report_is_relayed_with_the_member_session_and_errors_are_readable():
    client, seen = relay()
    r = client.post("/api/account/moderation/report", json={"token": "t", "kind": "group_message", "target": REPORT,
                                                            "reason": "harassment", "comment": "  insultes  "})
    assert r.status_code == 200 and r.json() == {"id": REPORT, "ok": True}
    assert seen[-1][2] == {"p_kind": "group_message", "p_target": REPORT, "p_reason": "harassment", "p_comment": "insultes"}
    r = client.post("/api/account/moderation/report", json={"token": "t", "kind": "profile", "target": LEA, "reason": "spam"})
    assert r.status_code == 400 and r.json()["detail"] == "tu as fait beaucoup de signalements, réessaie plus tard"
    bad = client.post("/api/account/moderation/report", json={"token": "t", "kind": "profile", "target": LEA, "reason": "vente"})
    assert bad.status_code == 422


def test_blocked_people_list_and_unblock():
    client, seen = relay()
    r = client.post("/api/account/moderation/block", json={"token": "t", "user_id": LEA, "on": False})
    assert r.status_code == 200
    assert ("POST", "/rest/v1/rpc/set_block", {"target": LEA, "blocked": False}) in seen
    person = r.json()["blocks"][0]
    assert person["name"] == "Léa" and person["photo"].endswith("/profile-photos/lea.jpg?t=1")


def test_terms_status_carries_the_page_link():
    client, _ = relay()
    r = client.post("/api/account/moderation/terms", json={"token": "t"})
    assert r.json()["url"] == "/events/terms" and r.json()["accepted"] is False


def test_queue_signs_photos_and_hiding_a_profile_photo_removes_the_file():
    queue = [{"id": REPORT, "kind": "profile_photo", "target_id": LEA, "reason": "shocking", "comment": None,
              "snapshot": {"text": "Léa", "photo_path": f"{LEA}/a.jpg", "place": "Profil"}, "status": "open",
              "created_at": "2026-11-04T10:00:00Z", "reporter": {"id": "x", "name": "Tom"},
              "target_user": {"id": LEA, "name": "Léa", "avatar_url": f"{LEA}/a.jpg", "status": "active"},
              "same_target": 2, "user_reports": 3, "sanctions": []}]
    client, seen = relay(queue=queue, act={"id": REPORT, "status": "actioned", "remove_photo": f"{LEA}/a.jpg"})
    q = client.post("/api/account/moderation/queue", json={"token": "t"}).json()
    item = q["reports"][0]
    assert item["reason_label"] == "Contenu choquant" and item["photo"].endswith(f"/profile-photos/{LEA}/a.jpg?t=1")
    assert item["user"]["name"] == "Léa" and item["same_target"] == 2 and item["reporter"] == "Tom"
    r = client.post("/api/account/moderation/act", json={"token": "t", "report_id": REPORT, "action": "hide"})
    assert r.status_code == 200
    assert ("DELETE", "/storage/v1/object/profile-photos", {"prefixes": [f"{LEA}/a.jpg"]}) in seen
    assert client.post("/api/account/moderation/act", json={"token": "t", "report_id": REPORT, "action": "suspend",
                                                            "days": 400}).status_code == 422
