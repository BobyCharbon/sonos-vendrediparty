"""Onglet « Ton avis » de bout en bout : l'invité envoie, l'admin voit et traite."""
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import ADMIN_PIN, FakeSupabase, Phone, Server, sign_in  # noqa: E402


@pytest.fixture
def server():
    supabase = FakeSupabase()
    s = Server(supabase)
    yield s
    s.stop()
    supabase.stop()


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
        sign_in(guest, "jeton-de-test-guest-plus-0001")  # « Ton avis » : Guest+ et au-dessus
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
        sign_in(guest, "jeton-de-test-guest-plus-0001")
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


def test_feedback_tab_is_only_for_guest_plus_and_above(browser, server):
    """Non connecté ou Guest : pas d'onglet « Ton avis », et le serveur refuse l'envoi ; Guest+ : l'onglet revient."""
    phone = Phone(browser, server, "Tom")
    tab = phone.page.locator('#tabs button[data-tab="feedback"]')
    try:
        phone.page.goto("/")
        expect(tab).to_be_hidden()  # non connecté
        refused = phone.page.request.post(f"{server.url}/api/feedback", data={
            "guest_id": phone.gid, "name": "Tom", "kind": "idea", "text": "Un mode équipe au Quiz, avec deux camps"})
        assert refused.status == 403
        sign_in(phone, "jeton-de-test-guest-0001")
        phone.page.wait_for_function("account && account.name === 'Tom'")
        expect(tab).to_be_hidden()  # Guest connecté : toujours pas
        sign_in(phone, "jeton-de-test-guest-plus-0001")
        expect(tab).to_be_visible()  # Guest+ : l'onglet apparaît
        phone.page.evaluate("showTab('feedback')")
        phone.page.locator("#fbText").fill("Trop court")
        phone.page.locator("#fbSend").tap()
        expect(phone.page.locator("#fbMine")).to_be_hidden()  # moins de 30 caractères : rien d'envoyé
        assert not phone.errors and not server.errors(), phone.errors
    finally:
        phone.close()
