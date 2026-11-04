"""Messages directs (décision de l'admin du 4.11), sur la VRAIE base de test (jamais la prod) : une seule conversation par
paire même en parallèle, confidentialité vis-à-vis d'un tiers, d'un Admin et de Root, qui peut écrire à qui (groupe en
commun ou numéro dans ses contacts), blocage, pas d'@annonce, notification « Nouveau message de X » et son interrupteur.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_direct_messages_live.py -q"""
import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP
from tests.supabase_live.test_member_admin_live import ROOT_ID, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


def as_user(uid: str, query: str) -> list:
    """Requête faite comme cette personne connectée (rôle authenticated, règles RLS appliquées) : sert pour Root, dont
    le numéro est réel (jamais de vrai SMS dans les tests)."""
    claims = json.dumps({"sub": uid, "role": "authenticated"})
    return sql(f"begin; set local role authenticated; set local request.jwt.claims to '{claims}'; {query}; commit;")


def forget_pair(x: str, y: str):
    sql(f"delete from public.direct_chats where user_a = least('{x}'::uuid, '{y}'::uuid) and user_b = greatest('{x}'::uuid, '{y}'::uuid)")


@pytest.fixture(scope='module')
def people():
    admin, a, b, c = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    for s, name in ((a, 'Testeur 1'), (b, 'Testeur 2')):
        s.set_nickname(name)
    forget_pair(a.uid, b.uid)
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**a.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test messages directs', 'created_by': a.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    assert httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers=a.headers, timeout=30,
                      json={'group_id': group, 'user_id': b.uid}).status_code == 201
    yield admin, a, b, c
    forget_pair(a.uid, b.uid)
    forget_pair(a.uid, c.uid)
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)


def start(s: Session, target: str, **extra) -> httpx.Response:
    return s.rpc('start_direct_chat', target=target, **extra)


def post(s: Session, chat: str, body: str, **extra) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/direct_messages', timeout=30, headers={**s.headers, 'Prefer': 'return=representation'},
                      json={'chat_id': chat, 'body': body, **extra})


@pytest.fixture(scope='module')
def chat(people):
    admin, a, b, c = people
    r = start(a, b.uid)
    assert r.status_code == 200, r.text
    return r.json()


def test_one_conversation_per_pair_even_when_both_start_at_once(people):
    admin, a, b, c = people
    forget_pair(a.uid, b.uid)
    with ThreadPoolExecutor(8) as pool:
        ids = list(pool.map(lambda s: start(s, (b if s is a else a).uid), [a, b] * 4))
    assert all(r.status_code == 200 for r in ids), [r.text for r in ids]
    assert len({r.json() for r in ids}) == 1
    rows = sql(f"select count(*)::int n from public.direct_chats where user_a = least('{a.uid}'::uuid, '{b.uid}'::uuid) "
               f"and user_b = greatest('{a.uid}'::uuid, '{b.uid}'::uuid)")
    assert rows[0]['n'] == 1
    assert start(a, a.uid).status_code >= 400  # pas de conversation avec soi-même


def test_the_conversation_shows_up_only_after_the_first_message_and_mixes_with_groups(people, chat):
    admin, a, b, c = people
    assert chat not in [x['id'] for x in a.rpc('my_chats').json()]  # ouverte mais vide : pas encore dans la liste
    assert post(a, chat, 'Salut, ça va ?').status_code == 201
    mine = {x['id']: x for x in a.rpc('my_chats').json()}
    theirs = {x['id']: x for x in b.rpc('my_chats').json()}
    assert mine[chat]['kind'] == 'direct' and mine[chat]['name'] == 'Testeur 2' and mine[chat]['user_id'] == b.uid
    assert mine[chat]['last'] == 'Toi : Salut, ça va ?' and mine[chat]['unread'] == 0
    assert theirs[chat]['name'] == 'Testeur 1' and theirs[chat]['last'] == 'Salut, ça va ?' and theirs[chat]['unread'] >= 1
    assert theirs[chat]['admin'] is False
    assert any(x['kind'] == 'group' for x in theirs.values())  # groupes et messages directs dans la même liste
    order = [x['last_at'] or '' for x in b.rpc('my_chats').json()]
    assert order[:len([o for o in order if o])] == sorted([o for o in order if o], reverse=True)  # dernier message en haut
    assert b.rpc('mark_direct_read', chat=chat).status_code == 204
    assert {x['id']: x for x in b.rpc('my_chats').json()}[chat]['unread'] == 0


