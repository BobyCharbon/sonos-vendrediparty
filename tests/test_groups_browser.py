"""Groupes : nouveau graphisme (17.11.2026, maquette A « Néon & couvertures » + bulles et QR de B), dans un vrai
navigateur, Supabase simulé :
- liste façon WhatsApp (tuile emoji sur la couleur du groupe, dernier message, non lus, prochain événement), grande carte
  « Crée le groupe de ta bande », « Membres Vendredi Party » ; état vide qui donne envie ;
- création en 2 étapes : nom + emoji + couleur (CGU d'abord), puis Inviter (lien WhatsApp / Copier / Autre, code QR,
  recherche « numéro exact ou nom », jamais de liste de personnes) ou « Plus tard » → la page du groupe s'ouvre ;
- réglages (22.11) : « Tous les membres peuvent inviter », « Événements à valider » ;
- page du groupe : couverture, membres, « Créer un événement pour le groupe » (ce groupe coché, « Prévenir » éteint),
  Inviter, Discussion, prochains événements ; réglages : quitter soi-même (jamais Vendredi Party) ;
- onglet Événements : bulles « Tes groupes » (« Crée ton groupe » en premier) et étiquette du groupe sur les cartes.
Captures : PARTY_SHOTS=<dossier> (sinon le dossier temporaire)."""
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

SHOTS = Path(os.environ.get('PARTY_SHOTS') or tempfile.gettempdir())
SUPABASE = 'https://gsuetixzobooggeaubvb.supabase.co/**'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile'}

VIP, FOOT, DISCO, FAMILLE = (f'5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a0{i}' for i in range(1, 5))
NEW = '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a99'
CHLOE, MALIK, INES, KOFI, TOM = (f'7a1c2b3d-0000-4000-8000-00000000000{i}' for i in range(1, 6))
TOKEN = '0a0b0c0d-0000-4000-8000-00000000abcd'


def face(uid, name):
    return {'id': uid, 'name': name, 'avatar_url': None}


def overview(gid, name, emoji, color, **kw):
    return {'id': gid, 'name': name, 'emoji': emoji, 'color': color, 'system': False, 'creator': False, 'manage': False,
            'member': True, 'created_by_name': 'Tom', 'members': 4, 'faces': [face(CHLOE, 'Chloé'), face(MALIK, 'Malik')],
            'last': None, 'last_by': None, 'last_at': None, 'unread': 0, 'next_event': None, **kw}


GROUPS = [
    overview(VIP, 'Vendredi Party', '🎉', 'lavender', system=True, members=128, created_by_name=None,
             last='La saison d’hiver est lancée !', last_by='Sofia', last_at='2026-11-16T19:00:00Z'),
    overview(FOOT, 'Les potes du foot', '⚽', 'mint', creator=True, manage=True, members=14, unread=3,
             last='Qui ramène le ballon samedi ?', last_by='Yanis', last_at='2026-11-17T08:14:00Z',
             next_event={'id': EVENT, 'title': 'Match + apéro', 'starts_at': '2030-11-23T09:00:00Z', 'date_mode': 'fixed'}),
    overview(DISCO, 'Soirées du vendredi', '🪩', 'pink', last='J’ai fait la playlist 🎧', last_by='Chloé',
             last_at='2026-11-16T17:02:00Z',
             next_event={'id': EVENT, 'title': 'Vendredi Disco', 'starts_at': '2030-11-22T20:00:00Z', 'date_mode': 'fixed'}),
    overview(FAMILLE, 'La famille', '🏡', 'coral', last='Bisous à tous ❤️', last_by='Maman', last_at='2026-11-10T10:00:00Z'),
]
PEOPLE = [{'id': USER, 'display_name': 'Compte de démonstration', 'avatar_url': None},
          {'id': CHLOE, 'display_name': 'Chloé', 'avatar_url': None}, {'id': MALIK, 'display_name': 'Malik', 'avatar_url': None},
          {'id': INES, 'display_name': 'Inès', 'avatar_url': None}, {'id': TOM, 'display_name': 'Tom', 'avatar_url': None}]
