"""Sécurité de la base (campagne du 14.11.2026), attaques POUR DE VRAI sur la base de TEST, avec la clé publique et de
vrais comptes de test : Bot Olga (rôle Organisateur) organise un événement « sur invitation » avec une adresse ; Bot Vera
(Membre) est invitée ; Bot Mia (Basic, sans droit de voir les événements) ne l'est pas. Chaque attaque doit être refusée.
Tout ce qui est créé est annulé puis effacé à la fin.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_securite_rls_live.py -q"""
import json
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
OLGA, VERA, MIA = '41790000103', '41790000106', '41790000110'
ADDRESS = 'Rue Secrète 7, 1950 Sion'
HAS_NODE = shutil.which('node') and (ROOT / 'web/events/node_modules/@supabase').exists()


def call(s: Session | None, method: str, path: str, body=None, prefer: str = 'return=representation') -> httpx.Response:
    headers = {**(s.headers if s else {'apikey': KEY_FILE.read_text().strip(), 'Content-Type': 'application/json'}), 'Prefer': prefer}
    return httpx.request(method, f'{TEST_URL}/rest/v1/{path}', headers=headers, json=body, timeout=30)


def new_event(s: Session, title: str, **fields) -> str:
    start = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    r = call(s, 'POST', 'events?select=id', {'title': title, 'status': 'published', 'visibility': 'invited',
                                            'notify_on_publish': False, 'starts_at': start, **fields})
    assert r.status_code == 201, r.text
    return r.json()[0]['id']


def drop_event(s: Session, e: str):
    call(s, 'PATCH', f'events?id=eq.{e}', {'status': 'cancelled'}, 'return=minimal')  # publié : annuler avant d'effacer
    call(s, 'DELETE', f'events?id=eq.{e}', prefer='return=minimal')


def refused(r: httpx.Response) -> bool:
    return r.status_code in (401, 403) or (r.status_code == 200 and r.json() in ([], None, {'enabled': False}))


@pytest.fixture(scope='module')
def world():
    olga, vera, mia = Session(OLGA), Session(VERA), Session(MIA)
    e = new_event(olga, '[Sécurité] Soirée privée', location_name='Chez Olga', location_address=ADDRESS, carpool_enabled=True)
    try:
        assert call(olga, 'POST', 'event_invites', {'event_id': e, 'user_id': vera.uid}, 'return=minimal').status_code == 201
        yield {'olga': olga, 'vera': vera, 'mia': mia, 'e': e}
    finally:
        drop_event(olga, e)


def test_an_outsider_never_reads_the_private_event_nor_its_address(world):
    mia, e = world['mia'], world['e']
    assert call(mia, 'GET', f'events?id=eq.{e}&select=id,location_address').json() == []
    assert refused(call(None, 'GET', f'events?id=eq.{e}&select=id,location_address'))
    for name, args in (('public_event', {'e': e}), ('event_guest_list', {'e': e}), ('calendar_feed_token', {'e': e, 'add': True}),
                       ('carpool', {'e': e})):
        r = mia.rpc(name, **args)
        assert refused(r) and ADDRESS not in r.text, (name, r.text)
    assert call(mia, 'GET', f'rsvps?event_id=eq.{e}').json() == []
    assert call(mia, 'GET', f'event_invites?event_id=eq.{e}').json() == []


def test_nobody_reads_phone_numbers_or_hidden_identity(world):
    for who in (world['mia'], world['vera'], None):
        for column in ('phone', 'first_name', 'last_name'):
            assert refused(call(who, 'GET', f'profiles?select=id,{column}&limit=3')), column
    assert refused(call(world['mia'], 'GET', 'event_phone_invites?select=*&limit=3'))


def test_nobody_answers_for_someone_else_nor_changes_his_answer(world):
    olga, vera, mia, e = world['olga'], world['vera'], world['mia'], world['e']
    assert call(vera, 'POST', 'rsvps', {'event_id': e, 'user_id': vera.uid, 'status': 'yes'}, 'return=minimal').status_code == 201
    try:
        assert call(mia, 'POST', 'rsvps', {'event_id': e, 'user_id': vera.uid, 'status': 'no'}).status_code == 403
        assert call(mia, 'POST', 'rsvps', {'event_id': e, 'user_id': mia.uid, 'status': 'yes'}).status_code == 403  # pas invitée
        assert call(mia, 'PATCH', f'rsvps?event_id=eq.{e}&user_id=eq.{vera.uid}', {'status': 'no'}).json() == []
        # L'organisateur lui-même passe par set_rsvp_for (tracé, la personne prévenue), jamais par la table.
        assert call(olga, 'PATCH', f'rsvps?event_id=eq.{e}&user_id=eq.{vera.uid}', {'status': 'no'}).json() == []
        assert mia.rpc('set_rsvp_for', event=e, member=vera.uid, answer='no').status_code == 403
        mine = call(vera, 'GET', f'rsvps?event_id=eq.{e}&user_id=eq.{vera.uid}&select=status').json()
        assert mine == [{'status': 'yes'}]
    finally:
        call(vera, 'DELETE', f'rsvps?event_id=eq.{e}&user_id=eq.{vera.uid}', prefer='return=minimal')


