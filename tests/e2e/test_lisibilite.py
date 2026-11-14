"""Lisibilité de la page Party et de l'admin (campagne du 14.11.2026), réglages de la prod (Zicou et Discussions éteints) :
- les boutons des cartes de jeux ont un texte lisible sur leur couleur (WCAG AA 4,5:1) : « Lancer le test » était blanc
  sur rose clair (1,9:1), « Créer un quiz » blanc sur violet (4,35:1) ;
- sur ordinateur, aucun libellé du rail d'onglets n'est coupé (« Se connec… ») ;
- le bandeau d'annonce ne cache plus le titre ni le prénom : la page descend sous lui ;
- dans admin.html, une maintenance ne couvre pas la page de l'admin (code PIN et panneau restent utilisables)."""
import httpx
import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect

from tests.e2e.helpers import ADMIN_PIN, DEVICES, Phone, Server

CONTRAST = """(sel) => {
  const rgb = c => c.match(/[\\d.]+/g).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; })
    .reduce((s, v, i) => s + v * [.2126, .7152, .0722][i], 0);
  return [...document.querySelectorAll(sel)].filter(el => el.offsetParent).map(el => {
    const cs = getComputedStyle(el);
    const bg = rgb(cs.backgroundColor);
    if (cs.backgroundImage !== 'none' || (bg.length > 3 && bg[3] < 1)) return null;  // dégradé : non mesuré ici
    const a = lum(rgb(cs.color)), b = lum(bg);
    return { text: el.textContent.trim(), ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05) };
  }).filter(Boolean);
}"""


@pytest.fixture(scope="module")
def server():
    s = Server(compagnon=False)
    yield s
    errors = s.errors()
    s.stop()
    assert not errors, errors[-3000:]


@pytest.fixture
def phone(browser, server):
    p = Phone(browser, server, "Alice")
    yield p
    p.close()


def test_game_card_buttons_are_readable(phone):
    phone.open_games()
    measured = phone.page.evaluate(CONTRAST, "#gHome .g-go, #gHome .g-modes button.on")
    assert {"Lancer le test", "Créer un quiz"} <= {m["text"] for m in measured}
    low = [m for m in measured if m["ratio"] < 4.5]
    assert not low, low


def test_desktop_rail_labels_are_not_cut(browser, server):
    ctx = browser.new_context(base_url=server.url, locale="fr-CH", **DEVICES["desktop"])
    page = ctx.new_page()
    page.goto("/")
    expect(page.locator("#tabs")).to_be_visible()
    cut = page.evaluate("""[...document.querySelectorAll('#tabs button:not(.hidden) span')]
        .filter(s => s.offsetParent && s.scrollWidth > s.clientWidth + 1).map(s => s.textContent)""")
    ctx.close()
    assert not cut, cut


def test_the_announce_banner_does_not_hide_the_title(phone, server):
    admin = httpx.Client(base_url=server.url, timeout=10)
    assert admin.post("/api/admin/login", json={"pin": ADMIN_PIN}).status_code == 200
    admin.post("/api/admin/notice", json={"kind": "announce", "message": "Karaoké à 22 h dans le salon ! Venez nombreux."})
    try:
        phone.page.goto("/")
        phone.page.locator('#tabs button[data-tab="music"]').click()
        banner = phone.page.locator("#partyNotice.pn-banner")
        expect(banner).to_be_visible()
        phone.page.wait_for_timeout(400)  # fin de l'arrivée du bandeau
        b = banner.bounding_box()
        for sel in ("#appTitle", "#nameChip"):
            el = phone.page.locator(sel)
            if el.is_visible():
                assert el.bounding_box()["y"] >= b["y"] + b["height"], f"{sel} sous le bandeau"
        phone.page.get_by_role("button", name="Masquer ce message").click()
        expect(banner).to_have_count(0)
        assert phone.page.locator("#appTitle").bounding_box()["y"] < b["y"] + b["height"]  # la page remonte
    finally:
        admin.delete("/api/admin/notice")


def test_maintenance_does_not_cover_the_admin_page(browser, server):
    admin = httpx.Client(base_url=server.url, timeout=10)
    assert admin.post("/api/admin/login", json={"pin": ADMIN_PIN}).status_code == 200
    admin.post("/api/admin/notice", json={"kind": "maintenance", "message": "Retour vers 18 h"})
    ctx = browser.new_context(base_url=server.url, locale="fr-CH", **DEVICES["iphone"])
    page = ctx.new_page()
    try:
        page.goto("/admin")
        expect(page.locator("#partyNotice.pn-banner")).to_contain_text("affiché à tous")
        expect(page.locator("#partyNotice.pn-overlay")).to_have_count(0)
        page.locator("#pin").fill(ADMIN_PIN)
        page.locator("#login button").click()
        expect(page.locator("#tabs")).to_be_visible()
        page.locator('#tabs button[data-tab="settings"]').click()
        expect(page.locator('section[data-view="settings"]')).to_be_visible()
        # Un invité, lui, reste derrière l'écran de maintenance.
        guest = Phone(browser, server, "Bob")
        guest.page.goto("/")
        expect(guest.page.locator("#partyNotice.pn-overlay")).to_contain_text("Mise à jour en cours")
        guest.close()
    finally:
        ctx.close()
        admin.delete("/api/admin/notice")
