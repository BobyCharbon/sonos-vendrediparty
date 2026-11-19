"""« Ça me garde un message en non lu alors que je suis allé sur la conversation » (admin, 19.11.2026, app iPhone BETA),
sur la VRAIE base de TEST, comptes de test ADMIN (A, comme l’admin qui a signalé le bug) et GUEST_B, les trois sortes de discussion (message direct, groupe,
discussion d'événement) :
  B écrit à A ; A a aussi « Marquer comme non lu » ; la liste (chat_list), la pastille de l'onglet (chat_badge) et le
  compteur de la fiche (event_chat_prefs_get) comptent le message.
  Chemin de l'app iPhone : la liste précharge la conversation (/api/account/chats/open avec prefetch : rien n'est lu),
  puis A l'ouvre. L'app d'avant ne marquait lu que si l'ouverture apportait un message INCONNU du téléphone : préchargée,
  la conversation restait non lue (reproduit ci-dessous). Ouvrir = /api/account/chats/read (groupe, direct) ou
  mark_event_chat_read / event-chat/read (événement), comme le fait désormais l'app à chaque ouverture.
  Chemin du web : les fonctions que GroupChat.tsx appelle (mark_direct_read, mark_group_read, mark_event_chat_read).
  Après la lecture : 0 non lu, plus de « non lu » manuel, pastille diminuée d'autant, compteur de la fiche à 0.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussions_lu_live.py -q"""
import httpx
import pytest

from app import accounts as accounts_mod, group_admin as ga, group_chats as gc
from app.event_chats import EventChats
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_B
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


@pytest.fixture(scope='module')
def world():
    mp = pytest.MonkeyPatch()
    for mod in (accounts_mod, ga, gc):
        mp.setattr(mod, 'SUPABASE_URL', TEST_URL, raising=False)
    mp.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    a, b = Session(ADMIN), Session(GUEST_B)
    sql("insert into public.terms_acceptances (user_id, version) select x, (select terms_version from private.moderation_settings "
        f"where id = 1) from unnest(array['{a.uid}', '{b.uid}']::uuid[]) x on conflict do nothing")
    low, high = sorted([a.uid, b.uid])
    sql(f"delete from public.direct_chats where user_a = '{low}' and user_b = '{high}'")
    direct = sql(f"insert into public.direct_chats (user_a, user_b, created_by, status) values ('{low}', '{high}', '{a.uid}', 'active') "
                 "returning id::text id")[0]['id']
    group = sql(f"insert into public.member_groups (name, created_by) values ('[LU] Bande', '{a.uid}') returning id::text id")[0]['id']
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{group}', '{a.uid}'), ('{group}', '{b.uid}') "
        "on conflict do nothing")
    event = sql("insert into public.events (title, status, visibility, notify_on_publish, starts_at, created_by, forum_enabled) "
                f"values ('[LU] Soirée', 'published', 'invited', false, now() + interval '2 days', '{a.uid}', true) returning id::text id")[0]['id']
    sql(f"insert into public.event_invites (event_id, user_id) values ('{event}', '{b.uid}') on conflict do nothing")
    # Discussion d'événement : Présent / Peut-être et organisation seulement (migration 20261119120000).
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{b.uid}', 'yes') on conflict (event_id, user_id) do update set status = 'yes'")
    chats = gc.GroupChats(ga.GroupAdmin(accounts_mod.Accounts(b'secret', httpx.Client(timeout=30))))
    token = a.headers['Authorization'].removeprefix('Bearer ')
    yield {'a': a, 'b': b, 'token': token, 'chats': chats, 'events': EventChats(chats),
           'direct': direct, 'group': group, 'event': event}
    sql(f"delete from public.direct_chats where id = '{direct}'")
    sql(f"delete from public.member_groups where id = '{group}'")
    sql(f"delete from public.events where id = '{event}'")
    sql(f"delete from public.chat_list_state where chat_id in ('{direct}', '{group}', '{event}')")
    mp.undo()


def b_writes(w, kind: str) -> None:
    b, target = w['b'].uid, w[kind]
    table, col = {'direct': ('direct_messages', 'chat_id'), 'group': ('group_messages', 'group_id'), 'event': ('messages', 'event_id')}[kind]
    sql(f"insert into public.{table} ({col}, user_id, body) values ('{target}', '{b}', 'Tu viens ce soir ?')")


