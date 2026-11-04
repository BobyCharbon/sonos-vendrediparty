"""Fiche d'un joueur (profile-card.js) › « Écrire » (messages directs, 4.11), dans un vrai navigateur : le bouton ouvre
la conversation privée dans l'onglet Discussions ; il est caché sur ma propre fiche et quand Discussions est « Bientôt » ;
un refus (pas de groupe ni d'événement en commun) s'affiche sans fermer la fiche."""
import json

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from tests.e2e.test_brain_qa_stats import CARD, json_route, make_phone, server, signed_in  # noqa: F401 (fixtures)

DM = "6f1e7b62-9a2d-4d62-8b3c-3c2f9f5d1b01"


def open_card(phone, card=CARD, direct=None, status=200):
    page = phone.page
    calls = []

    def start(route):
        calls.append(json.loads(route.request.post_data))
        route.fulfill(status=status, content_type="application/json", body=json.dumps(direct))
    page.route("**/api/account/card", json_route(card))
    page.route("**/api/brain/compare", json_route({"target": None}))
    page.route("**/api/account/chats/direct", start)
    signed_in(phone)
    page.evaluate("PartyEvents.soon = false")
    page.evaluate("ProfileCard.open('1234', 'p-bob')")
    sheet = page.locator(".pc-card")
    expect(sheet.locator(".pc-name")).to_have_text(card["display_name"])
    return sheet, calls


def test_write_opens_the_private_conversation_in_discussions(make_phone):
    phone = make_phone()
    sheet, calls = open_card(phone, direct={"id": DM})
    sheet.get_by_role("button", name="💬 Écrire").click()
    expect(phone.page.locator(".pc-card")).to_have_count(0)
    phone.page.wait_for_function("document.body.dataset.tab === 'chats'")
    assert calls[0]["user_id"] == CARD["id"] and calls[0]["token"]
    assert phone.page.evaluate("frameAt") == f"/chats/{DM}"


def test_refusal_keeps_the_card_and_explains(make_phone):
    phone = make_phone()
    sheet, _ = open_card(phone, direct={"detail": "Tu ne peux pas écrire à cette personne."}, status=400)
    sheet.get_by_role("button", name="💬 Écrire").click()
    expect(phone.page.get_by_text("Tu ne peux pas écrire à cette personne.").first).to_be_visible()
    expect(sheet).to_be_visible()


def test_no_write_button_on_my_own_card_or_when_discussions_are_coming_soon(make_phone):
    phone = make_phone()
    sheet, _ = open_card(phone, card={**CARD, "me": True})
    expect(sheet.get_by_role("button", name="💬 Écrire")).to_have_count(0)
    phone.page.evaluate("PartyEvents.soon = true")
    phone.page.evaluate("ProfileCard.open('1234', 'p-bob')")
    expect(phone.page.locator(".pc-card .pc-name")).to_have_text(CARD["display_name"])
    expect(phone.page.locator(".pc-write")).to_have_count(0)
