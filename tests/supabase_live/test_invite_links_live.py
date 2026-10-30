"""Liens et invitations (avis n°9), sur la VRAIE base de test (jamais la prod) : événement sur invitation avec un lien
partageable, lien et invitations de groupe acceptées ou refusées.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, create_event
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401


def anon_rpc(name: str, **args) -> httpx.Response:
    key = KEY_FILE.read_text().strip()
    return httpx.post(f'{TEST_URL}/rest/v1/rpc/{name}', json=args, timeout=30,
                      headers={'apikey': key, 'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})


NEW = '41768163120'  # Guest au profil vide (code fixe de la base de test)


@pytest.fixture(scope='module')
def people():
    return Session(ADMIN), Session(GUEST_A), Session(GUEST_B)


@pytest.fixture(scope='module')
def newcomer():
    return Session(NEW)


def test_an_invitation_only_event_is_joined_through_its_link(people, newcomer):
    admin, ga, gb = people
    event = create_event(admin, 'Test lien d’invitation', visibility='invited')
    try:
        assert ga.get(f'events?select=id&id=eq.{event}').json() == []  # pas invité : invisible
        token = admin.rpc('event_invite_link', e=event).json()
        assert ga.rpc('event_invite_link', e=event).status_code >= 400  # seuls les organisateurs ont le lien
        # Sans compte, ou avec un profil incomplet : rien n'est visible ni rejoignable (inscription d'abord).
        assert anon_rpc('invite_event', token=token).status_code >= 400
        assert newcomer.rpc('invite_event', token=token).json() is None
        refused = newcomer.rpc('join_event_by_link', token=token)
        assert refused.status_code >= 400 and 'profile_incomplete' in refused.text
        preview = ga.rpc('invite_event', token=token).json()
        assert preview['title'] == 'Test lien d’invitation' and preview['organizer'] == 'Admin test' and not preview['joined']

        assert ga.rpc('join_event_by_link', token=token).json() == event
        assert ga.get(f'events?select=id&id=eq.{event}').json() != []  # cet événement seulement
        invite = admin.get(f'event_invites?select=via_link&event_id=eq.{event}&user_id=eq.{ga.uid}').json()
        assert invite == [{'via_link': True}]  # « invité par lien » (orange)
        notes = admin.get(f"notifications?select=body&kind=eq.link_join&event_id=eq.{event}").json()
        assert notes == [{'body': 'Testeur 1 a rejoint ton événement par le lien'}]
        assert ga.rpc('join_event_by_link', token=token).json() == event  # deux fois : pas de doublon
        assert len(admin.get(f"notifications?select=id&kind=eq.link_join&event_id=eq.{event}").json()) == 1

        new = admin.rpc('event_invite_link', e=event, renew=True).json()
        assert new != token and gb.rpc('join_event_by_link', token=token).status_code >= 400  # ancien lien mort
        assert gb.rpc('invite_event', token=token).json() is None
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)


def test_a_group_is_joined_by_link_and_invitations_are_answered(people, newcomer):
    admin, ga, gb = people
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**ga.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test invitations', 'created_by': ga.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    try:
        token = ga.rpc('group_invite_link', grp=group).json()
        assert gb.rpc('group_invite_link', grp=group).status_code >= 400  # seul le créateur
        assert anon_rpc('group_invite_info', token=token).status_code >= 400
        assert newcomer.rpc('group_invite_info', token=token).json() is None
        assert 'profile_incomplete' in newcomer.rpc('join_group_by_link', token=token).text
        info = gb.rpc('group_invite_info', token=token).json()
        assert info['name'] == 'Test invitations' and info['creator'] == 'Testeur 1'
        assert gb.rpc('join_group_by_link', token=token).json() == group
        members = ga.get(f'member_group_members?select=user_id&group_id=eq.{group}').json()
        assert {'user_id': gb.uid} in members
        assert ga.get("notifications?select=body&kind=eq.group_join&order=created_at.desc&limit=1").json()[0]['body'] == 'Testeur 2 a rejoint ton groupe'

        # Invitation par numéro (celui d'Admin test) : elle l'attend dans ses Réglages, il refuse puis on le réinvite et il accepte.
        assert ga.rpc('invite_to_group', grp=group, phone='+41 79 000 00 04').json() == {'invited': 'member'}
        pending = admin.rpc('my_group_invitations').json()
        mine = [i for i in pending if i['group_id'] == group]
        assert mine and mine[0]['invited_by'] == 'Testeur 1'
        assert all(i['group_id'] != group for i in admin.rpc('answer_group_invitation', inv=mine[0]['id'], accept=False).json())
        ga.rpc('invite_to_group', grp=group, member=admin.uid)
        again = [i for i in admin.rpc('my_group_invitations').json() if i['group_id'] == group]
        admin.rpc('answer_group_invitation', inv=again[0]['id'], accept=True)
        assert {'user_id': admin.uid} in ga.get(f'member_group_members?select=user_id&group_id=eq.{group}').json()
        assert ga.rpc('invite_to_group', grp=group, member=admin.uid).status_code >= 400  # déjà dans le groupe

        # Numéro sans compte : l'invitation est gardée (personne d'autre ne la voit).
        assert ga.rpc('invite_to_group', grp=group, phone='0799999999').json() == {'invited': 'phone'}
        assert all(i['group_id'] != group for i in gb.rpc('my_group_invitations').json())
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=ga.headers, timeout=30)


def test_the_vendredi_party_group_has_no_link(people):
    admin, ga, gb = people
    vip = admin.get('member_groups?select=id&system_key=eq.vip').json()
    if vip:
        assert admin.rpc('group_invite_link', grp=vip[0]['id']).status_code >= 400
