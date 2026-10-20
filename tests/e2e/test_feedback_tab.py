"""Onglet « Ton avis » de bout en bout : l'invité envoie, l'admin voit et traite."""
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import ADMIN_PIN, Phone, Server  # noqa: E402


@pytest.fixture
def server():
    s = Server()
    yield s
    s.stop()


def open_feedback(guest):
    """« Ton avis » : 4e onglet tant que les Événements sont « Bientôt », sinon un lien des Réglages ou de la connexion."""
    tab = guest.page.locator('button[data-tab="feedback"]')
    if tab.is_visible():
        tab.tap()
    else:
        guest.page.evaluate("showTab('feedback')")  # lien du module (testé dans test_events_browser)


def test_guest_feedback_reaches_admin(browser, server):
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Admin", "desktop")
    try:
        guest.page.set_viewport_size({"width": 360, "height": 740})
        guest.page.goto("/")
        open_feedback(guest)
        assert guest.page.evaluate("document.documentElement.scrollWidth <= innerWidth")  # 4 onglets tiennent
        guest.page.locator('[data-fb-kind="bug"]').tap()
        guest.page.locator("#fbText").fill("Le joystick est trop petit")
        guest.page.locator("#fbSend").tap()
        expect(guest.page.locator("#fbMine")).to_contain_text("Le joystick est trop petit")
        guest.shot("feedback_guest")
        boss.page.goto("/admin")
        boss.page.locator("#pin").fill(ADMIN_PIN)
        boss.page.locator("#pin").press("Enter")
        expect(boss.page.locator("#fbBadge")).to_have_text("1")
        boss.page.locator('button[data-tab="feedback"]').click()
        expect(boss.page.locator("#fbList")).to_contain_text("Le joystick est trop petit")
        expect(boss.page.locator("#fbList")).to_contain_text("Bug")
        boss.shot("feedback_admin")
        boss.page.locator('#fbList [data-fb="done"]').click()
        expect(boss.page.locator("#fbList")).to_contain_text("Rien à traiter")
        guest.page.locator('button[data-tab="music"]').tap()
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("Pris en compte")
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()
