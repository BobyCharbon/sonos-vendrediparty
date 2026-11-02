"""Tests sur la vraie base de TEST : certains fichiers attendent les surnoms « Testeur 1 » et « Testeur 2 », que d'autres
tests changent (« Guest A »…). Ces fichiers les remettent eux-mêmes avant de commencer : l'ordre de passage ne compte plus."""
import os

import pytest

NAMED = {"test_group_chats_live", "test_group_chats_relay_live", "test_invite_links_live"}


@pytest.fixture(autouse=True, scope="module")
def tester_names(request):
    if request.module.__name__.rsplit(".", 1)[-1] in NAMED and os.environ.get("SUPABASE_LIVE_TESTS"):
        from tests.supabase_live.test_member_admin_live import Session
        for i, phone in enumerate(("41790000001", "41790000002")):
            Session(phone).set_nickname(f"Testeur {i + 1}")
    yield
