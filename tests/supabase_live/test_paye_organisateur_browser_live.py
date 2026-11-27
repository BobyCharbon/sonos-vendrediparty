"""Recette RÉELLE du 20.11.2026 (demande de l'admin) : l'organisateur coche lui-même « A payé ✓ » dans la carte
« Paiements » de la fiche, pour une personne qui a payé sur le site (ou à lui) sans l'avoir noté, puis « Annuler ».
Vrai navigateur (390 × 844), vrai serveur Party, base de TEST, comptes de test à code fixe, réglages de prod.
Événement « sur invitation », sans annonce : seuls les comptes de test le voient.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $PAY_SHOTS si la variable est définie."""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import create_event
from tests.supabase_live.test_event_tickets_live import answer, ticket
from tests.supabase_live.test_inscription_complete_browser_live import browser, party  # noqa: F401
from tests.supabase_live.test_member_admin_live import TEST_URL
from tests.supabase_live.test_paiement_mode_browser_live import (  # noqa: F401
    DIST, pages, people, pytestmark, shot, sql)

pw = pytest.importorskip('playwright.sync_api')
TITLE = 'Paintball « A payé » recette'


@pytest.fixture(scope='module')
def event(people):
    admin, a = people['admin'], people['a']
    eid = create_event(admin, TITLE, visibility='invited', price_chf=30, payment_mode='online',
                       payment_url='https://billetterie.example.ch/paintball-a-paye')
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': a.uid}, timeout=30)
        assert r.status_code == 201, r.text
        answer(a, eid, 'yes')
        yield eid
    finally:
        sql(f"delete from public.events where id = '{eid}'")


def paid_row(eid: str, uid: str) -> dict:
    rows = sql(f"select paid, paid_by::text, pay_declared_at from public.event_tickets where event_id = '{eid}' and user_id = '{uid}'")
    return rows[0] if rows else {'paid': False}


@pytest.mark.parametrize('mode', ['online', 'organizer'])
def test_the_organizer_ticks_a_payment_on_the_event_and_cancels_it(pages, party, people, event, mode):  # noqa: F811
    admin, a = people['admin'], people['a']
    sql(f"update public.events set payment_mode = '{mode}' where id = '{event}'")
    page, errors = pages('admin')
    page.goto(f'{party}/events/event/{event}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text(TITLE, exact=True).first).to_be_visible(timeout=30000)
    todo = page.get_by_text('PAS ENCORE PAYÉ · 1', exact=True)
    pw.expect(todo).to_be_visible(timeout=30000)
    hint = ('Payé sur le site sans le noter ? Si on te le dit, note-le ici.' if mode == 'online'
            else 'Payé sans le noter ? Si tu as reçu le paiement, note-le ici.')
    pw.expect(page.get_by_text(hint, exact=True)).to_be_visible()
    todo.scroll_into_view_if_needed()
    shot(page, f'a-paye-{mode}-1-avant')

    page.get_by_role('button', name='A payé ✓', exact=True).click()
    pw.expect(page.get_by_text('ONT PAYÉ · 1', exact=True)).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('1 / 1 payé', exact=True)).to_be_visible()
    row = paid_row(event, a.uid)
    assert row['paid'] is True and row['paid_by'] == admin.uid, row
    assert ticket(a, event)['paid'] is True  # l'invité voit sa place payée
    shot(page, f'a-paye-{mode}-2-coche')

    page.get_by_role('button', name='Annuler', exact=True).click()
    pw.expect(page.get_by_text('PAS ENCORE PAYÉ · 1', exact=True)).to_be_visible(timeout=15000)
    assert paid_row(event, a.uid)['paid'] is False
    shot(page, f'a-paye-{mode}-3-annule')
    assert not errors, errors


def test_the_guest_has_no_a_paye_button(pages, party, people, event):  # noqa: F811
    page, errors = pages('a')
    page.goto(f'{party}/events/event/{event}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text(TITLE, exact=True).first).to_be_visible(timeout=30000)
    page.wait_for_timeout(2500)
    assert page.get_by_role('button', name='A payé ✓', exact=True).count() == 0
    assert page.get_by_text('PAS ENCORE PAYÉ', exact=False).count() == 0
    assert not errors, errors
