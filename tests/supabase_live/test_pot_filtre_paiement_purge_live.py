"""Contrôle Apple du 26.11, tour 3 (migration 20261126160000) sur la VRAIE base de TEST (jamais la prod) :
- profil de paiement du Pot commun : titulaire et note passent le filtre du pot (un texte refusé n'est pas enregistré) ;
- event_pay_info : IBAN, titulaire, liens et note de l'organisateur seulement en « On me paie », jamais en ligne ni sur place ;
- photos et vocaux de la discussion d'un événement (public.messages) effacés à 90 jours, comme groupes et directs.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_pot_filtre_paiement_purge_live.py -q"""
import json

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, complete_profile, create_event
from tests.supabase_live.test_event_tickets_live import answer
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def q(v):
    return "null" if v is None else "'" + str(v).replace("'", "''") + "'"


def keep_payment(uid):
    rows = sql(f"select iban, holder, links, note from public.tc_payment where user_id = '{uid}'")

    def restore():
        sql(f"delete from public.tc_payment where user_id = '{uid}'")
        for p in rows:
            sql("insert into public.tc_payment (user_id, iban, holder, links, note) values "
                f"('{uid}', {q(p['iban'])}, {q(p['holder'])}, '{json.dumps(p['links'] or {})}'::jsonb, {q(p['note'])})")
    return restore


def test_payment_holder_and_note_pass_the_filter():
    a = Session(GUEST_A)
    restore = keep_payment(a.uid)
    try:
        ok = a.rpc('tc_set_payment', pay_iban='', pay_holder='Léa Test', pay_links={}, pay_note='Merci !')
        assert ok.status_code in (200, 204), ok.text
        for holder, note in (('sale arabe', ''), ('Léa Test', 'sale arabe')):   # haine : refusé, rien d'enregistré
            r = a.rpc('tc_set_payment', pay_iban='', pay_holder=holder, pay_links={}, pay_note=note)
            assert r.status_code == 400 and 'content_refused' in r.text, r.text
        row = sql(f"select holder, note from public.tc_payment where user_id = '{a.uid}'")[0]
        assert row == {'holder': 'Léa Test', 'note': 'Merci !'}
        # Insulte : masquée, comme dans le pot.
        r = a.rpc('tc_set_payment', pay_iban='', pay_holder='Léa connard', pay_links={}, pay_note="t'es un connard")
        assert r.status_code in (200, 204), r.text
        row = sql(f"select holder, note from public.tc_payment where user_id = '{a.uid}'")[0]
        assert 'connard' not in row['holder'] and 'connard' not in row['note'] and '•' in row['note'], row
    finally:
        restore()


@pytest.fixture
def party():
    admin, a = Session(ADMIN), Session(GUEST_A)
    complete_profile(a, 'Guest A')
    restore = keep_payment(admin.uid)
    eid = create_event(admin, 'Test moyens de paiement montrés', visibility='invited', notify_on_publish=False, price_chf=20)
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': a.uid}, timeout=30)
        assert r.status_code == 201, r.text
        answer(a, eid, 'yes')
        sql(f"""insert into public.tc_payment (user_id, iban, holder, links, note) values
                ('{admin.uid}', 'CH9300762011623852957', 'Orga Test', '{{"revolut": "https://revolut.me/orga"}}'::jsonb, 'Merci')
                on conflict (user_id) do update set iban = excluded.iban, holder = excluded.holder, links = excluded.links,
                note = excluded.note""")
        yield admin, a, eid
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)
        restore()


def patch(admin, eid, **row):
    r = httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, json=row, timeout=30)
    assert r.status_code in (200, 204), r.text


def test_organizer_payment_details_only_for_on_me_paie(party):
    admin, a, eid = party
    info = a.rpc('event_pay_info', e=eid).json()
    assert info['mode'] == 'organizer' and info['iban'] == 'CH9300762011623852957' and info['holder'] == 'Orga Test'
    assert info['links'] == {'revolut': 'https://revolut.me/orga'} and info['note'] == 'Merci'
    for mode, url in (('online', 'https://billetterie.example.ch/x'), ('on_site', None)):
        patch(admin, eid, payment_mode=mode, payment_url=url)
        for who in (a, admin):
            info = who.rpc('event_pay_info', e=eid).json()
            assert info['mode'] == mode
            assert info['iban'] is None and info['holder'] is None and info['note'] is None and info['links'] == {}, info


def test_event_chat_photos_and_voices_expire_after_90_days():
    admin = Session(ADMIN)
    eid = create_event(admin, 'Test purge photos discussion', visibility='invited', notify_on_publish=False)
    try:
        rows = sql(f"""insert into public.messages (event_id, user_id, body, photo_path, audio_path, audio_seconds, created_at) values
              ('{eid}', '{admin.uid}', '', '{eid}/vieille.jpg', null, null, now() - interval '91 days'),
              ('{eid}', '{admin.uid}', '', null, '{eid}/vieux.m4a', 12, now() - interval '91 days'),
              ('{eid}', '{admin.uid}', 'légende', '{eid}/recente.jpg', null, null, now() - interval '10 days')
              returning id""")
        assert len(rows) == 3
        sql("select private.expire_chat_photos()")
        got = sql(f"select body, photo_path, audio_path, audio_seconds from public.messages where event_id = '{eid}' order by created_at, body")
        old = [r for r in got if r['photo_path'] is None and r['audio_path'] is None]
        assert sorted(r['body'] for r in old) == sorted(['📷 Photo expirée', '🎤 Message vocal expiré'])
        assert all(r['audio_seconds'] is None for r in old)
        assert [r['photo_path'] for r in got if r['body'] == 'légende'] == [f'{eid}/recente.jpg']
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)
