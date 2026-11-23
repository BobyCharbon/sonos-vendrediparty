"""Groupes libres (décision de l'admin du 22.11.2026), étape 2 « Qui est invité » dans un vrai navigateur (Supabase
simulé) pour un compte SANS « publier sans validation » :
- « Public » dit AVANT de publier qu'un organisateur, un co-admin ou un admin de Vendredi Party doit l'accepter, et que
  l'équipe peut le modifier, le refuser ou le retirer ; le bouton dit « Envoyer pour validation » ;
- « Des groupes » (ses groupes seulement) : « Publier pour « Ski » », publié (la base décide : guard_event), jamais
  « Envoyé pour validation »."""
import json
from urllib.parse import urlparse

import pytest

from tests.test_ai_event_steps_browser import EMPTY_LIST, PEOPLE, SKI, draft_event, member_without_vip, open_step_two
from tests.test_events_browser import DIST, EVENT, browser, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import CORS, mock_invites, v2_origin  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')


def test_a_member_without_the_right_publishes_in_his_group_and_is_told_before_a_public_event(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, people=PEOPLE)
        mock_invites(page, guest_list=EMPTY_LIST)
        writes = draft_event(page)
        member_without_vip(page)
        perms = ['events.view', 'events.rsvp', 'events.create', 'chat.write']  # pas « publier sans validation »
        page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/my_permissions*', lambda route: route.fulfill(
            status=204, headers=CORS) if route.request.method == 'OPTIONS' else route.fulfill(
            status=200, content_type='application/json', headers=CORS, body=json.dumps(perms)))
        published = []

        def database_decides(route):
            """Comme guard_event : réservé à un groupe ordinaire, le statut demandé (« pending ») devient « published »."""
            request = route.request
            body = json.loads(request.post_data or 'null') if request.method == 'PATCH' else None
            if not (isinstance(body, dict) and 'status' in body and urlparse(request.url).path.endswith('/events')):
                return route.fallback()
            published.append(body['status'])
            route.fallback(post_data=json.dumps({**body, 'status': 'published'}))
        page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/events*', database_decides)

        open_step_two(page, v2_origin)
        pw.expect(page.get_by_text('Tes groupes : un toucher le publie', exact=False)).to_be_visible()
        pw.expect(page.get_by_text('attend l’accord d’un organisateur, d’un co-admin ou d’un admin de Vendredi Party', exact=False)).to_be_visible()
        pw.expect(page.get_by_text('modifier ses informations ou le retirer', exact=False)).to_be_visible()
        pw.expect(page.get_by_role('button', name='🌍 Public + lien public : Envoyer pour validation')).to_be_visible()
        page.get_by_role('button', name='👥 Des groupes', exact=True).click()
        pw.expect(page.get_by_role('button', name='Publier pour « Ski »')).to_be_visible()
        page.get_by_role('button', name='Publier pour « Ski »').click()
        pw.expect(page.get_by_label('Invités', exact=True).get_by_role('button', name='Inviter', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('Envoyé pour validation', exact=True)).to_have_count(0)
        assert ('POST', 'event_groups', [{'event_id': EVENT, 'group_id': SKI}]) in writes
        assert published == ['pending'], published  # l'écran demande, la base publie
        assert not errors, errors
    finally:
        context.close()


def test_a_member_is_told_before_publishing_that_the_group_must_accept_it(browser, v2_origin):  # noqa: F811
    """Recette iPhone du 22.11 : dans un groupe « Événements à valider » qu'il ne gère pas, un membre est prévenu AVANT
    de publier que l'événement n'y sera visible qu'une fois accepté (le bandeau ne valait que pour une modification)."""
    from tests.test_annonces_groupe_browser import BASE, new_page
    from tests.test_events_browser import USER, login
    context, page, errors = new_page(browser)
    try:
        mock_services(page)
        group = {'id': SKI, 'name': 'Ski', 'created_by': 'bbbbbbbb-0000-4000-8000-000000000009', 'system_key': None,
                 'events_need_approval': True, 'announce_mode': 'request', 'member_group_members': [{'user_id': USER}]}
        single = lambda r: 'vnd.pgrst.object' in (r.request.headers.get('accept') or '')  # noqa: E731
        page.route(f'{BASE}/member_groups*', lambda r: r.fulfill(status=204, headers=CORS) if r.request.method == 'OPTIONS' else r.fulfill(
            status=200, content_type='application/json', headers=CORS, body=json.dumps(group if single(r) else [group])))
        perms = ['events.view', 'events.rsvp', 'events.create', 'chat.write']
        page.route(f'{BASE}/rpc/my_permissions*', lambda route: route.fulfill(status=204, headers=CORS) if route.request.method == 'OPTIONS'
                   else route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(perms)))
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_role('button', name='Rechercher', exact=True)).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/event/new?group={SKI}', wait_until='domcontentloaded')
        note = page.get_by_test_id('group-recheck')
        pw.expect(note).to_be_visible(timeout=15000)
        pw.expect(note).to_contain_text('« Ski » fait valider les événements de ses membres')
        pw.expect(note).to_contain_text('visible une fois accepté par qui gère le groupe')
        pw.expect(note).not_to_contain_text('repasse en validation')
        assert not errors, errors
    finally:
        context.close()