def test_nobody_votes_for_someone_else(world):
    olga, vera = world['olga'], world['vera']
    p = new_event(olga, '[Sécurité] Sondage de dates', date_mode='poll', starts_at=None)
    try:
        assert call(olga, 'POST', 'event_invites', {'event_id': p, 'user_id': vera.uid}, 'return=minimal').status_code == 201
        start = (datetime.now(timezone.utc) + timedelta(days=25)).isoformat()
        option = call(olga, 'POST', 'date_options?select=id', {'event_id': p, 'starts_at': start, 'proposed_by': olga.uid})
        assert option.status_code == 201, option.text
        o = option.json()[0]['id']
        assert call(olga, 'POST', 'date_votes', {'option_id': o, 'user_id': olga.uid, 'vote': 'yes'}, 'return=minimal').status_code == 201
        assert call(vera, 'POST', 'date_votes', {'option_id': o, 'user_id': olga.uid, 'vote': 'no'}).status_code == 403
        assert call(vera, 'PATCH', f'date_votes?option_id=eq.{o}&user_id=eq.{olga.uid}', {'vote': 'no'}).json() == []
        assert call(olga, 'GET', f'date_votes?option_id=eq.{o}&user_id=eq.{olga.uid}&select=vote').json() == [{'vote': 'yes'}]
    finally:
        drop_event(olga, p)


def test_nobody_gives_himself_a_right(world):
    mia, e = world['mia'], world['e']
    assert call(mia, 'PATCH', f'profiles?id=eq.{mia.uid}&select=id', {'role': 'admin'}).status_code == 403
    assert call(mia, 'POST', 'role_permissions', {'role': 'basic', 'perm': 'events.view'}).status_code in (401, 403)
    assert call(mia, 'POST', 'beta_testers', {'user_id': mia.uid}).status_code in (401, 403)
    assert mia.rpc('set_role_permission', target='basic', perm='events.view', granted=True).status_code == 403
    assert mia.rpc('set_beta_tester', member=mia.uid, enabled=True).status_code == 403
    assert call(mia, 'POST', 'event_organizers', {'event_id': e, 'user_id': mia.uid}).status_code == 403
    assert call(mia, 'POST', 'event_invites', {'event_id': e, 'user_id': mia.uid}).status_code == 403
    assert call(mia, 'POST', 'notifications', {'user_id': world['vera'].uid, 'kind': 'x', 'title': 't', 'body': 'b'}).status_code in (401, 403)


def test_a_staff_role_cannot_rename_someone_else(world):
    """Faille du 14.11 : « modifier son profil » ouvrait la ligne entière d'un autre compte aux rôles qui valident les
    membres (Organisateur compris) ; la garde ne contrôlait que le rôle et l'accès. Un espace en trop suffit à le montrer :
    la base l'efface (aucune donnée changée avant la correction), mais la demande doit être refusée."""
    olga, vera = world['olga'], world['vera']
    name = call(vera, 'GET', f'profiles?id=eq.{vera.uid}&select=display_name').json()[0]['display_name']
    r = call(olga, 'PATCH', f'profiles?id=eq.{vera.uid}&select=id', {'display_name': name + ' '})
    assert r.status_code == 403 and 'seule la personne' in r.text, r.text
    # La personne, elle, change toujours son surnom.
    assert call(vera, 'PATCH', f'profiles?id=eq.{vera.uid}&select=id', {'display_name': name + ' '}).status_code == 200


def test_the_organizer_approval_cannot_be_bypassed_and_a_guest_sees_numbers_never_names(world):
    olga, vera, mia, e = world['olga'], world['vera'], world['mia'], world['e']
    link = vera.rpc('create_event_invite', e=e, places=1)
    assert link.status_code == 200, link.text
    token = link.json()['token']
    try:
        r = mia.rpc('accept_invite', token=token, answer='yes')
        assert r.status_code == 200 and r.json()['pending'] is True and r.json()['location_address'] is None, r.text
        preview = mia.rpc('invite_preview', token=token, opened=False)
        assert preview.json()['state'] == 'waiting' and ADDRESS not in preview.text
        assert call(mia, 'GET', f'events?id=eq.{e}&select=id').json() == []
        assert call(mia, 'POST', 'rsvps', {'event_id': e, 'user_id': mia.uid, 'status': 'yes'}).status_code == 403
        assert mia.rpc('calendar_feed_token', e=e, add=True).status_code == 403
        assert mia.rpc('carpool_seek', e=e).status_code == 403
        for who in (mia, vera):  # ni la personne en attente, ni l'invité qui a créé le lien ne décident
            assert who.rpc('decide_join_request', e=e, person=mia.uid, accept=True).status_code == 403
        assert refused(call(mia, 'GET', 'event_join_requests?select=*'))
        # Vue de l'invité : les chiffres, jamais un nom ni un identifiant (pas même ceux venus par son propre lien).
        guest = vera.rpc('event_guest_list', e=e)
        assert guest.status_code == 200 and guest.json()['guest'] is True and guest.json()['people'] == []
        assert mia.uid not in guest.text and 'Bot Mia' not in guest.text and olga.uid not in guest.text, guest.text
        assert guest.json().get('requests', []) == []
    finally:
        vera.rpc('revoke_invite_link', tok=token)
        olga.rpc('decide_join_request', e=e, person=mia.uid, accept=False)


