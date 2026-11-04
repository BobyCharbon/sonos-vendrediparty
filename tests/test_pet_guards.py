"""Compagnon : chaque faille du playtest « Marc » (4 novembre 2026) reproduite, puis corrigée. Serveur Party réel
(/api/pet/*), faux Supabase (FakeBase, mêmes règles que la migration 20261104170000) et horloge simulée.
La base elle-même est testée sur la vraie base de TEST : tests/supabase_live/test_pet_guards_live.py."""
import hashlib
import random
from datetime import date, timedelta


from app import main, pet, pet_chest, pet_loop, pet_store, pet_streak
from tests.test_pet_api import ALICE, BOB, PET_KEY, T0, TOK_A, TOK_B, act, me, setup  # noqa: F401 (fixture)

CAROL, DAN = "c0c0c0c0-1111-4222-8333-444455556666", "d0d0d0d0-1111-4222-8333-444455556666"
TOK_C, TOK_D = "c" * 40, "d" * 40


def hatch_both(c, clock):
    me(c)
    me(c, TOK_B)
    clock.go(minutes=5)
    me(c)
    me(c, TOK_B)


# ── F1 (critique) : seul le serveur, avec sa clé, écrit l'état ──

def test_f1_the_server_presents_its_key_and_without_it_the_base_refuses(setup, monkeypatch):
    c, base, clock, acc, log = setup
    me(c)
    assert base.pets[ALICE]["version"] == 1   # avec la clé : enregistré
    monkeypatch.setattr(main, "pet_service", lambda: pet_store.PetStore(acc, log, clock, secret=""))
    r = c.post("/api/pet/me", json={"token": TOK_A})
    assert r.status_code == 503 and "ne répond pas" in r.json()["detail"]   # clé absente : panne, pas « ta faute »
    monkeypatch.setenv("PET_SECRET", PET_KEY)
    assert pet_store.PetStore(acc, log, clock).secret == PET_KEY   # lue dans l'environnement du serveur


def test_f1_the_key_never_reaches_the_browser(setup):
    c, *_ = setup
    hatch_both(c, setup[2])
    for path, body in (("me", {}), ("act", {"action": "cuddle"}), ("friends", {}), ("game", {})):
        text = c.post(f"/api/pet/{path}", json={"token": TOK_A, **body}).text
        assert PET_KEY not in text


def test_without_pet_secret_the_server_makes_its_own_key_once_in_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("PET_SECRET", raising=False)
    key, from_env = pet_store.load_secret(tmp_path)
    path = tmp_path / pet_store.SECRET_FILE
    assert not from_env and len(key) == 64 and path.read_text() == key
    assert path.stat().st_mode & 0o777 == 0o600
    assert pet_store.load_secret(tmp_path) == (key, False)   # réutilisée ensuite
    monkeypatch.setenv("PET_SECRET", "cle-posee-sur-le-serveur-0123456789abcdef")
    assert pet_store.load_secret(tmp_path) == ("cle-posee-sur-le-serveur-0123456789abcdef", True)   # prioritaire


def test_without_pet_secret_the_companion_still_works_the_key_is_enrolled_once(setup, monkeypatch, tmp_path):
    c, base, clock, acc, log = setup
    monkeypatch.delenv("PET_SECRET", raising=False)
    own, _ = pet_store.load_secret(tmp_path)
    monkeypatch.setattr(pet_store, "_ENROLLED", set())
    monkeypatch.setattr(main, "pet_service", lambda: pet_store.PetStore(acc, log, clock, secret=own, enroll=True))
    assert me(c)["pet"]["stage"] == "egg" and base.enrolled == own   # enrôlée au premier besoin, rien de cassé
    assert act(c, "rename", name="Mochi").status_code == 200
    intruder = "une-autre-cle-qui-arrive-trop-tard-0123456789"
    monkeypatch.setattr(main, "pet_service", lambda: pet_store.PetStore(acc, log, clock, secret=intruder, enroll=True))
    assert c.post("/api/pet/me", json={"token": TOK_A}).status_code == 503   # une seule clé enrôlée
    assert base.enrolled == own


