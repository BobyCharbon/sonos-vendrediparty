"""📜 Journal de l'admin : visible dans Réglages de /admin et dans « Invités et messages » de l'app, noms échappés."""
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402
from tests.e2e.helpers import ADMIN_PIN, Phone, Server  # noqa: E402

XSS = '<img src=x onerror="window.pwned=1">'


@pytest.fixture
def server():
    s = Server()
    yield s
    s.stop()


def test_admin_settings_show_the_journal_newest_first_with_escaped_names(browser, server):
    boss = Phone(browser, server, "Boss", device="desktop")
    try:
        req = boss.page.request
        assert req.post(f"{server.url}/api/admin/login", data={"pin": "0000"}).status == 401
        assert req.post(f"{server.url}/api/admin/login", data={"pin": ADMIN_PIN}).ok
        req.post(f"{server.url}/api/admin/rename", data={"guest_id": "g-xss-000001", "name": XSS})
        req.post(f"{server.url}/api/admin/ban", data={"guest_id": "g-xss-000001", "minutes": 10})
        boss.page.goto("/admin#settings")
        rows = boss.page.locator("#auditAdmin [data-audit-row]")
        expect(rows.first).to_contain_text("a bloqué", timeout=10000)
        expect(rows.first).to_contain_text("(10 min)")
        expect(rows.nth(1)).to_contain_text("a renommé")
        expect(rows.nth(2)).to_contain_text("Code PIN s'est connecté à l'admin")
        expect(rows.nth(3)).to_contain_text("code admin incorrect")
        assert boss.page.evaluate("window.pwned") is None  # le nom saisi reste du texte
        assert not boss.errors
    finally:
        boss.ctx.close()


def test_account_admin_sees_the_journal_on_the_guests_page_of_the_app(browser, server):
    boss = Phone(browser, server, "Boss")
    try:
        boss.page.goto("/")
        boss.page.request.post(f"{server.url}/api/admin/login", data={"pin": ADMIN_PIN})
        boss.page.evaluate("account = { name: 'Boss', admin: true }; adminSession = true; fbSyncRole(); showTab('host');")
        expect(boss.page.locator("#auditAdmin [data-audit-row]").first).to_contain_text("s'est connecté à l'admin", timeout=10000)
        assert not boss.errors
    finally:
        boss.ctx.close()
