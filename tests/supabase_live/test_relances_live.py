"""Relances des invités sans réponse (demande de l'admin, 19.11.2026), sur la VRAIE base de TEST (jamais la prod).

De bout en bout, comme la relance part depuis la fiche (carte « Invités ») :
- un co-organisateur relance ; l'invité qui n'a que la webapp (abonnement Web Push) ET celui qui a l'app iPhone (jeton
  APNs) reçoivent la notification : ligne public.notifications, puis la file de chaque canal (private.web_push_deliveries,
  public.notification_deliveries) préparée par les mêmes fonctions que le cron ;
- le contenu de chaque push est calculé par le VRAI code des fonctions send-web-push (target.ts) et send-push (apns.ts) :
  titre, texte, lien du toucher (la fiche de l'événement sur Événements) ;
- une relance par jour ; interrupteur « Invitations » éteint ou sans appareil → partage ; personne bloquée → rien ;
  événement terminé → refus ; non-organisateur → refus.
Appareils factices (aucun vrai téléphone) : clés Web Push invalides (l'envoi échoue avant tout appel réseau), jeton APNs
inventé (Apple le refuse, la fonction l'oublie). Données à ce test, effacées à la fin.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_relances_live.py -q"""
import json
import secrets
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, create_event
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

ROOT = Path(__file__).resolve().parents[2]
ORIGIN = 'https://partytest.bobycharbon.ch'


def payloads(note: dict, origin: str) -> dict:
    """Ce que les fonctions Edge enverraient pour cette notification, calculé par leur propre code (node, TypeScript)."""
    script = f"""
      const web = await import({json.dumps(str(ROOT / 'supabase/functions/send-web-push/target.ts'))});
      const apns = await import({json.dumps(str(ROOT / 'supabase/functions/send-push/apns.ts'))});
      const n = {json.dumps(note)};
      const row = {{ origin: {json.dumps(origin)}, kind: n.kind, event_id: n.event_id, group_id: n.data.group_id ?? null,
                     notification_id: n.id, url: n.data.url }};
      console.log(JSON.stringify({{
        web: {{ title: n.title.slice(0, 100), body: n.body.slice(0, 180), url: web.notificationTarget(row), tag: web.notificationTag(row) }},
        apns: {{ aps: apns.apsFor(n.title, n.body, n.data.silent === true), url: apns.tapPath(n.data), thread: apns.threadFor(n.data),
                 category: apns.categoryFor(n.data) }},
      }}));"""
    out = subprocess.run(['node', '--no-warnings', '--experimental-strip-types', '--input-type=module', '-e', script],
                         capture_output=True, text=True, timeout=60, check=True)
    return json.loads(out.stdout)


def last_session(uid: str) -> str:
    return sql(f"select id from auth.sessions where user_id = '{uid}' order by created_at desc limit 1")[0]['id']


@pytest.fixture(scope='module')
def people():
    return Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)