SUGGESTIONS = [
    {'id': CHLOE, 'display_name': 'Chloé', 'avatar_url': None, 'together': 4, 'last_title': 'Vendredi Disco', 'invited': False},
    {'id': MALIK, 'display_name': 'Malik', 'avatar_url': None, 'together': 1, 'last_title': 'Les potes du foot', 'invited': False},
    {'id': INES, 'display_name': 'Inès', 'avatar_url': None, 'together': 1, 'last_title': 'Vendredi Disco', 'invited': False},
    {'id': KOFI, 'display_name': 'Kofi', 'avatar_url': None, 'together': 2, 'last_title': 'Brunch', 'invited': True},
]

# group_people_search (22.11) : surnom, photo, initiale du nom ; jamais le numéro.
FOUND = [
    {'id': CHLOE, 'display_name': 'Chloé', 'avatar_url': None, 'initial': 'D', 'invited': False},
    {'id': MALIK, 'display_name': 'Malik', 'avatar_url': None, 'initial': 'B', 'invited': False},
    {'id': KOFI, 'display_name': 'Kofi', 'avatar_url': None, 'initial': 'A', 'invited': True},
]

category = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
MATCH = {'id': EVENT, 'title': 'Match + apéro', 'description': None, 'created_by': TOM, 'status': 'published', 'date_mode': 'fixed',
         'starts_at': '2030-11-23T09:00:00Z', 'ends_at': None, 'created_at': '2026-11-01T08:00:00Z', 'updated_at': '2026-11-01T08:00:00Z',
         'location_name': 'Terrain synthétique', 'category_id': category['id'], 'category': category, 'event_tags': [],
         'date_options': [], 'rsvps': [], 'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': False, 'max_plus_ones': 0,
         'max_participants': None, 'rsvp_deadline': None, 'visibility': 'invited', 'event_groups': [{'group_id': FOOT}]}



def group_row(gid, created_by=USER, members=(USER, CHLOE, MALIK, INES)):
    g = next(x for x in GROUPS if x['id'] == gid)
    return {'id': gid, 'name': g['name'], 'emoji': g['emoji'], 'color': g['color'], 'created_by': None if g['system'] else created_by,
            'created_at': '2026-11-01T10:00:00Z', 'system_key': 'vip' if g['system'] else None, 'events_need_approval': False,
            'announce_mode': 'request', 'members_invite': True, 'member_group_members': [{'user_id': u, 'added_at': None} for u in members]}


