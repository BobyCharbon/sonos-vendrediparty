"""Message pour tout le monde (avis eb710b132330), dans un vrai navigateur :
- l'admin choisit Maintenance, Information ou Annonce et écrit son message, dans les Réglages de l'app ;
- une annonce s'affiche en haut de TOUS les onglets ; chacun la ferme d'un ✕ ;
- une maintenance couvre toute l'app (sauf chez l'admin) ;
- pendant une mise à jour (serveur arrêté puis relancé), on lit « Mise à jour en cours », jamais une erreur ;
  la partie reprend toute seule et le message s'efface quand le serveur revient."""
import os
import subprocess
import sys

import httpx
import pytest

pytest.importorskip('playwright.sync_api')
from playwright.sync_api import expect

from tests.e2e.helpers import ADMIN_PIN, ROOT, FakeSupabase, Phone, Server, sign_in

ADMIN_TOKEN = "jeton-de-test-admin-0001"


class AdminSupabase(FakeSupabase):
    ACCOUNTS = {**FakeSupabase.ACCOUNTS,
                ADMIN_TOKEN: ("u-admin", "Boby", ["party.admin", "party.settings", "feedback.write", "music.add"])}


@pytest.fixture
def server():
    supa = AdminSupabase()
    s = Server(supabase=supa, compagnon=False)
    yield s
    s.stop()
    supa.stop()


@pytest.fixture
def guest(browser, server):
    p = Phone(browser, server, "Alice")
    yield p
    errors = list(p.errors)
    p.close()
    assert not server.errors()
    assert not errors, "\n".join(errors)


def admin_api(server) -> httpx.Client:
    c = httpx.Client(base_url=server.url, timeout=10)
    assert c.post("/api/admin/login", json={"pin": ADMIN_PIN}).status_code == 200
    return c


def banner(page):
    return page.locator("#partyNotice.pn-banner")


def cover(page):
    return page.locator("#partyNotice.pn-overlay")


def test_an_announce_shows_on_every_tab_and_closes(guest, server):
    admin = admin_api(server)
    admin.post("/api/admin/notice", json={"kind": "announce", "message": "Karaoké à 22 h dans le salon !"})
    guest.page.goto("/")
    expect(banner(guest.page)).to_contain_text("Karaoké à 22 h dans le salon !")
    expect(banner(guest.page)).to_contain_text("Annonce")
    for tab in ("games", "music", "events", "account"):
        guest.page.locator(f'#tabs button[data-tab="{tab}"]').click()
        expect(banner(guest.page)).to_be_visible()
        box = banner(guest.page).bounding_box()
        assert box and box["y"] < 120, f"le bandeau n'est pas en haut de l'onglet {tab}"
    guest.shot("notice-annonce")
    guest.page.get_by_role("button", name="Masquer ce message").click()
    expect(banner(guest.page)).to_have_count(0)
    guest.page.reload()
    guest.page.wait_for_timeout(800)
    expect(banner(guest.page)).to_have_count(0)
    # Un nouveau message revient chez tout le monde.
    admin.post("/api/admin/notice", json={"kind": "info", "title": "Wi-Fi", "message": "Le réseau s'appelle Party"})
    guest.page.evaluate("PartyNotice.refresh()")
    expect(banner(guest.page)).to_contain_text("Le réseau s'appelle Party")


def test_a_maintenance_covers_a_running_game_then_lets_it_go_on(guest, server):
    guest.create("undercover")
    admin = admin_api(server)
    admin.post("/api/admin/notice", json={"kind": "maintenance", "message": "Retour vers 18 h"})
    # La partie interroge le serveur chaque seconde : le message arrive sans attendre.
    expect(cover(guest.page)).to_contain_text("Mise à jour en cours", timeout=12000)
    expect(cover(guest.page)).to_contain_text("Retour vers 18 h")
    guest.shot("notice-maintenance")
    admin.delete("/api/admin/notice")
    guest.page.evaluate("PartyNotice.refresh()")
    expect(cover(guest.page)).to_have_count(0)
    expect(guest.page.locator("#gamePlay")).to_be_visible()


def test_a_server_update_says_so_and_the_game_comes_back_by_itself(guest, server):
    code = guest.create("undercover")
    # Comme deploy/update.sh : le message, puis l'arrêt du serveur.
    subprocess.run([sys.executable, "-m", "app.notice", "deploy"], check=True, cwd=ROOT,
                   env={**os.environ, "DATA_DIR": server.data})
    expect(cover(guest.page)).to_contain_text("Mise à jour en cours", timeout=12000)
    server.halt()
    guest.page.wait_for_timeout(4000)
    expect(cover(guest.page)).to_contain_text("Mise à jour en cours")
    expect(guest.page.get_by_text("injoignable")).to_have_count(0)
    guest.shot("notice-mise-a-jour")
    server.start_again()
    # Le serveur revenu efface sa maintenance ; la page le voit toute seule et la partie reprend.
    expect(cover(guest.page)).to_have_count(0, timeout=15000)
    assert httpx.get(server.url + "/api/notice").json() == {"notice": None}
    expect(guest.page.locator("#gamePlay")).to_be_visible()
    assert guest.current() == code
    # Les requêtes refusées pendant l'arrêt sont attendues (console « Failed to load ») ; rien d'autre.
    guest.errors[:] = [e for e in guest.errors if "Failed to fetch" not in e and "fetch" not in e.lower()]


def test_the_admin_writes_the_message_in_the_settings_and_keeps_the_app_during_maintenance(browser, server):
    admin = Phone(browser, server, "Boby")
    admin.page.goto("/")
    sign_in(admin, ADMIN_TOKEN)
    admin.page.wait_for_function("window.partyIsAdmin && window.partyIsAdmin()", timeout=10000)
    admin.page.evaluate("showTab('notice')")
    screen = admin.page.locator("#noticeAdmin")
    expect(screen).to_contain_text("Aucun message en ce moment.")
    for label in ("Maintenance", "Information", "Annonce"):
        expect(screen.get_by_role("radio", name=label)).to_be_visible()
    screen.get_by_role("radio", name="Annonce").click()
    screen.locator("#noticeText").fill("Soirée raclette vendredi !")
    admin.shot("notice-reglages")
    screen.get_by_role("button", name="Afficher à tout le monde").click()
    expect(screen).to_contain_text("Affiché à tous depuis")
    expect(banner(admin.page)).to_contain_text("Soirée raclette vendredi !")
    assert httpx.get(server.url + "/api/notice").json()["notice"]["message"] == "Soirée raclette vendredi !"

    # Maintenance : tout le monde est bloqué, sauf l'admin (bandeau « Gérer »).
    admin.page.on("dialog", lambda d: d.accept())
    screen.get_by_role("radio", name="Maintenance").click()
    screen.locator("#noticeText").fill("Retour à 18 h")
    screen.get_by_role("button", name="Afficher à tout le monde").click()
    expect(banner(admin.page)).to_contain_text("affiché à tous")
    expect(cover(admin.page)).to_have_count(0)
    admin.shot("notice-admin-maintenance")
    admin.page.get_by_role("button", name="Retirer le message").click()
    expect(screen).to_contain_text("Aucun message en ce moment.")
    expect(admin.page.locator("#partyNotice")).to_have_count(0)
    assert httpx.get(server.url + "/api/notice").json() == {"notice": None}
    errors = admin.errors
    admin.close()
    assert not errors, "\n".join(errors)
