"""Compagnon câblé au serveur (/api/pet/*) avec un faux Supabase et une horloge simulée : premier œuf, actions,
enregistrement (version, projections, journal), conflit entre deux appareils, récompenses (Méninges, parties de
Party, soirées), cadeaux d'amis, visites limitées à ce qui est montrable, erreurs."""
import copy
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, main, pet, pet_store

TOK_A, TOK_B, TOK_GONE = "a" * 40, "b" * 40, "z" * 40
ALICE, BOB = "9a8b7c6d-1111-4222-8333-444455556666", "5d1f7f0e-3a1b-4c6e-9d2a-0b8e1c2d3f40"
STRANGER = "00000000-0000-4000-8000-000000000000"
T0 = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)


class FakeBase:
    """Faux Supabase : jetons → comptes, et les fonctions pet_* tenues en mémoire (mêmes règles que la migration)."""

    def __init__(self):
        self.users = {TOK_A: ALICE, TOK_B: BOB}
        self.pets: dict[str, dict] = {}
        self.gifts: list[dict] = []
        self.journal: list[tuple[str, dict]] = []
        self.saves: list[dict] = []
        self.brain: dict[str, list[str]] = {}
        self.events: dict[str, list[dict]] = {}
        self.friends = {ALICE: {BOB}, BOB: {ALICE}}
        self.down = False
        self.race = 0   # nombre d'enregistrements « d'un autre appareil » à simuler juste avant le prochain

    def handler(self, request: httpx.Request):
        uid = self.users.get(request.headers["Authorization"].removeprefix("Bearer "))
        path = request.url.path
        if path == "/auth/v1/user":
            return httpx.Response(200, json={"id": uid}) if uid else httpx.Response(401, json={})
        if self.down:
            return httpx.Response(503, json={})
        body = json.loads(request.content or b"{}")
        name = path.removeprefix("/rest/v1/rpc/")
        return getattr(self, name)(uid, body)

    @staticmethod
    def err(message):
        return httpx.Response(400, json={"message": message})

    def pet_load(self, uid, _):
        row = self.pets.get(uid)
        return httpx.Response(200, json={
            "pet": {k: copy.deepcopy(row[k]) for k in ("life", "owner", "version")} if row else None,
            "gifts": [{"id": g["id"], "kind": g["kind"], "from_name": g["from_name"]} for g in self.gifts
                      if g["to"] == uid and not g["applied"]],
            "brain": self.brain.get(uid, []), "events": self.events.get(uid, [])})

    def pet_save(self, uid, b):
        self.saves.append(b)
        row = self.pets.get(uid)
        if self.race:
            self.race -= 1
            if row:
                row["version"] += 1
        if (row["version"] if row else 0) != b["p_version"]:
            return self.err("conflict: Ton compagnon a changé sur un autre appareil.")
        self.pets[uid] = {"life": b["p_life"], "owner": b["p_owner"], "version": b["p_version"] + 1,
                          "dies_at": b["p_dies_at"], "hungry_at": b["p_hungry_at"]}
        for g in self.gifts:
            if g["to"] == uid and g["id"] in b["p_gifts"]:
                g["applied"] = True
        self.journal += [(uid, e) for e in b["p_journal"]]
        return httpx.Response(200, json={"version": b["p_version"] + 1})

    def _card(self, me, friend):
        row = self.pets[friend]
        return {"id": friend, "name": " <b>Bob</b> ", "avatar_url": None, "life": row["life"],
                "gifted": any(g["from"] == me and g["to"] == friend for g in self.gifts)}

    def pet_friends(self, uid, _):
        return httpx.Response(200, json=[self._card(uid, f) for f in self.friends.get(uid, set()) if f in self.pets])

    def pet_friend(self, uid, b):
        if b["p_friend"] not in self.friends.get(uid, set()) or b["p_friend"] not in self.pets:
            return self.err("forbidden: Tu ne peux rendre visite qu'aux membres de tes groupes.")
        return httpx.Response(200, json=self._card(uid, b["p_friend"]))

    def pet_gift(self, uid, b):
        if b["p_friend"] not in self.friends.get(uid, set()):
            return self.err("forbidden: Tu ne peux rendre visite qu'aux membres de tes groupes.")
        if any(g["from"] == uid and g["to"] == b["p_friend"] for g in self.gifts):
            return self.err("limit: Tu lui as déjà fait un cadeau aujourd'hui. Reviens demain 💜")
        self.gifts.append({"id": f"g{len(self.gifts)}", "from": uid, "to": b["p_friend"], "kind": b["p_kind"],
                           "from_name": "Alice", "applied": False})
        return httpx.Response(200, json={"ok": True})


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def go(self, **kw):
        self.now += timedelta(**kw)


