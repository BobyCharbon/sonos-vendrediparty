"""Tests sur la vraie base de TEST : certains fichiers attendent les surnoms « Testeur 1 » et « Testeur 2 », que d'autres
tests changent (« Guest A »…). Ces fichiers les remettent eux-mêmes avant de commencer : l'ordre de passage ne compte plus."""
import os
from unittest import mock

import httpx
import pytest

NAMED = {"test_group_chats_live", "test_group_chats_relay_live", "test_invite_links_live", "test_rsvp_digest_live"}


def _quiet_event(method: str, url, kwargs: dict) -> dict:
    """Un événement de test ne prévient JAMAIS de vrais membres : la base de test contient de vrais comptes (avec
    leur iPhone) et notify_on_publish vaut true par défaut. Sans précision, il passe donc à false ; à true, il n'est
    accepté que pour un événement « sur invitation » (seuls les comptes de test invités sont prévenus)."""
    if "/rest/v1/events" not in str(url) or "/rest/v1/events_" in str(url) or not isinstance(kwargs.get("json"), dict):
        return kwargs
    body = dict(kwargs["json"])
    if method == "POST":
        body.setdefault("notify_on_publish", False)
    if body.get("notify_on_publish") and body.get("visibility") != "invited":
        raise AssertionError("Test live : un événement qui notifie doit être visibility='invited' (jamais de vrais membres prévenus)")
    return {**kwargs, "json": body}


@pytest.fixture(autouse=True, scope="session")
def no_notification_to_real_members():
    real_post, real_patch = httpx.post, httpx.patch
    with mock.patch.object(httpx, "post", lambda url, **kw: real_post(url, **_quiet_event("POST", url, kw))), \
            mock.patch.object(httpx, "patch", lambda url, **kw: real_patch(url, **_quiet_event("PATCH", url, kw))):
        yield


@pytest.fixture(autouse=True, scope="module")
def tester_names(request):
    if request.module.__name__.rsplit(".", 1)[-1] in NAMED and os.environ.get("SUPABASE_LIVE_TESTS"):
        from tests.supabase_live.test_member_admin_live import Session
        for i, phone in enumerate(("41790000001", "41790000002")):
            Session(phone).set_nickname(f"Testeur {i + 1}")
    yield
