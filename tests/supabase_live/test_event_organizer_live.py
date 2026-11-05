"""Parcours ORGANISATEUR sur la VRAIE base de test (jamais la prod) : co-organisateur, brouillon, validation, refus,
annulation, sondage de dates fixé, droits de modification et de suppression. Événements « sur invitation » et sans
annonce : seuls les comptes de test sont prévenus, aucun vrai membre.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_event_organizer_live.py -q"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, create_event, make_vip, unmake_vip
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401

QUIET = {'visibility': 'invited', 'notify_on_publish': False}


@pytest.fixture(scope='module')
def people():
    admin, ga, vip = Session(ADMIN), Session(GUEST_A), Session(VIP)
    make_vip(admin, vip)
    made: list[str] = []
    yield admin, ga, vip, made
    for eid in made:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)
    unmake_vip(admin, vip)


def event(admin: Session, made: list[str], title: str, **fields) -> str:
    eid = create_event(admin, title, **{**QUIET, **fields})
    made.append(eid)
    return eid


def post(who: Session, table: str, body) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/{table}', headers={**who.headers, 'Prefer': 'return=representation'}, json=body, timeout=30)


def patch(who: Session, path: str, body: dict) -> httpx.Response:
    return httpx.patch(f'{TEST_URL}/rest/v1/{path}', headers={**who.headers, 'Prefer': 'return=representation'}, json=body, timeout=30)


def delete(who: Session, path: str) -> httpx.Response:
    return httpx.delete(f'{TEST_URL}/rest/v1/{path}', headers={**who.headers, 'Prefer': 'return=representation'}, timeout=30)


def row(who: Session, eid: str, cols: str = 'status,title') -> dict | None:
    rows = who.get(f'events?select={cols}&id=eq.{eid}').json()
    return rows[0] if rows else None


def organizers(admin: Session, eid: str) -> set[str]:
    return {r['user_id'] for r in admin.get(f'event_organizers?select=user_id&event_id=eq.{eid}').json()}


def test_a_co_organizer_saving_the_form_keeps_every_co_organizer(people):
    """Ce que fait le formulaire (EventForm.syncChildren) : effacer les AUTRES co-organisateurs puis les réinscrire."""
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test co-organisateur enregistre')
    assert post(admin, 'event_organizers', [{'event_id': eid, 'user_id': u} for u in (vip.uid, ga.uid)]).status_code == 201
    assert delete(vip, f'event_organizers?event_id=eq.{eid}&user_id=neq.{vip.uid}').status_code == 200
    assert post(vip, 'event_organizers', [{'event_id': eid, 'user_id': ga.uid}]).status_code == 201
    assert organizers(admin, eid) == {vip.uid, ga.uid}
    # L'ancien enchaînement (tout effacer, soi compris) : la réinscription des autres est refusée par la base.
    assert delete(vip, f'event_organizers?event_id=eq.{eid}').status_code == 200
    assert post(vip, 'event_organizers', [{'event_id': eid, 'user_id': ga.uid}]).status_code in (401, 403)
    assert organizers(admin, eid) == set()


def test_a_cancelled_event_stays_cancelled_when_an_organizer_edits_it(people):
    """Bug : modifier un événement annulé (organisateur sans droit « tous les événements ») le republiait en silence
    (garde public.guard_event : statut recalculé comme pour une proposition)."""
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test annulé puis modifié')
    assert post(admin, 'event_organizers', {'event_id': eid, 'user_id': vip.uid}).status_code == 201
    assert patch(vip, f'events?id=eq.{eid}', {'status': 'cancelled'}).json()[0]['status'] == 'cancelled'
    edited = patch(vip, f'events?id=eq.{eid}', {'title': 'Test annulé puis modifié (corrigé)'})
    assert edited.status_code == 200, edited.text
    assert row(admin, eid) == {'status': 'cancelled', 'title': 'Test annulé puis modifié (corrigé)'}
    # Rouvrir reste réservé à l'admin (droit « tous les événements »).
    patch(vip, f'events?id=eq.{eid}', {'status': 'published'})
    assert row(admin, eid)['status'] == 'cancelled'
    assert patch(admin, f'events?id=eq.{eid}', {'status': 'published'}).json()[0]['status'] == 'published'


def test_someone_who_is_not_organizer_changes_nothing(people):
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test pas organisateur')
    assert post(admin, 'event_invites', {'event_id': eid, 'user_id': vip.uid}).status_code == 201
    assert patch(vip, f'events?id=eq.{eid}', {'title': 'Piraté'}).json() == []
    assert patch(vip, f'events?id=eq.{eid}', {'status': 'cancelled'}).json() == []
    assert delete(vip, f'events?id=eq.{eid}').json() == []
    assert post(vip, 'event_organizers', {'event_id': eid, 'user_id': vip.uid}).status_code in (401, 403)
    assert row(admin, eid) == {'status': 'published', 'title': 'Test pas organisateur'}


def test_a_draft_is_seen_by_its_author_only_and_can_be_deleted(people):
    admin, ga, vip, made = people
    r = post(vip, 'events', {'title': 'Test brouillon VIP', 'status': 'draft', **QUIET,
                             'starts_at': (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()})
    assert r.status_code == 201, r.text
    eid = r.json()[0]['id']
    made.append(eid)
    assert r.json()[0]['status'] == 'draft'
    assert post(vip, 'event_invites', {'event_id': eid, 'user_id': ga.uid}).status_code == 201
    assert row(ga, eid) is None  # invitée, mais rien tant que c'est un brouillon
    assert delete(vip, f'events?id=eq.{eid}').json()[0]['id'] == eid
    assert row(admin, eid) is None


def test_a_published_event_cannot_be_deleted_by_its_co_organizer(people):
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test suppression refusée')
    assert post(admin, 'event_organizers', {'event_id': eid, 'user_id': vip.uid}).status_code == 201
    assert delete(vip, f'events?id=eq.{eid}').json() == []
    assert row(admin, eid)['status'] == 'published'


def test_pending_then_approved_or_rejected(people):
    admin, ga, vip, made = people
    ids = []
    for title in ('Test proposition approuvée', 'Test proposition refusée'):
        r = post(admin, 'events', {'title': title, 'status': 'draft', **QUIET,
                                   'starts_at': (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()})
        eid = r.json()[0]['id']
        made.append(eid)
        sql = patch(admin, f'events?id=eq.{eid}', {'status': 'pending'})  # admin : le statut demandé est gardé
        assert sql.json()[0]['status'] == 'pending'
        ids.append(eid)
    assert vip.rpc('approve_event', e=ids[0]).status_code >= 400  # pas le droit de valider
    assert admin.rpc('approve_event', e=ids[0]).status_code == 204
    assert row(admin, ids[0])['status'] == 'published'
    assert admin.rpc('reject_event', e=ids[1], reason='Date déjà prise').status_code == 204
    assert row(admin, ids[1], 'status,rejection_reason') == {'status': 'rejected', 'rejection_reason': 'Date déjà prise'}


def test_fixing_the_date_of_a_poll_turns_votes_into_answers(people):
    admin, ga, vip, made = people
    eid = event(admin, made, 'Test sondage de dates', date_mode='poll', starts_at=None)
    for who in (ga, vip):
        assert post(admin, 'event_invites', {'event_id': eid, 'user_id': who.uid}).status_code == 201
    soon = datetime.now(timezone.utc) + timedelta(days=15)
    options = post(admin, 'date_options', [{'event_id': eid, 'starts_at': (soon + timedelta(days=i)).isoformat(), 'proposed_by': admin.uid}
                                           for i in range(2)])
    assert options.status_code == 201, options.text
    first = options.json()[0]['id']
    for who, vote in ((ga, 'yes'), (vip, 'if_needed')):
        r = post(who, 'date_votes', {'option_id': first, 'user_id': who.uid, 'vote': vote})
        assert r.status_code == 201, r.text
    assert vip.rpc('fix_event_date', e=eid, opt=first).status_code >= 400  # pas organisateur
    assert admin.rpc('fix_event_date', e=eid, opt=first).status_code == 204
    fixed = row(admin, eid, 'date_mode,starts_at')
    assert fixed['date_mode'] == 'fixed' and fixed['starts_at']
    answers = {r['user_id']: r['status'] for r in admin.get(f'rsvps?select=user_id,status&event_id=eq.{eid}').json()}
    assert answers[ga.uid] == 'yes' and answers[vip.uid] == 'maybe'
