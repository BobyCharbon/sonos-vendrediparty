"""Modération commune (4.11, Apple 1.2 / Google UGC) sur la VRAIE base de test (jamais la prod) : filtre (masque, refus,
contournements), Signaler (raison, copie, RLS, limite anti-abus), blocage commun (messages directs, mentions,
invitations, fiche, notifications), droit « Modérer les signalements », actions (masquer, avertir, suspendre, bannir
par identifiant de compte, lever), CGU (acceptation par version, exigence par l'admin).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_moderation_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def post(s: Session, table: str, body: dict) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/{table}', timeout=30, headers={**s.headers, 'Prefer': 'return=representation'}, json=body)


def unblock_all(*people: Session):
    ids = ",".join(f"'{p.uid}'" for p in people)
    sql(f"delete from public.direct_blocks where user_id in ({ids}) or blocked_id in ({ids})")


@pytest.fixture(scope='module')
def people():
    admin, a, b, c = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    for s, name in ((a, 'Testeur 1'), (b, 'Testeur 2')):
        s.set_nickname(name)
    unblock_all(a, b, c)
    sql(f"delete from public.content_reports where reporter_id in ('{a.uid}', '{b.uid}', '{c.uid}')")
    r = post(a, 'member_groups', {'name': 'Test modération', 'created_by': a.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]['id']
    assert post(a, 'member_group_members', {'group_id': group, 'user_id': b.uid}).status_code == 201
    yield admin, a, b, c, group
    unblock_all(a, b, c)
    sql("update private.moderation_settings set terms_enforced = false where id = 1")
    sql(f"update public.profiles set status = 'active' where id in ('{a.uid}', '{b.uid}') and status = 'banned'")
    sql(f"update public.moderation_sanctions set lifted_at = now() where user_id in ('{a.uid}', '{b.uid}') and lifted_at is null")
    sql(f"delete from public.content_reports where reporter_id in ('{a.uid}', '{b.uid}', '{c.uid}')")
    httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, timeout=30)


def say(s: Session, group: str, body: str, **extra) -> httpx.Response:
    return post(s, 'group_messages', {'group_id': group, 'body': body, **extra})


def test_a_one_word_insult_is_masked_and_hate_or_disguised_insults_are_refused(people):
    admin, a, b, c, group = people
    r = say(a, group, "t'es un vrai connard")
    assert r.status_code == 201, r.text
    assert r.json()[0]['body'] == "t'es un vrai •••••••"
    r = say(a, group, 'sale nègre')
    assert r.status_code == 400 and 'propos haineux' in r.json()['message']
    r = say(a, group, 's.a.l.o.p.e')
    assert r.status_code == 400 and r.json()['message'].startswith('content_refused:')
    assert say(a, group, 'On se retrouve chez Léa à 20 h, 079 123 45 67').status_code == 201  # numéro permis dans un message


def test_an_edit_goes_through_the_same_filter(people):
    admin, a, b, c, group = people
    msg = say(a, group, 'Bonne soirée').json()[0]['id']
    r = a.rpc('edit_group_message', msg=msg, new_body='bande de salopes')
    assert r.status_code in (200, 204), r.text
    assert sql(f"select body from public.group_messages where id = '{msg}'")[0]['body'] == 'bande de •••••••'


def test_nicknames_and_group_names_refuse_bad_words_links_and_numbers(people):
    admin, a, b, c, group = people
    for bad in ('Hurensohn', 's@l0pe', 'insta.com', '0791234567'):
        r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{a.uid}', headers=a.headers, json={'display_name': bad}, timeout=30)
        assert r.status_code == 400 and 'content_refused' in r.json()['message'], (bad, r.text)
    a.set_nickname('Testeur 1')
    r = httpx.patch(f'{TEST_URL}/rest/v1/member_groups?id=eq.{group}', headers=a.headers, json={'name': 'Les connards'}, timeout=30)
    assert r.status_code == 400
    assert a.rpc('moderation_check', p_text='Zicou', p_kind='name').json()['ok'] is True
    assert a.rpc('moderation_check', p_text='Fotze', p_kind='name').json()['category'] == 'sexuel'


def test_report_keeps_a_copy_is_private_to_the_reporter_and_never_self(people):
    admin, a, b, c, group = people
    msg = say(a, group, 'message à signaler').json()[0]['id']
    assert b.rpc('report_content', p_kind='group_message', p_target=msg, p_reason='harassment').status_code == 200
    again = b.rpc('report_content', p_kind='group_message', p_target=msg, p_reason='spam', p_comment='encore')
    assert again.status_code == 200  # même signalement ouvert : mis à jour, pas doublé
    mine = b.get(f'content_reports?select=reason,comment,snapshot,target_user&target_id=eq.{msg}').json()
    assert len(mine) == 1 and mine[0]['reason'] == 'spam' and mine[0]['snapshot']['text'] == 'message à signaler'
    assert mine[0]['target_user'] == a.uid and 'owner' not in mine[0]['snapshot']
    assert a.get(f'content_reports?select=id&target_id=eq.{msg}').json() == []  # l'auteur signalé ne voit rien
    assert a.rpc('report_content', p_kind='group_message', p_target=msg, p_reason='spam').status_code >= 400  # soi-même
    assert c.rpc('report_content', p_kind='group_message', p_target=msg, p_reason='spam').status_code >= 400  # pas dans le groupe
    assert b.rpc('report_content', p_kind='group_message', p_target=msg, p_reason='nimporte').status_code >= 400


def test_reporting_is_rate_limited(people):
    admin, a, b, c, group = people
    sql(f"delete from public.content_reports where reporter_id = '{c.uid}'")
    sql("insert into public.content_reports (reporter_id, target_kind, target_id, reason, status) "
        f"select '{c.uid}', 'profile', gen_random_uuid()::text, 'spam', 'dismissed' from generate_series(1, 10)")
    r = c.rpc('report_content', p_kind='profile', p_target=a.uid, p_reason='spam')
    assert r.status_code >= 400 and 'rate_limited' in r.json()['message']
    sql(f"delete from public.content_reports where reporter_id = '{c.uid}'")


def test_only_moderators_read_the_queue_and_moderators_are_notified(people):
    admin, a, b, c, group = people
    assert b.rpc('moderation_queue').status_code >= 400
    queue = admin.rpc('moderation_queue')
    assert queue.status_code == 200, queue.text
    assert any(x['reporter']['id'] == b.uid for x in queue.json())
    assert 'moderation.reports' in admin.rpc('my_permissions').json()
    note = sql(f"select count(*)::int n from public.notifications where user_id = '{admin.uid}' and kind = 'report_new'")
    assert note[0]['n'] >= 1


def test_hide_warn_suspend_ban_and_lift_by_account_identifier(people):
    admin, a, b, c, group = people
    msg = say(a, group, 'contenu limite').json()[0]['id']
    rid = b.rpc('report_content', p_kind='group_message', p_target=msg, p_reason='shocking').json()
    assert admin.rpc('moderation_act', p_report=rid, p_action='hide').status_code == 200
    row = sql(f"select body, deleted_at, deleted_by_admin from public.group_messages where id = '{msg}'")[0]
    assert row['body'] == '' and row['deleted_at'] and row['deleted_by_admin']
    assert b.get(f'content_reports?select=status&id=eq.{rid}').json()[0]['status'] == 'actioned'

    rid = b.rpc('report_content', p_kind='profile', p_target=a.uid, p_reason='harassment').json()
    assert admin.rpc('moderation_act', p_report=rid, p_action='warn', p_note='Reste correct').status_code == 200
    assert sql(f"select count(*)::int n from public.notifications where user_id = '{a.uid}' and kind = 'moderation_notice'")[0]['n'] >= 1
    assert a.get('moderation_sanctions?select=kind').json()[-1]['kind'] == 'warn'  # visible par la personne

    rid = b.rpc('report_content', p_kind='profile', p_target=a.uid, p_reason='harassment').json()
    assert admin.rpc('moderation_act', p_report=rid, p_action='suspend').status_code >= 400  # durée obligatoire
    assert admin.rpc('moderation_act', p_report=rid, p_action='suspend', p_days=3).status_code == 200
    assert sql(f"select status from public.profiles where id = '{a.uid}'")[0]['status'] == 'banned'
    assert say(a, group, 'je suis suspendu').status_code >= 400  # compte suspendu : plus rien
    sql(f"update public.moderation_sanctions set ends_at = now() - interval '1 minute' where user_id = '{a.uid}' and kind = 'suspend' and lifted_at is null")
    sql('select private.lift_expired_suspensions()')
    assert sql(f"select status from public.profiles where id = '{a.uid}'")[0]['status'] == 'active'

    rid = c.rpc('report_content', p_kind='profile', p_target=b.uid, p_reason='scam').json()
    assert admin.rpc('moderation_act', p_report=rid, p_action='ban').status_code == 200
    assert sql(f"select status from public.profiles where id = '{b.uid}'")[0]['status'] == 'banned'
    sql('select private.lift_expired_suspensions()')  # un bannissement ne s'arrête pas tout seul
    assert sql(f"select status from public.profiles where id = '{b.uid}'")[0]['status'] == 'banned'
    assert admin.rpc('moderation_lift', p_user=b.uid).status_code == 204
    assert sql(f"select status from public.profiles where id = '{b.uid}'")[0]['status'] == 'active'
    journal = sql(f"select action from public.member_audit where target in ('{a.uid}', '{b.uid}') and action like 'moderation.%' "
                  "order by id desc limit 10")
    assert {'moderation.hide', 'moderation.warn', 'moderation.suspend', 'moderation.ban', 'moderation.lift'} <= {j['action'] for j in journal}


def test_a_guest_without_the_right_cannot_act(people):
    admin, a, b, c, group = people
    rid = b.rpc('report_content', p_kind='profile', p_target=c.uid, p_reason='other').json()
    r = c.rpc('moderation_act', p_report=rid, p_action='dismiss')
    assert r.status_code >= 400 and 'modérateurs' in r.json()['message']
    assert admin.rpc('moderation_act', p_report=rid, p_action='dismiss').status_code == 200


def test_blocking_stops_direct_messages_mentions_invitations_notifications_and_the_card(people):
    admin, a, b, c, group = people
    unblock_all(a, b)
    assert a.rpc('set_block', target=b.uid, blocked=True).status_code == 204
    assert [x['id'] for x in a.rpc('my_blocks').json()] == [b.uid]
    assert b.rpc('blocked_with', target=a.uid).json() is True
    assert b.rpc('start_direct_chat', target=a.uid).status_code >= 400
    # Mention et notification : b cite a dans le groupe → citation retirée, a n'est pas prévenu.
    sql(f"insert into public.group_chat_settings (group_id, user_id, notify) values ('{group}', '{a.uid}', 'all') "
        "on conflict (group_id, user_id) do update set notify = 'all'")
    m = say(b, group, '@Testeur 1 coucou', mentions=[a.uid]).json()[0]
    assert m['mentions'] == []
    assert sql(f"select count(*)::int n from public.notifications where user_id = '{a.uid}' and data->>'message_id' = '{m['id']}'")[0]['n'] == 0
    # Invitation dans un groupe : refusée dans les deux sens.
    r = post(b, 'member_groups', {'name': 'Groupe de b', 'created_by': b.uid})
    other = r.json()[0]['id']
    try:
        r = b.rpc('invite_to_group', grp=other, member=a.uid)
        assert r.status_code >= 400 and 'inviter' in r.json()['message']
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/member_groups?id=eq.{other}', headers=b.headers, timeout=30)
    # Fiche : b (bloqué) ne voit plus que le surnom ; a voit qu'il a bloqué b.
    card = b.rpc('member_card', target=a.uid).json()
    assert card['restricted'] is True and card['groups'] == [] and card['phone'] is None
    assert a.rpc('member_card', target=b.uid).json()['blocked'] is True
    assert a.rpc('set_block', target=b.uid, blocked=False).status_code == 204
    assert b.rpc('member_card', target=a.uid).json().get('restricted') is None


def test_terms_are_accepted_per_version_and_enforced_when_the_admin_asks(people):
    admin, a, b, c, group = people
    sql(f"delete from public.terms_acceptances where user_id = '{a.uid}'")
    info = a.rpc('my_terms').json()
    assert info['accepted'] is False and info['version']
    assert b.rpc('set_moderation_settings', p_terms_enforced=True).status_code >= 400  # admins seulement
    assert admin.rpc('set_moderation_settings', p_terms_enforced=True).status_code == 200
    try:
        r = say(a, group, 'premier message')
        assert r.status_code >= 400 and 'terms_required' in r.json()['message']
        assert a.rpc('accept_terms', p_version='1999-01-01').status_code >= 400
        assert a.rpc('accept_terms', p_version=info['version']).json()['accepted'] is True
        assert say(a, group, 'premier message').status_code == 201
    finally:
        admin.rpc('set_moderation_settings', p_terms_enforced=False)
    anon = httpx.post(f'{TEST_URL}/rest/v1/rpc/moderation_public_info', headers={'apikey': a.key}, json={}, timeout=30)
    assert anon.status_code == 200 and anon.json()['terms_enforced'] is False
