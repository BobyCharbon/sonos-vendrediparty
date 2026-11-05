"""Parcours PARTICIPANT d'un événement, sur la VRAIE base de test (jamais la prod) : liste d'attente et montée
automatique, place gardée en attente quand on écrit un mot, accompagnant de plus en liste d'attente quand l'événement est complet
(la personne garde sa place, il monte à son rang), date limite, sondage de dates (voter puis changer), forum d'un événement public.
Événements « sur invitation » ou publics SANS annonce : seuls les comptes de test y répondent, aucun vrai membre prévenu.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_event_participant_live.py -q"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, create_event
from tests.supabase_live.test_event_tickets_live import answer
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture(scope='module')
def people():
    return Session(ADMIN), Session(GUEST_A), Session(GUEST_B)


@pytest.fixture()
def made(people):
    admin = people[0]
    ids: list[str] = []

    def make(title: str, **fields) -> str:
        eid = create_event(admin, title, public_link=True, reminders=[], **fields)
        ids.append(eid)
        return eid
    yield make
    for eid in ids:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def state(s: Session, eid: str) -> dict:
    rows = s.get(f'rsvps?select=user_id,status,waitlisted,plus_ones&event_id=eq.{eid}').json()
    return {r['user_id']: (r['status'], r['waitlisted'], r['plus_ones']) for r in rows}


def note(who: Session, eid: str, text: str) -> httpx.Response:
    return httpx.patch(f'{TEST_URL}/rest/v1/rsvps?event_id=eq.{eid}&user_id=eq.{who.uid}', headers=who.headers,
                       json={'note': text}, timeout=30)


def test_the_waitlist_moves_up_when_a_place_is_freed_and_the_person_is_told(people, made):
    admin, ga, gb = people
    eid = made('Test participant liste d’attente', max_participants=1, waitlist_enabled=True)
    answer(ga, eid, 'yes')
    answer(gb, eid, 'yes')
    assert state(admin, eid) == {ga.uid: ('yes', False, 0), gb.uid: ('yes', True, 0)}
    answer(ga, eid, 'no')  # changer d'avis libère la place
    assert state(admin, eid)[gb.uid] == ('yes', False, 0)
    told = gb.get(f'notifications?select=kind,body&event_id=eq.{eid}&kind=eq.waitlist').json()
    assert told and 'Tu es inscrit' in told[-1]['body']


def test_writing_a_note_keeps_the_place_in_the_waitlist(people, made):
    admin, ga, gb = people
    eid = made('Test participant ordre de la liste d’attente', max_participants=1, waitlist_enabled=True)
    answer(admin, eid, 'yes')          # place prise
    answer(ga, eid, 'yes')             # 1er en attente
    answer(gb, eid, 'yes')             # 2e en attente
    assert note(ga, eid, 'Je peux amener des chips').status_code in (200, 204)
    answer(admin, eid, 'no')           # la place se libère : elle revient au 1er arrivé, pas au dernier qui a écrit
    now = state(admin, eid)
    assert now[ga.uid] == ('yes', False, 0) and now[gb.uid] == ('yes', True, 0)


def extra(who: Session, eid: str, total: int) -> httpx.Response:
    """Comme l'app : le total d'accompagnants voulu dans plus_ones, 0 en attente (la base répartit)."""
    return httpx.patch(f'{TEST_URL}/rest/v1/rsvps?event_id=eq.{eid}&user_id=eq.{who.uid}', headers=who.headers,
                       json={'plus_ones': total, 'plus_ones_waitlisted': 0}, timeout=30)


def waiting_extras(s: Session, eid: str, who: Session) -> int:
    rows = s.get(f'rsvps?select=plus_ones_waitlisted&event_id=eq.{eid}&user_id=eq.{who.uid}').json()
    return rows[0]['plus_ones_waitlisted']


def test_an_extra_guest_waits_when_the_event_is_full_and_the_person_keeps_the_place(people, made):
    admin, ga, gb = people
    eid = made('Test participant accompagnant complet', max_participants=2, waitlist_enabled=True,
               allow_plus_ones=True, max_plus_ones=2)
    answer(admin, eid, 'yes')
    answer(ga, eid, 'yes')             # complet : 2 / 2
    assert extra(admin, eid, 1).status_code in (200, 204)
    # La personne garde sa place ; seul l'accompagnant attend (il ne compte pas comme présent).
    assert state(admin, eid) == {admin.uid: ('yes', False, 0), ga.uid: ('yes', False, 0)}
    assert waiting_extras(admin, eid, admin) == 1
    extra(admin, eid, 1)               # renvoyer « 1 confirmé, 0 en attente » ne fait pas sauter la file
    assert state(admin, eid)[admin.uid] == ('yes', False, 0) and waiting_extras(admin, eid, admin) == 1
    assert admin.rpc('event_attendance', ids=[eid]).json()[0]['going'] == 2  # pastille : confirmés seulement
    answer(ga, eid, 'no')              # une place se libère : l'accompagnant monte, et on est prévenu
    assert state(admin, eid)[admin.uid] == ('yes', False, 1) and waiting_extras(admin, eid, admin) == 0
    told = admin.get(f'notifications?select=body&event_id=eq.{eid}&kind=eq.waitlist').json()
    assert told and 'accompagnant est inscrit' in told[-1]['body']
    # Retirer un accompagnant reste toujours possible.
    assert extra(admin, eid, 0).status_code in (200, 204)
    assert state(admin, eid)[admin.uid] == ('yes', False, 0)


def test_extra_guests_and_people_share_one_queue_in_order_of_arrival(people, made):
    admin, ga, gb = people
    # Accompagnant arrivé AVANT la personne : il passe en premier.
    eid = made('Test participant rang accompagnant d’abord', max_participants=2, waitlist_enabled=True,
               allow_plus_ones=True, max_plus_ones=2)
    answer(admin, eid, 'yes')
    answer(ga, eid, 'yes')
    extra(admin, eid, 1)               # 1er dans la file
    answer(gb, eid, 'yes')             # 2e dans la file
    answer(ga, eid, 'no')
    now = state(admin, eid)
    assert now[admin.uid] == ('yes', False, 1) and now[gb.uid] == ('yes', True, 0)
    # Personne arrivée AVANT l'accompagnant : elle passe en premier, l'accompagnant attend encore.
    eid = made('Test participant rang personne d’abord', max_participants=2, waitlist_enabled=True,
               allow_plus_ones=True, max_plus_ones=2)
    answer(admin, eid, 'yes')
    answer(ga, eid, 'yes')
    answer(gb, eid, 'yes')             # 1re dans la file
    extra(admin, eid, 1)               # 2e dans la file
    answer(ga, eid, 'no')
    now = state(admin, eid)
    assert now[gb.uid] == ('yes', False, 0) and now[admin.uid] == ('yes', False, 0)
    assert waiting_extras(admin, eid, admin) == 1


def test_absent_from_the_card_drops_waiting_extra_guests_for_good(people, made):
    admin, ga, gb = people
    eid = made('Test participant absent vide l’attente', max_participants=2, waitlist_enabled=True,
               allow_plus_ones=True, max_plus_ones=2)
    answer(admin, eid, 'yes')
    answer(ga, eid, 'yes')             # complet
    extra(admin, eid, 1)               # accompagnant en attente
    answer(admin, eid, 'no')           # comme la carte de la liste : statut + plus_ones = 0, sans la colonne d'attente
    assert state(admin, eid)[admin.uid] == ('no', False, 0) and waiting_extras(admin, eid, admin) == 0
    answer(ga, eid, 'no')
    answer(admin, eid, 'yes')          # repasser Présent : l'accompagnant ne revient jamais
    assert state(admin, eid)[admin.uid] == ('yes', False, 0) and waiting_extras(admin, eid, admin) == 0


def test_a_waiting_person_moves_up_alone_when_only_one_place_is_freed(people, made):
    admin, ga, gb = people
    eid = made('Test participant monte seul', max_participants=2, waitlist_enabled=True,
               allow_plus_ones=True, max_plus_ones=2)
    answer(ga, eid, 'yes')
    answer(gb, eid, 'yes')             # complet
    answer(admin, eid, 'yes', plus_ones=1)   # en attente, avec son accompagnant
    assert state(admin, eid)[admin.uid] == ('yes', True, 1)
    answer(ga, eid, 'no')              # une seule place : la personne monte, son accompagnant attend
    assert state(admin, eid)[admin.uid] == ('yes', False, 0) and waiting_extras(admin, eid, admin) == 1
    answer(gb, eid, 'no')
    assert state(admin, eid)[admin.uid] == ('yes', False, 1) and waiting_extras(admin, eid, admin) == 0


def test_a_guest_has_no_extra_guest_even_if_asked(people, made):
    admin, ga, gb = people
    eid = made('Test participant Guest sans accompagnant', allow_plus_ones=True, max_plus_ones=2)
    answer(ga, eid, 'yes', plus_ones=2)
    assert state(admin, eid)[ga.uid] == ('yes', False, 0)


def test_after_the_deadline_the_answer_is_closed_for_the_participant(people, made):
    admin, ga, gb = people
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    eid = made('Test participant date limite', rsvp_deadline=past)
    r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=ga.headers, timeout=30,
                   json={'event_id': eid, 'user_id': ga.uid, 'status': 'yes'})
    assert r.status_code >= 400 and 'date limite' in r.text


def test_a_date_poll_vote_is_given_then_changed_then_withdrawn(people, made):
    admin, ga, gb = people
    eid = made('Test participant sondage de dates', date_mode='poll', starts_at=None)
    later = [(datetime.now(timezone.utc) + timedelta(days=d)).isoformat() for d in (20, 21)]
    r = httpx.post(f'{TEST_URL}/rest/v1/date_options', headers={**admin.headers, 'Prefer': 'return=representation'},
                   json=[{'event_id': eid, 'starts_at': t} for t in later], timeout=30)
    assert r.status_code == 201, r.text
    first = r.json()[0]['id']
    up = {**ga.headers, 'Prefer': 'resolution=merge-duplicates'}
    for v in ('yes', 'if_needed'):
        r = httpx.post(f'{TEST_URL}/rest/v1/date_votes', headers=up, json={'option_id': first, 'user_id': ga.uid, 'vote': v}, timeout=30)
        assert r.status_code in (200, 201), r.text
    assert [v['vote'] for v in ga.get(f'date_votes?option_id=eq.{first}&user_id=eq.{ga.uid}').json()] == ['if_needed']
    httpx.delete(f'{TEST_URL}/rest/v1/date_votes?option_id=eq.{first}&user_id=eq.{ga.uid}', headers=ga.headers, timeout=30)
    assert ga.get(f'date_votes?option_id=eq.{first}&user_id=eq.{ga.uid}').json() == []
    # Un Guest propose une autre date (members_can_propose_dates) : elle s'ajoute au sondage.
    r = httpx.post(f'{TEST_URL}/rest/v1/date_options', headers=ga.headers, timeout=30,
                   json={'event_id': eid, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=22)).isoformat(), 'proposed_by': ga.uid})
    assert r.status_code == 201, r.text


def test_a_guest_writes_in_the_forum_of_a_public_event(people, made):
    admin, ga, gb = people
    eid = made('Test participant forum public')
    answer(ga, eid, 'yes')
    r = httpx.post(f'{TEST_URL}/rest/v1/messages', headers=ga.headers, timeout=30,
                   json={'event_id': eid, 'user_id': ga.uid, 'body': 'Message de test (participant)'})
    assert r.status_code == 201, r.text
    assert [m['body'] for m in gb.get(f'messages?select=body&event_id=eq.{eid}').json()] == ['Message de test (participant)']


def test_a_maybe_or_absent_answer_is_never_on_the_waitlist(people, made):
    admin, ga, gb = people
    eid = made('Test participant peut-être jamais en attente', max_participants=1, waitlist_enabled=True)
    answer(admin, eid, 'yes')
    answer(ga, eid, 'yes')             # en attente
    answer(ga, eid, 'maybe')
    answer(gb, eid, 'no')
    now = state(admin, eid)
    assert now[ga.uid] == ('maybe', False, 0) and now[gb.uid] == ('no', False, 0)


NEWCOMER = '41768163120'  # Guest au profil vide (code fixe de la base de test) ; recréé à la connexion suivante


def test_a_deleted_account_leaves_no_answer_vote_or_message_behind(people, made):
    admin, ga, gb = people
    who = Session(NEWCOMER)
    eid = made('Test participant compte supprimé')
    poll = made('Test participant compte supprimé (sondage)', date_mode='poll', starts_at=None)
    r = httpx.post(f'{TEST_URL}/rest/v1/date_options', headers={**admin.headers, 'Prefer': 'return=representation'}, timeout=30,
                   json={'event_id': poll, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=25)).isoformat()})
    option = r.json()[0]['id']
    answer(who, eid, 'yes')
    assert httpx.post(f'{TEST_URL}/rest/v1/date_votes', headers=who.headers, timeout=30,
                      json={'option_id': option, 'user_id': who.uid, 'vote': 'yes'}).status_code == 201
    assert httpx.post(f'{TEST_URL}/rest/v1/messages', headers=who.headers, timeout=30,
                      json={'event_id': eid, 'user_id': who.uid, 'body': 'Message avant suppression'}).status_code == 201
    assert who.rpc('delete_my_account').status_code in (200, 204)
    assert admin.get(f'rsvps?select=user_id&user_id=eq.{who.uid}').json() == []
    assert admin.get(f'date_votes?select=user_id&user_id=eq.{who.uid}').json() == []
    assert admin.get(f'messages?select=id&user_id=eq.{who.uid}').json() == []
    assert admin.get(f'profiles?select=id&id=eq.{who.uid}').json() == []
    assert who.uid not in {p['id'] for p in admin.rpc('admin_member_list').json()}
