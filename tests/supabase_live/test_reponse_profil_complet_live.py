"""Répondre ou voter exige un profil complet, même par l'API (recette réelle du 10.11.2026, lien public « Partager ») :
un compte au profil vide posait un « Présent » ou un vote de date sur un événement public → invité sans nom chez
l'organisateur. Migration 20261110100000_reponse_profil_complet, vérifiée sur la VRAIE base de TEST.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_reponse_profil_complet_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, create_event
from tests.supabase_live.test_inscription_complete_live import ABANDONED, complete_identity, option, reset_account
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


@pytest.fixture(scope='module')
def people():
    admin, empty = Session(ADMIN), Session(ABANDONED)
    assert admin.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    reset_account(empty.uid)
    yield admin, empty
    reset_account(empty.uid)


def post(who: Session, table: str, body: dict) -> httpx.Response:
    # Comme l'écran : une réponse est une insertion simple, un vote de date un « upsert ».
    prefer = {'Prefer': 'resolution=merge-duplicates'} if table == 'date_votes' else {}
    return httpx.post(f'{TEST_URL}/rest/v1/{table}', timeout=30, json=body, headers={**who.headers, **prefer})


def test_an_empty_profile_can_neither_answer_nor_vote_through_the_api_then_can_once_complete(people):
    admin, empty = people
    fixed = create_event(admin, '[Recette] Public profil complet', visibility='all', public_link=True)
    poll = create_event(admin, '[Recette] Sondage profil complet', visibility='all', public_link=True,
                        date_mode='poll', starts_at=None)
    try:
        first = option(admin, poll, 20)
        assert empty.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)

        # Profil vide : refusé, rien n'est écrit, l'organisateur ne voit aucun invité sans nom.
        for table, body in (('rsvps', {'event_id': fixed, 'user_id': empty.uid, 'status': 'yes'}),
                            ('date_votes', {'option_id': first, 'user_id': empty.uid, 'vote': 'yes'})):
            r = post(empty, table, body)
            assert r.status_code in (401, 403) and 'profile_required' in r.text, r.text
        assert not sql(f"select 1 from public.rsvps where user_id = '{empty.uid}'")
        assert not sql(f"select 1 from public.date_votes where user_id = '{empty.uid}'")

        # Profil complet (« Faisons connaissance », photo facultative) : la réponse et le vote passent.
        complete_identity(empty, 'Vide', 'Recette', 'Vide R.')
        assert post(empty, 'rsvps', {'event_id': fixed, 'user_id': empty.uid, 'status': 'yes'}).status_code in (200, 201)
        assert post(empty, 'date_votes', {'option_id': first, 'user_id': empty.uid, 'vote': 'yes'}).status_code in (200, 201)
    finally:
        sql(f"delete from public.events where id in ('{fixed}', '{poll}')")


def test_the_organizer_still_notes_the_presence_of_someone_whose_profile_is_empty(people):
    admin, empty = people
    reset_account(empty.uid)
    event = create_event(admin, '[Recette] Présence notée', visibility='invited')
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, timeout=30,
                       json={'event_id': event, 'user_id': empty.uid})
        assert r.status_code == 201, r.text
        r = admin.rpc('set_rsvp_for', event=event, member=empty.uid, answer='yes')  # comme la liste des invités
        assert r.status_code in (200, 204), r.text
        assert sql(f"select status from public.rsvps where event_id = '{event}' and user_id = '{empty.uid}'") == [{'status': 'yes'}]
    finally:
        sql(f"delete from public.events where id = '{event}'")
