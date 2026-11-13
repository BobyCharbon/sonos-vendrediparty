"""Recette RÉELLE du covoiturage (avis 34d5c07f2e56, 11.11.2026) : vrai navigateur, vrai serveur Party, base de TEST,
comptes de test à code fixe, réglages de prod (Invitations v2, CGU exigées). Événement public de l'admin avec l'option
Covoiturage ; Testeur 1 (Présent) conduit depuis Sion avec 2 places ; Testeur 2 (Présent) le voit et monte.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $CARPOOL_SHOTS si la variable est définie."""
import os
from pathlib import Path

import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, create_event
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['CARPOOL_SHOTS']) if os.environ.get('CARPOOL_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


@pytest.fixture(scope='module')
def event():
    admin, driver, rider = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    for s in (admin, driver, rider):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    e = create_event(admin, 'Covoiturage recette', visibility='all', public_link=True, carpool_enabled=True)
    for s in (driver, rider):
        sql(f"insert into public.rsvps (event_id, user_id, status) values ('{e}', '{s.uid}', 'yes')")
    yield driver, rider, e
    sql(f"delete from public.events where id = '{e}'")


def open_signed_in(browser, party, e, number):  # noqa: F811
    context, page, errors = phone_page(browser)
    page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')  # la connexion normale de l'app
    sign_in(page, number)
    pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
    page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text('🚗 Covoiturage', exact=True)).to_be_visible(timeout=30000)
    return context, page, errors


def test_a_driver_offers_two_seats_and_another_guest_gets_in(browser, party, event):  # noqa: F811
    driver, rider, e = event
    context, page, errors = open_signed_in(browser, party, e, '079 000 00 01')
    try:
        page.get_by_role('button', name='🚗 Je conduis').click()
        page.get_by_role('button', name='Une place de moins').click()  # 3 → 2
        page.get_by_label('Ville de départ (facultatif)').fill('Sion')
        page.get_by_role('button', name='Proposer mes places').click()
        pw.expect(page.get_by_text('Tu conduis depuis Sion · 2 places libres', exact=True)).to_be_visible(timeout=15000)
        shot(page, '01-conducteur')
        assert not errors, errors
    finally:
        context.close()

    context, page, errors = open_signed_in(browser, party, e, '079 000 00 02')
    try:
        page.get_by_text('🚗 Covoiturage', exact=True).scroll_into_view_if_needed()
        pw.expect(page.get_by_text('1 voiture · 2 places libres', exact=True)).to_be_visible()
        page.get_by_role('button', name=f'Monter avec {driver_name(driver)}').click()
        pw.expect(page.get_by_text(f'Tu montes avec {driver_name(driver)} (départ de Sion)', exact=True)).to_be_visible(timeout=15000)
        shot(page, '02-passager')
        assert not errors, errors
    finally:
        context.close()

    rows = sql(f"select user_id::text, role, seats, from_city, driver_id::text from public.event_carpool where event_id = '{e}' order by role")
    assert [(r['role'], r['seats'], r['from_city']) for r in rows] == [('driver', 2, 'Sion'), ('passenger', None, None)], rows
    assert rows[1]['driver_id'] == driver.uid


def driver_name(s: Session) -> str:
    return sql(f"select display_name from public.profiles where id = '{s.uid}'")[0]['display_name']
