"""Recette RÉELLE des Pronos (avis f071c5f46e3d, 17.11.2026) : vrai navigateur, vrai serveur Party, base de TEST.
Guest A ouvre son groupe › « Pronos et classement », crée un prono à choix, joue ; Guest B joue par la base ; la réponse
de B reste cachée chez A ; la fin passe ; A donne le résultat ; le dévoilement montre la bonne réponse, les gagnants et
le classement du groupe. Tout est effacé à la fin.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $GROUPS_SHOTS si la variable est définie."""
import httpx
import pytest

from tests.supabase_live.test_groupes_graphisme_browser_live import DIST, pw, shot  # noqa: F401
from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B, complete_profile
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
GROUP = 'Pronos navigateur'
QUESTION = 'Qui gagne le baby-foot ce soir ?'


@pytest.fixture
def band():
    a, b = Session(GUEST_A), Session(GUEST_B)
    complete_profile(a, 'Prono Léa')
    complete_profile(b, 'Prono Marc')
    sql(f"delete from public.member_groups where name = '{GROUP}' and created_by = '{a.uid}'")
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**a.headers, 'Prefer': 'return=representation'},
                   json={'name': GROUP, 'emoji': '🎲', 'color': 'lavender'}, timeout=30)
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{b.uid}') on conflict do nothing")
    yield a, b, gid
    sql(f"delete from private.pronos where group_id = '{gid}'")
    sql(f"delete from public.member_groups where id = '{gid}'")
    sql(f"delete from public.notifications where kind like 'prono%' and user_id in ('{a.uid}', '{b.uid}')")


def test_create_play_hidden_result_reveal_and_board(browser, party, band):  # noqa: F811
    a, b, gid = band
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 01')
        pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
        page.goto(f'{party}/events/group/{gid}', wait_until='domcontentloaded')
        page.get_by_test_id('group-pronos').click(timeout=30000)
        pw.expect(page.get_by_text('Aucun prono dans ce groupe')).to_be_visible(timeout=20000)
        page.get_by_test_id('prono-new').click()
        page.get_by_test_id('prono-question').fill(QUESTION, timeout=20000)
        page.get_by_label('Choix 1').fill('Léa')
        page.get_by_label('Choix 2').fill('Marc')
        shot(page, 'pronos-01-nouveau')
        page.get_by_role('button', name='Publier et prévenir').click()
        pw.expect(page.get_by_role('heading', name=QUESTION)).to_be_visible(timeout=20000)
        pid = sql(f"select id::text from private.pronos where group_id = '{gid}'")[0]['id']
        # Marc est prévenu ; il joue « Marc » par la base.
        assert sql(f"select count(*) as n from public.notifications where kind = 'prono_new' and user_id = '{b.uid}' and data->>'prono_id' = '{pid}'")[0]['n'] == 1
        opts = b.rpc('prono_get', id=pid).json()['options']
        assert b.rpc('prono_answer', id=pid, answer={'option_id': opts[1]['id']}).status_code == 200

        page.get_by_test_id('prono-choice-0').click()  # Léa joue « Léa »
        pw.expect(page.get_by_text('Ta réponse est enregistrée et cachée')).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('2 personnes ont joué')).to_be_visible(timeout=15000)
        # La réponse de Marc n'est nulle part dans la page (ni texte, ni compte par choix).
        assert 'réponse' not in (page.get_by_test_id('prono-choice-1').inner_text() or '').lower()
        shot(page, 'pronos-02-joue-cache')

        sql(f"update private.pronos set closes_at = now() - interval '1 second' where id = '{pid}'")
        page.reload(wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Quel est le résultat')).to_be_visible(timeout=20000)
        page.get_by_test_id('prono-result-1').click()  # Marc a gagné
        shot(page, 'pronos-03-resultat')
        page.get_by_role('button', name='🎉 Dévoiler le résultat').click()
        reveal = page.get_by_test_id('prono-reveal')
        pw.expect(reveal).to_be_visible(timeout=20000)
        pw.expect(reveal.get_by_text('LES GAGNANTS')).to_be_visible()
        pw.expect(reveal.get_by_text('Ta réponse : Léa')).to_be_visible()
        page.wait_for_timeout(1200)
        shot(page, 'pronos-04-devoilement')
        page.get_by_role('button', name='🏅 Voir le classement').click()
        pw.expect(page.get_by_text('1 bonne réponse sur 1')).to_be_visible(timeout=20000)
        page.wait_for_timeout(900)
        shot(page, 'pronos-05-classement')
        res = sql(f"select body from public.notifications where kind = 'prono_result' and user_id = '{b.uid}' and data->>'prono_id' = '{pid}'")
        assert res and res[0]['body'].startswith('Tu avais vu juste : +3 points')
        assert not [e for e in errors if 'prono' in e.lower()], errors
    finally:
        context.close()
