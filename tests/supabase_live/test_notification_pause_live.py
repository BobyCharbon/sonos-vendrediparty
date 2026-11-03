"""Notifications sur la VRAIE base de test (jamais la prod) :
- chaque type se coupe dans les Réglages, et un type coupé n'est envoyé sur AUCUN canal (iPhone APNs/Expo, Web Push) ;
- pause (lune, Discussions des groupes, discussions des événements) : la notification arrive quand même, mais
  marquée « silent » (sans son ni vibration) ; après la pause, tout repart avec le son.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import secrets
import time
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from tests.supabase_live.test_audiences_live import ADMIN
from tests.supabase_live.test_member_admin_live import Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import TOKEN_FILE, sql as raw_sql

MARK = 'Test réglages des notifications'
# Type de notification → réglage qui le coupe (notification_prefs). Tous les types qu'un membre peut recevoir.
SWITCHES = {
    'new_event': "new_event = 'none'", 'event_changed': 'event_changed = false', 'poll_new': 'poll_new = false',
    'date_fixed': 'date_fixed = false', 'poll_nudge': 'poll_nudge = false', 'waitlist': 'waitlist = false',
    'proposal': 'proposals = false', 'rsvp': 'rsvp_mine = false', 'message': "chat = 'none'",
    'reminder': "reminders = '{}'", 'rsvp_set': 'rsvp_set = false', 'private_invite': 'invites = false',
    'approved': 'proposal_result = false', 'rejected': 'proposal_result = false', 'link_join': 'link_join = false',
    'group_message': 'group_messages = false', 'group_invite': 'group_invites = false', 'group_join': 'group_joins = false',
    'admin_announcement': 'announcements = false',
}
DEFAULTS = ("push_enabled = true, quiet_start = null, quiet_end = null, new_event = 'all', event_changed = true, "
            "poll_new = true, date_fixed = true, poll_nudge = true, waitlist = true, proposals = true, rsvp_mine = true, "
            "chat = 'all', reminders = '{1d}', rsvp_set = true, invites = true, proposal_result = true, link_join = true, "
            "group_messages = true, group_invites = true, group_joins = true, announcements = true, "
            "muted_until = null, chats_muted_until = null, event_chats_muted_until = null")


def sql(query: str) -> list:
    """SQL sur la base de TEST ; l'API de gestion limite le débit (429) : on attend et on réessaie."""
    for wait in (5, 10, 20, 30, 45, 60):
        try:
            return raw_sql(query)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(wait)
    return raw_sql(query)


_announcement: list = []


def announcement_id() -> str:
    if not _announcement:
        rows = sql('select id::text from public.admin_announcements limit 1')
        _announcement.append(rows[0]['id'] if rows else '')
    return _announcement[0]


def pause(s: Session, what: str, span: str) -> dict:
    r = s.rpc('set_notification_pause', what=what, span=span)
    assert r.status_code == 200, r.text
    return r.json()


def queue(s: Session, kind: str) -> str:
    """Une notification comme celles des déclencheurs (insertion directe, service), pas encore envoyée. Un iPhone
    fictif est enregistré juste avant : l'envoi réel de la base de test l'essaie aussitôt et l'efface (jeton refusé)."""
    r = s.rpc('register_device_push_token', device_token='apns:' + secrets.token_hex(32), device_platform='ios')
    assert r.status_code in (200, 204), r.text
    data = f"jsonb_build_object('kind', '{kind}', 'announcement_id', '{announcement_id()}')"
    dedupe = f"'reminder:x:1d:{secrets.token_hex(4)}'" if kind == 'reminder' else 'null'
    return sql(f"insert into public.notifications (user_id, kind, title, body, data, dedupe_key) values ('{s.uid}', '{kind}', "
               f"'{MARK}', '{kind}', {data}, {dedupe}) returning id::text")[0]['id']


def channels(note: str) -> dict:
    """Après le passage de l'envoi : livraison iPhone préparée ? Web Push autorisé ? Et en silence ?"""
    return sql(f"select public.prepare_push_deliveries(); select (select count(*)::int from public.notification_deliveries d where d.notification_id = n.id) > 0 as iphone, "
               f"n.skipped, private.web_push_allowed(n) as web, private.push_paused(n.user_id, n.kind) as silent "
               f"from public.notifications n where n.id = '{note}'")[0]


def sent(note: str) -> bool:
    row = channels(note)
    assert row['iphone'] == row['web'], row  # même règle pour tous les canaux
    if not row['iphone']:
        assert row['skipped'], row
    return row['iphone']


