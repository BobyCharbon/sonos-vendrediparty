"""Réglages › Notifications (web, Supabase simulé) : section « 💬 Discussions des événements » en haut, « Mentions
seulement » par défaut et recommandé, ce qu'est une mention, la cloche de chaque discussion, et la liste « Discussions
réglées autrement » (event_chat_prefs) avec « Par défaut » (event_chat_set_level + event_chat_mute(null))."""
import json

import pytest

from tests.test_events_browser import ROOT, browser, events_origin, login, mock_services, pw  # noqa: F401
from tests.test_notification_pause_browser import CORS, PREFS

pytestmark = pytest.mark.skipif(not (ROOT / 'web/events/dist/index.html').exists(), reason='Construire web/events avant les tests navigateur')


def test_event_chats_section_default_mentions_and_overrides(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)
    prefs = dict(PREFS)
    rows = [{'event_id': 'e1', 'level': 'all', 'muted_until': None, 'events': {'title': 'Paintball'}},
            {'event_id': 'e2', 'level': 'mentions', 'muted_until': 'infinity', 'events': {'title': 'Soirée raclette'}},
            {'event_id': 'e3', 'level': 'mentions', 'muted_until': None, 'events': {'title': 'Pareil que défaut'}}]
    calls, patches = [], []

    def handle(route):
        r = route.request
        if r.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        url = r.url.split('?')[0]
        if url.endswith('/event_chat_prefs'):
            return route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(rows))
        if '/rpc/event_chat_' in url:
            args = json.loads(r.post_data)
            calls.append((url.rsplit('/', 1)[1], args))
            row = next(x for x in rows if x['event_id'] == args['e'])
            if 'level' in args:
                row['level'] = args['level']
            else:
                row['muted_until'] = args['until']
            return route.fulfill(status=200, content_type='application/json', headers=CORS, body='{}')
        if r.method == 'PATCH':
            patch = json.loads(r.post_data)
            patches.append(patch)
            prefs.update(patch)
        single = 'vnd.pgrst.object' in (r.headers.get('accept') or '')
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(prefs if single else [prefs]))
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/notification_prefs**', handle)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/event_chat_prefs**', handle)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/event_chat_**', handle)
    page.goto(events_origin, wait_until='domcontentloaded')
    page.locator('#accountTab').click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    frame.get_by_text('Notifications', exact=True).first.click()
    pw.expect(frame.get_by_text('💬 Discussions des événements')).to_be_visible(timeout=15000)
    pw.expect(frame.get_by_role('radio', name='Mentions seulement (recommandé)')).to_be_checked()
    pw.expect(frame.get_by_text('Chaque discussion peut avoir son propre réglage : la cloche en haut de la discussion.')).to_be_visible()
    pw.expect(frame.get_by_text('Paintball')).to_be_visible()
    pw.expect(frame.get_by_text('Mentions seulement · en sourdine')).to_be_visible()
    assert frame.get_by_text('Pareil que défaut').count() == 0
    frame.get_by_text('💬 Discussions des événements').scroll_into_view_if_needed()
    frame.get_by_role('button', name='Par défaut').nth(1).click()
    pw.expect(frame.get_by_text('Soirée raclette')).to_have_count(0)
    assert calls == [('event_chat_set_level', {'e': 'e2', 'level': 'mentions'}), ('event_chat_mute', {'e': 'e2', 'until': None})]
    frame.get_by_role('radio', name='Tout').click()
    pw.expect(frame.get_by_role('radio', name='Tout')).to_be_checked()
    assert patches[-1] == {'chat': 'all'}
    # Paintball (all) devient pareil que le défaut ; « Pareil que défaut » (mentions) s'affiche.
    pw.expect(frame.get_by_text('Pareil que défaut')).to_be_visible()
    pw.expect(frame.get_by_text('Paintball')).to_have_count(0)
    context.close()
