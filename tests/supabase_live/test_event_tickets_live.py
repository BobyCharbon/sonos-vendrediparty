"""Billets QR et pastille des présents, sur la VRAIE base de test (jamais la prod) : chaque présent a son billet,
seul l'organisateur (ou un admin) le scanne, l'arrivée n'est notée qu'une fois, « payé » se coche à la main, et la
pastille compte juste même quand la liste des participants est cachée.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_event_tickets_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, complete_profile, create_event
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


def answer(who: Session, event: str, status: str, plus_ones: int = 0):
    """Réponse comme dans l'app : modifier la sienne (seuls status, plus_ones, note sont modifiables), sinon la créer."""
    r = httpx.patch(f'{TEST_URL}/rest/v1/rsvps?event_id=eq.{event}&user_id=eq.{who.uid}', timeout=30,
                    headers={**who.headers, 'Prefer': 'return=representation'}, json={'status': status, 'plus_ones': plus_ones})
    assert r.status_code == 200, r.text
    if not r.json():
        r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', timeout=30, headers=who.headers,
                       json={'event_id': event, 'user_id': who.uid, 'status': status, 'plus_ones': plus_ones})
        assert r.status_code == 201, r.text


@pytest.fixture(scope='module')
def party():
    admin, a, b = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    complete_profile(a, 'Guest A')
    complete_profile(b, 'Guest B')
    eid = create_event(admin, 'Test billets QR', public_link=True, price_chf=20, allow_plus_ones=True, max_plus_ones=2,
                       tickets_enabled=True)
    answer(a, eid, 'yes')
    answer(admin, eid, 'yes', plus_ones=1)  # un Guest n'a pas droit aux accompagnants : l'admin vient à deux
    answer(b, eid, 'maybe')
    assert admin.rpc('issue_all_event_tickets', e=eid).json() == 2  # billets remis (20261104233000)
    yield admin, a, b, eid
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def ticket(who: Session, eid: str) -> dict:
    r = who.rpc('my_event_ticket', e=eid)
    assert r.status_code == 200, r.text
    return r.json()


def test_a_present_guest_gets_a_personal_unguessable_ticket_and_others_none(party):
    admin, a, b, eid = party
    mine = ticket(a, eid)
    assert mine['state'] == 'ok' and len(mine['token']) == 64 and len(mine['code']) == 6
    assert mine['plus_ones'] == 0 and mine['paid'] is False
    assert ticket(admin, eid)['plus_ones'] == 1 and mine['checked_in_at'] is None
    assert ticket(a, eid)['token'] == mine['token']  # le même billet à chaque ouverture
    assert ticket(b, eid) == {'state': 'none'}  # peut-être : pas de billet
    # La table reste fermée : personne ne lit les jetons directement, pas même un admin.
    assert b.get(f'event_tickets?event_id=eq.{eid}').status_code in (401, 403)
    assert admin.get(f'event_tickets?event_id=eq.{eid}').status_code in (401, 403)


def test_only_the_organizer_scans_and_the_second_scan_says_already(party):
    admin, a, b, eid = party
    token = ticket(a, eid)['token']
    refused = b.rpc('check_in_ticket', e=eid, scanned=token)
    assert refused.status_code >= 400 and 'organisateurs' in refused.text
    first = admin.rpc('check_in_ticket', e=eid, scanned=token).json()
    assert first['result'] == 'ok'
    person = first['person']
    assert person['user_id'] == a.uid and person['display_name'] == 'Guest A' and person['plus_ones'] == 0
    assert person['price_chf'] == 20 and person['paid'] is False and person['checked_in_at']
    assert 'token' not in person
    again = admin.rpc('check_in_ticket', e=eid, scanned=token).json()
    assert again['result'] == 'already' and again['person']['checked_in_at'] == person['checked_in_at']
    assert ticket(a, eid)['checked_in_at'] == person['checked_in_at']  # le billet de A affiche « arrivé »


def test_short_code_unknown_tickets_and_tickets_of_another_event(party):
    admin, a, b, eid = party
    code = ticket(a, eid)['code']
    assert admin.rpc('check_in_ticket', e=eid, scanned=code.lower()).json()['result'] == 'already'
    assert admin.rpc('check_in_ticket', e=eid, scanned='0' * 64).json() == {'result': 'unknown'}
    assert admin.rpc('check_in_ticket', e=eid, scanned='nimporte quoi').json() == {'result': 'unknown'}
    other = create_event(admin, 'Test autre soirée')
    try:
        r = admin.rpc('check_in_ticket', e=other, scanned=ticket(a, eid)['token']).json()
        assert r == {'result': 'other_event', 'event_title': 'Test billets QR'}
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{other}', headers=admin.headers, timeout=30)


