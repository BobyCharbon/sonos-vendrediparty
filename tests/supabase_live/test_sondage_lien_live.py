"""Sondage de dates, une seule logique partout (retours de l'admin du 08.11), sur la VRAIE base de TEST : l'invité venu
par un lien vote les dates comme un membre (jamais de « je viens » avant la date fixée), la liste des invités compte les
votants, et la date fixée inscrit chacun selon son vote pour CETTE date (Oui et Si besoin = vient, Non = ne vient pas ;
le vote remplace une ancienne réponse).
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
        # Compte neuf : profil complet d'abord (« Faisons connaissance », 10.11), puis il vote comme un membre.
        assert new.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
        r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{new.uid}', headers=new.headers, timeout=30,
                        json={'first_name': 'Zoé', 'last_name': 'Sondage', 'display_name': 'Zoé'})
        assert r.status_code in (200, 204), r.text
        done = new.rpc('accept_invite', token=link['token'], answer='poll').json()
        assert done['status'] is None and done['date_mode'] == 'poll'
        assert [rsvp(event, p.uid) for p in (ga, gb, new)] == [None, None, None]

        # Ils votent les dates comme dans l'app.
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
        assert [rsvp(event, p.uid) for p in (ga, gb, new)] == ['yes', 'yes', 'no']  # « Si besoin » = vient (règle de l'admin)

        # Date fixée : on répond normalement, « poll » n'est plus une réponse.
        assert 'La date est fixée' in error_of(new.rpc('accept_invite', token=link['token'], answer='poll'))
        assert new.rpc('accept_invite', token=link['token'], answer='yes').json()['status'] == 'yes'
    finally:
        sql(f"delete from public.events where id = '{event}'")


def test_a_removed_guest_loses_his_votes_and_the_fixed_date_frees_places_for_yes(people):  # noqa: F811
    """Agent « Cohérence » (08.11) : un invité retiré après avoir voté revenait dans la liste et était inscrit à la date
    fixée ; avec les places prises, un « Non » qui remplace un ancien « je viens » doit libérer la place pour un « Oui » ;
    « Si besoin » sans « Peut-être » efface l'ancienne réponse."""
    admin, ga, gb, vip, new = people
    event = create_event(admin, 'Test sondage places', visibility='invited', date_mode='poll', starts_at=None,
                         allow_maybe=False, max_participants=2, waitlist_enabled=False)
    try:
        first = option(admin, event, 21)
        link = admin.rpc('create_event_invite', e=event, places=4).json()
        for who in (ga, gb, vip):
            assert who.rpc('accept_invite', token=link['token'], answer='poll').status_code == 200
        # Retiré après avoir voté : ses votes partent, il n'est plus dans la liste ni inscrit plus tard.
        vote(vip, first, 'yes')
        assert admin.rpc('remove_invitee', e=event, member=vip.uid).status_code in (200, 204)
        assert vip.uid not in {p['id'] for p in admin.rpc('event_guest_list', e=event).json()['people']}
        # Anciennes réponses « je viens » d'avant le sondage (deux places, prises) : ga vote Non, gb Oui, new Si besoin.
        sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{ga.uid}', 'yes'), ('{event}', '{new.uid}', 'yes')")
        sql(f"insert into public.event_invites (event_id, user_id, via_group, via_link) values ('{event}', '{new.uid}', false, true) on conflict do nothing")
        vote(ga, first, 'no'); vote(gb, first, 'yes'); vote(new, first, 'if_needed')
        assert admin.rpc('fix_event_date', e=event, opt=first).status_code in (200, 204)
        assert [rsvp(event, p.uid) for p in (ga, gb, new, vip)] == ['no', 'yes', 'yes', None]
    finally:
        sql(f"delete from public.events where id = '{event}'")


def test_if_needed_without_maybe_frees_the_place_for_a_yes(people):  # noqa: F811
    """1 place, « Peut-être » désactivé ; A avait « je viens » par lien et vote « Si besoin », B vote Oui → les « Oui »
    passent d'abord : B prend la place, A (Si besoin = vient, mais plus de place) n'est pas inscrit."""
    admin, ga, gb, _vip, _new = people
    event = create_event(admin, 'Test sondage si besoin', visibility='invited', date_mode='poll', starts_at=None,
                         allow_maybe=False, max_participants=1, waitlist_enabled=False)
    try:
        first = option(admin, event, 22)
        link = admin.rpc('create_event_invite', e=event, places=2).json()
        for who in (ga, gb):
            assert who.rpc('accept_invite', token=link['token'], answer='poll').status_code == 200
        sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{ga.uid}', 'yes')")
        vote(ga, first, 'if_needed'); vote(gb, first, 'yes')
        assert admin.rpc('fix_event_date', e=event, opt=first).status_code in (200, 204)
        assert [rsvp(event, p.uid) for p in (ga, gb)] == [None, 'yes']
    finally:
        sql(f"delete from public.events where id = '{event}'")


def test_the_link_card_of_a_poll_is_closed_when_the_vote_deadline_is_past(people):  # noqa: F811
    from tests.supabase_live.test_invite_links_live import anon_rpc
    admin = people[0]
    event = create_event(admin, 'Test sondage fermé', visibility='invited', date_mode='poll', starts_at=None)
    try:
        link = admin.rpc('create_event_invite', e=event, places=2).json()
        assert anon_rpc('invite_preview', token=link['token']).json()['closed'] is False
        sql(f"update public.events set poll_deadline = now() - interval '1 hour' where id = '{event}'")
        assert anon_rpc('invite_preview', token=link['token']).json()['closed'] is True
    finally:
        sql(f"delete from public.events where id = '{event}'")