# ── F2 (élevée) : tirages imprévisibles sans la clé, rejouables et vérifiables avec ──

def _sha_category(uid: str, day: str, purpose: str = "chest") -> str:
    """La prédiction du playtest (ancienne graine sha256 sans secret)."""
    roll = random.Random(int(hashlib.sha256(f"party-pet:{uid}:{day}:{purpose}".encode()).hexdigest(), 16)).random()
    return pet_chest._weighted(pet_chest._Fixed(roll), [(r, r["weight"]) for r in pet_chest.CHEST_TABLE])[0]["cat"]


def test_f2_the_chest_cannot_be_predicted_without_the_server_key():
    store = pet_store.PetStore(None, pet_store.PartyLog(None), secret=PET_KEY)
    days = [(date(2026, 11, 5) + timedelta(days=i)).isoformat() for i in range(300)]
    def cat(d):
        roll = random.Random(store.seed(ALICE, d, "chest")).random()
        return pet_chest._weighted(pet_chest._Fixed(roll), [(r, r["weight"]) for r in pet_chest.CHEST_TABLE])[0]["cat"]
    same = sum(cat(d) == _sha_category(ALICE, d) for d in days)
    assert same < 0.7 * len(days)   # ≈ le hasard (0,7² + 0,2² + … ≈ 54 %), plus 100 % comme avant
    rare_old = {d for d in days if _sha_category(ALICE, d) == "rare"}
    rare_new = {d for d in days if cat(d) == "rare"}
    assert rare_old != rare_new
    other = pet_store.PetStore(None, pet_store.PartyLog(None), secret="une-autre-cle-de-serveur-0123456789abcdef")
    assert [store.seed(ALICE, d, "chest") for d in days[:5]] != [other.seed(ALICE, d, "chest") for d in days[:5]]


def test_f2_a_draw_stays_deterministic_and_the_admin_can_verify_it(setup, monkeypatch):
    c, base, clock, acc, log = setup
    monkeypatch.setattr(main, "pet_service", lambda: pet_store.PetStore(acc, log, clock, secret=PET_KEY))
    me(c)
    clock.go(minutes=5)
    me(c)
    found = act(c, "chest").json()["effect"]["found"]
    store = pet_store.PetStore(None, pet_store.PartyLog(None), secret=PET_KEY)
    assert store.verify_roll(ALICE, pet.day_of(clock.now), "chest") == found["roll"]
    a = store._rng(ALICE, T0, "chest").random()
    assert a == store._rng(ALICE, T0 + timedelta(hours=3), "chest").random()   # même jour : même tirage
    assert a != store._rng(ALICE, T0 + timedelta(days=1), "chest").random()
    assert a != store._rng(BOB, T0, "chest").random() and a != store._rng(ALICE, T0, "bonus_chest").random()


# ── F3 (moyenne) : le score du mini-jeu est calculé par le serveur ──

def _new_game(c, tok=TOK_A):
    r = c.post("/api/pet/game", json={"token": tok})
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["notes"] == pet_store.GAME_NOTES and g["ms"] == pet_store.GAME_MS
    return g["game"]


