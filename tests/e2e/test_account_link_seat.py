"""Avis 6bad207324a3 (vrai navigateur) : Léa joue dans la salle de jeux sans compte, se connecte en pleine soirée,
puis l'animateur lance un jeu : elle n'y a qu'une place (pas de « deuxième Léa »), et c'est la même qu'avant."""
import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import FakeSupabase, Phone, Server, sign_in, wait_state  # noqa: E402

# État d'une partie vu par ce téléphone, sous l'identité qu'il utilise vraiment (localStorage vp_guest).
STATE_JS = """(code) => fetch(`/api/games/${code}?guest_id=${encodeURIComponent(localStorage.getItem('vp_guest'))}`)
  .then((r) => r.json())"""


@pytest.fixture
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    errors = s.errors()
    s.stop()
    supabase.stop()
    assert not errors, errors[-3000:]


def test_signing_in_mid_party_keeps_a_single_seat_in_the_next_game(browser, server):
    boby, lea = Phone(browser, server, "Boby"), Phone(browser, server, "Lea")
    try:
        room = boby.create("room")
        lea.join(room)
        lea.act("join")
        before = lea.pid()
        assert before
        sign_in(lea, "jeton-de-test-guest-plus-0001")  # compte « Léa »
        lea.page.wait_for_function("localStorage.getItem('vp_guest').startsWith('acct-')")
        account = lea.page.evaluate("localStorage.getItem('vp_guest')")
        players = wait_state(boby, lambda s: len(s.get("players", [])) == 2)["players"]
        assert [p["pid"] for p in players].count(before) == 1  # même place, renommée au compte

        boby.act("launch", settings={"type": "undercover"})
        expect(lea.page.locator("#gamePlay")).to_be_visible()
        child = wait_state(boby, lambda s: (s.get("room_info") or {}).get("current"))["room_info"]["current"]["code"]
        seen = lea.page.evaluate(STATE_JS, child)
        assert seen["type"] == "undercover" and bool(seen["me"]) and len(seen["players"]) == 2, json.dumps(seen)[:500]
        assert account not in json.dumps(seen) and lea.gid not in json.dumps(seen)  # identités secrètes jamais montrées
        assert lea.errors == [] and boby.errors == []
    finally:
        lea.close()
        boby.close()
