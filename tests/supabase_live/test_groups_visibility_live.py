"""Groupes visibles par leurs membres seulement (avis 1b4b43021c1e de Lidia : « je vois un groupe dans lequel je ne suis
pas »), sur la VRAIE base de test (jamais la prod). Un groupe et sa composition se lisent par ses membres, son créateur
et les Admins du site ; le nom des groupes invités à un événement reste lisible par qui voit l'événement.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, create_event, make_vip, unmake_vip
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

NAME = 'Test DreamTeam'


@pytest.fixture(scope='module')
def world():
    admin, a, b, vip = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    make_vip(admin, vip)  # Membre VIP : compte actif (events.view), celui qui voyait tous les groupes avant
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**b.headers, 'Prefer': 'return=representation'},
                   json={'name': NAME, 'created_by': b.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    assert httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=b.headers, timeout=30,
                      json={'group_id': group, 'user_id': a.uid}).status_code == 201
    event = create_event(admin, 'Test groupe invité', visibility='invited')
    assert httpx.post(f'{TEST_URL}/rest/v1/event_groups', headers=admin.headers, timeout=30,
                      json={'event_id': event, 'group_id': group}).status_code == 201
    yield admin, a, b, vip, group, event
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=b.headers, timeout=30)
    unmake_vip(admin, vip)


def groups_seen(s: Session) -> set[str]:
    r = s.get('member_groups?select=id')
    assert r.status_code == 200, r.text
    return {g['id'] for g in r.json()}


def members_seen(s: Session, group: str) -> set[str]:
    r = s.get(f'member_group_members?select=user_id&group_id=eq.{group}')
    assert r.status_code == 200, r.text
    return {m['user_id'] for m in r.json()}


def test_an_active_member_outside_the_group_sees_neither_the_group_nor_its_members(world):
    _, a, b, vip, group, _ = world
    assert group not in groups_seen(vip)
    assert members_seen(vip, group) == set()
    assert vip.get(f'member_groups?select=invite_token&id=eq.{group}').json() == []  # ni son lien d'invitation
    embedded = vip.get('member_groups?select=id,member_group_members(user_id)').json()
    assert group not in {g['id'] for g in embedded}


def test_the_creator_and_the_members_still_see_the_group_and_its_composition(world):
    _, a, b, _, group, _ = world
    for who in (a, b):
        assert group in groups_seen(who)
        assert members_seen(who, group) == {a.uid, b.uid}  # le créateur en fait partie d'office


def test_the_site_admin_sees_every_group(world):
    admin, a, b, _, group, _ = world
    assert group in groups_seen(admin)
    assert members_seen(admin, group) == {a.uid, b.uid}


def test_my_own_memberships_stay_readable_for_the_app_start(world):
    """auth.tsx : « membre d'un groupe privé » se lit sur mes propres lignes, jointes à leur groupe."""
    _, a, _, vip, group, _ = world
    rows = a.get(f'member_group_members?select=group_id,member_groups!inner(system_key)&user_id=eq.{a.uid}'
                 '&member_groups.system_key=is.null').json()
    assert group in {r['group_id'] for r in rows}
    vip_rows = vip.get(f'member_group_members?select=group_id,member_groups!inner(system_key)&user_id=eq.{vip.uid}').json()
    assert any(r['member_groups']['system_key'] == 'vip' for r in vip_rows)  # Vendredi Party : il en fait partie


def test_an_outsider_cannot_compose_a_foreign_group(world):
    _, _, _, vip, group, _ = world
    r = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=vip.headers, timeout=30,
                   json={'group_id': group, 'user_id': vip.uid})
    assert r.status_code in (401, 403), r.text


def test_the_creator_still_adds_and_removes_members(world):
    _, a, b, vip, group, _ = world
    assert httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=b.headers, timeout=30,
                      json={'group_id': group, 'user_id': vip.uid}).status_code == 201
    assert group in groups_seen(vip) and members_seen(vip, group) == {a.uid, b.uid, vip.uid}  # devenu membre : il voit
    assert httpx.delete(f'{TEST_URL}/rest/v1/member_group_members?group_id=eq.{group}&user_id=eq.{vip.uid}',
                        headers=b.headers, timeout=30).status_code == 204
    assert group not in groups_seen(vip)


def test_group_names_of_an_event_follow_who_sees_the_event(world):
    admin, a, _, vip, group, event = world
    assert a.rpc('event_group_names', e=event).json() == [NAME]  # invité par le groupe
    assert vip.rpc('event_group_names', e=event).json() == []  # ne voit pas l'événement
    assert httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, timeout=30,
                      json={'event_id': event, 'user_id': vip.uid}).status_code == 201
    assert vip.rpc('event_group_names', e=event).json() == [NAME]  # invité seul : voit le nom, pas la composition
    assert members_seen(vip, group) == set()
