"""Campagne 2 des bots (07.11.2026), restes de la base (migration 20261107120000), sur la VRAIE base de TEST
(jamais la prod), comptes de test à code fixe seulement :
- la carte d'invitation (« qui vient déjà ») montre le surnom entier, pas son premier mot ;
- signaler un contenu qu'on n'a pas le droit de lire : refus propre (404, « not_found: … »), jamais une erreur 500 ;
- public_event rend l'affiche (https seulement), image de l'aperçu des liens.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_campagne2_restes_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_B, create_event
from tests.supabase_live.test_invite_links_live import anon_rpc
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

COVER = 'https://ewromqfsmcqsthftyhzm.supabase.co/storage/v1/object/public/event-covers/test-c2.jpg'


@pytest.fixture(scope='module')
def people():
    sessions = Session(ADMIN), Session(GUEST_B)
    version = sql('select terms_version v from private.moderation_settings where id = 1')[0]['v']
    for s in sessions:  # CGU exigées comme en prod : les comptes de test les acceptent (comme au doigt)
        assert s.rpc('accept_terms', p_version=version).status_code in (200, 204)
    return sessions


@pytest.fixture
def event(people):
    admin, _ = people
    made = []

    def make(**fields) -> str:
        made.append(create_event(admin, 'Test C2 restes', **fields))
        return made[-1]
    yield make
    for e in made:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{e}', headers=admin.headers, timeout=30)


def test_the_invitation_card_shows_whole_nicknames_of_who_is_coming(people, event):
    admin, _ = people
    e = event(visibility='invited', show_participants=True)
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{e}', '{admin.uid}', 'yes')")
    name = sql(f"select display_name from public.profiles where id = '{admin.uid}'")[0]['display_name']
    assert ' ' in name.strip(), 'le compte de test doit avoir un surnom en plusieurs mots'
    token = admin.rpc('create_event_invite', e=e, places=2).json()['token']
    preview = anon_rpc('invite_preview', token=token).json()
    assert preview['going_names'] == [name.strip()], preview


def test_reporting_something_you_cannot_read_is_a_clean_refusal(people, event):
    admin, gb = people
    e = event(visibility='all')
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{e}', '{admin.uid}', 'yes'); "
        f"insert into public.rsvp_notes (event_id, user_id, note) values ('{e}', '{admin.uid}', 'Mot de test C2')")
    note = sql(f"select id from public.rsvp_notes where event_id = '{e}'")[0]['id']
    r = gb.rpc('report_content', p_kind='rsvp_note', p_target=note, p_reason='spam')  # mot lu par l'organisation seulement
    assert r.status_code == 404, (r.status_code, r.text)
    assert r.json()['message'].startswith('not_found: '), r.text
    r = gb.rpc('report_content', p_kind='rsvp_note', p_target='pas-un-id', p_reason='spam')
    assert r.status_code == 404, (r.status_code, r.text)
    assert sql(f"select count(*) n from public.content_reports where target_id = '{note}'") == [{'n': 0}]


def test_public_event_gives_the_poster_only_when_it_is_https(people, event):
    e = event(visibility='all', public_link=True, cover_url=COVER)
    assert anon_rpc('public_event', e=e).json()['cover_url'] == COVER
    sql(f"update public.events set cover_url = 'event-covers/local.jpg' where id = '{e}'")
    assert anon_rpc('public_event', e=e).json()['cover_url'] is None
    hidden = event(visibility='invited', cover_url=COVER)
    assert anon_rpc('public_event', e=hidden).json() is None
