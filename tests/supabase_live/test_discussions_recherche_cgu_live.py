"""« Nouveau message » sans les CGU en cours (retour de l'admin du 19.11, « Il trouve personne ») sur la VRAIE base de
TEST : la recherche et les suggestions montrent les gens ; écrire demande les CGU (open_direct_chat → terms_required,
feuille des CGU puis nouvel essai). Réglage et acceptations du compte remis tels quels.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussions_recherche_cgu_live.py -q"""
import pytest

from tests.supabase_live.test_audiences_live import ADMIN
from tests.supabase_live.test_member_admin_live import Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


@pytest.fixture
def without_terms():
    who = Session(ADMIN)
    was = sql("select terms_enforced from private.moderation_settings where id = 1")[0]['terms_enforced']
    kept = sql(f"select version, accepted_at from public.terms_acceptances where user_id = '{who.uid}'")
    try:
        sql(f"delete from public.terms_acceptances where user_id = '{who.uid}'")
        sql("update private.moderation_settings set terms_enforced = true where id = 1")
        yield who
    finally:
        sql(f"update private.moderation_settings set terms_enforced = {'true' if was else 'false'} where id = 1")
        sql(f"delete from public.terms_acceptances where user_id = '{who.uid}'")
        for row in kept:
            sql(f"insert into public.terms_acceptances (user_id, version, accepted_at) values "
                f"('{who.uid}', '{row['version']}', '{row['accepted_at']}') on conflict do nothing")


def test_search_shows_people_and_writing_asks_for_the_terms(without_terms):
    who = without_terms
    found = who.rpc('chat_people_search', q='vip').json()
    assert found, "la recherche était vide sans les CGU"
    assert all(p['link'] in ('direct', 'request') for p in found)
    sugg = who.rpc('chat_people_suggestions').json()
    assert set(sugg) == {'recent', 'crossed', 'groups'}
    # Écrire reste gardé : chat_link (dm_link) dit toujours « none » tant que les CGU manquent.
    target = next(p['id'] for p in found)
    assert who.rpc('chat_link', target=target).json() == 'none'
    version = who.rpc('my_terms').json()['version']
    assert who.rpc('accept_terms', p_version=version).json()['accepted'] is True
    assert who.rpc('chat_link', target=target).json() in ('direct', 'request')