def row(w, kind: str) -> dict:
    r = w['a'].rpc('chat_list', include_archived=True)
    assert r.status_code == 200, r.text
    return next(c for c in r.json() if c['id'] == w[kind])


def badge(w) -> int:
    r = w['a'].rpc('chat_badge')
    assert r.status_code == 200, r.text
    return r.json()


def unread_and_marked(w, kind: str) -> None:
    """B écrit ; A marque aussi la discussion « non lue » à la main (pastille de la liste)."""
    b_writes(w, kind)
    assert w['a'].rpc('set_chat_state', kind=kind, chat=w[kind], unread=True).status_code == 200
    r = row(w, kind)
    assert r['unread'] >= 1 and r['marked_unread'], r


def read_everywhere(w, kind: str, before: int) -> None:
    r = row(w, kind)
    assert r['unread'] == 0 and not r['marked_unread'], r
    assert badge(w) == before - 1
    if kind == 'event':
        prefs = w['a'].rpc('event_chat_prefs_get', e=w['event']).json()
        assert prefs['unread'] == 0, prefs  # compteur de la discussion sur la fiche


@pytest.mark.parametrize('kind', ['direct', 'group'])
def test_iphone_a_prefetched_conversation_is_read_when_opened(world, kind):
    w, direct = world, kind == 'direct'
    unread_and_marked(w, kind)
    before = badge(w)
    # La liste de l'iPhone précharge la conversation (le dernier message est déjà sur le téléphone) : rien n'est lu.
    pre = w['chats'].conversation(w['token'], w[kind], direct, prefetch=True)
    assert pre['messages'][-1]['body'] == 'Tu viens ce soir ?'
    # Toucher : la conversation s'ouvre. Sans « lu » envoyé (app d'avant : aucun message nouveau), elle reste non lue.
    w['chats'].conversation(w['token'], w[kind], direct)
    stuck = row(w, kind)
    assert stuck['unread'] >= 1 and stuck['marked_unread'] and badge(w) == before, stuck
    # App corrigée : l'ouverture envoie toujours « lu ».
    w['chats'].read(w['token'], w[kind], direct)
    read_everywhere(w, kind, before)


def test_iphone_event_chat_opened_from_the_list_or_the_page_is_read(world):
    w = world
    unread_and_marked(w, 'event')
    before = badge(w)
    assert w['a'].rpc('event_chat_prefs_get', e=w['event']).json()['unread'] >= 1  # compteur de la fiche
    w['events'].conversation(w['token'], w['event'])
    # Écran natif : mark_event_chat_read (relais, liste v2) puis event-chat/read (fiche).
    assert w['a'].rpc('mark_event_chat_read', e=w['event']).status_code in (200, 204)
    read_everywhere(w, 'event', before)
    # Deuxième message, discussion ouverte depuis la FICHE (event-chat/read seul).
    unread_and_marked(w, 'event')
    before = badge(w)
    assert w['events'].read(w['token'], w['event']) == {'unread': 0}
    read_everywhere(w, 'event', before)


@pytest.mark.parametrize('kind', ['direct', 'group', 'event'])
def test_web_opening_the_conversation_reads_it(world, kind):
    w = world
    unread_and_marked(w, kind)
    before = badge(w)
    fn, arg = {'direct': ('mark_direct_read', 'chat'), 'group': ('mark_group_read', 'grp'), 'event': ('mark_event_chat_read', 'e')}[kind]
    assert w['a'].rpc(fn, **{arg: w[kind]}).status_code in (200, 204)
    read_everywhere(w, kind, before)


@pytest.mark.parametrize('kind', ['direct', 'group', 'event'])
def test_my_own_message_never_counts(world, kind):
    w = world
    fn, arg = {'direct': ('mark_direct_read', 'chat'), 'group': ('mark_group_read', 'grp'), 'event': ('mark_event_chat_read', 'e')}[kind]
    w['a'].rpc(fn, **{arg: w[kind]})
    table, col = {'direct': ('direct_messages', 'chat_id'), 'group': ('group_messages', 'group_id'), 'event': ('messages', 'event_id')}[kind]
    sql(f"insert into public.{table} ({col}, user_id, body) values ('{w[kind]}', '{w['a'].uid}', 'Moi')")
    assert row(w, kind)['unread'] == 0