def test_nobody_else_reads_it_not_even_an_admin_or_root(people, chat):
    admin, a, b, c = people
    assert post(b, chat, 'Secret entre nous').status_code == 201
    up = httpx.post(f'{TEST_URL}/storage/v1/object/chat-photos/{chat}/test-dm.jpg', timeout=30,
                    headers={**a.headers, 'Content-Type': 'image/jpeg', 'x-upsert': 'true'}, content=JPEG)
    assert up.status_code == 200, up.text
    assert b.get(f'direct_messages?select=id&chat_id=eq.{chat}').json()  # l'autre personne lit
    for outsider in (c, admin):
        assert outsider.get(f'direct_messages?select=id&chat_id=eq.{chat}').json() == []
        assert outsider.get(f'direct_chats?select=id&id=eq.{chat}').json() == []
        assert chat not in [x['id'] for x in outsider.rpc('my_chats').json()]
        assert outsider.rpc('direct_chat_people', chat=chat).json() == []
        assert post(outsider, chat, 'Je m’incruste').status_code >= 400
        signed = httpx.post(f'{TEST_URL}/storage/v1/object/sign/chat-photos/{chat}/test-dm.jpg', headers=outsider.headers,
                            json={'expiresIn': 60}, timeout=30)
        assert signed.status_code >= 400
        assert outsider.rpc('mark_direct_read', chat=chat).status_code == 204  # sans effet
        assert outsider.rpc('set_direct_chat_notify', chat=chat, level='none').status_code >= 400
    # Root (lit toutes les discussions de groupe) : rien des messages directs, ni messages, ni liste, ni photo.
    seen = as_user(ROOT_ID, f"select (select count(*) from public.direct_messages where chat_id = '{chat}')::int msgs, "
                            f"(select count(*) from public.direct_chats where id = '{chat}')::int chats, "
                            f"(select count(*) from storage.objects where bucket_id = 'chat-photos' and name like '{chat}/%')::int photos, "
                            f"position('{chat}' in public.my_chats()::text) listed, "
                            f"jsonb_array_length(public.group_chat_people('{chat}')) people")
    assert seen == [{'msgs': 0, 'chats': 0, 'photos': 0, 'listed': 0, 'people': 0}]
    httpx.request('DELETE', f'{TEST_URL}/storage/v1/object/chat-photos', headers=a.headers, timeout=30,
                  json={'prefixes': [f'{chat}/test-dm.jpg']})


def test_writing_needs_to_know_the_person_group_event_or_contact(people):
    admin, a, b, c = people
    forget_pair(a.uid, c.uid)
    knows = sql(f"select private.dm_knows('{a.uid}', '{c.uid}') k")[0]['k']
    if knows:
        pytest.skip('Testeur 1 et VIP test ont déjà un groupe ou un événement en commun sur la base de test')
    assert start(a, c.uid).status_code >= 400
    assert start(a, c.uid, contact_hash='0' * 64).status_code >= 400  # empreinte fausse
    good = sql(f"select encode(extensions.hmac('+' || p.phone, k.key, 'sha256'), 'hex') h "
               f"from public.profiles p, private.contact_key k where p.id = '{c.uid}' and k.id = 1")[0]['h']
    r = start(a, c.uid, contact_hash=good)  # le numéro de VIP test est dans les contacts de Testeur 1
    assert r.status_code == 200, r.text
    assert start(c, a.uid).json() == r.json()  # une fois ouverte, l'autre peut répondre
    forget_pair(a.uid, c.uid)


