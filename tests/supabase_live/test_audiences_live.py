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


def make_vip(admin: Session, vip: Session):
    """Profil complet (photo réelle dans son dossier), puis l'admin le passe Membre VIP."""
    complete_profile(vip, 'VIP test')
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'member'}, timeout=30)
    assert r.status_code in (200, 204), r.text


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
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'guest'}, timeout=30)


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


def test_the_vendredi_party_group_follows_the_status_and_cannot_be_edited_by_hand(world):
    admin, ga, gb, vip, ids = world
    group = admin.get('member_groups?select=id,name,member_group_members(user_id)&system_key=eq.vip').json()[0]
    assert group['name'] == 'Vendredi Party' and vip.uid in {m['user_id'] for m in group['member_group_members']}
    assert ga.uid not in {m['user_id'] for m in group['member_group_members']}
    r = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=admin.headers, json={'group_id': group['id'], 'user_id': ga.uid}, timeout=30)
    assert r.status_code >= 400  # on passe par le statut, pas par le groupe
    r = httpx.patch(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group["id"]}', headers={**admin.headers, 'Prefer': 'return=representation'},
                    json={'name': 'Autre nom'}, timeout=30)
    assert r.json() == []  # ni renommé
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'guest'}, timeout=30)
    members = admin.get(f'member_group_members?select=user_id&group_id=eq.{group["id"]}').json()
    assert vip.uid not in {m['user_id'] for m in members}  # redevenu Guest : sorti du groupe
    assert 'vip' not in visible(vip, ids)
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{vip.uid}', headers=admin.headers, json={'role': 'member'}, timeout=30)


def test_invited_guests_get_their_invitation_and_members_get_new_event(world):
    admin, ga, gb, vip, ids = world
    def notes(s):
        return {(n['kind'], n['event_id']) for n in s.get('notifications?select=kind,event_id').json()}
    assert ('private_invite', ids['vip+A']) in notes(ga)
    assert ('private_invite', ids['numéro B']) in notes(gb)
    assert ('new_event', ids['vip']) not in notes(ga)
