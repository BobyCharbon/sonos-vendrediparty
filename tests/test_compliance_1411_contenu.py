"""Exigence Apple du 14.11.2026 (campagne de tests) : contenu, jeux, contenu des utilisateurs, notifications, tirages.
- 1.1 / 1.4.3 : questions « Pour ou contre » (141 WTF du 14.11 comprises) dans la classification 18+, sans geste imposé à
  un inconnu ni nourriture trafiquée ; Pyramide (mémorisation de 30 s) sans gorgée de plus ; un shot a toujours son
  verre d'eau ; un jeu à boire ne rapporte jamais rien ;
- 1.2 : tout texte libre montré aux autres passe le filtre commun — jeux (prénoms ajoutés par l'animateur, roue,
  réponses écrites, règles de Biskit, devinette de Mr. White) et base (prénom / nom du profil, nom d'un lien
  d'invitation, nom du lieu d'un événement : migration 20261114123000) ;
- 4.5.4 : chaque type de notification envoyé par la base a son interrupteur ;
- 5.3 : le règlement des cadeaux d'événement (Zicou, bêta) dit qu'Apple et Google ne sont ni organisateurs ni sponsors."""
import pathlib
import random
import re

import pytest

from app import games, moderation, pet_events, pet_reactions
from app.debate_questions import LIGHT, MORAL, RELATIONS, SOCIETY, WTF
from tests.test_games import biskit, draw, end_look, undercover

ROOT = pathlib.Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261114123000_filtre_noms_lieux.sql"
PROD = ROOT / "supabase/prod"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


# ── 1.1 : questions ──
@pytest.mark.parametrize("q", MORAL + SOCIETY + RELATIONS + LIGHT + WTF)
def test_every_dilemma_passes_the_common_filter_untouched(q):
    verdict = moderation.check(q, "message")
    assert verdict.ok and verdict.text == q


def test_wtf_dilemmas_never_push_drugs_alcohol_or_harm_to_someone():
    banned = re.compile(r"drogu|cannabis|cocaïne|\bjoint\b|ecstasy|alcool|\bivre|cuite|\bshots?\b|vodka|tequila|"
                        r"suicid|\barme|couteau|\bnazi|\bracis", re.IGNORECASE)
    assert [q for q in WTF if banned.search(q)] == []
    # Reformulées le 14.11 : rien qu'on fasse à un inconnu sans son accord, aucune nourriture trafiquée.
    gone = ("sauce piquante dans le yaourt", "l'aisselle de quelqu'un", "câlin de dix secondes à chaque personne",
            "renifler chaque inconnu")
    assert [q for q in MORAL + SOCIETY + RELATIONS + LIGHT + WTF if any(g in q for g in gone)] == []


# ── 1.4.3 : jeux à boire ──
def test_pyramid_memorising_adds_no_sip():
    g = games.new_game("pyramid", host="p0", name="P0")
    games.join(g, "p1", "P1")
    games.start(g, random.Random(7))
    P = g["pyr"]
    while g["phase"] == "deal":
        games.pyr_answer(g, P["order"][P["turn"]], games.PYR_STEPS[P["step"]][0])
    assert g["phase"] == "look"
    before = {k: dict(v) for k, v in g.get("tally", {}).items()}
    end_look(g)
    assert g["phase"] == "pyramid" and g.get("tally", {}) == before


def test_every_shot_comes_with_its_glass_of_water():
    page = read("app/static/games.js")
    shots = re.findall(r"[^.<>`\"]*\bun shot\b[^.<>`\"]*", page)
    assert shots and [s for s in shots if not re.search(r"\bou (un |ton |de l')(verre d'eau|eau)", s)] == []


@pytest.mark.parametrize("game", [{"type": "pyramid"}, {"type": "beerpong"}, {"type": "biskit"},
                                  {"type": "likely", "options": {"sips": 2}}, {"type": "quiz", "options": {"sips": 1}}])
def test_a_drinking_game_never_earns_anything(game):
    assert not pet_reactions.rewardable_game(game)


# ── 1.2 : textes des jeux ──
def test_a_name_typed_by_the_host_is_filtered():
    g = games.new_game("likely", host="h", name="Hôte")
    with pytest.raises(games.GameError, match="insulte"):
        games.add_guest(g, "Connard")
    assert games.add_guest(g, "Mamie")["name"] == "Mamie"
    wheel = games.new_game("roulette", host="h", name="Hôte")
    with pytest.raises(games.GameError, match="insulte"):
        games.set_names(wheel, ["Léa", "salope"])
    games.set_names(wheel, ["Léa", "Bob"])
    assert wheel["names"] == ["Léa", "Bob"]


