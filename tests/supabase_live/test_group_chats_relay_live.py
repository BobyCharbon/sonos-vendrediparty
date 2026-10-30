"""Relais des Discussions pour l'app native (app/group_chats.py), sur la VRAIE base de test (jamais la prod) :
liste, conversation mise en forme, envoi avec citation, photo, réaction ajoutée puis retirée, épinglage, lecture."""
import time

import httpx
import pytest

from app import accounts as accounts_mod, group_admin as ga, group_chats as gc
from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


@pytest.fixture(scope='module')
def relay():
    mp = pytest.MonkeyPatch()
    key = KEY_FILE.read_text().strip()
    for mod in (accounts_mod, ga, gc):
        mp.setattr(mod, 'SUPABASE_URL', TEST_URL, raising=False)
    mp.setattr(accounts_mod, 'SUPABASE_ANON_KEY', key)
    a, b = Session(GUEST_A), Session(GUEST_B)
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**a.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test relais natif', 'created_by': a.uid})
    group = r.json()[0]['id']
    for uid in (a.uid, b.uid):
        httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=a.headers, timeout=30, json={'group_id': group, 'user_id': uid})
    chats = gc.GroupChats(ga.GroupAdmin(accounts_mod.Accounts(b'secret', httpx.Client(timeout=30))))
    token = lambda s: s.headers['Authorization'].removeprefix('Bearer ')  # noqa: E731
    yield chats, token(a), token(b), group, b.uid
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)
    mp.undo()


def test_native_relay_end_to_end(relay):
    chats, ta, tb, group, b_uid = relay
    assert any(c['id'] == group for c in chats.chats(ta)['chats'])
    chats.send(ta, group, '@Testeur 2 tu viens ?', None, None)
    path = chats.upload_photo(tb, group, JPEG)['path']
    first = chats.conversation(tb, group)['messages'][0]
    chats.send(tb, group, 'Oui', first['id'], path)
    chats.react(tb, first['id'], '🔥', True)
    c = chats.conversation(ta, group)
    m1, m2 = c['messages']
    assert m1['body'] == '@Testeur 2 tu viens ?' and m1['mine'] and m1['reactions'] == [{'emoji': '🔥', 'count': 1, 'mine': False}]
    assert m2['reply'] == {'name': 'Testeur 1', 'text': '@Testeur 2 tu viens ?'} and m2['photo'].startswith(TEST_URL)
    assert httpx.get(m2['photo'], timeout=30).status_code == 200  # lien signé valable
    assert c['admin'] and c['can_name_admins'] and {m['name'] for m in c['members']} == {'Testeur 1', 'Testeur 2'}
    chats.react(tb, first['id'], '🔥', False)
    assert chats.conversation(ta, group)['messages'][0]['reactions'] == []
    chats.pin(ta, m2['id'], True)
    with pytest.raises(accounts_mod.AccountError):
        chats.pin(tb, m2['id'], False)  # Testeur 2 n'est pas admin
    chats.set_admin(ta, group, b_uid, True)
    assert chats.conversation(tb, group)['admin']
    chats.delete(ta, m2['id'])
    gone = chats.conversation(tb, group)['messages'][1]
    assert gone['deleted'] and gone['body'] == 'Message supprimé par un admin' and gone['photo'] is None
    before = next(c for c in chats.chats(tb)['chats'] if c['id'] == group)['unread']
    assert before >= 1
    chats.read(tb, group)
    time.sleep(0.5)
    assert next(c for c in chats.chats(tb)['chats'] if c['id'] == group)['unread'] == 0
    assert chats.notify(tb, group, 'none') == {'notify': 'none'}


def test_members_phone_is_shown_only_when_shared_in_this_group(relay):
    chats, ta, tb, group, b_uid = relay
    b = {m['id']: m for m in chats.conversation(ta, group)['members']}[b_uid]
    assert b['phone'] is None  # pas montré : invisible
    share = httpx.post(f'{TEST_URL}/rest/v1/rpc/set_group_phone_share', timeout=30, json={'grp': group, 'visible': True},
                       headers={'apikey': KEY_FILE.read_text().strip(), 'Authorization': f'Bearer {tb}', 'Content-Type': 'application/json'})
    assert share.status_code == 200, share.text
    b = {m['id']: m for m in chats.conversation(ta, group)['members']}[b_uid]
    assert b['phone'] == '+41790000002'  # montré dans ce groupe : appelable


M4A = b"\x00\x00\x00\x1cftypM4A \x00\x00\x00\x00M4A mp42isom" + b"\x00" * 64


def test_voice_message_and_reply_notify_like_a_mention(relay):
    chats, ta, tb, group, b_uid = relay
    first = chats.conversation(ta, group)['messages'][0]
    path = chats.upload_audio(tb, group, M4A)['path']
    chats.send(tb, group, '', first['id'], None, mentions=[], audio_path=path, audio_seconds=4.2,
               message_id='aaaaaaaa-bbbb-4ccc-8ddd-000000000001')
    voice = next(m for m in chats.conversation(ta, group)['messages'] if m['id'] == 'aaaaaaaa-bbbb-4ccc-8ddd-000000000001')
    assert voice['audio_seconds'] == 4.2 and voice['audio'].startswith(TEST_URL) and voice['reply']['name'] == 'Testeur 1'
    assert httpx.get(voice['audio'], timeout=30).status_code == 200  # lien d'écoute signé
    # Répondre (glisser) = citer : l'auteur du message est notifié, avec « 🎤 Message vocal ».
    key = KEY_FILE.read_text().strip()
    notes = httpx.get(f"{TEST_URL}/rest/v1/notifications?select=body,data&kind=eq.group_message&order=created_at.desc&limit=5",
                      headers={'apikey': key, 'Authorization': f'Bearer {ta}'}, timeout=30).json()
    assert any(n['body'] == 'Testeur 2 : 🎤 Message vocal' and n['data']['group_id'] == group for n in notes)
    last = next(c for c in chats.chats(tb)['chats'] if c['id'] == group)['last']
    assert last == 'Testeur 2 : 🎤 Message vocal'
    assert 'realtime' in chats.chats(tb) and chats.chats(tb)['realtime']['url'].startswith('wss://')