@pytest.fixture(scope='module')
def admin():
    if not TOKEN_FILE.exists():
        pytest.skip('jeton de l\'API de gestion absent')
    s = Session(ADMIN)
    sql(f"update public.notification_prefs set {DEFAULTS} where user_id = '{s.uid}'")
    yield s
    restore = DEFAULTS.replace("chat = 'all'", "chat = 'mentions'").replace("reminders = '{1d}'", "reminders = '{1d,0h}'")
    sql(f"update public.notification_prefs set {restore} where user_id = '{s.uid}'")
    sql(f"delete from public.notifications where user_id = '{s.uid}' and title = '{MARK}'")


@pytest.mark.parametrize('kind', sorted(SWITCHES))
def test_a_switched_off_type_is_sent_on_no_channel(admin, kind):
    if kind == 'admin_announcement' and not announcement_id():
        pytest.skip('aucune annonce sur la base de test')
    assert sent(queue(admin, kind)), kind  # réglage allumé : envoyée (iPhone et Web Push)
    sql(f"update public.notification_prefs set {SWITCHES[kind]} where user_id = '{admin.uid}'")
    try:
        assert not sent(queue(admin, kind)), kind
    finally:
        sql(f"update public.notification_prefs set {DEFAULTS} where user_id = '{admin.uid}'")


def test_the_moon_delivers_everything_silently_admin_included(admin):
    prefs = pause(admin, 'all', '1h')
    until = datetime.fromisoformat(prefs['muted_until'])
    assert timedelta(minutes=59) < until - datetime.now(timezone.utc) <= timedelta(hours=1, minutes=1)
    for kind in ('group_message', 'group_invite', 'admin_announcement'):
        if kind == 'admin_announcement' and not announcement_id():
            continue
        row = channels(queue(admin, kind))
        # Livrée (même règle pour tous les canaux : web_push_allowed), mais sans son. (La livraison iPhone elle-même
        # est vérifiée par le test par type : ici l'envoi réel de la base de test peut avoir déjà effacé l'iPhone fictif.)
        assert row['web'] and row['silent'], (kind, row)
    test = channels(queue(admin, 'push_test'))
    assert test['web'] and not test['silent']  # l'essai demandé sonne toujours
    # La livraison iPhone porte « silent » jusqu'à la fonction d'envoi.
    note = queue(admin, 'group_join')
    sql('select public.prepare_push_deliveries()')
    claimed = sql(f"select data->>'silent' as silent from public.claim_push_deliveries(100) where notification_id = '{note}'")
    assert all(c['silent'] == 'true' for c in claimed), claimed  # vide : déjà prise par l'envoi réel de la base de test


def test_after_the_moon_everything_rings_again(admin):
    pause(admin, 'all', '1h')
    sql(f"update public.notification_prefs set muted_until = now() - interval '1 minute' where user_id = '{admin.uid}'")
    assert not channels(queue(admin, 'group_message'))['silent']
    assert pause(admin, 'all', 'off')['muted_until'] is None


def test_group_and_event_discussions_have_separate_pauses(admin):
    pause(admin, 'all', 'off')
    prefs = pause(admin, 'chats', '30m')
    assert prefs['chats_muted_until'] and prefs['event_chats_muted_until'] is None and prefs['muted_until'] is None
    assert channels(queue(admin, 'group_message'))['silent']
    assert not channels(queue(admin, 'group_invite'))['silent']  # seulement les messages
    pause(admin, 'chats', 'off')
    prefs = pause(admin, 'event_chats', '2h')
    assert prefs['event_chats_muted_until'] and prefs['chats_muted_until'] is None
    assert not channels(queue(admin, 'group_message'))['silent']
    assert sql(f"select private.push_paused('{admin.uid}', 'message') as s")[0]['s'] is True
    pause(admin, 'event_chats', 'off')
    assert sql(f"select private.push_paused('{admin.uid}', 'message') as s")[0]['s'] is False


def test_until_tomorrow_morning_ends_at_the_next_eight_oclock_in_zurich(admin):
    pause(admin, 'all', 'morning')
    until = sql(f"select to_char(muted_until at time zone 'Europe/Zurich', 'HH24:MI') as hm, "
                f"muted_until > now() and muted_until <= now() + interval '24 hours' as soon "
                f"from public.notification_prefs where user_id = '{admin.uid}'")[0]
    assert until == {'hm': '08:00', 'soon': True}, until
    pause(admin, 'all', 'off')


def test_an_unknown_duration_or_scope_is_refused(admin):
    assert admin.rpc('set_notification_pause', what='all', span='12h').status_code == 400
    assert admin.rpc('set_notification_pause', what='events', span='1h').status_code == 400
