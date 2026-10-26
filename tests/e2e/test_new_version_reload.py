"""Nouvelle version déployée : l'app (installée, réveillée après le déploiement) se recharge pour prendre le
nouveau code. Référence = la version de la page chargée, pas la première annoncée par le serveur (bug du 26.10)."""
import pytest

pytest.importorskip("playwright.sync_api")
from tests.e2e.helpers import Phone, Server  # noqa: E402


@pytest.fixture
def server():
    s = Server()
    yield s
    s.stop()


def test_the_app_reloads_when_a_new_version_is_announced_even_if_it_woke_up_after_the_deploy(browser, server):
    phone = Phone(browser, server, "Lea")
    try:
        # App endormie : le flux en direct n'a encore rien annoncé quand elle se réveille après le déploiement.
        phone.page.route("**/api/events", lambda route: route.abort())
        phone.page.goto("/")
        build = phone.page.evaluate("siteBuild")
        assert build and build in phone.page.content()  # version de la page chargée (adresse de ses scripts)
        phone.page.evaluate(f"window.__same = true; checkBuild('{build}|42')")
        phone.page.wait_for_timeout(600)
        assert phone.page.evaluate("window.__same") is True  # même version : pas de rechargement
        with phone.page.expect_navigation():
            phone.page.evaluate("checkBuild('nouvelle-version|43')")  # 1er message après le réveil = nouveau code
        assert phone.page.evaluate("window.__same") is None
        assert not phone.errors
    finally:
        phone.ctx.close()
