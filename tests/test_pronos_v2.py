"""Pronos v2 (18.11.2026) côté serveur : relais des nouvelles fonctions (sac, saison, contestation, réactions, trophée,
modèles), drapeau « patates » (monnaie fictive, gratuite, sans valeur) et photos signées des visages des nouvelles réponses.
La base est testée pour de vrai dans tests/supabase_live/test_pronos_v2_live.py."""
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from app import features, main, pronos

PRONO = "0a0b0c0d-0000-4000-8000-000000000009"
GROUP = "0a0b0c0d-0000-4000-8000-00000000000a"
V2 = ["prono_bag", "prono_bag_history", "prono_season", "prono_contest", "prono_contest_vote", "prono_react",
      "prono_optout", "prono_templates"]


@pytest.fixture
def client():
    return TestClient(main.app)


def rpc(client, fn, args=None):
    return client.post("/api/account/pronos/rpc", json={"token": "t", "fn": fn, "args": args or {}})


def test_the_new_functions_are_relayed(client, monkeypatch):
    monkeypatch.setenv("PATATES_ENABLED", "1")
    assert set(V2) <= pronos.RELAY
    with mock.patch.object(pronos.Db, "call", return_value=(200, {"ok": True})) as call:
        for fn in V2:
            assert rpc(client, fn, {"id": PRONO}).json() == {"result": {"ok": True}}, fn
        assert [c.args[0] for c in call.call_args_list] == V2
        assert call.call_args_list[0].args[2] == "t"  # jeton de la personne : la base décide des droits


@pytest.mark.parametrize("fn", ["prono_bag_set", "prono_bag_give", "pronos_tick", "prono_bag_move", "agenda_links", ""])
def test_unknown_functions_are_refused_without_calling_the_database(client, fn, monkeypatch):
    monkeypatch.setenv("PATATES_ENABLED", "1")
    with mock.patch.object(pronos.Db, "call", return_value=(200, [])) as call:
        assert rpc(client, fn).status_code in (404, 422)
        assert rpc(client, "report_content", {"p_kind": "booking_request", "p_target": "x"}).status_code == 404
        assert call.call_count == 0


@pytest.mark.parametrize("url,expected", [("https://partytest.bobycharbon.ch", True), ("https://party.bobycharbon.ch", False)])
def test_patates_are_on_only_on_the_test_site_without_the_variable(monkeypatch, url, expected):
    monkeypatch.delenv("PATATES_ENABLED", raising=False)
    monkeypatch.setenv("PARTY_PUBLIC_URL", url)
    assert features.patates_enabled() is expected
    assert TestClient(main.app).get("/api/features").json()["patates"] is expected


def test_the_variable_decides(monkeypatch):
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://party.bobycharbon.ch")
    monkeypatch.setenv("PATATES_ENABLED", "1")
    assert TestClient(main.app).get("/api/features").json()["patates"] is True
    monkeypatch.setenv("PARTY_PUBLIC_URL", "https://partytest.bobycharbon.ch")
    monkeypatch.setenv("PATATES_ENABLED", "0")
    assert TestClient(main.app).get("/api/features").json()["patates"] is False


def test_patates_off_the_bag_and_season_are_soon_and_no_patate_gets_in(client, monkeypatch):
    monkeypatch.setenv("PATATES_ENABLED", "0")
    with mock.patch.object(pronos.Db, "call", return_value=(200, {})) as call:
        for fn in ("prono_bag", "prono_bag_history", "prono_season"):
            r = rpc(client, fn, {"group_id": GROUP})
            assert r.status_code == 404 and r.json()["detail"] == "Bientôt", fn
        assert call.call_count == 0
        rpc(client, "prono_answer", {"id": PRONO, "answer": {"option_id": "o", "stake": 20}, "stake": 5})
        rpc(client, "prono_create", {"body": {"question": "Qui gagne ?", "group_id": GROUP, "patates": True}})
        rpc(client, "prono_update", {"id": PRONO, "body": {"patates": True, "rules": "Le score final"}})
        sent = {c.args[0]: c.args[1] for c in call.call_args_list}
    assert sent["prono_answer"] == {"id": PRONO, "answer": {"option_id": "o"}}
    assert sent["prono_create"] == {"body": {"question": "Qui gagne ?", "group_id": GROUP}}
    assert sent["prono_update"] == {"id": PRONO, "body": {"rules": "Le score final"}}
    # Le reste des Pronos v2 (pour l'honneur) marche sans patates.
    with mock.patch.object(pronos.Db, "call", return_value=(200, [])):
        for fn in ("prono_templates", "prono_react", "prono_optout", "prono_contest", "prono_contest_vote"):
            assert rpc(client, fn, {"id": PRONO}).status_code == 200, fn


def test_patates_on_stake_and_patates_reach_the_database(client, monkeypatch):
    monkeypatch.setenv("PATATES_ENABLED", "1")
    with mock.patch.object(pronos.Db, "call", return_value=(200, {})) as call:
        rpc(client, "prono_answer", {"id": PRONO, "answer": {"option_id": "o", "stake": 12}})
        rpc(client, "prono_create", {"body": {"question": "Qui gagne ?", "group_id": GROUP, "patates": True}})
        assert rpc(client, "prono_bag", {"group_id": GROUP}).status_code == 200
        sent = {c.args[0]: c.args[1] for c in call.call_args_list}
    assert sent["prono_answer"]["answer"]["stake"] == 12 and sent["prono_create"]["body"]["patates"] is True


def face(i, path):
    return {"id": i, "name": i.upper(), "avatar_url": path}


def test_faces_of_the_new_answers_get_a_signed_photo(client, monkeypatch):
    monkeypatch.setenv("PATATES_ENABLED", "1")
    season = {"month": "2026-11-01", "rows": [{"user": face("a", "a/p.png"), "harvest_net": 18, "rank": 1},
                                              {"user": face("b", None), "harvest_net": -4, "rank": 2}],
              "me": {"user": face("c", "c/p.png"), "rank": 3}}
    detail = {"id": PRONO, "faces": [face("a", "a/p.png")], "answers": [{"user": face("c", "c/p.png"), "stake": 5}],
              "reactions": [{"emoji": "🥔", "count": 2, "mine": True}]}
    signed = mock.Mock(status_code=200, json=lambda: [
        {"path": p, "signedURL": f"/object/sign/profile-photos/{p}?token=x"} for p in ("a/p.png", "c/p.png")])
    for fn, data in (("prono_season", season), ("prono_contest", detail), ("prono_react", detail), ("prono_optout", detail)):
        with mock.patch.object(pronos.Db, "call", return_value=(200, data)), mock.patch.object(main.accounts, "_get", return_value=signed):
            out = rpc(client, fn, {"id": PRONO}).json()["result"]
        if fn == "prono_season":
            assert out["rows"][0]["user"]["photo"].endswith("/storage/v1/object/sign/profile-photos/a/p.png?token=x")
            assert out["rows"][1]["user"]["photo"] is None
            assert out["me"]["user"]["photo"].endswith("c/p.png?token=x")
        else:
            assert out["faces"][0]["photo"].endswith("a/p.png?token=x"), fn
            assert out["answers"][0]["user"]["photo"].endswith("c/p.png?token=x"), fn
