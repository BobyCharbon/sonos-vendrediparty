"""Sondage de dates, une seule logique partout (retours de l'admin du 08.11), sur la VRAIE base de TEST : l'invité venu
par un lien vote les dates comme un membre (jamais de « je viens » avant la date fixée), la liste des invités compte les
votants, et la date fixée inscrit chacun selon son vote pour CETTE date (le vote remplace une ancienne réponse).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_sondage_lien_live.py -q"""
from datetime import datetime, timedelta, timezone

import httpx

from tests.supabase_live.test_audiences_live import create_event
from tests.supabase_live.test_invitations_v2_live import error_of, people, terms_version  # noqa: F401
from tests.supabase_live.test_member_admin_live import TEST_URL, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def option(admin, event: str, days: int) -> str:
    r = httpx.post(f'{TEST_URL}/rest/v1/date_options', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                   json={'event_id': event, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()})
    assert r.status_code == 201, r.text
    return r.json()[0]['id']


def vote(who, opt: str, value: str):
    r = httpx.post(f'{TEST_URL}/rest/v1/date_votes', timeout=30, headers={**who.headers, 'Prefer': 'resolution=merge-duplicates'},
                   json={'option_id': opt, 'user_id': who.uid, 'vote': value})
    assert r.status_code in (200, 201), r.text


def rsvp(event: str, uid: str):
    rows = sql(f"select status from public.rsvps where event_id = '{event}' and user_id = '{uid}'")
    return rows[0]['status'] if rows else None


def test_a_link_guest_votes_the_dates_and_the_fixed_date_follows_the_votes(people):  # noqa: F811
    admin, ga, gb, _vip, new = people
    event = create_event(admin, 'Test sondage par lien', visibility='invited', date_mode='poll', starts_at=None, allow_maybe=True)
    try:
        first, second = option(admin, event, 20), option(admin, event, 27)
        link = admin.rpc('create_event_invite', e=event, places=3).json()

        # Carte : date à définir. Répondre « Je viens » (ancienne page) ou « poll » : aucune réponse « je viens ».
        assert ga.rpc('accept_invite', token=link['token'], answer='yes').json()['status'] is None
        assert gb.rpc('accept_invite', token=link['token'], answer='poll').json()['status'] is None
        assert new.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
        done = new.rpc('accept_invite', token=link['token'], answer='poll', first_name='Zoé').json()
        assert done['status'] is None and done['date_mode'] == 'poll'
        assert [rsvp(event, p.uid) for p in (ga, gb, new)] == [None, None, None]

        # Ils votent les dates comme dans l'app (leur compte léger suffit).
        vote(ga, first, 'yes'); vote(ga, second, 'no')
        vote(gb, first, 'if_needed')
        vote(new, first, 'no'); vote(new, second, 'yes')

        # Liste des invités : un sondage, trois votants.
        guests = admin.rpc('event_guest_list', e=event).json()
        assert guests['poll'] is True
        voted = {p['id']: p['voted'] for p in guests['people']}
        assert voted[ga.uid] and voted[gb.uid] and voted[new.uid]

        # Ancienne réponse par lien d'avant (« je viens ») : le vote pour la date retenue la remplace.
        sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{new.uid}', 'yes')")
        assert admin.rpc('fix_event_date', e=event, opt=first).status_code in (200, 204)
        assert [rsvp(event, p.uid) for p in (ga, gb, new)] == ['yes', 'maybe', 'no']

        # Date fixée : on répond normalement, « poll » n'est plus une réponse.
        assert 'La date est fixée' in error_of(new.rpc('accept_invite', token=link['token'], answer='poll'))
        assert new.rpc('accept_invite', token=link['token'], answer='yes').json()['status'] == 'yes'
    finally:
        sql(f"delete from public.events where id = '{event}'")
