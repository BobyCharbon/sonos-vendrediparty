"""Surnom de 12 caractères au plus (avis bda77087d7dc) : la même limite partout — base (guard_profile, dernière
migration qui le redéfinit), module Événements (IdentityForm) et app iPhone (ProfileRules). La base elle-même est testée
dans tests/supabase_live/test_surnom_12_live.py."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 12


def latest_guard_profile() -> str:
    for path in sorted((ROOT / "supabase/migrations").glob("*.sql"), reverse=True):
        text = path.read_text()
        if "function public.guard_profile()" in text:
            return text
    raise AssertionError("guard_profile introuvable")


def test_the_database_refuses_a_new_nickname_longer_than_twelve_but_keeps_older_ones():
    sql = latest_guard_profile()
    assert f"char_length(new.display_name) > {LIMIT}" in sql
    assert "new.display_name is distinct from btrim(old.display_name)" in sql
    assert f"le surnom est limité à {LIMIT} caractères" in sql


def test_the_web_form_and_the_iphone_use_the_same_limit():
    web = (ROOT / "web/events/src/lib/profile.ts").read_text()
    assert re.search(rf"export const NICKNAME_MAX = {LIMIT};", web)
    form = (ROOT / "web/events/src/components/IdentityForm.tsx").read_text()
    assert "maxLength={NICKNAME_MAX}" in form and "/ ${NICKNAME_MAX}" in form
    ios = (ROOT / "ios/Party/Settings/NotificationModels.swift").read_text()
    assert f"static let nicknameLength = {LIMIT}" in ios


def test_the_refusal_is_said_in_plain_words_on_the_web():
    moderation = (ROOT / "web/events/src/lib/moderation.ts").read_text()
    assert "nickname_too_long" in moderation
