"""Modèles d'événement sur la VRAIE base de test (jamais la prod) : perso ou d'équipe, réservés aux organisateurs et
admins ; chacun supprime les siens, un admin supprime n'importe lequel.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, make_vip
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


def add(s: Session, name: str, shared: bool, **extra) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/event_templates', headers={**s.headers, 'Prefer': 'return=representation'},
                      json={'name': name, 'shared': shared, 'data': {'title': name}, **extra}, timeout=30)


def names(s: Session) -> set[str]:
    return {t['name'] for t in s.get('event_templates?select=name').json()}


@pytest.fixture(scope='module')
def world():
    admin, guest, orga = Session(ADMIN), Session(GUEST_A), Session(VIP)
    make_vip(admin, orga)
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{orga.uid}', headers=admin.headers, json={'role': 'organizer'}, timeout=30)
    assert r.status_code in (200, 204), r.text
    yield admin, guest, orga
    httpx.delete(f'{TEST_URL}/rest/v1/event_templates?name=like.Test%25', headers=admin.headers, timeout=30)
    httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{orga.uid}', headers=admin.headers, json={'role': 'guest'}, timeout=30)


def test_team_templates_are_shared_and_personal_ones_stay_private(world):
    admin, guest, orga = world
    assert add(orga, 'Test perso orga', False).status_code == 201
    assert add(admin, 'Test équipe admin', True).status_code == 201
    assert add(admin, 'Test perso admin', False).status_code == 201
    assert {'Test perso orga', 'Test équipe admin'} <= names(orga) and 'Test perso admin' not in names(orga)
    assert 'Test perso orga' not in names(admin)


def test_guests_neither_see_nor_create_templates(world):
    admin, guest, orga = world
    assert add(guest, 'Test invité', False).status_code >= 400
    assert names(guest) == set()


def test_nobody_creates_a_template_in_someone_elses_name(world):
    admin, guest, orga = world
    assert add(orga, 'Test usurpé', True, owner_id=admin.uid).status_code >= 400


def test_an_organizer_deletes_only_their_own_templates_an_admin_any(world):
    admin, guest, orga = world
    team = add(admin, 'Test équipe à garder', True).json()[0]['id']
    mine = add(orga, 'Test orga à supprimer', True).json()[0]['id']
    httpx.delete(f'{TEST_URL}/rest/v1/event_templates?id=eq.{team}', headers=orga.headers, timeout=30)
    assert 'Test équipe à garder' in names(admin)  # pas le sien : rien n'est supprimé
    httpx.delete(f'{TEST_URL}/rest/v1/event_templates?id=eq.{mine}', headers=orga.headers, timeout=30)
    assert 'Test orga à supprimer' not in names(admin)
    other = add(orga, 'Test orga supprimé par admin', True).json()[0]['id']
    httpx.delete(f'{TEST_URL}/rest/v1/event_templates?id=eq.{other}', headers=admin.headers, timeout=30)
    assert 'Test orga supprimé par admin' not in names(orga)


def test_an_update_never_changes_the_author(world):
    admin, guest, orga = world
    tid = add(orga, 'Test auteur fixe', False).json()[0]['id']
    r = httpx.patch(f'{TEST_URL}/rest/v1/event_templates?id=eq.{tid}', headers=orga.headers,
                    json={'name': ' Test renommé ', 'owner_id': admin.uid}, timeout=30)
    assert r.status_code >= 400 or orga.get(f'event_templates?select=owner_id,name&id=eq.{tid}').json() == [
        {'owner_id': orga.uid, 'name': 'Test renommé'}]
