"""Discussions de groupe (avis n°10), sur la VRAIE base de test (jamais la prod) : messages, citations et
notifications, @tout selon le groupe, @annonce et organisateurs, suppression par un admin, épinglage, réactions, photos, non-membres exclus.
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
    for uid in (b.uid,):  # le créateur (Testeur 1) en fait partie d'office
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


def set_broadcasts(s: Session, on: bool):
    r = httpx.patch(f'{TEST_URL}/rest/v1/notification_prefs?user_id=eq.{s.uid}', headers=s.headers, timeout=30,
                    json={'group_broadcasts': on})
    assert r.status_code in (200, 204), r.text


def test_everyone_tag_follows_the_group_choice(chat):
    """@tout (réponse de l'admin du 3.11) : chaque groupe choisit, par ses admins : tous les membres (défaut) ou
    admins et organisateurs ; chacun est notifié selon son réglage du groupe et peut couper « Annonces et @tout »."""
    admin, a, b, group = chat
    before = len(chat_notes(a, group))
    assert post(b, group, '@tout réunion !', mention_all=True)['mention_all'] is True  # défaut : tous les membres
    assert len(chat_notes(a, group)) == before + 1
    set_broadcasts(a, False)  # Réglages › Notifications : « Annonces et @tout des groupes » coupé
    post(b, group, '@tout encore', mention_all=True)
    assert len(chat_notes(a, group)) == before + 1
    set_broadcasts(a, True)
    a.rpc('set_group_chat_notify', grp=group, level='none')
    post(b, group, '@tout toujours', mention_all=True)
    assert len(chat_notes(a, group)) == before + 1  # « rien » pour ce groupe : pas de notification
    a.rpc('set_group_chat_notify', grp=group, level='mentions')

    assert b.rpc('set_group_everyone_tag', grp=group, who='staff').status_code >= 400  # Testeur 2 n'est pas admin
    assert a.rpc('set_group_everyone_tag', grp=group, who='staff').status_code == 204
    assert a.get(f'member_groups?select=everyone_tag&id=eq.{group}').json()[0]['everyone_tag'] == 'staff'
    assert post(b, group, '@tout réservé', mention_all=True)['mention_all'] is False
    assert post(a, group, '@tout de l’admin', mention_all=True)['mention_all'] is True
    assert a.rpc('set_group_organizer', grp=group, member=b.uid, organizer=True).status_code == 204
    assert post(b, group, '@tout organisateur', mention_all=True)['mention_all'] is True
    a.rpc('set_group_organizer', grp=group, member=b.uid, organizer=False)
    a.rpc('set_group_everyone_tag', grp=group, who='all')


def test_announcements_are_for_admins_and_organizers_and_notify_everyone(chat):
    """@annonce (réponses de l'admin du 3.11) : admins et organisateurs ; épinglée, annonce, notifiée à tout le groupe ;
    d'un simple membre, un message normal ; retirée par les admins et les organisateurs."""
    admin, a, b, group = chat
    plain = post(b, group, '@annonce de Testeur 2', pinned=True, announcement=True)
    assert plain['pinned'] is False and plain['announcement'] is False  # simple membre : message normal
    assert b.rpc('set_group_organizer', grp=group, member=b.uid, organizer=True).status_code >= 400  # pas admin
    assert a.rpc('set_group_organizer', grp=group, member=b.uid, organizer=True).status_code == 204
    assert [o['user_id'] for o in b.get(f'group_organizers?select=user_id&group_id=eq.{group}').json()] == [b.uid]
    before = len(chat_notes(a, group))
    msg = post(b, group, '@annonce Rendez-vous samedi 18h')
    assert msg['pinned'] is True and msg['announcement'] is True and msg['mention_all'] is True
    assert chat_notes(a, group)[-1] == 'Testeur 2 : 📣 @annonce Rendez-vous samedi 18h' and len(chat_notes(a, group)) == before + 1
    assert post(b, group, 'Pas une @annonces ni mail@annonce.ch')['announcement'] is False  # mot entier seulement
    assert post(b, group, 'Hé @ANNONCE !')['announcement'] is True  # sans casse
    normal = post(b, group, 'Rien de spécial')
    assert b.rpc('pin_group_message', msg=normal['id'], pin=True).status_code >= 400  # épingler : admins seulement
    assert b.rpc('pin_group_message', msg=msg['id'], pin=False).status_code == 204  # l'organisateur retire l'annonce
    assert b.get(f"group_messages?select=pinned,announcement&id=eq.{msg['id']}").json()[0] == {'pinned': False, 'announcement': False}
    again = post(a, group, '@annonce bis')
    assert a.rpc('delete_group_message', msg=again['id']).status_code == 204
    assert b.get(f"group_messages?select=pinned,announcement&id=eq.{again['id']}").json()[0] == {'pinned': False, 'announcement': False}
    a.rpc('set_group_organizer', grp=group, member=b.uid, organizer=False)
    third = post(a, group, '@annonce ter')
    assert b.rpc('pin_group_message', msg=third['id'], pin=False).status_code >= 400  # plus organisateur : ne retire plus
    # Pas de modification directe des colonnes (aucun droit d'écriture UPDATE sur la table).
    patch = httpx.patch(f"{TEST_URL}/rest/v1/group_messages?id=eq.{normal['id']}", headers=b.headers, timeout=30, json={'announcement': True})
    assert patch.status_code >= 400 or b.get(f"group_messages?select=announcement&id=eq.{normal['id']}").json()[0]['announcement'] is False


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


def test_group_creator_is_a_member_and_admin_from_the_start():
    """Réponse de l'admin du 3.11 : « si c'est toi qui crées le groupe alors tu es dedans d'office en tant que
    Créateur - Admin » (Réglages › Groupes comme Discussions)."""
    a = Session(GUEST_A)
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', timeout=30, headers={**a.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Test créateur membre', 'created_by': a.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    try:
        assert [m['user_id'] for m in a.get(f'member_group_members?select=user_id&group_id=eq.{group}').json()] == [a.uid]
        chat = next(c for c in a.rpc('my_chats').json() if c['id'] == group)
        assert chat['member'] is True and chat['admin'] is True and chat['creator'] is True
        again = httpx.post(f'{TEST_URL}/rest/v1/member_group_members', headers={**a.headers, 'Prefer': 'resolution=ignore-duplicates'},
                           timeout=30, json={'group_id': group, 'user_id': a.uid})
        assert again.status_code in (200, 201, 409)  # l'app qui l'ajoute aussi ne casse rien
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)