def group_services(page, groups=GROUPS, row_for=group_row, rank=None):
    """Base simulée des groupes, posée par-dessus mock_services (les routes posées après passent d'abord)."""
    calls = mock_services(page)
    state = {'inserted': [], 'invites': [], 'deleted': [], 'groups': groups, 'searches': [], 'rules': []}

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        url = urlparse(request.url)
        path, query = url.path, parse_qs(url.query)
        single = 'vnd.pgrst.object' in (request.headers.get('accept') or '')
        body = json.loads(request.post_data) if request.post_data else None
        if path.endswith('/rpc/my_rank') and rank is not None:
            result = rank  # Membre (rang 2) : pas Admin du site
        elif path.endswith('/rpc/my_groups_overview'):
            result = state['groups']
        elif path.endswith('/rpc/my_group_invitations') or path.endswith('/rpc/my_privacy'):
            result = [] if 'invitations' in path else {'phone_groups': []}
        elif path.endswith('/rpc/my_terms'):
            result = {'version': '2026-11-16', 'accepted': True, 'accepted_at': None, 'contact_email': None, 'enforced': True}
        elif path.endswith('/rpc/group_invite_link'):
            result = TOKEN
        elif path.endswith('/rpc/group_invite_suggestions'):
            result = SUGGESTIONS
        elif path.endswith('/rpc/group_people_search'):
            state['searches'].append(body['q'])
            q = body['q'].lower()
            result = [] if q.startswith('+') else [p for p in FOUND if q in p['display_name'].lower()]
        elif path.endswith('/rpc/set_group_members_invite') or path.endswith('/rpc/set_group_event_rules'):
            state['rules'].append((path.rsplit('/', 1)[1], body))
            result = None
        elif path.endswith('/rpc/invite_to_group'):
            state['invites'].append(body)
            result = {'invited': 'member'}
        elif path.endswith('/rpc/group_events'):
            result = [{'id': EVENT, 'upcoming': True, 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z'}]
        elif path.endswith('/member_groups') and request.method == 'POST':
            state['inserted'].append(body)
            result = {'id': NEW} if single else [{'id': NEW}]
        elif path.endswith('/member_groups') and request.method == 'PATCH':
            state.setdefault('updated', []).append(body)
            result = None
        elif path.endswith('/member_groups'):
            wanted = (query.get('id') or [''])[0].removeprefix('eq.')
            if wanted == NEW:
                ins = state['inserted'][-1]
                row = {'id': NEW, 'name': ins['name'], 'emoji': ins['emoji'], 'color': ins['color'], 'created_by': USER,
                       'created_at': '2026-11-17T10:00:00Z', 'system_key': None, 'events_need_approval': False,
                       'announce_mode': 'request', 'member_group_members': [{'user_id': USER, 'added_at': None}]}
            else:
                row = row_for(wanted) if wanted else None
            result = row if single else ([row] if row else [{'id': g['id'], 'name': g['name'], 'created_by': USER,
                       'system_key': 'vip' if g['system'] else None, 'member_group_members': [{'user_id': USER}]} for g in state['groups']])
        elif path.endswith('/member_group_members') and request.method == 'DELETE':
            state['deleted'].append(dict(query))
            result = {'user_id': USER} if single else []
        elif path.endswith('/member_group_members'):
            result = None if single else []
        elif path.endswith('/events') and (query.get('id') or [''])[0].startswith('in.'):
            result = [MATCH]
        elif path.endswith('/profiles') and 'in.' in (query.get('id') or [''])[0]:
            result = PEOPLE
        else:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route(SUPABASE, handle)
    state['calls'] = calls
    return state


def signed_in(page, events_origin, path='/'):
    """Module Événements ouvert seul (comme l'app iPhone le charge), connecté, puis à la page voulue."""
    page.goto(events_origin + '/events/', wait_until='domcontentloaded')
    login(page)
    page.wait_for_timeout(500)
    if path != '/':
        page.goto(f'{events_origin}/events{path}', wait_until='domcontentloaded')


@pytest.fixture
def phone(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    yield page, errors
    context.close()


def shot(page, name):
    page.wait_for_timeout(700)  # animations d'entrée finies
    page.screenshot(path=str(SHOTS / name))


def test_the_list_reads_like_whatsapp_with_a_big_create_card(phone, events_origin):
    page, errors = phone
    group_services(page)
    signed_in(page, events_origin, '/groups')
    pw.expect(page.get_by_role('heading', name='Groupes')).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('Crée le groupe de ta bande', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('TES GROUPES · 4', exact=True)).to_be_visible()
    # Vendredi Party en premier, sous son nom de communauté ; dernier message, non lus, prochain événement.
    rows = page.get_by_test_id(f'group-row-{VIP}')
    pw.expect(rows.get_by_text('Membres Vendredi Party', exact=True)).to_be_visible()
    pw.expect(rows.get_by_text('🔒 Toute la communauté · 128')).to_be_visible()
    foot = page.get_by_role('link', name='Les potes du foot, 3 non lus')
    pw.expect(foot.get_by_text('Qui ramène le ballon samedi ?', exact=False)).to_be_visible()
    pw.expect(foot.get_by_text('📅 Sam. 23 nov. · Match + apéro', exact=False)).to_be_visible()
    pw.expect(page.get_by_test_id(f'group-row-{FAMILLE}').get_by_text('Aucun événement prévu')).to_be_visible()
    shot(page, 'groupes-liste.png')
    foot.click()
    pw.expect(page.get_by_test_id('group-page')).to_be_visible()
    assert page.url.endswith(f'/events/group/{FOOT}')
    assert not errors, errors


def test_no_group_yet_shows_an_inviting_empty_state(phone, events_origin):
    page, errors = phone
    group_services(page, groups=[GROUPS[0]])  # seulement Vendredi Party
    signed_in(page, events_origin, '/groups')
    pw.expect(page.get_by_text('Ta bande mérite son groupe', exact=True)).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('Invite tout le monde d’un toucher', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('Crée le groupe de ta bande', exact=True)).to_have_count(0)
    pw.expect(page.get_by_text('Membres Vendredi Party', exact=True)).to_be_visible()  # « Ta communauté »
    shot(page, 'groupes-vide.png')
    # Une idée de nom pré-remplit la création.
    page.get_by_role('button', name='Créer « Pizza du jeudi »').click()
    pw.expect(page.get_by_label('Nom du groupe')).to_have_value('Pizza du jeudi')
    pw.expect(page.get_by_role('radio', name='Emoji 🍕')).to_have_attribute('aria-checked', 'true')
    assert not errors, errors


def test_creating_a_group_in_two_steps_then_inviting_people_found_by_the_search(phone, events_origin):
    page, errors = phone
    state = group_services(page)
    signed_in(page, events_origin, '/group/new')
    pw.expect(page.get_by_label('Nom du groupe')).to_be_visible(timeout=15000)
    page.get_by_label('Nom du groupe').fill('Soirées du vendredi')
    page.get_by_role('radio', name='Emoji 🪩').click()
    page.get_by_role('radio', name='Couleur Rose').click()
    pw.expect(page.get_by_test_id('group-preview').get_by_text('Soirées du vendredi')).to_be_visible()
    pw.expect(page.get_by_text('19/60')).to_be_visible()
    shot(page, 'groupes-creer-etape1.png')
    page.get_by_role('button', name='Continuer').click()

    # Étape 2 : lien, QR, puis « numéro exact ou nom » : aucune liste de personnes avant de chercher.
    panel = page.get_by_test_id('group-invite-panel')
    pw.expect(panel.get_by_text('Invite ta bande', exact=True)).to_be_visible()
    assert state['inserted'] == [{'name': 'Soirées du vendredi', 'emoji': '🪩', 'color': 'pink', 'created_by': USER}]
    pw.expect(panel.get_by_text(f'/events/group-invite/{TOKEN}', exact=False)).to_be_visible()
    for name in ('WhatsApp', 'Copier', 'Autre'):
        pw.expect(panel.get_by_role('button', name=name, exact=True)).to_be_visible()
    pw.expect(panel.get_by_label('Code QR du lien du groupe')).to_be_visible()
    pw.expect(panel.get_by_text('Tape son numéro (079…', exact=False)).to_be_visible()
    pw.expect(panel.get_by_role('checkbox')).to_have_count(0)
    search = panel.get_by_label('Chercher une personne')
    search.fill('ch')  # 2 lettres : on ne cherche pas encore
    page.wait_for_timeout(700)
    assert state['searches'] == []
    search.fill('chl')
    pw.expect(panel.get_by_role('checkbox', name='Ajouter Chloé')).to_be_visible()
    pw.expect(panel.get_by_role('checkbox', name='Ajouter Chloé').get_by_text('D.', exact=False)).to_be_visible()  # initiale du nom
    panel.get_by_role('checkbox', name='Ajouter Chloé').click()
    search.fill('kof')
    pw.expect(panel.get_by_role('checkbox', name='Déjà invité : Kofi')).to_be_disabled()
    search.fill('mal')
    panel.get_by_role('checkbox', name='Ajouter Malik').click()
    pw.expect(panel.get_by_role('checkbox', name='Retirer Chloé')).to_be_visible()  # le choix reste quand la recherche change
    # Un numéro sans compte : l'invitation l'attend.
    search.fill('079 123 45 67')
    panel.get_by_role('button', name='Inviter le numéro 079 123 45 67').click()
    pw.expect(panel.get_by_role('button', name='Inviter Chloé, Malik et 079 123 45 67')).to_be_visible()
    shot(page, 'groupes-creer-etape2-inviter.png')
    panel.get_by_role('button', name='Inviter Chloé, Malik et 079 123 45 67').click()
    pw.expect(page.get_by_text('Invitation envoyée à Chloé, Malik et 079 123 45 67 ✓')).to_be_visible()
    assert [(i['member'], i['phone']) for i in state['invites']] == [(CHLOE, None), (MALIK, None), (None, '41791234567')]
    assert all(i['grp'] == NEW for i in state['invites'])
    assert 'chl' in state['searches'] and '+41791234567' in state['searches'] and 'ch' not in state['searches']

    # « Plus tard » : la page du groupe s'ouvre.
    page.get_by_role('button', name='Plus tard').click()
    pw.expect(page.get_by_test_id('group-page')).to_be_visible()
    assert page.url.endswith(f'/events/group/{NEW}')
    assert not errors, errors


def test_the_group_page_creates_an_event_with_the_group_checked_and_without_notifying(phone, events_origin):
    page, errors = phone
    group_services(page)
    signed_in(page, events_origin, f'/group/{FOOT}')
    pw.expect(page.get_by_role('heading', name='Les potes du foot')).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('4 membres · créé par toi')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Inviter', exact=True)).to_be_visible()
    pw.expect(page.get_by_role('button', name='Discussion, 3 non lus')).to_be_visible()
    pw.expect(page.get_by_text('Match + apéro', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('MEMBRES · 4')).to_be_visible()
    shot(page, 'groupes-page-du-groupe.png')
    page.get_by_role('button', name='Créer un événement pour le groupe').click()
    pw.expect(page.get_by_text('Prévenir le groupe', exact=False).first).to_be_visible(timeout=15000)
    assert f'group={FOOT}' in page.url
    # « Prévenir le groupe » éteint : on choisit soi-même plus tard.
    pw.expect(page.get_by_role('switch', name='Prévenir le groupe', exact=False).first).not_to_be_checked()
    chip = page.get_by_text('✓ Les potes du foot · 1', exact=True)  # le groupe déjà coché, « Sur invitation »
    chip.scroll_into_view_if_needed()
    pw.expect(chip).to_be_visible()
    pw.expect(page.get_by_text('✓ Sur invitation', exact=True)).to_be_visible()
    shot(page, 'groupes-creer-evenement.png')
    assert not errors, errors


def test_members_leave_from_the_settings_never_vendredi_party(phone, events_origin):
    page, errors = phone
    state = group_services(page, row_for=lambda gid: group_row(gid, created_by=TOM, members=(USER, TOM)), rank=2)
    signed_in(page, events_origin, f'/group/{DISCO}')
    pw.expect(page.get_by_role('heading', name='Soirées du vendredi')).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('button', name='Inviter', exact=True)).to_have_count(0)  # seul le créateur invite
    page.get_by_test_id('group-settings').click()
    pw.expect(page.get_by_text('Seul le créateur du groupe change son nom', exact=False)).to_be_visible()
    page.get_by_role('button', name='Quitter le groupe').click()
    page.get_by_role('button', name='Confirmer : quitter le groupe').click()
    page.wait_for_url('**/events/groups')
    assert state['deleted'] and state['deleted'][0]['group_id'] == [f'eq.{DISCO}'] and state['deleted'][0]['user_id'] == [f'eq.{USER}']

    page.goto(f'{events_origin}/events/group/{VIP}/settings', wait_until='domcontentloaded')
    pw.expect(page.get_by_text('Tous les Membres VIP et au-dessus', exact=False)).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('button', name='Quitter le groupe')).to_have_count(0)
    assert not errors, errors


def test_events_tab_shows_group_bubbles_and_the_group_tag_on_cards(phone, events_origin):
    page, errors = phone
    group_services(page)

    def events(route):  # la liste : un événement du groupe du foot (étiquette du groupe sur la carte)
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        if route.request.method != 'GET':
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps([MATCH]), headers=CORS)
    page.route('**/rest/v1/events?*', events)
    signed_in(page, events_origin)
    bubbles = page.get_by_test_id('group-bubbles')
    pw.expect(bubbles).to_be_visible(timeout=15000)
    labels = bubbles.get_by_role('link').all_inner_texts()
    assert labels[0].strip().endswith('Crée ton groupe'), labels
    pw.expect(bubbles.get_by_role('link', name='Groupe Les potes du foot, 3 non lus')).to_be_visible()
    pw.expect(page.get_by_label('Groupe Les potes du foot', exact=True)).to_be_visible()  # étiquette sur la carte
    shot(page, 'groupes-bulles-evenements.png')
    bubbles.get_by_role('link', name='Groupe Les potes du foot, 3 non lus').click()
    pw.expect(page.get_by_test_id('group-page')).to_be_visible()
    assert not errors, errors


def test_a_simple_member_invites_when_the_group_allows_it(phone, events_origin):
    page, errors = phone
    groups = [GROUPS[0], GROUPS[1], {**GROUPS[2], 'invite': True}, GROUPS[3]]
    group_services(page, groups=groups, row_for=lambda gid: group_row(gid, created_by=TOM, members=(USER, TOM)), rank=2)
    signed_in(page, events_origin, f'/group/{DISCO}')
    pw.expect(page.get_by_role('heading', name='Soirées du vendredi')).to_be_visible(timeout=15000)
    page.get_by_role('button', name='Inviter', exact=True).click()
    pw.expect(page.get_by_test_id('group-invite-panel')).to_be_visible()
    pw.expect(page.get_by_label('Chercher une personne')).to_be_visible()
    # Simple membre : pas de réglages du groupe.
    page.goto(f'{events_origin}/events/group/{DISCO}/settings', wait_until='domcontentloaded')
    pw.expect(page.get_by_text('Seul le créateur du groupe change son nom', exact=False)).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('switch', name='Tous les membres peuvent inviter')).to_have_count(0)
    pw.expect(page.get_by_role('switch', name='Événements à valider')).to_have_count(0)
    assert not errors, errors


def test_the_creator_sets_who_invites_and_events_to_approve(phone, events_origin):
    page, errors = phone
    state = group_services(page)
    signed_in(page, events_origin, f'/group/{FOOT}/settings')
    invite = page.get_by_role('switch', name='Tous les membres peuvent inviter')
    pw.expect(invite).to_be_visible(timeout=15000)
    pw.expect(invite).to_be_checked()  # allumé par défaut
    approval = page.get_by_role('switch', name='Événements à valider')
    pw.expect(approval).not_to_be_checked()  # éteint par défaut
    shot(page, 'groupes-reglages-regles.png')
    invite.click()
    pw.expect(page.get_by_text('Seuls ceux qui gèrent le groupe invitent')).to_be_visible()
    approval.click()
    page.wait_for_timeout(500)
    assert ('set_group_members_invite', {'grp': FOOT, 'allowed': False}) in state['rules']
    assert ('set_group_event_rules', {'grp': FOOT, 'need_approval': True, 'mode': 'request'}) in state['rules']
    assert not errors, errors
