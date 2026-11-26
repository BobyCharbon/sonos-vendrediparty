"""Exigences Apple du 14.11 dans le vrai module Événements (navigateur, Supabase simulé) : la page Confidentialité,
lisible sans compte, montre les données ajoutées depuis le 9.11 et la section Union européenne (RGPD, DSA)."""
import os

import pytest

from tests.test_events_browser import DIST, browser, events_origin, mock_services, pw  # noqa: F401 (fixtures)

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')


def test_privacy_page_shows_the_new_data_and_the_eu_section_without_an_account(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        page.goto(f'{events_origin}/events/privacy', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Mise à jour du 25 novembre 2026', exact=False)).to_be_visible(timeout=15000)
        for text in ('Covoiturage, seulement si l’organisateur l’ouvre', 'Nouveau compte :', 'Liens nommés et accord',
                     'Droit applicable (RGPD, nLPD, DSA)', 'la CNIL (France)', 'point de contact unique'):
            pw.expect(page.get_by_text(text, exact=False).first).to_be_attached()
        page.get_by_text('Droit applicable (RGPD, nLPD, DSA)', exact=False).first.scroll_into_view_if_needed()
        shots = os.environ.get('PARTY_SHOTS')
        if shots:
            page.screenshot(path=os.path.join(shots, 'confidentialite-ue.png'))
    finally:
        context.close()
