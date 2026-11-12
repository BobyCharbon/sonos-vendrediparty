"""Pause des notifications dans le module web (Supabase simulé, aucun SMS réel) : la lune en haut à droite des
Réglages (1 h, 2 h, 8 h du matin, Réactiver) et la pause des Discussions (Réglages › Notifications)."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from tests.test_events_browser import ROOT, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

pytestmark = pytest.mark.skipif(not (ROOT / 'web/events/dist/index.html').exists(), reason='Construire web/events avant les tests navigateur')
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile',
        'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS'}
PREFS = {'user_id': 'dd6a80f1-cc84-4fc2-8764-770b45786c04', 'push_enabled': True, 'quiet_start': None, 'quiet_end': None,
         'new_event': 'all', 'event_changed': True, 'poll_new': True, 'poll_nudge': True, 'date_fixed': True, 'waitlist': True,
         'proposals': True, 'rsvp_mine': True, 'chat': 'mentions', 'reminders': ['1d'], 'muted_until': None, 'chats_muted_until': None,
         'event_chats_muted_until': None}
SPANS = {'30m': timedelta(minutes=30), '1h': timedelta(hours=1), '2h': timedelta(hours=2), 'morning': timedelta(hours=5)}


def mock_pause(page) -> list:
    """notification_prefs et set_notification_pause, comme la base (la fin de pause est calculée côté serveur)."""
    prefs, picks = dict(PREFS), []

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        if request.url.split('?')[0].endswith('/rpc/set_notification_pause'):
            args = json.loads(request.post_data)
            picks.append(args)
            until = None if args['span'] == 'off' else (datetime.now(timezone.utc) + SPANS[args['span']]).isoformat()
            prefs[{'all': 'muted_until', 'chats': 'chats_muted_until', 'event_chats': 'event_chats_muted_until'}[args['what']]] = until
        single = 'vnd.pgrst.object' in (request.headers.get('accept') or '') or 'set_notification_pause' in request.url
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(prefs if single else [prefs]))
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/notification_prefs**', handle)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/set_notification_pause', handle)
    return picks


def open_settings(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)
    picks = mock_pause(page)
    page.goto(events_origin, wait_until='domcontentloaded')
    page.locator('#accountTab').click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    return context, page, frame, picks


def test_the_moon_at_the_top_right_of_settings_pauses_and_reactivates(browser, events_origin):  # noqa: F811
    context, page, frame, picks = open_settings(browser, events_origin)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        moon = frame.get_by_role('button', name='Mettre les notifications en pause')
        pw.expect(moon).to_be_visible(timeout=15000)
        # En haut à droite, à la hauteur du titre « Réglages ».
        box, title = moon.bounding_box(), frame.get_by_text('Réglages', exact=True).first.bounding_box()
        assert box['x'] + box['width'] > 390 - 40 and abs((box['y'] + box['height'] / 2) - (title['y'] + title['height'] / 2)) < 24
        assert box['width'] >= 40 and box['height'] >= 40
        moon.click()
        for label in ('1 heure', '2 heures', 'Jusqu’à 8 h du matin'):
            pw.expect(frame.get_by_role('menuitem', name=label, exact=True)).to_be_visible()
        pw.expect(frame.get_by_role('menuitem', name='30 minutes', exact=True)).to_have_count(0)
        frame.get_by_role('menuitem', name='1 heure', exact=True).click()
        pw.expect(frame.get_by_text('Notifications en pause jusqu’à', exact=False).first).to_be_visible()
        pw.expect(frame.get_by_text('elles arrivent sans son ni vibration', exact=False)).to_be_visible()
        assert picks == [{'what': 'all', 'span': '1h'}]
        # Lune pleine, puis « Réactiver » depuis le bandeau.
        frame.get_by_role('button', name='Réactiver les notifications').click()
        pw.expect(frame.get_by_role('button', name='Mettre les notifications en pause')).to_be_visible()
        assert picks[-1] == {'what': 'all', 'span': 'off'}
        # Et depuis la lune elle-même : « Jusqu’à 8 h du matin », puis « Réactiver maintenant ».
        frame.get_by_role('button', name='Mettre les notifications en pause').click()
        frame.get_by_role('menuitem', name='Jusqu’à 8 h du matin', exact=True).click()
        frame.get_by_role('button', name='Notifications en pause jusqu’à', exact=False).click()
        frame.get_by_role('menuitem', name='Réactiver maintenant', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Mettre les notifications en pause')).to_be_visible()
        assert picks[-2:] == [{'what': 'all', 'span': 'morning'}, {'what': 'all', 'span': 'off'}]
        assert frame.locator('html').evaluate('e => e.scrollWidth <= innerWidth')  # rien ne déborde à droite
        assert not errors, errors
    finally:
        context.close()


def test_group_and_event_discussions_have_separate_pauses_and_every_type_its_switch(browser, events_origin):  # noqa: F811
    context, page, frame, picks = open_settings(browser, events_origin)
    try:
        frame.get_by_text('Notifications', exact=True).click()
        groups = frame.get_by_role('button', name='Mettre en sourdine : Discussions des groupes')
        events = frame.get_by_role('button', name='Mettre en sourdine : Discussions des événements')
        pw.expect(groups).to_be_visible(timeout=15000)
        pw.expect(events).to_be_visible()
        groups.click()
        for label in ('30 minutes', '1 heure', '2 heures', 'Jusqu’à 8 h du matin'):
            pw.expect(frame.get_by_role('menuitem', name=label, exact=True)).to_be_visible()
        frame.get_by_role('menuitem', name='30 minutes', exact=True).click()
        pw.expect(frame.get_by_text('Discussions des groupes en pause jusqu’à', exact=False)).to_be_visible()
        assert picks == [{'what': 'chats', 'span': '30m'}]
        events.click()
        frame.get_by_role('menuitem', name='2 heures', exact=True).click()
        pw.expect(frame.get_by_text('Discussions des événements en pause jusqu’à', exact=False)).to_be_visible()
        assert picks[-1] == {'what': 'event_chats', 'span': '2h'}
        # Chaque type qu'on peut recevoir a son interrupteur, y compris les annonces des admins et la soirée.
        for label in ('Un organisateur répond pour moi', 'Invitation à un événement privé', 'Messages des groupes',
                      'Invitation dans un groupe', 'Quelqu’un rejoint mon groupe', 'Quelqu’un rejoint ou demande à venir par un lien',
                      'Ma proposition validée ou refusée', 'Annonces des admins'):
            pw.expect(frame.get_by_label(label, exact=True).first).to_be_attached()
        pw.expect(frame.get_by_text('Soirée : musique et avis', exact=True)).to_be_visible()
        # Indépendantes de la lune : la lune reste éteinte.
        frame.get_by_role('button', name='Retour : Réglages').click()
        pw.expect(frame.get_by_role('button', name='Mettre les notifications en pause')).to_be_visible()
    finally:
        context.close()
