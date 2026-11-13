"""Réglages › Groupes (site, module Événements) — avis 1b4b43021c1e de Lidia : « je vois un groupe dans lequel je ne
suis pas ». Dans un vrai navigateur : « Mes groupes » = créés par moi ou dont je fais partie ; « Modifier » réservé au
créateur ; les Admins du site (rang Admin) voient en plus « Tous les groupes (admin) », repliée. Supabase est simulé."""
import json
from urllib.parse import urlparse

import pytest

from tests.test_events_browser import USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

LEA, TOM = '7a1c2b3d-0000-4000-8000-000000000001', '7a1c2b3d-0000-4000-8000-000000000002'
MINE = {'id': '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a01', 'name': 'Mes potes', 'created_by': USER, 'system_key': None,
        'member_group_members': [{'user_id': USER}, {'user_id': LEA}]}
INSIDE = {'id': '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a02', 'name': 'Rando', 'created_by': TOM, 'system_key': None,
          'member_group_members': [{'user_id': USER}, {'user_id': TOM}]}
FOREIGN = {'id': '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a03', 'name': 'DreamTeam', 'created_by': TOM, 'system_key': None,
           'member_group_members': [{'user_id': TOM}, {'user_id': LEA}]}
VIP = {'id': '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a04', 'name': 'Vendredi Party', 'created_by': None, 'system_key': 'vip',
       'member_group_members': [{'user_id': TOM}]}
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile'}


def open_groups(page, events_origin, rank: int, groups: list[dict], before_open=None):
    """rank : my_rank simulé (anciens rangs : Co-admin 3, Admin 4). groups : ce que la base renvoie à ce compte.
    before_open(page) : simulations de plus, prioritaires, posées avant l'ouverture de la page."""
    mock_services(page)
    people = [{'id': USER, 'display_name': 'Compte de démonstration', 'role': 'admin', 'avatar_url': None},
              {'id': LEA, 'display_name': 'Léa', 'role': 'member', 'avatar_url': None},
              {'id': TOM, 'display_name': 'Tom', 'role': 'member', 'avatar_url': None}]

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        path = urlparse(request.url).path
        if path.endswith('/member_groups'):
            result = groups
        elif path.endswith('/rpc/my_rank'):
            result = rank
        elif path.endswith('/rpc/my_privacy'):
            result = {'phone_groups': []}
        elif path.endswith('/rpc/my_group_invitations'):
            result = []
        elif path.endswith('/profiles'):
            result = people
        else:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route('https://gsuetixzobooggeaubvb.supabase.co/**', handle)
    if before_open:
        before_open(page)
    page.goto(events_origin, wait_until='domcontentloaded')
    page.locator('#accountTab').click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    pw.expect(frame.get_by_role('button', name='Mon profil : Compte de démonstration')).to_be_visible(timeout=15000)
    frame.get_by_text('Groupes', exact=True).first.click()
    pw.expect(frame.get_by_text('Mes groupes', exact=True)).to_be_visible(timeout=15000)
    return frame


@pytest.fixture
def phone(browser):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    yield page, errors
    context.close()


def test_my_groups_are_only_the_ones_i_created_or_belong_to_and_only_the_creator_edits(phone, events_origin):
    page, errors = phone
    # Co-admin : la base ne lui renvoie plus que ses groupes ; même si elle en renvoyait un autre, il n'est pas affiché.
    frame = open_groups(page, events_origin, rank=3, groups=[MINE, INSIDE, FOREIGN, VIP])
    pw.expect(frame.get_by_text('Mes potes', exact=True)).to_be_visible()
    pw.expect(frame.get_by_text('Rando', exact=True)).to_be_visible()
    pw.expect(frame.get_by_text('DreamTeam', exact=True)).to_have_count(0)
    pw.expect(frame.get_by_text('Vendredi Party', exact=True)).to_have_count(0)  # je n'en fais pas partie
    pw.expect(frame.get_by_text('Tous les groupes (admin)', exact=True)).to_have_count(0)
    # « Modifier » : seulement sur le groupe que j'ai créé (pas sur Rando, créé par Tom), même pour un Co-admin.
    pw.expect(frame.get_by_role('button', name='Modifier', exact=True)).to_have_count(1)
    assert not errors, errors


def test_a_site_admin_sees_every_other_group_in_a_folded_admin_section_and_can_edit_it(phone, events_origin):
    page, errors = phone
    frame = open_groups(page, events_origin, rank=4, groups=[MINE, INSIDE, FOREIGN, VIP])
    pw.expect(frame.get_by_text('Tous les groupes (admin)', exact=True)).to_be_visible()
    pw.expect(frame.get_by_text('DreamTeam', exact=True)).to_have_count(0)  # repliée
    frame.get_by_role('button', name='Voir les 2 autres groupes').click()
    pw.expect(frame.get_by_text('DreamTeam', exact=True)).to_be_visible()
    pw.expect(frame.get_by_text('Vendredi Party', exact=True)).to_be_visible()
    # Mes potes (le mien) + DreamTeam (admin) ; ni Rando (pas le mien), ni Vendredi Party (groupe du système).
    pw.expect(frame.get_by_role('button', name='Modifier', exact=True)).to_have_count(2)
    frame.get_by_role('button', name='Masquer les autres groupes').click()
    pw.expect(frame.get_by_text('DreamTeam', exact=True)).to_have_count(0)
    assert not errors, errors


def test_my_own_group_offers_a_ready_invite_link_at_the_top(phone, events_origin):
    """Avis e39b166040ea (13.11) : « Inviter avec un lien » prêt en haut de MON groupe (Copier / Partager), sans ouvrir
    « Modifier » ; pas sur le groupe d'un autre."""
    page, errors = phone
    token = '0a0b0c0d-0000-4000-8000-00000000abcd'
    calls = []

    def link(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        calls.append(json.loads(route.request.post_data or '{}'))
        route.fulfill(status=200, content_type='application/json', body=json.dumps(token), headers=CORS)

    frame = open_groups(page, events_origin, rank=3, groups=[MINE, INSIDE],
                        before_open=lambda p: p.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/group_invite_link*', link))
    card = frame.get_by_label('Inviter dans Mes potes')
    pw.expect(card).to_be_visible()
    pw.expect(card.get_by_text(f'/events/group-invite/{token}', exact=False)).to_be_visible()
    pw.expect(card.get_by_role('button', name='Copier')).to_be_visible()
    pw.expect(card.get_by_role('button', name='Partager')).to_be_visible()
    pw.expect(frame.get_by_label('Inviter dans Rando')).to_have_count(0)
    assert calls and calls[0]['renew'] is False
    assert not errors, errors