def test_tmc_written_answer_is_filtered_like_le_masque():
    g = games.new_game("tmc", host="h", name="Hôte", plays=False)
    for gid, name in (("a", "Ana"), ("b", "Bob")):
        games.join(g, gid, name)
    games.start(g, random.Random(1))
    subject = g["tmc"]["duo"]["subject"]
    with pytest.raises(games.GameError, match="lien"):
        games.tmc_answer(g, subject, "va sur www.exemple.ch")
    games.tmc_answer(g, subject, "Une voiture de connard")
    assert g["tmc"]["duo"]["answers"][subject] == "Une voiture de •••••••"


def test_biskit_rule_is_filtered():
    g = biskit()
    a = draw(g, "JH")
    with pytest.raises(games.GameError, match="lien"):
        games.bk_complete(g, a, text="Tout le monde sur www.exemple.ch")
    games.bk_complete(g, a, text="Interdit de dire connard")
    assert g["bk"]["rules"][0]["text"] == "Interdit de dire •••••••"


def test_mr_white_guess_is_filtered():
    g = undercover(5)
    white = next(p["id"] for p in g["players"] if p["role"] == "white")
    games.start_vote(g)
    games.eliminate(g, white)
    with pytest.raises(games.GameError, match="lien"):
        games.white_guess(g, white, "www.exemple.ch")
    games.white_guess(g, white, "connard")
    assert g["last"]["guess"] == "•••••••"


# ── 1.2 : textes gardés par la base ──
def test_migration_filters_profile_names_link_names_and_place_names():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "before insert or update of first_name, last_name on public.profiles" in sql
    assert "private.moderate_text(new.first_name, 'name')" in sql and "private.moderate_text(new.last_name, 'name')" in sql
    assert "before insert or update of label on private.invite_links" in sql
    assert "private.moderate_text(new.label, 'name')" in sql
    assert "before insert or update of location_name on public.events" in sql
    assert "private.event_text_verdict(new.location_name, 'le nom du lieu')" in sql
    assert sql.count("if auth.uid() is null then return new; end if;") == 3  # le système (cron, service) n'y passe pas
    for trigger in ("profiles_identity_moderation", "invite_links_label_moderation", "events_place_moderation"):
        assert f"drop trigger if exists {trigger}" in sql
    assert not re.search(r"\bdrop (table|column)\b|\bupdate public\.|\bdelete from\b", sql, re.IGNORECASE)


def test_prod_files_are_ready():
    apply = (PROD / "2026-11-14-filtre-noms-lieux-apply.sql").read_text(encoding="utf-8")
    rollback = (PROD / "2026-11-14-filtre-noms-lieux-rollback.sql").read_text(encoding="utf-8")
    body = MIGRATION.read_text(encoding="utf-8").strip()
    assert apply.count("begin;") == 1 and "commit;" in apply and body in apply
    assert "values ('20261114123000', 'filtre_noms_lieux')" in apply
    assert "delete from supabase_migrations.schema_migrations where version = '20261114123000'" in rollback
    for trigger in ("profiles_identity_moderation", "invite_links_label_moderation", "events_place_moderation"):
        assert f"drop trigger if exists {trigger}" in rollback


# ── 4.5.4 : un interrupteur par type de notification ──
def test_every_notification_kind_queued_by_the_base_has_a_switch():
    sql = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "supabase/migrations").glob("*.sql")))
    queued = set(re.findall(r"queue_notification\(\s*[^,()]+,\s*'([a-z_]+)'", sql))
    switched = set(re.findall(r"when '([a-z_]+)' then (?:coalesce\()?prefs\.", sql))
    switched |= set(re.findall(r"when '([a-z_]+)' then split_part\(", sql))  # rappels : un interrupteur par délai
    assert len(queued) > 20
    assert queued - switched == {"push_test"}  # le test d'envoi demandé par la personne elle-même


# ── 5.3 : tirages ──
def test_draw_rules_say_apple_and_google_are_not_sponsors_on_every_screen():
    line = "Apple et Google ne sont ni organisateurs ni sponsors"
    assert any(line in r for r in pet_events.RULES)
    gifts = read("web/events/src/components/EventGifts.tsx")
    assert line in gifts and "RULES.map" in gifts
    assert "compagnonOn ?" in read("web/events/src/app/event/[id]/gifts.tsx")  # Zicou : bêta seulement
