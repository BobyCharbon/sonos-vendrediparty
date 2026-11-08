"""Accueil Événements, maquette A (08.11) : sans barre « Activité | Mon profil », cloche à bulle rouge, pastilles compactes.

Vrai navigateur, module construit (web/events/dist), Supabase simulé : chaque bouton de l'en-tête est touché.
"""
import json
from urllib.parse import parse_qs, urlparse

from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

POLL = '5c1f0b56-6b8e-4a59-9a43-6d0f4b6a2e11'
DRAFT = '7a2d4c10-1111-4c5e-9d1e-2b3c4d5e6f70'
PENDING = '7a2d4c10-2222-4c5e-9d1e-2b3c4d5e6f71'
NOTIFS = [
    {'id': 'n1', 'kind': 'poll_new', 'title': 'Nouveau sondage', 'body': 'Raclette de novembre : choisis tes dates', 'event_id': POLL,
     'created_at': '2026-11-08T10:00:00Z', 'read_at': None},
    {'id': 'n2', 'kind': 'private_invite', 'title': 'Léa t’invite', 'body': 'Soirée jeux', 'event_id': EVENT,
     'created_at': '2026-11-08T09:00:00Z', 'read_at': None},
    {'id': 'n3', 'kind': 'link_join', 'title': 'Marc a répondu par ton lien', 'body': 'Soirée jeux', 'event_id': None,
     'created_at': '2026-11-07T09:00:00Z', 'read_at': None},
    {'id': 'n4', 'kind': 'date_fixed', 'title': 'Date fixée', 'body': 'Karaoké', 'event_id': None,
     'created_at': '2026-11-06T09:00:00Z', 'read_at': '2026-11-06T10:00:00Z'},
]
IMPORTANT = {'announce_accepted', 'announce_refused', 'group_event_accepted', 'group_event_refused', 'private_invite', 'new_event', 'group_invite', 'poll_new', 'poll_nudge', 'date_fixed', 'event_changed', 'waitlist',
             'coorganizer_added', 'approved', 'rejected', 'group_event_request', 'announce_request', 'ticket_issued',
             'ticket_pay_confirmed', 'ticket_pay_declared', 'moderation_notice'}
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Expose-Headers': 'Content-Range',
        'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS, HEAD'}


def base_event(**over):
    category = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
    e = {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'description': 'Données fictives.', 'created_by': USER,
         'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
         'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu de démonstration',
         'category_id': category['id'], 'category': category, 'event_tags': [], 'date_options': [], 'rsvps': [],
         'event_organizers': [], 'polls': [], 'bring_items': [], 'author': {'display_name': 'Compte de démonstration'},
         'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None,
         'rsvp_deadline': None, 'poll_deadline': None, 'forum_enabled': True, 'all_day': False, 'price_chf': None, 'visibility': 'all'}
    return {**e, **over}


def setup(page):
    """Faux Supabase de base + notifications (compte exact, lecture, « lu ») + un sondage, un brouillon, une proposition."""
    mock_services(page)
    notifs = [dict(n) for n in NOTIFS]
    events = [
        base_event(),
        base_event(id=POLL, title='Raclette de novembre', date_mode='poll', starts_at=None,
                   date_options=[{'id': 'o1', 'starts_at': '2030-11-20T18:00:00Z', 'date_votes': []},
                                 {'id': 'o2', 'starts_at': '2030-11-21T18:00:00Z', 'date_votes': []}]),
        base_event(id=DRAFT, title='Mon brouillon de pique-nique', status='draft'),
        base_event(id=PENDING, title='Ma proposition de bowling', status='pending'),
    ]

    def notifications(route):
        req = route.request
        if req.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        q = parse_qs(urlparse(req.url).query)
        if req.method == 'PATCH':
            one = q.get('id', [''])[0].removeprefix('eq.')
            for n in notifs:
                if n['id'] == one or (not one and n['read_at'] is None):
                    n['read_at'] = '2026-11-08T12:00:00Z'
            return route.fulfill(status=204, headers=CORS)
        rows = [n for n in notifs if n['kind'] != 'admin_announcement']
        if 'read_at' in q:
            rows = [n for n in rows if n['read_at'] is None]
        if q.get('kind', [''])[0].startswith('in.'):
            rows = [n for n in rows if n['kind'] in IMPORTANT]
        if req.method == 'HEAD':
            return route.fulfill(status=200, headers={**CORS, 'Content-Range': f'*/{len(rows)}'})
        route.fulfill(status=200, content_type='application/json', body=json.dumps(rows),
                      headers={**CORS, 'Content-Range': f'0-{max(len(rows) - 1, 0)}/{len(rows)}'})

    def event_list(route):
        req = route.request
        if req.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        q = parse_qs(urlparse(req.url).query)
        body = events
        if 'id' in q:
            wanted = q['id'][0].removeprefix('eq.')
            body = next((e for e in events if e['id'] == wanted), events[0])
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=CORS)

    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/notifications**', notifications)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/events?**', event_list)
    return notifs


