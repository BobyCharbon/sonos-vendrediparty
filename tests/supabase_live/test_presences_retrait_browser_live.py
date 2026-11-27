"""Recette RÉELLE du 27.11.2026 (retour de l'admin sur la prod) : dans la carte « Présences » de la fiche, l'organisation
retire la réponse d'un MEMBRE (✕) et une personne SANS compte ; chaque ✕ demande « Retirer <nom> des présences ? »
(Retirer / Annuler), rien ne part au premier toucher. Vrai navigateur (390 × 844), vrai serveur Party, base de TEST.
Événement « sur invitation », sans annonce : seuls les comptes de test le voient.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $PAY_SHOTS si la variable est définie."""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import create_event
from tests.supabase_live.test_event_tickets_live import answer
from tests.supabase_live.test_inscription_complete_browser_live import browser, party  # noqa: F401
from tests.supabase_live.test_member_admin_live import TEST_URL
from tests.supabase_live.test_paiement_mode_browser_live import (  # noqa: F401
    DIST, pages, people, pytestmark, shot, sql)

pw = pytest.importorskip('playwright.sync_api')
TITLE = 'Présences retrait recette'
NOBODY = 'Pote Théo recette'


@pytest.fixture(scope='module')
def event(people):
    admin, a = people['admin'], people['a']
    eid = create_event(admin, TITLE, visibility='invited')
    try:
        r = httpx.post(f'{TEST_URL}/rest/v1/event_invites', headers=admin.headers, json={'event_id': eid, 'user_id': a.uid}, timeout=30)
        assert r.status_code == 201, r.text
        answer(a, eid, 'yes')
        r = httpx.post(f'{TEST_URL}/rest/v1/event_manual_guests', headers=admin.headers,
                       json={'event_id': eid, 'name': NOBODY, 'status': 'yes'}, timeout=30)
        assert r.status_code == 201, r.text
        yield eid
    finally:
        sql(f"delete from public.events where id = '{eid}'")


def rsvp_of(eid: str, uid: str):
    rows = sql(f"select status::text from public.rsvps where event_id = '{eid}' and user_id = '{uid}'")
    return rows[0]['status'] if rows else None


def manual_count(eid: str) -> int:
    return sql(f"select count(*)::int n from public.event_manual_guests where event_id = '{eid}'")[0]['n']


def test_removing_a_member_and_someone_without_account_asks_first_and_holds(pages, party, people, event):  # noqa: F811
    a = people['a']
    page, errors = pages('admin')
    page.goto(f'{party}/events/event/{event}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text(TITLE, exact=True).first).to_be_visible(timeout=30000)
    pw.expect(page.get_by_label('Présents : 2', exact=True)).to_be_visible(timeout=30000)
    remove = page.get_by_role('button', name='Retirer Guest A', exact=True)
    remove.scroll_into_view_if_needed()
    shot(page, 'retrait-1-avant')

    # Premier toucher : rien ne part, la question s'affiche ; Annuler ne retire rien.
    remove.click()
    pw.expect(page.get_by_text('Retirer Guest A des présences ?', exact=True)).to_be_visible(timeout=10000)
    shot(page, 'retrait-2-question')
    page.wait_for_timeout(1500)
    assert rsvp_of(event, a.uid) == 'yes'
    page.get_by_role('button', name='Annuler', exact=True).click()
    pw.expect(page.get_by_text('Retirer Guest A des présences ?', exact=True)).to_have_count(0)
    assert rsvp_of(event, a.uid) == 'yes'

    # Retirer : la réponse part de la base, la ligne disparaît, les compteurs suivent, et ça tient au rechargement.
    remove.click()
    page.get_by_role('button', name='Retirer', exact=True).click()
    pw.expect(page.get_by_label('Présents : 1', exact=True)).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('button', name='Retirer Guest A', exact=True)).to_have_count(0)
    assert rsvp_of(event, a.uid) is None
    shot(page, 'retrait-3-membre-retire')
    page.reload(wait_until='domcontentloaded')
    pw.expect(page.get_by_label('Présents : 1', exact=True)).to_be_visible(timeout=30000)
    page.wait_for_timeout(2500)  # temps réel, relecture : la ligne ne revient pas
    pw.expect(page.get_by_role('button', name='Retirer Guest A', exact=True)).to_have_count(0)

    # Sans compte : même question, Annuler puis Retirer.
    nobody = page.get_by_role('button', name=f'Retirer {NOBODY}', exact=True)
    nobody.click()
    pw.expect(page.get_by_text(f'Retirer {NOBODY} des présences ?', exact=True)).to_be_visible(timeout=10000)
    page.wait_for_timeout(1000)
    assert manual_count(event) == 1
    page.get_by_role('button', name='Annuler', exact=True).click()
    assert manual_count(event) == 1
    nobody.click()
    page.get_by_role('button', name='Retirer', exact=True).click()
    pw.expect(page.get_by_label('Présents : 0', exact=True)).to_be_visible(timeout=15000)
    assert manual_count(event) == 0
    shot(page, 'retrait-4-tout-retire')
    assert not errors, errors