def test_paid_is_ticked_by_hand_and_the_entry_list_shows_arrivals(party):
    admin, a, b, eid = party
    assert b.rpc('set_ticket_paid', e=eid, member=a.uid, is_paid=True).status_code >= 400
    assert admin.rpc('set_ticket_paid', e=eid, member=a.uid, is_paid=True).json()['paid'] is True
    assert ticket(a, eid)['paid'] is True
    answer(b, eid, 'yes')
    rows = admin.rpc('event_checkins', e=eid).json()
    assert rows[0]['user_id'] == a.uid and rows[0]['checked_in_at']  # arrivés d'abord, puis attendus
    assert {r['user_id'] for r in rows[1:]} == {admin.uid, b.uid} and all(r['checked_in_at'] is None for r in rows[1:])
    assert b.rpc('event_checkins', e=eid).status_code >= 400
    # Arrivée à la main, puis retirée.
    assert admin.rpc('set_ticket_arrival', e=eid, member=b.uid, arrived=True).json()['checked_in_at']
    assert admin.rpc('set_ticket_arrival', e=eid, member=b.uid, arrived=False).json()['checked_in_at'] is None


def test_a_renewed_ticket_kills_the_old_qr_and_absent_people_are_refused(party):
    admin, a, b, eid = party
    answer(b, eid, 'yes')
    assert admin.rpc('issue_event_ticket', e=eid, member=b.uid, issued=True).json()['issued'] is True
    old = ticket(b, eid)['token']
    new = b.rpc('renew_event_ticket', e=eid).json()
    assert new['state'] == 'ok' and new['token'] != old
    assert admin.rpc('check_in_ticket', e=eid, scanned=old).json() == {'result': 'unknown'}
    assert a.rpc('renew_event_ticket', e=eid, member=b.uid).status_code >= 400  # pas le billet d'un autre
    answer(b, eid, 'no')
    r = admin.rpc('check_in_ticket', e=eid, scanned=new['token']).json()
    assert r['result'] == 'not_registered' and r['person']['status'] == 'no'
    assert ticket(b, eid) == {'state': 'none'}


def test_the_badge_counts_everyone_but_shows_faces_only_to_who_may_see_them(party):
    admin, a, b, eid = party
    answer(b, eid, 'maybe')
    row = a.rpc('event_attendance', ids=[eid]).json()[0]
    assert (row['going'], row['maybe'], row['waitlist']) == (3, 1, 0)  # A, l'admin et son accompagnant ; B peut-être
    assert [f['id'] for f in row['faces']] == [a.uid, admin.uid] and row['faces'][0]['name'] == 'Guest A'
    httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, json={'show_participants': False}, timeout=30)
    try:
        hidden = b.rpc('event_attendance', ids=[eid]).json()[0]
        assert (hidden['going'], hidden['maybe']) == (3, 1) and hidden['faces'] == []
        assert admin.rpc('event_attendance', ids=[eid]).json()[0]['faces']  # l'admin voit toujours qui vient
    finally:
        httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, json={'show_participants': True}, timeout=30)


def notes(who: Session, eid: str, kind: str) -> list:
    return who.get(f'notifications?select=id,body,data&event_id=eq.{eid}&kind=eq.{kind}&order=created_at').json()


def sql_test(query: str) -> list:
    """SELECT sur la base de TEST (API de gestion, rôle propriétaire : la règle des notifications est privée)."""
    from pathlib import Path
    token = Path.home() / '.config/supabase-claude/token'
    if not token.exists():
        pytest.skip('jeton de gestion Supabase absent')
    r = httpx.post('https://api.supabase.com/v1/projects/ewromqfsmcqsthftyhzm/database/query', timeout=60,
                   headers={'Authorization': f'Bearer {token.read_text().strip()}', 'User-Agent': 'party-claude'}, json={'query': query})
    assert r.status_code in (200, 201), r.text
    return r.json()