def open_home(browser, origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    notifs = setup(page)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    pw.expect(frame.get_by_role('heading', name='Événements', exact=True)).to_be_visible(timeout=15000)
    return context, page, frame, notifs, errors


def module_path(page):
    return page.evaluate("document.getElementById('eventsFrame').contentWindow.location.pathname")


def test_home_has_no_profile_or_activity_tabs_and_is_compact(browser, events_origin):
    context, page, frame, _, errors = open_home(browser, events_origin)
    try:
        # Plus de barre « Événements | Activité | Mon profil », ni de « Salut … » ni d'onglet « En attente ».
        for gone in ('Mon profil', 'Activité'):
            pw.expect(frame.get_by_role('link', name=gone, exact=True)).to_have_count(0)
        pw.expect(frame.get_by_text('Salut', exact=False)).to_have_count(0)
        pw.expect(frame.get_by_role('tab', name='En attente', exact=True)).to_have_count(0)
        # Titre, loupe et cloche sur UNE ligne, pastilles juste en dessous.
        title = frame.get_by_role('heading', name='Événements', exact=True).bounding_box()
        bell = frame.get_by_test_id('home-bell').bounding_box()
        search = frame.get_by_test_id('home-search').bounding_box()
        assert abs((title['y'] + title['height'] / 2) - (bell['y'] + bell['height'] / 2)) < 12
        assert abs(bell['y'] - search['y']) < 2 and bell['width'] >= 44 and bell['height'] >= 44
        pills = [frame.get_by_test_id(f'pill-{k}').bounding_box() for k in ('upcoming', 'polls', 'drafts', 'past', 'filters')]
        assert all(p['height'] >= 40 for p in pills)
        assert len({round(p['y']) for p in pills}) == 1, 'les pastilles tiennent sur une ligne'
        assert pills[0]['y'] - (bell['y'] + bell['height']) < 24
        # Recherche fermée par défaut (gain de place).
        pw.expect(frame.get_by_label('Rechercher un événement', exact=True)).to_have_count(0)
        assert page.frame(url=events_origin + '/events/').evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path='/tmp/claude-501/accueil-a.png')
        assert not errors, errors
    finally:
        context.close()


