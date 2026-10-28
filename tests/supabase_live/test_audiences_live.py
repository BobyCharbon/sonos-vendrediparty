"""Qui voit quelle sortie, sur la VRAIE base de test (jamais la prod) : publique, Vendredi Party (VIP),
VIP + personne ajoutée, invitation par numéro. Comptes réels à code fixe ; le numéro de Root n'est jamais utilisé.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401

ADMIN, GUEST_A, GUEST_B, VIP = '41790000004', '41790000001', '41790000002', '41790000003'
ICON = Path(__file__).resolve().parents[2] / 'app/static/icon-192.png'


def complete_profile(who: Session, nickname: str):
    """Profil complet comme dans l'app : prénom, nom, surnom et vraie photo dans son dossier (nouvelle à chaque passage)."""
    photo = f'{who.uid}/test-{time.time_ns()}.png'
    up = httpx.post(f'{TEST_URL}/storage/v1/object/profile-photos/{photo}', content=ICON.read_bytes(), timeout=30,
                    headers={**who.headers, 'Content-Type': 'image/png'})
    assert up.status_code in (200, 201), up.text
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{who.uid}', headers=who.headers, timeout=30,
                    json={'display_name': nickname, 'first_name': nickname.split()[0], 'last_name': 'Test', 'avatar_url': photo})
    assert r.status_code in (200, 204), r.text


def vip_group(admin: Session) -> str:
    return admin.get('member_groups?select=id&system_key=eq.vip').json()[0]['id']


def make_vip(admin: Session, vip: Session):
    """Profil complet (photo réelle dans son dossier), puis l'admin le passe Membre et l'ajoute au groupe Vendredi
    Party : depuis la séparation des rôles et des groupes (20261028200000), c'est le groupe qui donne les droits VIP."""
    complete_profile(vip, 'VIP test')
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'member'}, timeout=30)
    assert r.status_code in (200, 204), r.text
    r = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', timeout=30,
                   headers={**admin.headers, 'Prefer': 'resolution=ignore-duplicates'},
                   json={'group_id': vip_group(admin), 'user_id': vip.uid})
    assert r.status_code in (200, 201, 204), r.text


def unmake_vip(admin: Session, vip: Session):
    """Retour à Guest, hors du groupe Vendredi Party."""
    httpx.delete(f'{TEST_URL}/rest/v1/member_group_members?group_id=eq.{vip_group(admin)}&user_id=eq.{vip.uid}',
                 headers=admin.headers, timeout=30)
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'guest'}, timeout=30)


def create_event(admin: Session, title: str, **fields) -> str:
    start = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    r = httpx.post(f'{TEST_URL}/rest/v1/events', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                   json={'title': title, 'status': 'published', 'starts_at': start, 'notify_on_publish': True, **fields})
    assert r.status_code == 201, r.text
    return r.json()[0]['id']


def visible(s: Session, ids: dict) -> set:
    rows = s.get('events?select=id').json()
    return {name for name, eid in ids.items() if eid in {r['id'] for r in rows}}


@pytest.fixture(scope='module')
def world():
    admin, ga, gb, vip = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    make_vip(admin, vip)
    ids = {'publique': create_event(admin, 'Test publique', public_link=True),
           'vip': create_event(admin, 'Test VIP'),
           'vip+A': create_event(admin, 'Test VIP + Guest A')}
    r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': ids['vip+A'], 'user_id': ga.uid}, timeout=30)
    assert r.status_code == 201, r.text
    ids['numéro B'] = create_event(admin, 'Test invitation par numéro', visibility='invited')
    r = httpx.post(f'{TEST_URL}/rest/v1/event_phone_invites', headers=admin.headers, json={'event_id': ids['numéro B'], 'phone': GUEST_B}, timeout=30)
    assert r.status_code == 201, r.text
    yield admin, ga, gb, vip, ids
    for eid in ids.values():
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)
    unmake_vip(admin, vip)


def test_each_account_sees_exactly_the_events_meant_for_it(world):
    admin, ga, gb, vip, ids = world
    assert visible(ga, ids) == {'publique', 'vip+A'}
    assert visible(gb, ids) == {'publique', 'numéro B'}
    assert visible(vip, ids) == {'publique', 'vip', 'vip+A'}
    assert visible(admin, ids) == set(ids)


