"""Inscription complète des invités (avis 39f148377a8f du 10.11, sondage du paintball), sur une VRAIE base (base de TEST
ou sa copie locale, jamais la prod) :
- répondre à une invitation exige un profil complet (prénom, nom, surnom) : plus de compte « au prénom seul » ;
- un invité venu par lien sur un sondage PUBLIC apparaît chez l'organisateur, avec ses votes, et la purge nocturne des
  comptes minimaux ne peut plus l'effacer (cause du bug : ni invitation ni réponse → compte et votes supprimés) ;
- un compte vraiment abandonné (rien fait) reste purgé ;
- la carte du lien et la page publique comptent les votants d'un sondage, comme la fiche.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_inscription_complete_live.py -q"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, create_event
from tests.supabase_live.test_invitations_v2_live import error_of, terms_version
from tests.supabase_live.test_invite_links_live import NEW, anon_rpc
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

ABANDONED = '41790000007'  # compte de test à code fixe, laissé vide


def option(admin: Session, event: str, days: int) -> str:
    r = httpx.post(f'{TEST_URL}/rest/v1/date_options', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                   json={'event_id': event, 'starts_at': (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()})
    assert r.status_code == 201, r.text
    return r.json()[0]['id']


def vote(who: Session, opt: str, value: str):
    r = httpx.post(f'{TEST_URL}/rest/v1/date_votes', timeout=30, headers={**who.headers, 'Prefer': 'resolution=merge-duplicates'},
                   json={'option_id': opt, 'user_id': who.uid, 'vote': value})
    assert r.status_code in (200, 201), r.text


def complete_identity(who: Session, first: str, last: str, nickname: str):
    r = httpx.patch(f'{TEST_URL}/rest/v1/profiles?id=eq.{who.uid}', timeout=30, headers=who.headers,
                    json={'first_name': first, 'last_name': last, 'display_name': nickname})
    assert r.status_code in (200, 204), r.text


def purge_list() -> set:
    return {row['id'] for row in sql('select x::text id from private.light_invitees_to_purge() x')}


def make_old_light_invitee(uid: str, event: str):
    """Comme un compte créé au prénom seul il y a un mois (avant cette correction)."""
    sql(f"insert into private.light_invitees (user_id, event_id, created_at) values ('{uid}', '{event}', now() - interval '30 days') "
        f"on conflict (user_id) do update set created_at = now() - interval '30 days'")


def reset_account(uid: str):
    """Compte de test remis à vide (le garde de profil interdit de vider un profil complet : déclencheurs coupés ici)."""
    sql("begin;\nset local session_replication_role = replica;\n"
        f"update public.profiles set first_name = '', last_name = '', display_name = '' where id = '{uid}';\n"
        "commit;\n"
        f"delete from private.light_invitees where user_id = '{uid}';\n"
        f"delete from public.rsvps where user_id = '{uid}';\n"
        f"delete from public.terms_acceptances where user_id = '{uid}'")


@pytest.fixture(scope='module')
def people():
    admin, guest, newcomer, abandoned = Session(ADMIN), Session(GUEST_A), Session(NEW), Session(ABANDONED)
    for s in (admin, guest):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    for s in (newcomer, abandoned):
        reset_account(s.uid)
    yield admin, guest, newcomer, abandoned
    for s in (newcomer, abandoned):
        reset_account(s.uid)


def test_answering_an_invitation_needs_the_full_profile_first_name_alone_is_refused(people):
    admin, _guest, new, _abandoned = people
    event = create_event(admin, 'Test inscription complète', visibility='invited')
    try:
        link = admin.rpc('create_event_invite', e=event, places=3).json()
        assert new.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)

        # Prénom seul (ancien écran) : refusé, rien n'est créé, le lien n'est pas consommé.
        refused = error_of(new.rpc('accept_invite', token=link['token'], answer='yes', first_name='Zoé'))
        assert 'profile_required' in refused
        assert not sql(f"select 1 from private.light_invitees where user_id = '{new.uid}'")
        assert not sql(f"select 1 from public.event_invites where event_id = '{event}' and user_id = '{new.uid}'")
        assert sql(f"select uses from private.invite_links where token = '{link['token']}'")[0]['uses'] == 0
        assert anon_rpc('invite_preview', token=link['token']).json()['me_complete'] is False

        # Profil complet (parcours « Faisons connaissance ») : la réponse passe et la personne est bien invitée.
        complete_identity(new, 'Zoé', 'Martin', 'Zoé M.')
        done = new.rpc('accept_invite', token=link['token'], answer='yes').json()
        assert done['status'] == 'yes'
        row = sql(f"select via_link from public.event_invites where event_id = '{event}' and user_id = '{new.uid}'")
        assert row == [{'via_link': True}]
        assert new.rpc('invite_preview', token=link['token']).json()['me_complete'] is True
    finally:
        sql(f"delete from public.events where id = '{event}'")
        reset_account(new.uid)


def test_a_link_guest_on_a_public_poll_is_listed_with_his_votes_and_the_purge_never_takes_him(people):
    admin, guest, new, _abandoned = people
    event = create_event(admin, 'Test paintball public', visibility='all', public_link=True, date_mode='poll', starts_at=None)
    try:
        first, second = option(admin, event, 20), option(admin, event, 27)
        link = admin.rpc('create_event_invite', e=event, places=10).json()
        assert new.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
        complete_identity(new, 'Léa', 'Paint', 'Léa P.')

        # Sondage public : l'invité par lien répond en votant les dates (aucune réponse « je viens »).
        done = new.rpc('accept_invite', token=link['token'], answer='poll').json()
        assert done['status'] is None and done['date_mode'] == 'poll'
        vote(new, first, 'yes')
        vote(new, second, 'no')
        vote(guest, first, 'if_needed')  # un Guest qui voit l'événement public sans lien vote aussi

        # L'organisateur le voit : dans la liste (venu par le lien, a voté) et dans les votes du sondage.
        listed = {p['id']: p for p in admin.rpc('event_guest_list', e=event).json()['people']}
        assert listed[new.uid]['source'] == 'link' and listed[new.uid]['voted'] is True
        assert listed[guest.uid]['voted'] is True
        options = admin.get(f'date_options?select=id,date_votes(user_id,vote)&event_id=eq.{event}').json()
        votes = {(o['id'], v['user_id']): v['vote'] for o in options for v in o['date_votes']}
        assert votes[(first, new.uid)] == 'yes' and votes[(second, new.uid)] == 'no'

        # Même un ancien compte « au prénom seul » vieux d'un mois n'est plus purgé dès qu'il a voté ou est invité.
        make_old_light_invitee(new.uid, event)
        assert new.uid not in purge_list()
        sql(f"delete from public.event_invites where event_id = '{event}' and user_id = '{new.uid}'")
        assert new.uid not in purge_list(), 'ses votes suffisent à le garder'

        # La carte du lien et la page publique comptent les votants, comme la fiche (2 personnes ont voté).
        card = anon_rpc('invite_preview', token=link['token']).json()
        assert card['voters'] == 2
        public = anon_rpc('public_event', e=event).json()
        assert public['voters'] == 2 and public['date_mode'] == 'poll'
        # Participants cachés par l'organisateur : le nombre reste, les noms jamais (comme « qui vient »).
        assert set(card['voter_names']) == {'Léa P.', 'Testeur 1'}
        sql(f"update public.events set show_participants = false where id = '{event}'")
        hidden = anon_rpc('invite_preview', token=link['token']).json()
        assert hidden['voters'] == 2 and hidden['voter_names'] == []
    finally:
        sql(f"delete from public.events where id = '{event}'")
        reset_account(new.uid)


def test_a_really_abandoned_minimal_account_is_still_purged(people):
    admin, _guest, _new, abandoned = people
    event = create_event(admin, 'Test purge', visibility='invited')
    try:
        make_old_light_invitee(abandoned.uid, event)
        assert abandoned.uid in purge_list(), 'rien fait depuis un mois : compte minimal à effacer'
        sql(f"insert into public.rsvps (event_id, user_id, status) values ('{event}', '{abandoned.uid}', 'no')")
        assert abandoned.uid not in purge_list(), 'une réponse, même « non », le garde'
    finally:
        sql(f"delete from public.events where id = '{event}'")
        reset_account(abandoned.uid)


def test_an_arrival_by_link_never_gets_the_private_invitation_notification(people):
    """Revue de sécurité (10.11) : une ligne event_invites « via_link » existe désormais pour tout non-membre venu par lien ;
    elle ne déclenche jamais « 🔒 Invitation à un événement privé » à la personne qui vient elle-même de répondre
    (queue_notification ignore sa propre action) : garde-fou contre une régression."""
    admin, _guest, new, _abandoned = people
    event = create_event(admin, 'Test sans notification', visibility='invited', notify_on_publish=True)
    try:
        link = admin.rpc('create_event_invite', e=event, places=3).json()
        assert new.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
        complete_identity(new, 'Noa', 'Lien', 'Noa L.')
        assert new.rpc('accept_invite', token=link['token'], answer='yes').json()['status'] == 'yes'
        assert sql(f"select via_link from public.event_invites where event_id = '{event}' and user_id = '{new.uid}'") == [{'via_link': True}]
        assert sql(f"select count(*) n from public.notifications where user_id = '{new.uid}' and event_id = '{event}' "
                   "and kind = 'private_invite'") == [{'n': 0}]
    finally:
        sql(f"delete from public.events where id = '{event}'")
        reset_account(new.uid)