@pytest.fixture
def setup(monkeypatch, tmp_path):
    base, clock = FakeBase(), Clock()
    acc = accounts_mod.Accounts(b"secret", httpx.Client(transport=httpx.MockTransport(base.handler)))
    log = pet_store.PartyLog(tmp_path / "pet_party.json")
    monkeypatch.setattr(main, "accounts", acc)
    monkeypatch.setattr(main, "pet_party_log", log)
    monkeypatch.setattr(main, "pet_service", lambda: pet_store.PetStore(acc, log, clock))
    monkeypatch.setattr(main, "account_limiter", main.Limiter(per_ip=1000, ip_lock=1, global_max=10000, global_window=1, global_lock=1))
    with TestClient(main.app) as c:
        yield c, base, clock, acc, log


def me(c, tok=TOK_A):
    r = c.post("/api/pet/me", json={"token": tok})
    assert r.status_code == 200, r.text
    return r.json()


def act(c, action, tok=TOK_A, **kw):
    return c.post("/api/pet/act", json={"token": tok, "action": action, **kw})


def test_the_first_visit_lays_an_egg_that_hatches(setup):
    c, base, clock, *_ = setup
    first = me(c)
    assert first["pet"]["stage"] == "egg" and first["pet"]["next_stage_in"] == pet.EGG_SECONDS
    assert base.pets[ALICE]["version"] == 1 and base.journal[0] == (ALICE, {"kind": "egg", "detail": {"gen": 1}})
    assert me(c)["pet"]["stage"] == "egg" and len(base.saves) == 1   # rien de nouveau : pas d'écriture
    clock.go(minutes=4)
    hatched = me(c)
    assert hatched["pet"]["stage"] == "baby" and hatched["news"] == [{"kind": "hatched", "text": "🐣 L'œuf a éclos !"}]
    assert base.saves[-1]["p_dies_at"] and base.saves[-1]["p_hungry_at"]


