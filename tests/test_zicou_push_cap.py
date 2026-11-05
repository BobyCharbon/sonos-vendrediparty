"""Plafond des notifications Zicou (migration 20261105170000) : lu dans le SQL, sans base. Le comportement réel est
vérifié sur la base de test par tests/supabase_live/test_pet_push_cap_live.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261105170000_zicou_notifs_plafond.sql"
PROD = ROOT / "supabase/prod/2026-11-04-personnage-apply.sql"
ROLLBACK = ROOT / "supabase/prod/2026-11-04-personnage-rollback.sql"


def sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def function_body(text: str, name: str) -> str:
    start = text.index(f"create or replace function private.{name}(")
    return text[start:text.index("\n$$;", start)]


def test_the_cap_is_two_a_day():
    assert re.search(r"private\.pet_push_max\(\) returns integer\s+language sql immutable set search_path = '' as \$\$ select 2 \$\$", sql())


def test_every_zicou_push_takes_a_place_before_being_inserted():
    for name, kinds in (("pet_notify", 2), ("pet_bar_notify", 1)):
        body = function_body(sql(), name)
        inserts = [m.start() for m in re.finditer(r"insert into public\.notifications", body)]
        takes = [m.start() for m in re.finditer(r"continue when not private\.pet_push_take\(", body)]
        assert len(inserts) == kinds and len(takes) == kinds
        assert all(t < i for t, i in zip(takes, inserts))


def test_the_bar_never_takes_the_last_place_nor_follows_the_daily_reminder():
    body = function_body(sql(), "pet_bar_notify")
    assert "private.pet_push_take(r.user_id, at_time, 1)" in body
    assert "p.daily_sent_on is distinct from today" in body


def test_the_reminder_leaves_the_last_place_to_a_coming_hunger_alert():
    body = function_body(sql(), "pet_notify")
    assert "when v_kind = 'pet_gift' then private.pet_push_max()" in body
    assert "r.dies_at <= at_time + interval '48 hours' then private.pet_push_max() - 1" in body


def test_the_migration_is_additive_and_replayable():
    text = sql()
    assert "add column if not exists push_on" in text and "add column if not exists push_n" in text
    assert not re.search(r"^\s*(drop table|drop column|alter table .* drop|truncate|delete from)", text, re.I | re.M)
    assert text.count("create or replace function") == 4


def test_it_is_in_the_prod_file_with_its_rollback():
    prod = PROD.read_text(encoding="utf-8")
    assert "('20261105170000', 'zicou_notifs_plafond')" in prod
    assert prod.index("20261105160000', 'zicou_barre'") < prod.index("20261105170000', 'zicou_notifs_plafond'")
    back = ROLLBACK.read_text(encoding="utf-8")
    assert "drop function if exists private.pet_push_take(uuid, timestamptz, integer)" in back
    assert "drop column if exists push_n" in back
