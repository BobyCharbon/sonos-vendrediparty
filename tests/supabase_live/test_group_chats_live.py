"""Discussions de groupe (avis n°10), sur la VRAIE base de test (jamais la prod) : messages, citations et
notifications, @tout réservé aux admins, suppression par un admin, épinglage, réactions, photos, non-membres exclus.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import time

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


@pytest.fixture(scope='module')
def chat():
    admin, a, b = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**a.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test discussion', 'created_by': a.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    for uid in (a.uid, b.uid):
        assert httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=a.headers, timeout=30,
                          json={'group_id': group, 'user_id': uid}).status_code == 201
    yield admin, a, b, group
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)


def post(s: Session, group: str, body: str, **extra) -> dict:
    r = httpx.post(f'{TEST_URL}/rest/v1/group_messages', timeout=30, headers={**s.headers, 'Prefer': 'return=representation'},
                   json={'group_id': group, 'body': body, **extra})
    assert r.status_code == 201, r.text
    return r.json()[0]


def chat_notes(s: Session, group: str) -> list[str]:
    rows = s.get(f"notifications?select=body,data&kind=eq.group_message&order=created_at").json()
    return [n['body'] for n in rows if n['data'].get('group_id') == group]


def test_mentions_notify_by_default_and_plain_messages_do_not(chat):
    admin, a, b, group = chat
    post(a, group, 'Salut tout le monde')
    post(a, group, '@Testeur 2 tu viens ?', mentions=[b.uid])
    assert chat_notes(b, group) == ['Testeur 1 : @Testeur 2 tu viens ?']  # seulement la citation
    reply_to = post(b, group, 'Oui !')
    post(a, group, 'Top', reply_to=reply_to['id'])
    assert chat_notes(b, group)[-1] == 'Testeur 1 : Top'  # une réponse compte comme une citation

    assert a.rpc('set_group_chat_notify', grp=group, level='all').status_code == 204
    post(b, group, 'Je ramène les chips')
    assert chat_notes(a, group)[-1] == 'Testeur 2 : Je ramène les chips'  # « tous les messages »
    a.rpc('set_group_chat_notify', grp=group, level='none')
    post(b, group, '@Testeur 1 hello', mentions=[a.uid])
    assert chat_notes(a, group)[-1] == 'Testeur 2 : Je ramène les chips'  # « rien » : même cité
    a.rpc('set_group_chat_notify', grp=group, level='mentions')


def test_everyone_tag_is_for_group_admins_only(chat):
    admin, a, b, group = chat
    msg = post(b, group, '@tout réunion !', mention_all=True)
    assert msg['mention_all'] is False  # Testeur 2 n'est pas admin du groupe
    before = len(chat_notes(b, group))
    assert post(a, group, '@tout ce soir 20h', mention_all=True)['mention_all'] is True  # le créateur l'est
    assert len(chat_notes(b, group)) == before + 1


def test_admin_deletion_pinning_and_promotion(chat):
    admin, a, b, group = chat
    msg = post(b, group, 'Message à supprimer')
    assert b.rpc('pin_group_message', msg=msg['id'], pin=True).status_code >= 400  # pas admin
    assert a.rpc('pin_group_message', msg=msg['id'], pin=True).status_code == 204
    assert a.rpc('delete_group_message', msg=msg['id']).status_code == 204
    row = b.get(f"group_messages?select=body,deleted_by_admin,deleted_at,pinned&id=eq.{msg['id']}").json()[0]
    assert row['body'] == '' and row['deleted_by_admin'] is True and row['deleted_at'] and row['pinned'] is False

    mine = post(b, group, 'Le mien')
    assert b.rpc('delete_group_message', msg=mine['id']).status_code == 204
    assert b.get(f"group_messages?select=deleted_by_admin&id=eq.{mine['id']}").json()[0]['deleted_by_admin'] is False
    other = post(a, group, 'Celui du créateur')
    assert b.rpc('delete_group_message', msg=other['id']).status_code >= 400

    assert b.rpc('set_group_admin', grp=group, member=b.uid, admin=True).status_code >= 400  # seul le créateur nomme
    assert a.rpc('set_group_admin', grp=group, member=b.uid, admin=True).status_code == 204
    assert b.rpc('pin_group_message', msg=other['id'], pin=True).status_code == 204  # admin désormais
    a.rpc('set_group_admin', grp=group, member=b.uid, admin=False)


def test_reactions_photos_and_outsiders(chat):
    admin, a, b, group = chat
    msg = post(a, group, 'Réagissez')
    r = httpx.post(f'{TEST_URL}/rest/v1/group_message_reactions', headers=b.headers, timeout=30,
                   json={'message_id': msg['id'], 'emoji': '👍'})
    assert r.status_code == 201, r.text
    assert a.get(f"group_message_reactions?select=emoji&message_id=eq.{msg['id']}").json() == [{'emoji': '👍'}]

    path = f'{group}/test-{int(time.time())}.jpg'
    up = httpx.post(f'{TEST_URL}/storage/v1/object/chat-photos/{path}', content=JPEG, timeout=30,
                    headers={**b.headers, 'Content-Type': 'image/jpeg'})
    assert up.status_code == 200, up.text
    photo = post(b, group, '', photo_path=path)
    assert photo['photo_path'] == path
    outsider = httpx.post(f'{TEST_URL}/storage/v1/object/chat-photos/{group}/intrus.jpg', content=JPEG, timeout=30,
                          headers={**admin.headers, 'Content-Type': 'image/jpeg'})
    assert outsider.status_code >= 400  # Admin test n'est pas dans le groupe
    assert admin.get(f'group_messages?select=id&group_id=eq.{group}').json() == []  # et ne lit rien
    r = httpx.post(f'{TEST_URL}/rest/v1/group_messages', headers=admin.headers, timeout=30, json={'group_id': group, 'body': 'intrus'})
    assert r.status_code >= 400

    chats = {c['id']: c for c in b.rpc('my_chats').json()}
    assert chats[group]['unread'] >= 1 and chats[group]['last'].startswith('Testeur 2 : ')
    b.rpc('mark_group_read', grp=group)
    assert {c['id']: c for c in b.rpc('my_chats').json()}[group]['unread'] == 0
    sql(f"update public.group_messages set created_at = now() - interval '91 days' where id = '{photo['id']}'")
    sql('select private.expire_chat_photos()')
    assert b.get(f"group_messages?select=photo_path&id=eq.{photo['id']}").json()[0]['photo_path'] is None  # 90 jours
