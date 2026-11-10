"""Lien « Partager le lien » (/?tab=events&event=<id>) ouvert dans Party puis page RECHARGÉE (recette réelle du 10.11.2026,
iOS qui recharge l'app installée) : l'événement reste ouvert, au lieu de la connexion puis de l'accueil du module.
L'adresse garde l'événement seulement (jamais un billet scanné) et l'oublie dès qu'on change d'onglet."""
import pytest

from tests.test_events_browser import EVENT, browser, events_origin, mock_services  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
TICKET = 'a' * 64


def frame_path(page) -> str:
    page.wait_for_function("() => (document.getElementById('eventsFrame')?.src || '').includes('/events/')", timeout=10000)
    return page.evaluate("() => new URL(document.getElementById('eventsFrame').src).pathname")


def test_reloading_a_shared_event_link_keeps_the_event_open(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        page.goto(f'{events_origin}/?tab=events&event={EVENT}', wait_until='domcontentloaded')
        assert frame_path(page) == f'/events/event/{EVENT}'
        assert page.evaluate('location.search') == f'?tab=events&event={EVENT}'

        page.reload(wait_until='domcontentloaded')
        assert frame_path(page) == f'/events/event/{EVENT}'

        # Un autre onglet : l'adresse oublie l'événement (un rechargement ne ramène plus dessus).
        page.locator('#tabs [data-tab="music"]').click()
        assert page.evaluate('location.search') == ''
    finally:
        context.close()


def test_a_scanned_ticket_never_stays_in_the_address(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        page.goto(f'{events_origin}/?tab=events&event={EVENT}&ticket={TICKET}', wait_until='domcontentloaded')
        assert frame_path(page) == f'/events/event/{EVENT}/scan/{TICKET}'
        assert page.evaluate('location.search') == ''
    finally:
        context.close()
