"""Réponses aux événements regroupées, sur la VRAIE base de test (jamais la prod) : quelqu'un change d'avis plusieurs
fois de suite, l'organisateur ne reçoit qu'UNE notification au bout de 5 minutes, avec l'état final ; et une
notification créée réveille l'envoi tout de suite (sans attendre la tâche de chaque minute).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import json
import pathlib
import urllib.request

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, create_event
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

TEST_REF = 'ewromqfsmcqsthftyhzm'  # base de TEST uniquement
TOKEN_FILE = pathlib.Path.home() / '.config/supabase-claude/token'


def sql(query: str) -> list:
    """SQL sur la base de TEST (API de gestion) : avancer le temps de la fenêtre, lancer l'envoi groupé."""
    req = urllib.request.Request(f'https://api.supabase.com/v1/projects/{TEST_REF}/database/query', method='POST',
                                 data=json.dumps({'query': query}).encode(),
                                 headers={'Authorization': f'Bearer {TOKEN_FILE.read_text().strip()}',
                                          'Content-Type': 'application/json', 'User-Agent': 'party-claude'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or '[]')


def answer(s: Session, event: str, status: str):
    """Comme l'app : première réponse créée, les suivantes changent seulement le statut."""
    r = httpx.patch(f'{TEST_URL}/rest/v1/rsvps?event_id=eq.{event}&user_id=eq.{s.uid}', timeout=30,
                    headers={**s.headers, 'Prefer': 'return=representation'}, json={'status': status})
    if r.status_code == 200 and r.json():
        return
    r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', timeout=30, headers={**s.headers, 'Prefer': 'return=minimal'},
                   json={'event_id': event, 'user_id': s.uid, 'status': status})
    assert r.status_code in (200, 201, 204), r.text


def rsvp_notes(admin: Session, event: str) -> list[str]:
    return [n['body'] for n in admin.get(f'notifications?select=body&kind=eq.rsvp&event_id=eq.{event}&order=created_at').json()]


@pytest.fixture(scope='module')
def world():
    if not TOKEN_FILE.exists():
        pytest.skip('jeton de l\'API de gestion absent')
    admin, ga, gb = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    event = create_event(admin, 'Test réponses regroupées', public_link=True)
    yield admin, ga, gb, event
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)


def test_many_changes_give_one_notification_after_five_minutes(world):
    admin, ga, gb, event = world
    for status in ('yes', 'maybe', 'no', 'yes', 'no', 'yes'):  # change d'avis toutes les secondes
        answer(ga, event, status)
    answer(gb, event, 'no')
    assert rsvp_notes(admin, event) == []  # rien pendant la fenêtre de 5 minutes
    held = sql(f"select status::text from private.rsvp_digest where event_id = '{event}' order by updated_at")
    assert [h['status'] for h in held] == ['yes', 'no']  # l'état final de chacun, une ligne par personne

    assert sql('select private.flush_rsvp_digests() as n')[0]['n'] == 0  # moins de 5 minutes : on attend encore
    kicked_before = sql('select at::text from private.push_kick')[0]['at']
    sql(f"update private.rsvp_digest set first_at = now() - interval '6 minutes' where event_id = '{event}'")
    assert sql('select private.flush_rsvp_digests() as n')[0]['n'] >= 1

    notes = rsvp_notes(admin, event)
    assert notes == ['Testeur 1 vient · Testeur 2 ne vient pas'], notes
    assert sql(f"select count(*)::int as n from private.rsvp_digest where event_id = '{event}'")[0]['n'] == 0
    assert sql('select private.flush_rsvp_digests() as n')[0]['n'] == 0  # rien de plus ensuite
    assert len(rsvp_notes(admin, event)) == 1
    # La notification créée a réveillé l'envoi aussitôt (APNs et web push), sans attendre la minute suivante.
    assert sql('select at::text from private.push_kick')[0]['at'] != kicked_before


def test_the_organizer_answering_his_own_event_is_not_notified(world):
    admin, ga, gb, event = world
    answer(admin, event, 'yes')
    sql(f"update private.rsvp_digest set first_at = now() - interval '6 minutes' where event_id = '{event}'")
    sql('select private.flush_rsvp_digests()')
    assert len(rsvp_notes(admin, event)) == 1  # toujours la seule de l'autre test
