"""Mise en page du module Événements sur petit écran (audit visuel du 05.11, configuration production) :
rien ne déborde à droite à 360 px (ni avec un texte agrandi, 260 px ≈ zoom 150 %), aucun onglet coupé (« À ve… »),
la pastille « qui vient » reste à l'écran au-dessus d'un très long titre, un très long prénom ne sort pas de sa carte,
les boutons de l'entrée laissent la place au nom. Supabase simulé : 200 participants, noms accentués et emoji."""
import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_events_browser import USER, browser, events_origin, pw, pytestmark  # noqa: F401 (fixtures)

EVENT = '32f18a3b-827f-4123-8cf4-33de06c9a5aa'
LONG_NAME = 'Marie-Thérèse-Bernadette de la Tour-Montagne-Saint-Hilaire 🌟'
LONG_TITLE = ('Grande soirée d’anniversaire surprise de François-Xavier au bord du lac Léman avec karaoké, '
              'barbecue géant et feu d’artifice 🎆🎂🥳')
PEOPLE = [{'id': f'00000000-0000-4000-8000-{i:012d}', 'display_name': LONG_NAME if i == 3 else ['Zoé 🎉', 'Anaïs Gonçalves', 'Noé'][i % 3]}
          for i in range(1, 201)]
CATEGORY = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Sport & plein air', 'color': '#5BE3A6', 'sort': 0, 'archived': False, 'icon': None}
PROFILE = {'id': USER, 'display_name': 'Camille', 'phone': '41791234567', 'role': 'admin', 'status': 'active', 'avatar_url': f'{USER}/p.jpg',
           'first_name': 'Camille', 'last_name': 'Démo', 'created_at': '2026-10-19T08:00:00Z'}
PERMS = ['events.view', 'events.rsvp', 'events.create', 'events.publish_direct', 'events.edit_own_published', 'events.manage_all',
         'events.approve', 'events.see_participants', 'polls.create', 'chat.write']


def rsvp(user, waitlisted=False):
    return {'event_id': EVENT, 'user_id': user, 'status': 'yes', 'plus_ones': 1 if user == USER else 0, 'note': None, 'waitlisted': waitlisted, 'set_by': None}


EVENT_ROW = {
    'id': EVENT, 'title': LONG_TITLE, 'description': 'Infos : https://www.exemple-de-lien-tres-long.ch/evenements/2030/anniversaire-surprise/inscription?source=party',
    'cover_url': None, 'category_id': CATEGORY['id'], 'category': CATEGORY, 'created_by': USER, 'status': 'published', 'rejection_reason': None,
    'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'all_day': False, 'poll_deadline': None,
    'members_can_propose_dates': False, 'auto_fix_date': False, 'location_name': 'Plage de Vidy, buvette du bord du lac, Lausanne (Vaud)',
    'location_address': None, 'location_url': None, 'price_chf': 42.5, 'payment_info': None, 'max_participants': 150, 'waitlist_enabled': True,
    'allow_plus_ones': True, 'max_plus_ones': 2, 'allow_maybe': True, 'rsvp_deadline': None, 'visibility': 'all', 'public_link': True,
    'show_participants': True, 'pot_enabled': False, 'tickets_enabled': True, 'forum_enabled': True, 'notify_on_publish': True, 'reminders': [],
    'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'author': {'id': USER, 'display_name': 'Camille'},
    'event_tags': [], 'event_organizers': [], 'date_options': [], 'event_groups': [], 'event_invites': [], 'event_phone_invites': [],
    'polls': [{'id': 'p1', 'event_id': EVENT, 'question': 'Quel fromage ?', 'multiple_choice': False, 'anonymous': False,
               'members_can_add_options': True, 'results_after_vote': False, 'closes_at': None, 'created_by': USER, 'sort': 0,
               'poll_options': [{'id': 'o1', 'poll_id': 'p1', 'label': 'Fromage du Valais AOP au lait cru, bien coulant', 'sort': 0},
                                {'id': 'o2', 'poll_id': 'p1', 'label': 'Fribourgeois', 'sort': 1}]}],
    'bring_items': [], 'rsvps': [rsvp(USER)] + [rsvp(p['id'], waitlisted=i >= 150) for i, p in enumerate(PEOPLE)],
}
CHECKINS = [{'user_id': p['id'], 'display_name': p['display_name'], 'avatar_url': None, 'status': 'yes', 'waitlisted': False, 'plus_ones': 1,
             'checked_in_at': None, 'paid': False, 'pay_pending': False, 'price_chf': 42.5, 'issued': False, 'issued_by_payment': False,
             'tickets_enabled': True} for p in PEOPLE[:12]]