def test_the_carpool_is_for_participants_only(world):
    vera, mia, e = world['vera'], world['mia'], world['e']
    assert mia.rpc('carpool_seek', e=e).status_code == 403
    assert vera.rpc('carpool_seek', e=e).status_code == 403  # invitée, mais sans réponse Présent / Peut-être
    assert vera.rpc('carpool_drive', e=e, seats=3).status_code == 403
    assert refused(call(mia, 'GET', 'event_carpool?select=*'))


def test_private_tables_are_out_of_reach(world):
    for table in ('calendar_feeds', 'calendar_feed_events', 'event_tickets', 'push_tokens', 'event_join_requests', 'event_carpool'):
        assert refused(call(world['mia'], 'GET', f'{table}?select=*&limit=3')), table


def _listen(who: Session, table: str):
    path = ROOT / f'web/events/rt-secu-{table}.mjs'
    shutil.copy(ROOT / 'tests/supabase_live/realtime_leak_probe.mjs', path)
    p = subprocess.Popen(['node', path.name, TEST_URL, KEY_FILE.read_text().strip(), who.headers['Authorization'].split()[1], table],
                         cwd=path.parent, stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == 'READY'
    return p, path


def _received_live(world, actions) -> dict:
    """Mia écoute rsvps, event_invites et events SANS filtre pendant que les actions ont lieu : ce qu'elle reçoit de l'événement."""
    probes = [(t, *_listen(world['mia'], t)) for t in ('rsvps', 'event_invites', 'events')]
    try:
        time.sleep(3)  # abonnements établis côté serveur
        actions()
        return {t: [x for x in json.loads(p.communicate(timeout=30)[0].strip()) if world['e'] in json.dumps(x)] for t, p, _ in probes}
    finally:
        for _, p, path in probes:
            p.kill()
            path.unlink(missing_ok=True)


@pytest.mark.skipif(not HAS_NODE, reason='node et web/events/node_modules requis')
def test_an_outsider_receives_nothing_live_of_a_private_event(world):
    olga, vera, e = world['olga'], world['vera'], world['e']

    def actions():
        call(vera, 'POST', 'rsvps', {'event_id': e, 'user_id': vera.uid, 'status': 'maybe'}, 'return=minimal')
        call(vera, 'PATCH', f'rsvps?event_id=eq.{e}&user_id=eq.{vera.uid}', {'status': 'yes'}, 'return=minimal')
        assert call(olga, 'PATCH', f'events?id=eq.{e}', {'location_address': ADDRESS + ' (2e étage)'}, 'return=minimal').status_code == 204
    try:
        got = _received_live(world, actions)
    finally:
        call(vera, 'DELETE', f'rsvps?event_id=eq.{e}&user_id=eq.{vera.uid}', prefer='return=minimal')
    assert got == {'rsvps': [], 'event_invites': [], 'events': []}, got


@pytest.mark.skipif(not HAS_NODE, reason='node et web/events/node_modules requis')
@pytest.mark.xfail(strict=True, reason='Non corrigé (décision de l’admin) : le temps réel de Supabase envoie chaque '
                   'suppression (clé seule : event_id, user_id) à tout compte abonné, sans les règles d’accès.')
def test_a_withdrawal_is_not_broadcast_to_outsiders(world):
    olga, vera, e = world['olga'], world['vera'], world['e']
    call(vera, 'POST', 'rsvps', {'event_id': e, 'user_id': vera.uid, 'status': 'yes'}, 'return=minimal')

    def actions():
        call(vera, 'DELETE', f'rsvps?event_id=eq.{e}&user_id=eq.{vera.uid}', prefer='return=minimal')
        call(olga, 'DELETE', f'event_invites?event_id=eq.{e}&user_id=eq.{vera.uid}', prefer='return=minimal')
    try:
        got = _received_live(world, actions)
    finally:
        call(olga, 'POST', 'event_invites', {'event_id': e, 'user_id': vera.uid}, 'return=minimal')
    assert got['rsvps'] == [] and got['event_invites'] == [], got
