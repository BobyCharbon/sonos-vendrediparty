"""Origine des inscriptions (avis 01da90202166, 22.11), module web, Supabase simulé : la connexion par SMS dit sa plateforme
(et le lien « Partager » d'où l'on vient) ; la fiche d'un membre montre « Inscrit via … » et Admin › Membres le compte par
source, seulement avec le droit « Voir l'origine des inscriptions »."""
import json

import pytest

from tests.test_app_invites_browser import CORS, MEMBER, mock_member
from tests.test_events_browser import ROOT, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)
from tests.test_members_root_browser import member_admin

pytestmark = pytest.mark.skipif(not (ROOT / 'web/events/dist/index.html').exists(), reason='Construire web/events avant les tests navigateur')
BASE = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
LINE = 'Inscrit via le lien d’invitation de « Raclette » (lien de Ludo) · site · 22.11.2026'
STATS = {'sources': [{'source': 'event_link', 'label': 'Lien d’invitation d’un événement', 'last30': 4, 'total': 9},
                     {'source': 'unknown', 'label': 'Inconnu (avant le suivi)', 'last30': 0, 'total': 31}],
         'platforms': [{'platform': 'ios', 'label': 'App iPhone', 'last30': 3, 'total': 5}]}


def mock_origin(page, allowed: bool) -> list:
    calls = []
    perms = ['events.view', 'members.view_identity', 'members.roles', 'members.ban'] + (['members.signup_source'] if allowed else [])

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        name = request.url.split('?')[0].rsplit('/', 1)[-1]
        calls.append((name, json.loads(request.post_data or '{}')))
        body = {'my_permissions': perms, 'note_signup': None,
                'admin_signup_sources': [{'id': MEMBER, 'source': 'event_link', 'line': LINE}], 'admin_signup_stats': STATS}[name]
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))
    for name in ('my_permissions', 'note_signup', 'admin_signup_sources', 'admin_signup_stats'):
        page.route(BASE + name, handle)
    return calls


def test_sign_in_tells_the_platform(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        calls = mock_origin(page, allowed=False)
        page.goto(events_origin + '/events/', wait_until='domcontentloaded')
        login(page)
        for _ in range(100):
            if any(c[0] == 'note_signup' for c in calls):
                break
            page.wait_for_timeout(100)
        assert ('note_signup', {'platform': 'web', 'shared_event': None}) in calls, calls
    finally:
        context.close()


@pytest.mark.parametrize('allowed', [False, True])
def test_member_card_and_admin_metric_only_with_the_right(browser, events_origin, allowed):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        member_admin(page)
        mock_member(page, None)
        calls = mock_origin(page, allowed)
        page.goto(events_origin + '/events/', wait_until='domcontentloaded')
        login(page)
        page.wait_for_timeout(500)
        page.goto(f'{events_origin}/events/member/{MEMBER}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Léa', exact=True).first).to_be_visible(timeout=15000)
        if allowed:
            pw.expect(page.get_by_text(LINE, exact=True)).to_be_visible()
        else:
            page.wait_for_timeout(500)
            pw.expect(page.get_by_text('Inscription', exact=True)).to_have_count(0)

        page.goto(f'{events_origin}/events/admin/members', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('3 compte(s) inscrit(s)', exact=True)).to_be_visible(timeout=15000)
        title = page.get_by_text('D’où viennent les inscrits', exact=True)
        if allowed:
            pw.expect(title).to_be_visible()
            pw.expect(page.get_by_text('Inconnu (avant le suivi)', exact=True)).to_be_visible()
            pw.expect(page.get_by_text('31', exact=True)).to_be_visible()
        else:
            pw.expect(title).to_have_count(0)
            assert not any(c[0].startswith('admin_signup') for c in calls), calls
    finally:
        context.close()
