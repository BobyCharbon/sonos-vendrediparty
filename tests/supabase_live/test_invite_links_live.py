"""Liens et invitations (avis n°9), sur la VRAIE base de test (jamais la prod) : événement sur invitation avec un lien
partageable, lien et invitations de groupe acceptées ou refusées.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, create_event
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


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


def test_a_private_event_is_joined_through_single_use_links(people, newcomer):
    admin, ga, gb = people
    event = create_event(admin, 'Test lien d’invitation', visibility='invited')
    try:
        assert ga.get(f'events?select=id&id=eq.{event}').json() == []  # pas invité : invisible
        token = admin.rpc('create_invite_link', k='event', target=event).json()
        assert ga.rpc('create_invite_link', k='event', target=event).status_code >= 400  # organisateurs seulement
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
        assert ga.rpc('join_event_by_link', token=token).json() == event  # la même personne y revient : pas de doublon
        assert len(admin.get(f"notifications?select=id&kind=eq.link_join&event_id=eq.{event}").json()) == 1

        # Lien unique : une seule personne. Le suivant voit « déjà utilisé » et rien de l'événement.
        used = gb.rpc('join_event_by_link', token=token)
        assert used.status_code >= 400 and 'déjà été utilisé' in used.text
        assert gb.rpc('invite_event', token=token).json() is None
        links = admin.rpc('my_invite_links', k='event', target=event).json()
        assert [(l['status'], l['used_by']) for l in links] == [('used', 'Testeur 1')]
        assert ga.rpc('my_invite_links', k='event', target=event).status_code >= 400

        # Annulé, puis expiré (7 jours) : refusés avec la raison.
        second = admin.rpc('create_invite_link', k='event', target=event).json()
        assert second != token and admin.rpc('revoke_invite_link', tok=second).status_code in (200, 204)
        assert 'annulé' in gb.rpc('join_event_by_link', token=second).text
        third = admin.rpc('create_invite_link', k='event', target=event).json()
        sql(f"update private.invite_links set expires_at = now() - interval '1 minute' where token = '{third}'")
        assert 'expiré' in gb.rpc('join_event_by_link', token=third).text
        assert {l['status'] for l in admin.rpc('my_invite_links', k='event', target=event).json()} == {'used', 'revoked', 'expired'}
        fourth = admin.rpc('event_invite_link', e=event).json()  # ancien appel : un lien unique de plus
        assert gb.rpc('join_event_by_link', token=fourth).json() == event
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)


def test_a_group_is_joined_by_link_and_invitations_are_answered(people, newcomer):
    admin, ga, gb = people
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**ga.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test invitations', 'created_by': ga.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    try:
        # Lien unique (par défaut) : une personne ; lien réutilisable : tout le monde, renouvelable.
        single = ga.rpc('create_invite_link', k='group', target=group).json()
        assert gb.rpc('create_invite_link', k='group', target=group).status_code >= 400  # seul le créateur
        assert admin.rpc('join_group_by_link', token=single).json() == group
        assert 'déjà été utilisé' in gb.rpc('join_group_by_link', token=single).text
        httpx.delete(f'{TEST_URL}/rest/v1/member_group_members?group_id=eq.{group}&user_id=eq.{admin.uid}', headers=ga.headers, timeout=30)
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