def test_a_nudge_reaches_the_webapp_and_the_iphone_with_the_right_push(people):
    admin, ga, gb, vip = people
    tag = secrets.token_hex(4)
    apns_token = 'apns:' + secrets.token_hex(32)
    event = create_event(admin, f'Test relances {tag}', visibility='invited')
    sub = None
    try:
        assert admin.rpc('invite_people', e=event, people=[ga.uid, gb.uid]).json() == {'people': 2, 'groups': 0}
        sql(f"insert into public.event_organizers (event_id, user_id) values ('{event}', '{vip.uid}') on conflict do nothing")
        # Guest A : la webapp seule (abonnement Web Push du navigateur) ; Guest B : l'app iPhone (jeton APNs).
        sub = sql(f"""insert into private.web_push_subscriptions (user_id, session_id, endpoint, subscription, origin)
            values ('{ga.uid}', '{last_session(ga.uid)}', 'https://fcm.googleapis.com/fcm/send/relances-{tag}',
              '{{"endpoint": "https://fcm.googleapis.com/fcm/send/relances-{tag}", "keys": {{"auth": "x", "p256dh": "y"}}}}'::jsonb,
              '{ORIGIN}') returning id""")[0]['id']
        sql(f"insert into public.push_tokens (token, user_id, platform, session_id) values ('{apns_token}', '{gb.uid}', 'ios', "
            f"'{last_session(gb.uid)}') on conflict do nothing")
        card = {p['id']: p for p in admin.rpc('event_guest_list', e=event).json()['people']}
        assert card[ga.uid]['has_app'] and card[gb.uid]['has_app']  # la webapp compte (avant le 19.11 : « sans l'app »)

        # Un invité ne relance pas ; le co-organisateur, si.
        assert ga.rpc('nudge_invitees', e=event, people=[gb.uid]).status_code >= 400
        r = vip.rpc('nudge_invitees', e=event, people=[ga.uid, gb.uid])
        assert r.json() == {'notified': 2, 'skipped': 0, 'share': []}, r.text
        notes = sql(f"""select id, user_id, kind, event_id, title, body, data, dedupe_key from public.notifications
            where event_id = '{event}' and dedupe_key like 'invite_nudge:%' order by user_id""")
        assert {n['user_id'] for n in notes} == {ga.uid, gb.uid}
        for n in notes:
            assert n['kind'] == 'private_invite' and n['title'] == f'📬 Test relances {tag}'
            assert n['body'] == 'Invitation de VIP test · Tu viens ? Réponds en un geste.'
            assert n['data']['event_id'] == event and n['data']['kind'] == 'private_invite'
        assert all(sql(f"select private.web_push_allowed(n) ok from public.notifications n where id = '{n['id']}'")[0]['ok'] for n in notes)

        # La file de chaque canal, préparée comme le cron (send-web-push, send-push).
        sql('select private.prepare_web_push_deliveries(); select public.prepare_push_deliveries();')
        web_note = next(n for n in notes if n['user_id'] == ga.uid)
        ios_note = next(n for n in notes if n['user_id'] == gb.uid)
        assert sql(f"select count(*) c from private.web_push_deliveries where notification_id = '{web_note['id']}' and subscription_id = '{sub}'")[0]['c'] == 1
        assert sql(f"select count(*) c from public.notification_deliveries where notification_id = '{ios_note['id']}' and token = '{apns_token}'")[0]['c'] == 1
        # Ni la webapp de B ni l'iPhone de A : chacun reçoit sur son appareil seulement.
        assert sql(f"select count(*) c from public.notification_deliveries where notification_id = '{web_note['id']}'")[0]['c'] == 0

        web = payloads(web_note, ORIGIN)['web']
        assert web == {'title': f'📬 Test relances {tag}', 'body': 'Invitation de VIP test · Tu viens ? Réponds en un geste.',
                       'url': f'{ORIGIN}/?tab=events&event={event}', 'tag': f"party-event-{web_note['id']}"}
        ios = payloads(ios_note, ORIGIN)['apns']
        assert ios['aps'] == {'alert': {'title': f'📬 Test relances {tag}', 'body': 'Invitation de VIP test · Tu viens ? Réponds en un geste.'},
                              'sound': 'default'}
        assert ios['url'] == f'/?tab=events&event={event}' and ios['category'] is None  # toucher → la fiche, sur Événements

        # Une relance par jour et par personne, même par un autre organisateur.
        assert admin.rpc('nudge_invitees', e=event, people=[ga.uid, gb.uid]).json() == {'notified': 0, 'skipped': 2, 'share': []}
        assert all(p['nudged_today'] for p in admin.rpc('event_guest_list', e=event).json()['people'])
    finally:
        sql(f"delete from public.push_tokens where token = '{apns_token}'; "
            + (f"delete from private.web_push_subscriptions where id = '{sub}'; " if sub else '')
            + f"delete from public.notifications where event_id = '{event}'")
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)


def test_switch_off_no_device_blocked_and_finished_events(people):
    admin, ga, gb, vip = people
    tag = secrets.token_hex(4)
    apns_a, apns_b = 'apns:' + secrets.token_hex(32), 'apns:' + secrets.token_hex(32)
    event = create_event(admin, f'Test relances limites {tag}', visibility='invited')
    before = sql(f"select invites from public.notification_prefs where user_id = '{ga.uid}'")[0]['invites']
    try:
        assert admin.rpc('invite_people', e=event, people=[ga.uid, gb.uid, vip.uid]).json() == {'people': 3, 'groups': 0}
        # Guest A a l'app mais a éteint « Invitations » ; Guest B a l'app mais bloque l'organisateur ; VIP n'a aucun appareil.
        sql(f"insert into public.push_tokens (token, user_id, platform, session_id) values "
            f"('{apns_a}', '{ga.uid}', 'ios', '{last_session(ga.uid)}'), ('{apns_b}', '{gb.uid}', 'ios', '{last_session(gb.uid)}'); "
            f"update public.notification_prefs set invites = false where user_id = '{ga.uid}'; "
            f"insert into public.direct_blocks (user_id, blocked_id) values ('{gb.uid}', '{admin.uid}') on conflict do nothing")
        card = {p['id']: p for p in admin.rpc('event_guest_list', e=event).json()['people']}
        assert not card[ga.uid]['has_app'] and not card[vip.uid]['has_app']

        result = admin.rpc('nudge_invitees', e=event, people=[ga.uid, gb.uid, vip.uid]).json()
        # Interrupteur éteint et sans appareil → le partage (WhatsApp, Messages…) ; bloqué → ni l'un ni l'autre.
        assert result == {'notified': 0, 'skipped': 0, 'share': [ga.uid, vip.uid]}
        assert sql(f"select count(*) c from public.notifications where event_id = '{event}' and dedupe_key like 'invite_nudge:%'")[0]['c'] == 0

        # Terminé (et date limite passée) : plus de relance.
        past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        sql(f"update public.events set starts_at = '{past}', ends_at = null where id = '{event}'")
        r = admin.rpc('nudge_invitees', e=event, people=[gb.uid])
        assert r.status_code >= 400 and 'terminé' in r.text
    finally:
        sql(f"delete from public.push_tokens where token in ('{apns_a}', '{apns_b}'); "
            f"update public.notification_prefs set invites = {'null' if before is None else str(before).lower()} where user_id = '{ga.uid}'; "
            f"delete from public.direct_blocks where user_id = '{gb.uid}' and blocked_id = '{admin.uid}'; "
            f"delete from public.notifications where event_id = '{event}'")
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{event}', headers=admin.headers, timeout=30)