def test_actions_are_saved_with_projections_and_journal(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(hours=12)
    r = act(c, "feed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["effect"] == {"action": "feed", "unlocked": []} and body["pet"]["left"]["feed"] == pet.DAILY_LIMITS["feed"] - 1
    save = base.saves[-1]
    assert save["p_cared"] is True and save["p_version"] == 1
    assert {"kind": "feed", "detail": {}} in save["p_journal"]
    assert set(save["p_life"]) >= {"g", "stage", "at"} and "memorial" in save["p_owner"]
    assert act(c, "play", score=60).json()["pet"]["stats"]["plays"] == 1
    assert act(c, "rename", name="<img src=x>").json()["pet"]["name"] == "<img src=x>"   # échappé par le navigateur


def test_refusals_are_400_with_a_gentle_message(setup):
    c, _, clock, *_ = setup
    me(c)
    r = act(c, "feed")
    assert r.status_code == 400 and "éclore" in r.json()["detail"]
    clock.go(minutes=5)
    r = act(c, "outfit", outfit="couronne")
    assert r.status_code == 400 and "débloquée" in r.json()["detail"]
    assert act(c, "dance").status_code == 422
    assert act(c, "play", score=101).status_code == 422
    assert act(c, "outfit", outfit="../x").status_code == 422


def test_without_a_valid_account(setup):
    c, *_ = setup
    assert c.post("/api/pet/me", json={"token": TOK_GONE}).status_code == 401
    assert c.post("/api/pet/me", json={"token": "court"}).status_code == 400
    assert act(c, "feed", tok=TOK_GONE).status_code == 401


def test_database_down_is_503(setup):
    c, base, *_ = setup
    base.down = True
    assert c.post("/api/pet/me", json={"token": TOK_A}).status_code == 503


def test_a_save_from_another_device_is_retried_once_then_reported(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(hours=10)
    base.race = 1
    assert act(c, "cuddle").status_code == 200    # relu et rejoué
    base.race = 2
    r = act(c, "cuddle")
    assert r.status_code == 409 and "autre appareil" in r.json()["detail"]


def test_rewards_from_brain_party_games_and_soirees(setup):
    c, base, clock, acc, log = setup
    me(c)
    clock.go(minutes=5)
    me(c)
    clock.go(hours=6)
    base.brain[ALICE] = [pet.iso(clock.now - timedelta(minutes=10))]
    log.note(acc.gid(ALICE), "partie-1", clock.now.timestamp() - 60)
    base.events[ALICE] = [{"id": "ev1", "starts_at": pet.iso(clock.now - timedelta(hours=3))}]
    news = me(c)["news"]
    assert [n["kind"] for n in news] == ["reward", "reward", "reward", "unlocked"]
    assert "Collier lumineux" in news[-1]["text"]
    assert me(c)["news"] == []   # rien n'est compté deux fois


def test_a_finished_party_game_is_noted_for_account_players_only(setup, monkeypatch):
    c, _, _, acc, log = setup
    gid = acc.gid(ALICE)
    g = {"id": "abc", "code": "ABCD", "type": "quiz", "phase": "end", "players": [{"id": gid}, {"id": "guest-x"}]}
    monkeypatch.setattr(main, "get_game", lambda code: g)
    monkeypatch.setattr(main, "check_store_game", lambda *a: None)
    monkeypatch.setattr(main, "full_view", lambda game, guest: {"ok": True})
    c.get(f"/api/games/ABCD?guest_id={gid}")
    c.get(f"/api/games/ABCD?guest_id={gid}")
    c.get("/api/games/ABCD?guest_id=guest-x")
    assert len(log.times(gid)) == 1 and log.times("guest-x") == []
    assert pet_store.PartyLog(log.path).times(gid) == log.times(gid)   # gardé dans le fichier


def test_friends_visit_and_gifts(setup):
    c, base, clock, *_ = setup
    me(c)
    me(c, TOK_B)
    clock.go(minutes=5)
    me(c, TOK_B)
    friends = c.post("/api/pet/friends", json={"token": TOK_A}).json()["friends"]
    assert len(friends) == 1
    card = friends[0]
    assert card["member"] == "<b>Bob</b>" and card["gifted"] is False
    assert set(card["pet"]) == {"name", "stage", "variant", "emotion", "outfit", "age_hours", "gen", "line"}
    r = c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "hug"})
    assert r.status_code == 200 and r.json()["gifted"] is True
    again = c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "snack"})
    assert again.status_code == 400 and "demain" in again.json()["detail"]
    assert c.post("/api/pet/gift", json={"token": TOK_A, "friend": BOB, "kind": "bomb"}).status_code == 422
    news = me(c, TOK_B)["news"]
    assert news == [{"kind": "gift", "text": "🤗 Alice lui a offert un câlin"}]
    assert base.gifts[0]["applied"] and me(c, TOK_B)["news"] == []


def test_strangers_cannot_be_visited(setup):
    c, *_ = setup
    me(c)
    r = c.post("/api/pet/friend", json={"token": TOK_A, "friend": STRANGER})
    assert r.status_code == 400 and "groupes" in r.json()["detail"]
    assert c.post("/api/pet/friend", json={"token": TOK_A, "friend": "pas-un-uuid"}).status_code == 422


def test_death_memorial_and_new_egg_through_the_api(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=5)
    me(c)
    clock.go(days=8)
    dead = me(c)
    assert dead["pet"]["stage"] == "dead" and dead["pet"]["emotion"] == "ghost"
    assert dead["pet"]["memorial"][0]["gen"] == 1 and base.saves[-1]["p_dies_at"] is None
    assert any(e["kind"] == "died" for _, e in base.journal)
    assert act(c, "feed").status_code == 400
    egg = act(c, "new_egg").json()["pet"]
    assert egg["stage"] == "egg" and egg["gen"] == 2 and egg["memorial"][0]["gen"] == 1