def test_bell_badge_counts_only_important_unread_and_opens_activity(browser, events_origin):
    context, page, frame, notifs, errors = open_home(browser, events_origin)
    try:
        # 2 importantes non lues (sondage + invitation) ; « Marc a répondu par ton lien » ne compte pas.
        pw.expect(frame.get_by_test_id('home-bell-badge')).to_have_text('2', timeout=10000)
        pw.expect(frame.get_by_role('button', name='Activité, 2 nouveautés importantes', exact=True)).to_be_visible()
        frame.get_by_test_id('home-bell').click()
        pw.expect(frame.get_by_role('heading', name='Activité', exact=True)).to_be_visible()
        # Ouvert sur « Importantes » : le lien de Marc n'y est pas, il est dans « Tout ».
        pw.expect(frame.get_by_role('button', name='✓ Importantes · 2', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('Nouveau sondage', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('Marc a répondu par ton lien', exact=True)).to_have_count(0)
        frame.get_by_role('button', name='Tout', exact=True).click()
        pw.expect(frame.get_by_text('Marc a répondu par ton lien', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('DÉJÀ LU', exact=True)).to_be_visible()
        page.screenshot(path='/tmp/claude-501/accueil-activite.png')
        # ✕ ferme et ramène à l'accueil.
        frame.get_by_role('button', name="Fermer l'activité", exact=True).click()
        pw.expect(frame.get_by_role('heading', name='Événements', exact=True)).to_be_visible()
        # « Tout marquer lu » : la bulle disparaît au retour.
        frame.get_by_test_id('home-bell').click()
        frame.get_by_role('button', name='Tout marquer lu', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Tout marquer lu', exact=True)).to_have_count(0)
        assert all(n['read_at'] for n in notifs)
        frame.get_by_role('button', name="Fermer l'activité", exact=True).click()
        pw.expect(frame.get_by_test_id('home-bell-badge')).to_have_count(0, timeout=10000)
        pw.expect(frame.get_by_role('button', name='Activité', exact=True)).to_be_visible()
        assert not errors, errors
    finally:
        context.close()


def test_activity_opened_from_a_notification_closes_to_home(browser, events_origin):
    """Lien d'une notification (/events/activity, sans historique) : ✕ ramène quand même à l'accueil."""
    context, page, frame, _, errors = open_home(browser, events_origin)
    try:
        page.evaluate("PartyEvents.open('/events/activity')")
        pw.expect(frame.get_by_role('heading', name='Activité', exact=True)).to_be_visible(timeout=15000)
        frame.get_by_role('button', name="Fermer l'activité", exact=True).click()
        pw.expect(frame.get_by_role('heading', name='Événements', exact=True)).to_be_visible()
        assert module_path(page).rstrip('/') == '/events'
        assert not errors, errors
    finally:
        context.close()


def test_new_poll_is_obvious_and_every_pill_works(browser, events_origin):
    context, page, frame, _, errors = open_home(browser, events_origin)
    try:
        # Sondage sans mon vote : bandeau rose en tête de liste + compte rouge sur « Sondages ».
        banner = frame.get_by_test_id('poll-banner')
        pw.expect(banner).to_contain_text('Nouveau sondage : Raclette de novembre')
        pw.expect(banner).to_contain_text('Voter')
        pw.expect(frame.get_by_role('tab', name='Sondages, 1 en attente de ton vote', exact=True)).to_be_visible()
        first_card = frame.get_by_text('Sortie de démonstration (test local)', exact=True).bounding_box()
        assert banner.bounding_box()['y'] < first_card['y'], 'le bandeau passe avant les événements'
        # Toucher le bandeau ouvre le sondage.
        banner.click()
        page.wait_for_function(f"() => document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/event/{POLL}')")
        page.evaluate("document.getElementById('eventsFrame').contentWindow.history.back()")
        pw.expect(frame.get_by_role('heading', name='Événements', exact=True)).to_be_visible()

        frame.get_by_test_id('pill-polls').click()
        pw.expect(frame.get_by_test_id('pill-polls')).to_have_attribute('aria-selected', 'true')
        pw.expect(frame.get_by_text('Raclette de novembre', exact=True)).to_be_visible()
        pw.expect(frame.get_by_test_id('poll-banner')).to_have_count(0)
        # Brouillons : mes brouillons ET mes propositions en attente (plus d'onglet « En attente »).
        frame.get_by_test_id('pill-drafts').click()
        pw.expect(frame.get_by_text('Mon brouillon de pique-nique', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('Ma proposition de bowling', exact=True)).to_be_visible()
        frame.get_by_test_id('pill-past').click()
        pw.expect(frame.get_by_text('Les événements passés apparaîtront ici.', exact=True)).to_be_visible()
        frame.get_by_test_id('pill-upcoming').click()
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible()

        # Filtres : s'ouvrent, filtrent, le nom du filtre s'affiche sur la pastille ; un second toucher l'enlève.
        pw.expect(frame.get_by_role('button', name='Mes abonnements', exact=True)).to_have_count(0)
        frame.get_by_test_id('pill-filters').click()
        frame.get_by_role('button', name='Soirée', exact=True).click()
        pw.expect(frame.get_by_test_id('pill-filters')).to_contain_text('Filtre : Soirée')
        frame.get_by_role('button', name='✓ Soirée', exact=True).click()
        pw.expect(frame.get_by_test_id('pill-filters')).to_have_text('Filtres')
        # « Mes abonnements » se retire aussi d'un second toucher (essai réel du 08.11).
        frame.get_by_role('button', name='Mes abonnements', exact=True).click()
        pw.expect(frame.get_by_test_id('pill-filters')).to_contain_text('Filtre : Mes abonnements')
        frame.get_by_role('button', name='✓ Mes abonnements', exact=True).click()
        pw.expect(frame.get_by_test_id('pill-filters')).to_have_text('Filtres')
        frame.get_by_test_id('pill-filters').click()
        pw.expect(frame.get_by_role('button', name='Mes abonnements', exact=True)).to_have_count(0)

        # Loupe : ouvre le champ, filtre ; refermer efface la recherche.
        frame.get_by_test_id('home-search').click()
        field = frame.get_by_label('Rechercher un événement', exact=True)
        pw.expect(field).to_be_focused()
        field.fill('aucun-resultat-xyz')
        pw.expect(frame.get_by_text('Aucun événement ne correspond à ta recherche.', exact=True)).to_be_visible()
        frame.get_by_role('button', name='Fermer la recherche', exact=True).click()
        pw.expect(field).to_have_count(0)
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible()

        # « + Proposer » ouvre le formulaire.
        frame.get_by_role('button', name='Proposer un événement', exact=True).click()
        page.wait_for_function("() => document.getElementById('eventsFrame').contentWindow.location.pathname.endsWith('/event/new')")
        assert not errors, errors
    finally:
        context.close()


def test_answers_to_the_organizer_requests_count_as_important():
    """Recette des bots du 08.11 : « Ton annonce a été acceptée / refusée » et la réponse pour un événement de groupe
    étaient cachées par le filtre « Importantes ». Toute réponse d'une demande (tell_requester) est importante."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    ts = (root / 'web/events/src/lib/activityBadge.ts').read_text()
    listed = set(re.findall(r"'([a-z_]+)'", ts.split('IMPORTANT_KINDS = [')[1].split('] as const')[0]))
    assert listed == IMPORTANT
    sql = '\n'.join(p.read_text() for p in (root / 'supabase/migrations').glob('*.sql'))
    answers = set(re.findall(r"tell_requester\([^;]*?'((?:announce|group_event)_[a-z]+)'", sql))
    assert {'announce_accepted', 'announce_refused', 'group_event_accepted', 'group_event_refused'} <= answers | IMPORTANT
    assert answers <= IMPORTANT