def session_script():
    enc = lambda v: base64.urlsafe_b64encode(json.dumps(v).encode()).decode().rstrip('=')
    token = '.'.join([enc({'alg': 'HS256', 'typ': 'JWT'}), enc({'sub': USER, 'aud': 'authenticated', 'role': 'authenticated', 'exp': int(time.time()) + 3600}), 'sig'])
    session = {'access_token': token, 'refresh_token': 'r', 'expires_in': 3600, 'expires_at': int(time.time()) + 3600, 'token_type': 'bearer',
               'user': {'id': USER, 'aud': 'authenticated', 'phone': PROFILE['phone'], 'app_metadata': {}, 'user_metadata': {}, 'created_at': PROFILE['created_at']}}
    return f"localStorage.setItem('sb-gsuetixzobooggeaubvb-auth-token', {json.dumps(json.dumps(session))});"


def backend(page):
    headers = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
    rpcs = {'get_member_directory': PROFILE, 'my_permissions': PERMS, 'my_rank': 99, 'event_group_names': [], 'event_checkins': CHECKINS,
            'my_event_ticket': {'state': 'pending', 'plus_ones': 1, 'paid': False, 'pay_pending': False, 'price_chf': 42.5},
            'event_attendance': [{'event_id': EVENT, 'going': 151, 'maybe': 0, 'waitlist': 50,
                                  'faces': [{'id': p['id'], 'name': p['display_name'], 'avatar_url': None} for p in PEOPLE[:3]]}]}

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=headers)
        url = urlparse(request.url)
        name = url.path.rsplit('/', 1)[1]
        single = 'vnd.pgrst.object' in (request.headers.get('accept') or '')
        if '/rpc/' in url.path:
            body = rpcs.get(name)
        elif request.method != 'GET':
            body = None
        elif name == 'events':
            body = EVENT_ROW if single else [EVENT_ROW]
        elif name == 'profiles':
            body = [{'id': USER, 'display_name': 'Camille'}, *PEOPLE]
        elif name == 'categories':
            body = [CATEGORY]
        elif name == 'group_settings':
            body = {'require_approval': False} if single else [{'require_approval': False}]
        else:
            body = {} if single else []
        if '/storage/' in url.path:
            body = {'signedURL': '/x'}
        route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=headers)

    page.route('https://gsuetixzobooggeaubvb.supabase.co/**', handle)
    page.route_web_socket('wss://gsuetixzobooggeaubvb.supabase.co/**', lambda ws: ws.on_message(lambda _m: None))
    page.route('https://fonts.googleapis.com/**', lambda route: route.fulfill(status=200, body=''))
    page.add_init_script(session_script())


# Éléments (feuilles avec du texte) qui sortent de l'écran, hors bandeaux défilant horizontalement (filtres) et textes
# coupés proprement par leur parent.
OVERFLOW = """() => {
  const scrolls = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const cs = getComputedStyle(p);
    if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true; } return false; };
  // Coupé (« … ») par un parent qui, lui, tient dans l'écran : rien ne dépasse à l'œil.
  const clipped = (el) => { for (let p = el.parentElement; p; p = p.parentElement) { const cs = getComputedStyle(p);
    if (cs.overflowX !== 'visible' && p.getBoundingClientRect().right <= innerWidth + 1) return true; } return false; };
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || el.children.length || !(el.innerText || '').trim()) continue;
    if ((r.right > innerWidth + 1 || r.left < -1) && !scrolls(el) && !clipped(el)) out.push(`${el.innerText.trim().slice(0, 40)} [${Math.round(r.left)}→${Math.round(r.right)}]`);
  }
  return out;
}"""


def open_module(browser, origin, path, width):
    context = browser.new_context(viewport={'width': width, 'height': 780}, is_mobile=True, has_touch=True, locale='fr-CH')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    backend(page)
    page.goto(f'{origin}/events/{path}', wait_until='domcontentloaded')
    return context, page, errors


