"""Signaler un événement + filtre sur son titre et sa description (contrôle App Store du 05.11, O2) sur la VRAIE base
de test (jamais la prod). Événements sans annonce : aucun vrai membre n'est prévenu.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_report_event_live.py -q"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

QUIET = {'notify_on_publish': False}


def post_event(who: Session, title: str, **fields) -> httpx.Response:
    start = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    return httpx.post(f'{TEST_URL}/rest/v1/events', timeout=30, headers={**who.headers, 'Prefer': 'return=representation'},
                      json={'title': title, 'status': 'published', 'starts_at': start, **QUIET, **fields})


def patch_event(who: Session, eid: str, body: dict) -> httpx.Response:
    return httpx.patch(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', timeout=30,
                       headers={**who.headers, 'Prefer': 'return=representation'}, json=body)


@pytest.fixture(scope='module')
def people():
    admin, a, b = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    made: list[str] = []
    yield admin, a, b, made
    if made:
        ids = ",".join(f"'{e}'" for e in made)
        sql(f"delete from public.content_reports where target_kind = 'event' and target_id in ({ids})")
        sql(f"delete from public.notifications where kind = 'report_new' and body like '%un événement%'"
            f" and created_at > now() - interval '1 hour'")
        for eid in made:
            httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def test_title_and_description_go_through_the_content_filter(people):
    admin, a, b, made = people
    r = post_event(admin, 'sale nègre', visibility='invited')
    assert r.status_code == 400 and r.json()['message'].startswith('content_refused: Événement non enregistré : le titre')
    r = post_event(admin, 'Test filtre événement', visibility='invited', description="Venez, bande de connards ! Infos : www.exemple.ch")
    assert r.status_code == 201, r.text
    ev = r.json()[0]
    made.append(ev['id'])
    assert ev['description'] == 'Venez, bande de •••••••• ! Infos : www.exemple.ch'  # insulte masquée, lien gardé
    r = patch_event(admin, ev['id'], {'description': 'Fotze'})
    assert r.status_code == 400 and 'la description' in r.json()['message'] and 'contenu sexuel' in r.json()['message']
    assert patch_event(admin, ev['id'], {'title': 'Test filtre événement (modifié)'}).status_code == 200


def test_anyone_who_sees_the_event_can_report_it_and_moderators_hide_it(people):
    admin, a, b, made = people
    r = post_event(admin, 'Test signalement événement', visibility='all', public_link=True, description='Une description')
    assert r.status_code == 201, r.text
    eid = r.json()[0]['id']
    made.append(eid)
    private = post_event(admin, 'Test événement privé', visibility='invited').json()[0]['id']
    made.append(private)

    assert admin.rpc('report_content', p_kind='event', p_target=eid, p_reason='spam').status_code >= 400  # son propre événement
    r = a.rpc('report_content', p_kind='event', p_target=private, p_reason='spam')
    assert r.status_code >= 400 and 'not_found' in r.json()['message']  # pas invité : rien à signaler
    r = b.rpc('report_content', p_kind='event', p_target=eid, p_reason='shocking', p_comment='titre choquant')
    assert r.status_code == 200, r.text
    rid = r.json()
    snap = sql(f"select snapshot from public.content_reports where id = '{rid}'")[0]['snapshot']
    assert snap['text'] == 'Test signalement événement\n\nUne description' and snap['place'] == 'Événement' and snap['event_id'] == eid
    note = sql(f"select body from public.notifications where user_id = '{admin.uid}' and kind = 'report_new' order by created_at desc limit 1")
    assert note and note[0]['body'].endswith('un événement')
    assert any(x['id'] == rid and x['kind'] == 'event' for x in admin.rpc('moderation_queue').json())

    hidden = admin.rpc('moderation_act', p_report=rid, p_action='hide')
    assert hidden.status_code == 200, hidden.text
    row = sql(f"select title, description, cover_url, public_link from public.events where id = '{eid}'")[0]
    assert row == {'title': 'Événement masqué par la modération', 'description': '', 'cover_url': None, 'public_link': False}
    assert b.get(f'content_reports?select=status&id=eq.{rid}').json()[0]['status'] == 'actioned'