def test_friends_payment_declared_then_confirmed_with_switchable_notifications(party):
    admin, a, b, eid = party
    answer(b, eid, 'yes')
    before = admin.rpc('tc_my_payment').json()
    assert admin.rpc('tc_set_payment', pay_iban='CH9300762011623852957', pay_holder='Admin Test',
                     pay_links={'twint': '+41790000004'}, pay_note=None).status_code in (200, 204)
    try:
        info = b.rpc('event_pay_info', e=eid).json()
        assert info['amount'] == 20 and info['iban'] == 'CH9300762011623852957' and info['links'] == {'twint': '+41790000004'}
        assert info['organizer_id'] == admin.uid and info['reference'] == 'Party · Test billets QR'
        # Seulement aux présents : un peut-être ne voit pas l'IBAN.
        answer(b, eid, 'maybe')
        assert b.rpc('event_pay_info', e=eid).json() is None
        assert b.rpc('declare_ticket_payment', e=eid, declared=True).status_code >= 400
        answer(b, eid, 'yes')

        mine = b.rpc('declare_ticket_payment', e=eid, declared=True).json()
        assert mine['pay_pending'] is True and mine['paid'] is False
        assert b.rpc('declare_ticket_payment', e=eid, declared=True).json()['pay_pending'] is True  # 2e appui : rien de plus
        told = notes(admin, eid, 'ticket_pay_declared')
        assert len(told) == 1 and 'dit avoir payé sa place (20 CHF)' in told[0]['body'] and told[0]['data']['member'] == b.uid
        row = next(r for r in admin.rpc('event_checkins', e=eid).json() if r['user_id'] == b.uid)
        assert row['pay_pending'] is True

        assert a.rpc('confirm_ticket_payment', e=eid, member=b.uid, received=True).status_code >= 400  # pas l'organisateur
        refused = admin.rpc('confirm_ticket_payment', e=eid, member=b.uid, received=False).json()
        assert refused['paid'] is False and refused['pay_pending'] is False
        assert "n'a pas reçu ton paiement" in notes(b, eid, 'ticket_pay_confirmed')[-1]['body']

        assert b.rpc('declare_ticket_payment', e=eid, declared=True).json()['pay_pending'] is True
        assert len(notes(admin, eid, 'ticket_pay_declared')) == 2  # nouvelle déclaration : nouvelle notification
        ok = admin.rpc('confirm_ticket_payment', e=eid, member=b.uid, received=True).json()
        assert ok['paid'] is True and ok['pay_pending'] is False
        assert ticket(b, eid)['paid'] is True and ticket(b, eid)['pay_pending'] is False
        last = notes(b, eid, 'ticket_pay_confirmed')[-1]
        assert 'a bien reçu ton paiement' in last['body']

        # Chaque notification a son interrupteur, respecté par la règle commune à tous les canaux (ici celle que reçoit
        # l'organisateur ; un compte Guest ne reçoit pas de notifications d'événement, règle déjà en place).
        def allowed(note_id: str) -> bool:
            return sql_test(f"select private.web_push_allowed(n) as ok from public.notifications n where id = '{note_id}'")[0]['ok']

        def prefs(**values):
            r = httpx.patch(f'{TEST_URL}/rest/v1/notification_prefs?user_id=eq.{admin.uid}', headers=admin.headers, timeout=30, json=values)
            assert r.status_code in (200, 204), r.text
        was = admin.get(f'notification_prefs?select=push_enabled&user_id=eq.{admin.uid}').json()[0]['push_enabled']
        declared = notes(admin, eid, 'ticket_pay_declared')[-1]['id']
        try:
            prefs(push_enabled=True, ticket_pay_declared=True)
            assert allowed(declared) is True
            prefs(ticket_pay_declared=False)
            assert allowed(declared) is False
        finally:
            prefs(push_enabled=was, ticket_pay_declared=True)
    finally:
        admin.rpc('tc_set_payment', pay_iban=before.get('iban') or '', pay_holder=before.get('holder') or '',
                  pay_links=before.get('links') or {}, pay_note=before.get('note'))


def test_a_free_event_has_no_payment(party):
    admin, a, b, eid = party
    free = create_event(admin, 'Test gratuit', public_link=True)
    try:
        answer(a, free, 'yes')
        assert a.rpc('event_pay_info', e=free).json() is None
        assert a.rpc('declare_ticket_payment', e=free, declared=True).status_code >= 400
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{free}', headers=admin.headers, timeout=30)