@pytest.mark.parametrize('width', [360, 260])
def test_list_tabs_are_never_cut_and_nothing_leaves_the_screen(browser, events_origin, width):
    context, page, errors = open_module(browser, events_origin, '', width)
    try:
        pw.expect(page.get_by_role('tab', name='Passés', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text(LONG_TITLE, exact=True)).to_be_visible()
        for label in ('À venir', 'Sondages', 'Brouillons', 'Passés'):
            text = page.get_by_role('tab', name=label, exact=True).locator('div[dir="auto"]').first
            assert text.evaluate('e => e.scrollWidth <= e.clientWidth + 1'), f'onglet coupé à {width} px : {label}'
        assert page.evaluate(OVERFLOW) == []
        # La pastille « qui vient » ne vole plus la largeur du titre : il a toute la largeur de la carte.
        title = page.get_by_text(LONG_TITLE, exact=True).bounding_box()
        card = page.get_by_role('link', name=LONG_TITLE, exact=False).first.bounding_box()
        assert title['x'] + title['width'] > card['x'] + card['width'] * 0.8
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize('width', [360, 260])
def test_event_page_with_long_title_200_people_and_long_names_stays_on_screen(browser, events_origin, width):
    context, page, errors = open_module(browser, events_origin, f'event/{EVENT}', width)
    try:
        pw.expect(page.get_by_text(LONG_TITLE, exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Qui vient ?', exact=True)).to_be_attached()
        badge = page.get_by_role('button', name='151 présents', exact=False).first.bounding_box()
        assert badge['x'] >= 0 and badge['x'] + badge['width'] <= width, badge
        assert page.evaluate(OVERFLOW) == []
        assert '42.50 CHF / personne' in page.inner_text('body')
        # Option de sondage longue : sur plusieurs lignes, jamais « … ».
        option = page.get_by_text('Fromage du Valais AOP au lait cru, bien coulant', exact=True)
        assert option.evaluate('e => e.scrollHeight <= e.clientHeight + 1 && e.scrollWidth <= e.clientWidth + 1')
        assert not errors
    finally:
        context.close()


def test_entry_rows_keep_room_for_the_name(browser, events_origin):
    context, page, errors = open_module(browser, events_origin, f'event/{EVENT}/scan', 360)
    try:
        pw.expect(page.get_by_text('Arrivées', exact=True)).to_be_visible(timeout=15000)
        name = page.get_by_text('Anaïs Gonçalves', exact=True).first
        pw.expect(name).to_be_visible()
        assert name.evaluate('e => e.scrollWidth <= e.clientWidth + 1'), 'nom coupé par les boutons'
        # La colonne du nom garde la largeur de la carte (avant : « Z… », « Atte ndu· e » sur 40 px).
        status = page.get_by_text('Attendu·e', exact=False).first
        assert status.bounding_box()['width'] > 200
        assert page.evaluate(OVERFLOW) == []
        assert not errors
    finally:
        context.close()


def test_avatar_initials_never_show_half_an_emoji(browser, events_origin):
    context, page, errors = open_module(browser, events_origin, f'event/{EVENT}', 390)
    try:
        pw.expect(page.get_by_text('Qui vient ?', exact=True)).to_be_attached(timeout=15000)
        assert '�' not in page.inner_text('body')
        assert not errors
    finally:
        context.close()


def test_forum_message_field_grows_instead_of_cutting_the_first_line(browser, events_origin):
    """Retour de l'agent participant : à hauteur fixe, la 2e ligne saisie rognait le haut du texte."""
    context, page, errors = open_module(browser, events_origin, f'event/{EVENT}/chat', 390)
    try:
        field = page.get_by_label('Message', exact=True)
        pw.expect(field).to_be_visible(timeout=15000)
        field.fill('Salut tout le monde, je viens avec ma sœur et deux amis, on amène les jeux et le dessert, à samedi !')
        page.wait_for_timeout(300)
        assert field.evaluate('e => e.scrollHeight <= e.clientHeight + 1 && e.scrollTop === 0'), 'texte rogné'
        assert field.evaluate('e => e.getBoundingClientRect().height') > 60
        assert not errors
    finally:
        context.close()
