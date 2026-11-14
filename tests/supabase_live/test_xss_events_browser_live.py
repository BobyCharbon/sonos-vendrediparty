"""Recette RÉELLE (campagne sécurité du 14.11.2026) : un événement aux textes piégés s'affiche en texte, rien ne
s'exécute dans le module Événements. Vrai navigateur, vrai serveur Party, base de TEST.

Titre, description, nom du lieu et lien du lieu de l'événement contiennent « <img src=x onerror=…> », « "><img … »,
« " onfocus=… x=" », « javascript:… » et « data:text/html… ». La fiche s'ouvre comme chez l'organisateur : aucun appel
piégé exécuté, aucun élément ni attribut piégé dans le DOM, aucun lien javascript: / data:. Événement « sur invitation »
sans invité (personne n'est prévenu), supprimé à la fin.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>"""
import httpx
import pytest

from tests.e2e.test_xss_pages import FOUND, TRAP
from tests.supabase_live.test_audiences_live import ADMIN, create_event
from tests.supabase_live.test_inscription_complete_browser_live import (DIST, browser, party, phone_page,  # noqa: F401
                                                                        sign_in)
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark as live

pw = pytest.importorskip('playwright.sync_api')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]

TITLE = 'Recette XSS <img src=x onerror=__x(1)>'
DESCRIPTION = ('Lis ça "><img src=x onerror=__x(2)> puis javascript:__x(5) et data:text/html,<script>__x(6)</script> '
               'et https://exemple.ch/"onmouseover="__x(7)')


@pytest.fixture(scope='module')
def trapped_event():
    admin = Session(ADMIN)
    assert admin.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    e = create_event(admin, TITLE, visibility='invited', description=DESCRIPTION,
                     location_name='" onfocus=__x(3) autofocus x="', location_url='javascript:__x(4)')
    yield e
    r = httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', headers=admin.headers, timeout=30)
    assert r.status_code in (200, 204), r.text


def test_trapped_event_texts_stay_plain_text_on_the_event_page(browser, party, trapped_event):  # noqa: F811
    context, page, errors = phone_page(browser)
    context.add_init_script(TRAP)
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 04')
        pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
        page.goto(f'{party}/events/event/{trapped_event}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text(TITLE, exact=True).first).to_be_visible(timeout=30000)
        pw.expect(page.get_by_text('javascript:__x(5)', exact=False).first).to_be_visible()
        page.wait_for_timeout(1500)
        found = page.evaluate(FOUND)
        links = page.evaluate("() => [...document.querySelectorAll('a[href]')].map((a) => a.getAttribute('href'))")
        assert not found['fired'] and not found['nodes'], found
        assert not [h for h in links if h.strip().lower().startswith(('javascript:', 'data:', 'vbscript:'))], links
        assert 'https://exemple.ch/%22onmouseover=%22__x(7)' in links or not any('exemple.ch' in h for h in links), links
        assert not errors, errors
    finally:
        context.close()
