"""« Ça me garde un message en non lu alors que je suis allé sur la conversation » (admin, 19.11.2026), recette RÉELLE du
web : base de TEST, vrai navigateur, connexion normale de l'Admin de test ; GUEST_B écrit (en base). Pour un message
direct, un groupe et une discussion d'événement :
  * un message attend : la ligne de la liste dit « 1 non lu » ;
  * l'Admin ouvre la conversation depuis la liste ; pendant qu'elle est ouverte, un DEUXIÈME message arrive (à l'écran) ;
  * retour à la liste : plus aucun non-lu sur la ligne, et la base dit 0 (chat_list de l'Admin).
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de TEST> python -m pytest
tests/supabase_live/test_discussions_lu_browser_live.py -q"""
import re

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_B
from tests.supabase_live.test_bar_soiree_browser_live import browser, party, pw, shot, signed_in_page  # noqa: F401
from tests.supabase_live.test_member_admin_live import pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = live
FAST = 15000
TABLES = {'direct': ('direct_messages', 'chat_id'), 'group': ('group_messages', 'group_id'), 'event': ('messages', 'event_id')}


def uid(phone: str) -> str:
    return sql(f"select id::text id from public.profiles where phone = '{phone}'")[0]['id']


def listed(me: str, chat: str) -> dict:
    """La ligne de chat_list telle que l'Admin la reçoit (même transaction : identité de l'Admin)."""
    rows = sql(f"select set_config('request.jwt.claims', json_build_object('sub', '{me}', 'role', 'authenticated')::text, true); "
               "set local role authenticated; "
               f"select x ->> 'unread' unread, x ->> 'marked_unread' marked from jsonb_array_elements(public.chat_list(true)) x "
               f"where x ->> 'id' = '{chat}'")
    return rows[0]


def write(kind: str, chat: str, author: str, body: str) -> None:
    table, col = TABLES[kind]
    sql(f"insert into public.{table} ({col}, user_id, body) values ('{chat}', '{author}', '{body}')")


def test_a_conversation_read_on_the_web_leaves_no_unread_in_the_list(browser, party):  # noqa: F811
    a, b = uid(ADMIN), uid(GUEST_B)
    sql("insert into public.terms_acceptances (user_id, version) select x, (select terms_version from private.moderation_settings "
        f"where id = 1) from unnest(array['{a}', '{b}']::uuid[]) x on conflict do nothing")
    low, high = sorted([a, b])
    sql(f"delete from public.direct_chats where user_a = '{low}' and user_b = '{high}'")
    chats = {
        'direct': sql(f"insert into public.direct_chats (user_a, user_b, created_by, status) values ('{low}', '{high}', '{a}', 'active') "
                      "returning id::text id")[0]['id'],
        'group': sql(f"insert into public.member_groups (name, created_by) values ('[LU] Bande web', '{a}') returning id::text id")[0]['id'],
        'event': sql("insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by, forum_enabled) "
                     f"values ('[LU] Soirée web', 'published', 'invited', false, now() + interval '2 days', '{a}', true) "
                     "returning id::text id")[0]['id'],
    }
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{chats['group']}', '{a}'), ('{chats['group']}', '{b}') "
        "on conflict do nothing")
    sql(f"insert into public.event_invites (event_id, user_id) values ('{chats['event']}', '{b}') on conflict do nothing")
    # Discussion d'événement : Présent / Peut-être et organisation seulement (migration 20261119120000).
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{chats['event']}', '{b}', 'yes') "
        "on conflict (event_id, user_id) do update set status = 'yes'")
    b_name = sql(f"select display_name from public.profiles where id = '{b}'")[0]['display_name']
    names = {'direct': f'Message direct {b_name}', 'group': 'Discussion [LU] Bande web', 'event': 'Événement [LU] Soirée web'}
    errors: list = []
    context = None
    try:
        for kind in chats:
            write(kind, chats[kind], b, f'Premier {kind}')
        context, page = signed_in_page(browser, ADMIN, party, chats['event'], errors)
        for kind, chat in chats.items():
            page.goto(f'{party}/events/chats')
            row = page.locator(f'[aria-label^="{names[kind]}, 1 non lu"]:visible').first
            pw.expect(row).to_be_visible(timeout=30000)
            shot(page, f'lu-{kind}-1-liste')
            row.click()
            pw.expect(page.locator(f':text-is("Premier {kind}"):visible').first).to_be_visible(timeout=FAST)
            # Conversation ouverte : un deuxième message arrive, à l'écran sans recharger.
            write(kind, chat, b, f'Deuxième {kind}')
            pw.expect(page.locator(f':text-is("Deuxième {kind}"):visible').first).to_be_visible(timeout=FAST)
            page.wait_for_timeout(1500)
            shot(page, f'lu-{kind}-2-conversation')
            page.go_back()
            line = page.locator(f'[aria-label^="{names[kind]}"]:visible').first
            pw.expect(line).to_be_visible(timeout=FAST)
            pw.expect(line).not_to_have_attribute('aria-label', re.compile('non lu'), timeout=FAST)
            shot(page, f'lu-{kind}-3-retour-liste')
            assert listed(a, chat) == {'unread': '0', 'marked': 'false'}, kind
        assert not errors, errors
    finally:
        if context:
            context.close()
        sql(f"delete from public.direct_chats where id = '{chats['direct']}'")
        sql(f"delete from public.member_groups where id = '{chats['group']}'")
        sql(f"delete from public.events where id = '{chats['event']}'")
