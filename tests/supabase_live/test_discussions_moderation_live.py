"""Discussions v2 — modération (18.11, migration 20261118121000) sur la VRAIE base de TEST (jamais la prod) : preuve de la
photo signalée lisible des seuls modérateurs et partie avec le signalement, 10 messages précédents joints sur demande,
« Masquer » prévient l'auteur, invite_to_group (même réponse avec ou sans compte, 30 par jour, lien « direct »),
fichiers orphelins effacés (jamais un fichier encore désigné ni récent).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussions_moderation_live.py -q"""
import time
import uuid

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

JPEG = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


def post(s: Session, table: str, body: dict) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/{table}', timeout=30, headers={**s.headers, 'Prefer': 'return=representation'}, json=body)


def say(s: Session, group: str, body: str, **extra) -> dict:
    r = post(s, 'group_messages', {'group_id': group, 'body': body, **extra})
    assert r.status_code == 201, r.text
    return r.json()[0]


def upload(s: Session, group: str) -> str:
    path = f'{group}/{int(time.time() * 1000)}-{uuid.uuid4().hex[:10]}.jpg'
    up = httpx.post(f'{TEST_URL}/storage/v1/object/chat-photos/{path}', content=JPEG, timeout=30,
                    headers={**s.headers, 'Content-Type': 'image/jpeg'})
    assert up.status_code == 200, up.text
    return path


def stored(bucket: str, name: str) -> bool:
    return bool(sql(f"select 1 from storage.objects where bucket_id = '{bucket}' and name = '{name}'"))


def wait_until(check, seconds: float = 20) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return True
        time.sleep(1)
    return check()


def signed(s: Session, bucket: str, path: str) -> str | None:
    r = httpx.post(f'{TEST_URL}/storage/v1/object/sign/{bucket}', headers=s.headers, timeout=30,
                   json={'expiresIn': 60, 'paths': [path]})
    rows = r.json() if r.status_code == 200 else []
    return (rows[0].get('signedURL') if rows and isinstance(rows, list) else None) or None


