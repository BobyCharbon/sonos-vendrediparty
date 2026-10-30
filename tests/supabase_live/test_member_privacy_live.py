"""Fiche profil et confidentialité, sur la VRAIE base de test (jamais la prod) : nom et numéro cachés par défaut,
nom rendu public au choix de la personne, numéro montré seulement aux membres des groupes qu'elle a choisis.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture(scope='module')
def world():
    a, b = Session(GUEST_A), Session(GUEST_B)
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**a.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test confidentialité', 'created_by': a.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    for uid in (a.uid, b.uid):
        r = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=a.headers, timeout=30, json={'group_id': group, 'user_id': uid})
        assert r.status_code == 201, r.text
    yield a, b, group
    b.rpc('set_name_public', visible=False)
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)


def card(viewer: Session, target: Session) -> dict:
    r = viewer.rpc('member_card', target=target.uid)
    assert r.status_code == 200, r.text
    return r.json()


def test_name_and_phone_are_hidden_by_default(world):
    a, b, group = world
    assert b.rpc('set_name_public', visible=False).status_code == 200
    c = card(a, b)
    assert c['display_name'] == 'Testeur 2' and c['first_name'] is None and c['last_name'] is None and c['phone'] is None
    assert 'Test confidentialité' in c['groups']
    mine = card(b, b)  # sa propre fiche : tout
    assert mine['me'] and mine['first_name'] and mine['phone']


def test_a_member_makes_her_name_public(world):
    a, b, group = world
    assert b.rpc('set_name_public', visible=True).json()['show_name'] is True
    c = card(a, b)
    assert c['first_name'] and c['last_name'] and c['phone'] is None
    b.rpc('set_name_public', visible=False)
    assert card(a, b)['first_name'] is None


def test_the_phone_is_shown_only_in_the_chosen_group(world):
    a, b, group = world
    assert group in b.rpc('set_group_phone_share', grp=group, visible=True).json()['phone_groups']
    assert card(a, b)['phone']
    assert b.rpc('set_group_phone_share', grp=group, visible=False).json()['phone_groups'] == []
    assert card(a, b)['phone'] is None


def test_nobody_shares_a_phone_in_a_group_they_are_not_in(world):
    a, b, group = world
    vip = a.get('member_groups?select=id&system_key=eq.vip').json()
    if vip:
        r = b.rpc('set_group_phone_share', grp=vip[0]['id'], visible=True)
        assert r.status_code >= 400  # Testeur 2 (Guest) n'est pas dans Vendredi Party