def test_no_announcement_or_everyone_tag_and_only_the_author_deletes(people, chat):
    admin, a, b, c = people
    r = post(a, chat, '@annonce @tout rendez-vous', pinned=True)
    assert r.status_code == 201, r.text
    msg = r.json()[0]
    assert msg['pinned'] is False
    assert post(a, chat, 'x', mention_all=True).status_code >= 400  # pas de colonne @tout dans un message direct
    assert b.rpc('pin_direct_message', msg=msg['id'], pin=True).status_code == 204  # épingler : les deux personnes
    assert c.rpc('pin_direct_message', msg=msg['id'], pin=False).status_code >= 400
    assert b.rpc('delete_direct_message', msg=msg['id']).status_code >= 400  # pas l'auteur
    assert admin.rpc('delete_direct_message', msg=msg['id']).status_code >= 400
    assert a.rpc('delete_direct_message', msg=msg['id']).status_code == 204
    assert b.get(f"direct_messages?select=body,deleted_at&id=eq.{msg['id']}").json()[0]['body'] == ''


def dm_notes(s: Session, chat: str) -> list[dict]:
    rows = s.get('notifications?select=id,title,body,data&kind=eq.direct_message&order=created_at').json()
    return [n for n in rows if n['data'].get('chat_id') == chat]


def test_notification_new_message_from_x_with_its_own_switch_and_the_chats_pause(people, chat):
    admin, a, b, c = people
    assert post(b, chat, 'Tu viens ce soir ?').status_code == 201
    note = dm_notes(a, chat)[-1]
    assert note['title'] == 'Nouveau message de Testeur 2' and note['body'] == 'Tu viens ce soir ?'
    assert note['data']['group_id'] == chat and note['data']['direct'] is True  # le toucher ouvre la conversation
    assert dm_notes(c, chat) == [] and dm_notes(admin, chat) == []

    def allowed() -> bool:
        return sql(f"select private.web_push_allowed(n) ok from public.notifications n where n.id = '{note['id']}'")[0]['ok']

    sql(f"insert into public.notification_prefs (user_id) values ('{a.uid}') on conflict do nothing; "
        f"update public.notification_prefs set push_enabled = true where user_id = '{a.uid}'")
    assert allowed() is True
    patch = httpx.patch(f'{TEST_URL}/rest/v1/notification_prefs?user_id=eq.{a.uid}', headers=a.headers, timeout=30,
                        json={'direct_messages': False})
    assert patch.status_code in (200, 204), patch.text
    assert allowed() is False  # interrupteur « Messages directs » coupé : aucun canal
    httpx.patch(f'{TEST_URL}/rest/v1/notification_prefs?user_id=eq.{a.uid}', headers=a.headers, timeout=30,
                json={'direct_messages': True})
    assert allowed() is True

    assert a.rpc('set_notification_pause', what='chats', span='30m').status_code == 200
    assert sql(f"select private.push_paused('{a.uid}', 'direct_message') p")[0]['p'] is True  # pause des Discussions
    a.rpc('set_notification_pause', what='chats', span='off')

    before = len(dm_notes(a, chat))
    assert a.rpc('set_direct_chat_notify', chat=chat, level='none').status_code == 204  # sourdine de la conversation
    post(b, chat, 'Encore moi')
    assert len(dm_notes(a, chat)) == before
    a.rpc('set_direct_chat_notify', chat=chat, level='all')


def test_blocking_stops_messages_both_ways(people, chat):
    admin, a, b, c = people
    assert a.rpc('set_direct_block', target=b.uid, blocked=True).status_code == 204
    assert post(b, chat, 'Coucou').status_code >= 400
    assert post(a, chat, 'Coucou').status_code >= 400
    assert {x['id']: x for x in a.rpc('my_chats').json()}[chat]['blocked'] is True
    assert b.get(f'direct_blocks?select=user_id').json() == []  # la personne bloquée ne le voit pas
    assert b.get(f'direct_messages?select=id&chat_id=eq.{chat}').json()  # l'historique reste lisible
    assert a.rpc('set_direct_block', target=b.uid, blocked=False).status_code == 204
    assert post(b, chat, 'Re').status_code == 201
