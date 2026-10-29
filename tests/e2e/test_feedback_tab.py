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
        guest.page.locator("#fbText").fill("Le joystick est trop petit sur mon iPhone")
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
        boss.page.locator('#fbList [data-fb="done"]').first.click()
        expect(boss.page.locator("#fbList")).to_contain_text("Rien à traiter")
        guest.page.locator('button[data-tab="music"]').tap()
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("✅ Terminé")
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()


def act_as_account_admin(phone):
    """Compte Party admin connecté dans l'app : session admin (même cookie que /api/account/admin) + compte admin.
    La vérification du compte auprès de Supabase est testée dans test_accounts.py."""
    phone.page.request.post(f"{phone.server.url}/api/admin/login", data={"pin": ADMIN_PIN})
    phone.page.evaluate("account = { name: 'Boss', admin: true }; adminSession = true; fbSyncRole();")


def test_account_admin_manages_feedback_from_the_app_tab_and_guest_is_told(browser, server):
    guest, boss = Phone(browser, server, "Lea"), Phone(browser, server, "Boss")
    try:
        guest.page.goto("/")
        open_feedback(guest)
        guest.page.locator("#fbText").fill("Un mode équipe au Quiz, avec deux camps")
        guest.page.locator("#fbSend").tap()
        expect(guest.page.locator("#fbMine")).to_contain_text("Envoyé")

        boss.page.goto("/")
        act_as_account_admin(boss)
        tab = boss.page.locator('#tabs button[data-tab="feedback"]')
        expect(tab).to_be_visible()  # dans la barre du bas, plus besoin de /admin
        expect(tab).to_contain_text("Retours")
        expect(boss.page.locator("#fbTabBadge")).to_have_text("1")
        tab.tap()
        expect(boss.page.locator("#fbAdmin #fbList")).to_contain_text("Un mode équipe au Quiz")
        assert boss.page.locator("#fbGuest").is_hidden()

        # 🔧 En cours : l'invité voit « en cours de correction ».
        boss.page.locator('#fbAdmin [data-fb="progress"]').tap()
        expect(boss.page.locator("#fbTabBadge")).to_be_hidden()
        guest.page.reload()
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("En cours de correction")

        # ✅ Terminé avec un mot : l'invité a une pastille, voit le statut et le mot, puis la pastille s'éteint.
        boss.page.locator('#fbAdmin [data-fb-filter="progress"]').tap()
        boss.page.locator("#fbAdmin [data-fb-edit]").tap()
        boss.page.locator("#fbAdmin [data-fb-reply]").fill("Ajouté au Quiz, merci !")
        boss.page.locator('#fbAdmin .fb-edit [data-fb="done"]').tap()
        expect(boss.page.locator("#fbAdmin")).to_contain_text("Aucun retour")  # filtre « En cours » vide
        guest.page.locator('#tabs button[data-tab="music"]').tap()
        guest.page.reload()
        expect(guest.page.locator("#fbTabBadge")).to_have_text("1")
        open_feedback(guest)
        expect(guest.page.locator("#fbMine")).to_contain_text("✅ Terminé")
        expect(guest.page.locator("#fbMine")).to_contain_text("Ajouté au Quiz, merci !")
        expect(guest.page.locator("#fbTabBadge")).to_be_hidden()

        # L'admin peut toujours envoyer son propre avis.
        boss.page.locator('[data-fb-view="mine"]').tap()
        expect(boss.page.locator("#fbForm")).to_be_visible()
        assert boss.page.locator("#fbAdmin").is_hidden()
        assert not guest.errors and not boss.errors, guest.errors + boss.errors
    finally:
        guest.close(); boss.close()