def test_f3_a_declared_score_is_ignored(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(hours=2)
    r = act(c, "play", score=100)   # le playtest : mission « dépasse 40 » validée sans jouer
    assert r.status_code == 200
    assert next(j for j in base.saves[-1]["p_journal"] if j["kind"] == "play")["detail"]["score"] == 0
    assert all(m["have"] == 0 for m in r.json()["pet"]["daily"]["missions"] if m["id"] == "score40")


def test_f3_a_real_game_is_signed_timed_counted_once_and_bounded(setup):
    c, base, clock, *_ = setup
    hatch_both(c, clock)
    clock.go(hours=2)
    game = _new_game(c)
    clock.go(seconds=5)
    early = act(c, "play", game=game, hits=20)   # fini en 5 s : impossible
    assert early.status_code == 400 and "Rejoue" in early.json()["detail"]
    clock.go(seconds=16)
    assert act(c, "play", game=game, hits=pet_store.GAME_NOTES + 1).status_code == 400   # plus de notes que lancées
    stolen = _new_game(c, TOK_B)
    clock.go(seconds=21)
    assert act(c, "play", game=stolen, hits=10).status_code == 400   # la partie d'un autre compte
    forged = game[:-4] + "0000" if not game.endswith("0000") else game[:-4] + "1111"
    assert act(c, "play", game=forged, hits=10).status_code == 400   # signature fausse
    ok = act(c, "play", game=game, hits=25)
    assert ok.status_code == 200, ok.text
    assert next(j for j in base.saves[-1]["p_journal"] if j["kind"] == "play")["detail"] == {"score": 83, "hits": 25}
    assert act(c, "play", game=game, hits=25).status_code == 400   # déjà comptée
    clock.go(minutes=11)
    late = _new_game(c)
    clock.go(minutes=11)
    assert act(c, "play", game=late, hits=5).status_code == 400   # expirée
    assert c.post("/api/pet/act", json={"token": TOK_A, "action": "play", "game": "<x>", "hits": 1}).status_code == 422


# ── F4 (moyenne) : cadeaux de comptes secondaires ──

def test_f4_at_most_3_gifts_received_a_day_by_the_engine_too():
    life, owner = pet.new_pet(T0)
    pet.advance(life, T0 + timedelta(minutes=5), owner)
    gifts = [{"id": f"g{i}", "kind": "snack", "from_name": f"Alt {i}"} for i in range(6)]
    life, owner, applied = pet.gifts(life, owner, T0 + timedelta(minutes=6), gifts)
    assert len(applied) == pet.GIFTS_PER_DAY == 3 and owner["stats"]["gifts_received"] == 3
    _, owner, more = pet.gifts(life, owner, T0 + timedelta(minutes=7), gifts[:1])
    assert more == []   # le même jour : plus rien
    _, owner, tomorrow = pet.gifts(life, owner, T0 + timedelta(days=1), gifts[:1])
    assert len(tomorrow) == 1


def test_f4_a_dead_or_brand_new_giver_cannot_give_and_a_friend_receives_3_a_day(setup):
    c, base, clock, *_ = setup
    base.users.update({TOK_C: CAROL, TOK_D: DAN})
    for u in (ALICE, BOB, CAROL, DAN):
        base.friends[u] = {ALICE, BOB, CAROL, DAN} - {u}
    for tok in (TOK_A, TOK_B, TOK_C, TOK_D):
        me(c, tok)
    clock.go(minutes=5)
    for tok in (TOK_A, TOK_B, TOK_C, TOK_D):
        me(c, tok)
    base.young.add(DAN)
    r = c.post("/api/pet/gift", json={"token": TOK_D, "friend": ALICE, "kind": "snack"})
    assert r.status_code == 400 and "3 premiers jours" in r.json()["detail"]
    base.young.clear()
    for tok in (TOK_B, TOK_C, TOK_D):
        assert c.post("/api/pet/gift", json={"token": tok, "friend": ALICE, "kind": "hug"}).status_code == 200
    base.friends[ALICE].add("e0e0e0e0-1111-4222-8333-444455556666")
    base.users["e" * 40] = "e0e0e0e0-1111-4222-8333-444455556666"
    base.friends["e0e0e0e0-1111-4222-8333-444455556666"] = {ALICE}
    me(c, "e" * 40)
    clock.go(minutes=5)
    me(c, "e" * 40)
    fourth = c.post("/api/pet/gift", json={"token": "e" * 40, "friend": ALICE, "kind": "hug"})
    assert fourth.status_code == 400 and "plein de cadeaux" in fourth.json()["detail"]
    clock.go(days=8)   # Carol n'a jamais nourri le sien : envolé
    assert me(c, TOK_C)["pet"]["stage"] == "dead"
    dead = c.post("/api/pet/gift", json={"token": TOK_C, "friend": ALICE, "kind": "hug"})
    assert dead.status_code == 400


# ── F5 (faible) : rien ne continue avec un compagnon envolé ──

def test_f5_no_chest_no_bonus_no_tuck_no_streak_once_he_is_gone(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=5)
    me(c)
    clock.go(days=8)
    assert me(c)["pet"]["stage"] == "dead"
    streak = base.pets[ALICE]["owner"]["streak"]["count"]
    for action in ("chest", "bonus_chest", "tuck", "treat"):
        r = act(c, action, item="cupcake")
        assert r.status_code == 400 and "envolé" in r.json()["detail"], (action, r.text)
    assert base.pets[ALICE]["owner"]["streak"]["count"] == streak
    assert act(c, "new_egg").status_code == 200   # un nouvel œuf : tout revient


# ── F6 (faible) : un palier de série ne paie qu'une fois par compte ──

def test_f6_a_milestone_pays_once_per_account_even_with_new_streaks():
    owner = pet.new_owner()
    owner["loop"] = pet_loop.new_loop()
    d0, paid = date(2026, 11, 2), []
    for d in (0, 1, 2, 6, 7, 8, 12, 13, 14):   # 3 jours, pause, 3 jours, pause, 3 jours (le playtest)
        owner["streak"], events = pet_streak.note_day(owner["streak"], d0 + timedelta(days=d))
        paid += [e["days"] for e in pet_loop.streak_rewards(owner, events)]
    assert paid == [3] and owner["loop"]["coins"] == pet_loop.MILESTONE_REWARDS[3][0]
    view = pet_loop.view(pet.new_life(pet.parse("2026-11-16T10:00:00+00:00")), owner, pet.parse("2026-11-16T10:00:00+00:00"))
    assert view["streak"]["milestones"][0]["reward"] == "Déjà gagné ✅"


# ── F7 (faible) : nuit douce seulement après une vraie nuit ──

def test_f7_tucked_then_woken_right_away_gives_no_soft_night(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=5)
    me(c)
    clock.go(hours=11, minutes=30)   # 21 h 35 à Zurich
    assert act(c, "tuck").status_code == 200
    woke = act(c, "wake")
    assert woke.status_code == 200 and any(n["kind"] == "woke_early" for n in woke.json()["news"])
    clock.go(hours=11)
    assert not any(n["kind"] == "soft_night" for n in me(c)["news"])


def test_f7_a_real_night_gives_it_even_when_he_peeks_after_midnight(setup):
    c, base, clock, *_ = setup
    me(c)
    clock.go(minutes=5)
    me(c)
    clock.go(hours=13, minutes=15)   # 23 h 20
    assert act(c, "tuck").status_code == 200
    clock.go(hours=1)                # 0 h 20, nouveau jour : trop tôt pour la nuit douce
    assert not any(n["kind"] == "soft_night" for n in me(c)["news"])
    clock.go(hours=7)                # 7 h 20
    assert any(n["kind"] == "soft_night" for n in me(c)["news"])
    assert not any(n["kind"] == "soft_night" for n in me(c)["news"])   # une seule fois


# ── F8 (faible) : liste d'amis et débit ──

def test_f8_reopening_the_friends_list_does_not_rewrite_the_companion(setup):
    c, base, clock, *_ = setup
    hatch_both(c, clock)
    before = len(base.saves)
    for _ in range(30):
        assert c.post("/api/pet/friends", json={"token": TOK_A}).status_code == 200
    assert len(base.saves) - before == 1   # la mission « visite », notée une fois


def test_f8_an_account_is_rate_limited(setup, monkeypatch):
    c, *_ = setup
    monkeypatch.setattr(main, "pet_rate", pet_store.AccountRate(limit=5, window=60))
    codes = [c.post("/api/pet/me", json={"token": TOK_A, "src": "none"}).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5 and codes[5:] == [429, 429]
    assert c.post("/api/pet/me", json={"token": TOK_B, "src": "none"}).status_code == 200   # un autre compte : libre


def test_rate_key_reads_the_account_of_a_jwt():
    import base64
    import json
    payload = base64.urlsafe_b64encode(json.dumps({"sub": ALICE}).encode()).decode().rstrip("=")
    assert pet_store.rate_key(f"x.{payload}.y") == f"sub:{ALICE}"
    assert pet_store.rate_key("pas-un-jwt").startswith("tok:")