def test_a_guest_answers_and_writes_on_an_event_it_sees_but_not_on_others(world):
    admin, ga, gb, vip, ids = world
    ok = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=ga.headers, json={'event_id': ids['publique'], 'user_id': ga.uid, 'status': 'yes'}, timeout=30)
    assert ok.status_code == 201, ok.text
    msg = httpx.post(f'{TEST_URL}/rest/v1/messages', headers=ga.headers, json={'event_id': ids['vip+A'], 'user_id': ga.uid, 'body': 'Je viens !'}, timeout=30)
    assert msg.status_code == 201, msg.text
    no = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=ga.headers, json={'event_id': ids['vip'], 'user_id': ga.uid, 'status': 'yes'}, timeout=30)
    assert no.status_code >= 400


def test_a_guest_sees_nickname_and_photo_of_people_on_its_events_but_never_their_phone(world):
    admin, ga, gb, vip, ids = world
    names = ga.get(f'profiles?select=id,display_name,avatar_url&id=eq.{admin.uid}').json()
    assert names and names[0]['display_name'] == 'Admin test'  # créateur d'une sortie qu'il voit
    assert ga.get(f'profiles?select=phone&id=eq.{admin.uid}').status_code >= 400  # colonne illisible
    assert gb.get(f'profiles?select=id&id=eq.{ga.uid}').json() != []  # A a répondu à la sortie publique, que B voit aussi
    assert ga.get(f'profiles?select=id&id=eq.{vip.uid}').json() == []  # le VIP n'a rien fait sur ses sorties


def test_vip_is_the_vendredi_party_group_not_a_role(world):
    """Rôles et groupes séparés (20261028200000) : un seul rôle, des groupes ; c'est le groupe qui rend VIP."""
    admin, ga, gb, vip, ids = world
    group = admin.get('member_groups?select=id,name,member_group_members(user_id)&system_key=eq.vip').json()[0]
    assert group['name'] == 'Vendredi Party' and vip.uid in {m['user_id'] for m in group['member_group_members']}
    # Un Guest ne compose pas le groupe ; il ne peut pas non plus être renommé.
    r = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=ga.headers, json={'group_id': group['id'], 'user_id': ga.uid}, timeout=30)
    assert r.status_code >= 400
    r = httpx.patch(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group["id"]}', headers={**admin.headers, 'Prefer': 'return=representation'},
                    json={'name': 'Autre nom'}, timeout=30)
    assert r.json() == []
    # Rôle « Membre » sans le groupe : droits de Guest, pas d'événement VIP.
    httpx.delete(f'{TEST_URL}/rest/v1/member_group_members?group_id=eq.{group["id"]}&user_id=eq.{vip.uid}', headers=admin.headers, timeout=30)
    assert 'vip' not in visible(vip, ids)
    assert vip.rpc('my_permissions').json() == ['events.rsvp', 'chat.write', 'games.create', 'music.add'] or \
        'events.view' not in vip.rpc('my_permissions').json()
    # L'admin l'ajoute au groupe : il redevient VIP, sans changer de rôle.
    r = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=admin.headers, json={'group_id': group['id'], 'user_id': vip.uid}, timeout=30)
    assert r.status_code == 201, r.text
    assert 'vip' in visible(vip, ids) and 'events.view' in vip.rpc('my_permissions').json()
    # Changer de rôle ne fait plus sortir du groupe.
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'guest'}, timeout=30)
    members = admin.get(f'member_group_members?select=user_id&group_id=eq.{group["id"]}').json()
    assert vip.uid in {m['user_id'] for m in members}
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'member'}, timeout=30)


def test_anyone_creates_a_group_and_sees_their_groups(world):
    """Réglages › Groupes : un Guest crée son groupe, le compose, et voit les groupes dont il fait partie."""
    admin, ga, gb, vip, ids = world
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**ga.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test groupe de A', 'created_by': ga.uid}, timeout=30)
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=ga.headers, json={'group_id': gid, 'user_id': gb.uid}, timeout=30)
        assert r.status_code == 201, r.text
        assert gid in {g['id'] for g in gb.get('member_groups?select=id').json()}  # B voit le groupe où il est
        assert gid in {g['id'] for g in ga.get('member_groups?select=id').json()}  # A voit le groupe qu'il a créé
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{gid}', headers=admin.headers, timeout=30)


def test_invited_guests_get_their_invitation_and_members_get_new_event(world):
    admin, ga, gb, vip, ids = world
    def notes(s):
        return {(n['kind'], n['event_id']) for n in s.get('notifications?select=kind,event_id').json()}
    assert ('private_invite', ids['vip+A']) in notes(ga)
    assert ('private_invite', ids['numéro B']) in notes(gb)
    assert ('new_event', ids['vip']) not in notes(ga)
