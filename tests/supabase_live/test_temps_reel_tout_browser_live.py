"""Tout l'événement en temps réel (avis de l'admin du 16.11, migration 20261116140000), recette RÉELLE : base de TEST, vrai
navigateur, connexion normale. Rien n'est rechargé à la main ; la relecture de secours (45 s / 60 s) est bien plus lente que
les délais attendus ici.

  * un sondage ajouté puis retiré par l'organisateur apparaît puis disparaît chez l'invité (table hors du temps réel par
    tables + suppression, les deux trous d'avant) ;
  * une personne qui devient Membre VIP voit aussitôt l'événement réservé aux membres dans sa liste.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de TEST> python -m pytest
tests/supabase_live/test_temps_reel_tout_browser_live.py -q
"""
import time

import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, create_event
from tests.supabase_live.test_bar_soiree_browser_live import browser, party, pw, shot, signed_in_page  # noqa: F401
from tests.supabase_live.test_member_admin_live import Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = live
FAST = 6000  # ms : un signal de la base arrive en ~1 s


@pytest.fixture(scope='module')
def admin():
    return Session(ADMIN)


def test_a_poll_added_then_removed_shows_and_goes_away_on_the_guest_page(browser, party, admin):  # noqa: F811
    event = create_event(admin, 'Temps réel recette', visibility='all', public_link=True)
    errors: list = []
    ctx, g = signed_in_page(browser, GUEST_A, party, event, errors)
    try:
        pw.expect(g.get_by_text('Temps réel recette').first).to_be_visible(timeout=30000)
        g.wait_for_timeout(2500)  # abonnements établis
        poll = sql(f"insert into public.polls (event_id, question, created_by) values ('{event}', 'Quelle musique ce soir ?', "
                   f"'{admin.uid}') returning id::text id")[0]['id']
        sql(f"insert into public.poll_options (poll_id, label, created_by) values ('{poll}', 'Disco', '{admin.uid}')")
        started = time.monotonic()
        pw.expect(g.get_by_text('Quelle musique ce soir ?').first).to_be_visible(timeout=FAST)
        print(f"sondage ajouté visible en {time.monotonic() - started:.1f} s")
        shot(g, 'tr-01-sondage-ajoute')
        sql(f"delete from public.polls where id = '{poll}'")
        started = time.monotonic()
        pw.expect(g.get_by_text('Quelle musique ce soir ?')).to_have_count(0, timeout=FAST)
        print(f"sondage retiré disparu en {time.monotonic() - started:.1f} s")
        # Un détail changé (titre) suit aussi.
        sql(f"update public.events set title = 'Temps réel recette (modifiée)' where id = '{event}'")
        pw.expect(g.get_by_text('Temps réel recette (modifiée)').first).to_be_visible(timeout=FAST)
        assert not errors, errors
    finally:
        ctx.close()
        sql(f"delete from public.events where id = '{event}'")


def test_someone_made_vip_sees_the_members_event_in_the_list_at_once(browser, party, admin):  # noqa: F811
    vip_uid = sql("select id::text id from public.profiles where phone = '41790000003'")[0]['id']
    before = sql(f"select role from public.profiles where id = '{vip_uid}'")[0]['role']
    sql(f"update public.profiles set role = 'guest' where id = '{vip_uid}'")
    event = create_event(admin, 'Réservé aux membres recette', visibility='all', public_link=False)
    errors: list = []
    ctx, page = signed_in_page(browser, VIP, party, event, errors)
    try:
        page.goto(f'{party}/events')
        pw.expect(page.get_by_text('Réservé aux membres recette')).to_have_count(0, timeout=15000)
        page.wait_for_timeout(4000)  # liste chargée, abonnements établis
        assert page.get_by_text('Réservé aux membres recette').count() == 0
        sql(f"update public.profiles set role = 'member' where id = '{vip_uid}'")
        started = time.monotonic()
        pw.expect(page.get_by_text('Réservé aux membres recette').first).to_be_visible(timeout=FAST)
        print(f"événement des membres visible en {time.monotonic() - started:.1f} s")
        shot(page, 'tr-02-membre-vip')
        sql(f"update public.profiles set role = 'guest' where id = '{vip_uid}'")
        pw.expect(page.get_by_text('Réservé aux membres recette')).to_have_count(0, timeout=FAST)
        assert not errors, errors
    finally:
        ctx.close()
        sql(f"update public.profiles set role = '{before}' where id = '{vip_uid}'")
        sql(f"delete from public.events where id = '{event}'")