@pytest.fixture(scope='module')
def people():
    admin, a, b, c = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    for s, name in ((a, 'Testeur 1'), (b, 'Testeur 2')):
        s.set_nickname(name)
    for s in (a, b, c):
        assert s.rpc('accept_terms', p_version=s.rpc('my_terms').json()['version']).status_code == 200
    ids = ",".join(f"'{p.uid}'" for p in (a, b, c))
    sql(f"delete from public.direct_blocks where user_id in ({ids}) or blocked_id in ({ids})")
    sql(f"delete from public.content_reports where reporter_id in ({ids})")
    sql(f"delete from private.group_invite_log where user_id in ({ids})")
    r = post(a, 'member_groups', {'name': 'Test modération v2', 'created_by': a.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    assert post(a, 'member_group_members', {'group_id': group, 'user_id': b.uid}).status_code == 201
    yield admin, a, b, c, group
    sql(f"delete from public.content_reports where reporter_id in ({ids})")
    sql(f"delete from private.group_invite_log where user_id in ({ids})")
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)


def test_a_reported_photo_is_kept_for_moderators_only_and_leaves_with_the_report(people):
    admin, a, b, c, group = people
    path = upload(b, group)
    msg = say(b, group, 'regarde', photo_path=path)
    rid = a.rpc('report_content', p_kind='group_message', p_target=msg['id'], p_reason='shocking').json()
    snap = sql(f"select snapshot from public.content_reports where id = '{rid}'")[0]['snapshot']
    evidence = snap['evidence']['photo']
    assert evidence == f"{rid}/photo-{path.split('/')[1]}"
    assert wait_until(lambda: stored('moderation-evidence', evidence)), 'copie de la preuve jamais arrivée'
    # L'auteur supprime son message : la photo quitte la conversation, la preuve reste.
    assert b.rpc('delete_group_message', msg=msg['id']).status_code in (200, 204)
    url = signed(admin, 'moderation-evidence', evidence)
    assert url and httpx.get(f'{TEST_URL}/storage/v1{url}', timeout=30).content == JPEG
    assert signed(a, 'moderation-evidence', evidence) is None   # le signaleur ne la lit pas
    assert signed(b, 'moderation-evidence', evidence) is None   # l'auteur non plus
    sql(f"delete from public.content_reports where id = '{rid}'")
    assert wait_until(lambda: not stored('moderation-evidence', evidence)), 'preuve restée après le signalement'


def test_the_ten_previous_messages_are_joined_only_when_asked(people):
    admin, a, b, c, group = people
    for i in range(12):
        say(a, group, f'm{i + 1}')
    target = say(b, group, 'la cible')
    plain = b.rpc('report_content', p_kind='group_message', p_target=say(a, group, 'autre')['id'], p_reason='spam').json()
    assert 'context' not in sql(f"select snapshot from public.content_reports where id = '{plain}'")[0]['snapshot']
    rid = a.rpc('report_content', p_kind='group_message', p_target=target['id'], p_reason='harassment', p_context=True)
    assert rid.status_code == 200, rid.text
    ctx = sql(f"select snapshot from public.content_reports where id = '{rid.json()}'")[0]['snapshot']['context']
    assert [m['text'] for m in ctx] == [f'm{i}' for i in range(3, 13)]
    assert {m['author'] for m in ctx} == {'Testeur 1'} and all(m['at'] for m in ctx)
    # Ancienne forme (4 paramètres nommés, vieilles apps) : toujours acceptée.
    old = b.rpc('report_content', p_kind='profile', p_target=a.uid, p_reason='spam', p_comment='vieux client')
    assert old.status_code == 200, old.text


def test_hiding_tells_the_author_why_and_how_to_appeal(people):
    admin, a, b, c, group = people
    msg = say(b, group, 'à masquer')
    rid = a.rpc('report_content', p_kind='group_message', p_target=msg['id'], p_reason='harassment').json()
    assert admin.rpc('moderation_act', p_report=rid, p_action='hide').status_code == 200
    note = sql(f"select title, body from public.notifications where user_id = '{b.uid}' and kind = 'content_hidden' "
               f"and dedupe_key = 'content_hidden:group_message:{msg['id']}'")
    assert len(note) == 1
    assert note[0]['body'].startswith('Ton message a été retiré : harcèlement') and 'contester' in note[0]['body']
    assert 'Testeur 1' not in note[0]['body']  # jamais qui a signalé
    allowed = sql("select private.web_push_allowed(n) ok from public.notifications n "
                  f"where user_id = '{b.uid}' and kind = 'content_hidden' limit 1")
    assert allowed[0]['ok'] is True


def test_invite_by_number_answers_the_same_with_or_without_an_account_and_is_capped(people):
    admin, a, b, c, group = people
    member_phone = sql(f"select phone from public.profiles where id = '{c.uid}'")[0]['phone']
    known = a.rpc('invite_to_group', grp=group, phone=member_phone)
    unknown = a.rpc('invite_to_group', grp=group, phone='41799999931')
    assert known.status_code == unknown.status_code == 200, (known.text, unknown.text)
    assert known.json() == unknown.json() == {'invited': 'phone'}
    sql(f"insert into private.group_invite_log (user_id) select '{a.uid}' from generate_series(1, 30)")
    capped = a.rpc('invite_to_group', grp=group, phone='41799999932')
    assert capped.status_code >= 400 and capped.json()['message'].startswith('limit:')
    sql(f"delete from private.group_invite_log where user_id = '{a.uid}'")
    sql(f"delete from private.group_invitations where group_id = '{group}'")


def test_inviting_a_member_needs_a_direct_link(people):
    admin, a, b, c, group = people
    if not sql("select to_regprocedure('private.dm_link(uuid,uuid)') is not null as ok")[0]['ok']:
        pytest.skip('private.dm_link absente (migration discussions_v2 pas encore appliquée sur TEST)')
    link = sql(f"select private.dm_link('{a.uid}', '{c.uid}') l")[0]['l']
    r = a.rpc('invite_to_group', grp=group, member=c.uid)
    if link == 'direct':
        assert r.status_code == 200 and r.json() == {'invited': 'member'}
    else:
        assert r.status_code >= 400 and r.json()['message'].startswith('link_required:')
    sql(f"delete from private.group_invitations where group_id = '{group}'")


def test_orphan_files_are_removed_but_never_a_used_or_recent_one(people):
    admin, a, b, c, group = people
    used, orphan, recent = upload(b, group), upload(b, group), upload(b, group)
    say(b, group, '', photo_path=used)
    sql("update storage.objects set created_at = now() - interval '2 hours' "
        f"where bucket_id = 'chat-photos' and name in ('{used}', '{orphan}')")
    sql("delete from private.chat_files_gc_runs")
    anon = {'apikey': a.headers['apikey'], 'Content-Type': 'application/json'}
    r = httpx.post(f'{TEST_URL}/rest/v1/rpc/chat_files_gc', headers=anon, json={}, timeout=60)
    assert r.status_code == 200, r.text
    assert r.json()['chat-photos'] >= 1
    assert wait_until(lambda: not stored('chat-photos', orphan)), 'fichier orphelin resté'
    assert stored('chat-photos', used) and stored('chat-photos', recent)
    again = httpx.post(f'{TEST_URL}/rest/v1/rpc/chat_files_gc', headers=anon, json={}, timeout=60)
    assert again.json() == {'skipped': True}  # au plus une fois toutes les 10 minutes


def test_deleting_an_account_also_queues_its_message_files():
    rows = sql("select tgname from pg_trigger where tgrelid = 'auth.users'::regclass and tgname = 'chat_files_of_account'")
    assert rows == [{'tgname': 'chat_files_of_account'}]
