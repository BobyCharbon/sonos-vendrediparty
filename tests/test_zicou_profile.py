"""Zicou sur la fiche profil (/api/pet/profile) : l'apparence publique du Zicou d'un membre, jamais rien de privé
(jauges, pièces, inventaire, titre de vitrine), un nom seulement s'il passe le filtre, rien pour un membre bloqué, et
404 quand le Zicou est éteint (production)."""
import httpx
import pytest

from app import features, pet_profile
from tests.test_pet_api import ALICE, BOB, STRANGER, T0, TOK_A, TOK_B, me, setup  # noqa: F401 (fixture)

PUBLIC_KEYS = {"name", "stage", "variant", "emotion", "outfit", "acc", "shiny", "gen", "age_days", "best", "acc_items"}
PRIVATE_WORDS = ("gauges", "coins", "dust", "inv", "owner", "streak", "memorial", "g", "secret", "showcase", "line")


def with_profiles(base, blocks=()):
    """Même règle que public.pet_profile (migration 20261104240000) : null si bloqué ou inconnu ; jamais owner."""
    known = {ALICE, BOB}
    blocked = {frozenset(b) for b in blocks}

    def pet_profile(uid, b):
        target = b["p_member"]
        if target not in known or frozenset((uid, target)) in blocked:
            return httpx.Response(200, content=b"null")
        row = base.pets.get(target)
        life = row["life"] if row and row["life"]["stage"] != "dead" else None
        if life and isinstance(life.get("showcase"), dict):
            life = {**life, "showcase": {**life["showcase"], "title": ""}}
        mine = base.pets.get(uid)
        return httpx.Response(200, json={"life": life, "me": uid == target,
                                         "friend": uid != target and life is not None and target in base.friends.get(uid, set()),
                                         "mine": bool(mine) and mine["life"]["stage"] != "dead"})
    base.pet_profile = pet_profile


def profile(c, member, tok=TOK_A):
    return c.post("/api/pet/profile", json={"token": tok, "member": member})


def test_a_member_with_a_zicou_shows_only_his_public_look(setup):
    c, base, clock, *_ = setup
    with_profiles(base)
    me(c, TOK_B)
    clock.go(minutes=5)
    me(c, TOK_B)
    base.pets[BOB]["life"] |= {"shiny": True, "acc": {"head": "couronne"}, "showcase": {"title": "Mon secret", "items": [{"id": "lunettes"}]}}
    r = profile(c, BOB)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["member"] == BOB and body["me"] is False and body["friend"] is True and body["mine"] is False
    z = body["zicou"]
    assert set(z) == PUBLIC_KEYS
    assert z["stage"] == "baby" and z["shiny"] is True and z["acc"] == {"head": "couronne"} and z["gen"] == 1
    assert z["age_days"] == 0 and z["name"] == "Zicou"
    assert z["best"]["id"] == "couronne" and z["acc_items"][0]["label"]
    flat = r.text
    assert "Mon secret" not in flat and "coins" not in flat and "gauges" not in flat and '"owner"' not in flat


def test_age_is_counted_in_days(setup):
    c, base, clock, *_ = setup
    with_profiles(base)
    me(c, TOK_B)
    clock.go(minutes=5)
    me(c, TOK_B)
    clock.go(hours=50)
    me(c, TOK_B)
    assert profile(c, BOB).json()["zicou"]["age_days"] == 2


def test_a_refused_name_is_never_shown(setup):
    c, base, clock, *_ = setup
    with_profiles(base)
    me(c, TOK_B)
    base.pets[BOB]["life"]["name"] = "sale arabe"
    assert profile(c, BOB).json()["zicou"]["name"] is None


def test_without_a_zicou_the_card_says_so_and_knows_if_i_have_one(setup):
    c, base, *_ = setup
    with_profiles(base)
    body = profile(c, BOB).json()
    assert body["zicou"] is None and body["mine"] is False and body["friend"] is False
    me(c)   # j'adopte le mien
    assert profile(c, BOB).json()["mine"] is True
    own = profile(c, ALICE).json()
    assert own["me"] is True and own["friend"] is False and own["zicou"]["stage"] == "egg"


def test_a_zicou_that_flew_away_counts_as_none(setup):
    c, base, clock, *_ = setup
    with_profiles(base)
    me(c, TOK_B)
    clock.go(minutes=5)
    me(c, TOK_B)
    clock.go(days=8)
    assert me(c, TOK_B)["pet"]["stage"] == "dead"
    assert profile(c, BOB).json()["zicou"] is None


def test_a_blocked_member_sees_nothing(setup):
    c, base, *_ = setup
    with_profiles(base, blocks=[(ALICE, BOB)])
    me(c, TOK_B)
    assert profile(c, BOB).status_code == 404
    assert profile(c, ALICE, TOK_B).status_code == 404
    assert profile(c, STRANGER).status_code == 404


def test_bad_requests(setup):
    c, base, *_ = setup
    with_profiles(base)
    assert profile(c, "pas-un-uuid").status_code == 422
    assert profile(c, BOB, "z" * 40).status_code == 401


def test_off_in_production_is_404(setup, monkeypatch):
    c, base, *_ = setup
    with_profiles(base)
    monkeypatch.setenv("COMPAGNON_ENABLED", "0")
    r = profile(c, BOB)
    assert r.status_code == 404 and r.json()["detail"] == features.COMPAGNON_SOON


@pytest.mark.parametrize("life", [{"stage": "adult"}, {}, {"name": 3}])
def test_an_unreadable_zicou_shows_the_egg_instead_of_breaking(life):
    assert pet_profile.card({"life": life, "me": False, "friend": True, "mine": True}, BOB, T0)["zicou"] is None


def test_the_migration_reads_only_with_the_server_key_and_respects_blocks():
    from pathlib import Path
    sql = (Path(__file__).parents[1] / "supabase/migrations/20261104240000_zicou_fiche.sql").read_text()
    assert "private.pet_server_guard(p_key)" in sql and "private.blocked_either(me, p_member)" in sql
    assert "'owner'" not in sql and "p.owner" not in sql   # jamais ce qui reste au compte (pièces, inventaire)
    assert "revoke all on function public.pet_profile(uuid, text) from public, anon;" in sql
    prod = (Path(__file__).parents[1] / "supabase/prod/2026-11-04-personnage-apply.sql").read_text()
    assert "create or replace function public.pet_profile(" in prod and "'20261104240000'" in prod
