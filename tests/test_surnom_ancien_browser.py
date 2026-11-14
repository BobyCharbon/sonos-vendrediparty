"""Surnom de 12 caractères au plus (avis bda77087d7dc) : un surnom plus long d'avant la règle reste valable. Dans
Réglages › Mon profil (module Événements, Supabase simulé), la personne change son nom sans toucher au surnom : il part
tel quel (la base l'accepte, testé dans tests/supabase_live/test_surnom_12_live.py) ; le champ ne permet pas de l'allonger."""
import json

import pytest

from tests.test_events_browser import DIST, USER, browser, events_origin, login, mock_services, pw  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
LONG = 'Compte de démonstration'  # surnom du compte simulé : 23 caractères, d'avant la règle


def test_an_older_long_nickname_is_kept_when_the_name_changes(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        calls = mock_services(page)
        page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/my_privacy', lambda route: route.fulfill(
            status=200, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
            body=json.dumps({'show_name': False, 'phone_groups': []})))
        page.goto(f'{events_origin}/events/settings/profile', wait_until='domcontentloaded')
        login(page)
        nickname = page.get_by_label('Surnom', exact=False)
        pw.expect(nickname).to_have_value(LONG, timeout=15000)
        nickname.press('End')
        nickname.press_sequentially('X')  # déjà au-delà de la limite : rien ne s'ajoute
        pw.expect(nickname).to_have_value(LONG)
        page.get_by_label('Nom', exact=True).fill('Demo-Test')
        page.get_by_role('button', name='Enregistrer').click()
        page.wait_for_timeout(1500)
        patches = [json.loads(body) for method, path, body in calls if method == 'PATCH' and path.endswith('/profiles')]
        assert patches and patches[-1]['display_name'] == LONG and patches[-1]['last_name'] == 'Demo-Test', patches
        assert not errors, errors
    finally:
        context.close()
