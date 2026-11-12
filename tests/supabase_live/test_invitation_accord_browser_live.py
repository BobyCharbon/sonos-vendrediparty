"""Recette RÉELLE de l'accord de l'organisateur (décision de l'admin du 12.11.2026) : vrai navigateur, vrai serveur Party,
base de TEST, comptes de test à code fixe, réglages de prod (Invitations v2 allumées, CGU exigées). Événement privé de
l'admin, Guest A (Testeur 1) invité ; Guest B (Testeur 2) (pas invité) ouvre le lien de Testeur 1 : il sait AVANT de répondre que l'admin
accepte chaque invité, répond, voit « Demande envoyée » et pas la fiche. L'admin voit « À accepter », accepte : Testeur 2
voit l'événement avec sa réponse.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $ACCORD_SHOTS si la variable est définie."""
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
SHOTS = Path(os.environ['ACCORD_SHOTS']) if os.environ.get('ACCORD_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


@pytest.fixture(scope='module')
def event():
    """Événement privé de l'admin ; Testeur 1 invité crée son lien « Collègues » ; Testeur 2 n'est pas invité."""
    admin, guest, other = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    for s in (admin, guest, other):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    e = create_event(admin, 'Accord recette', visibility='invited', public_link=False)
    assert admin.rpc('invite_people', e=e, people=[guest.uid], groups=[]).status_code == 200
    token = guest.rpc('create_event_invite', e=e, places=1, label='Collègues').json()['token']
    yield admin, other, e, token
    sql(f"delete from public.events where id = '{e}'")


def test_a_person_invited_by_a_guest_waits_then_the_organizer_accepts(browser, party, event):  # noqa: F811
    admin, other, e, token = event
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/invite/{token}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('accepte chaque invité : tu verras l’événement dès qu’il aura dit oui.', exact=False)
                  ).to_be_visible(timeout=30000)
        shot(page, '00-carte-avec-accord')
        page.get_by_role('button', name='Je viens !').click()
        sign_in(page, '079 000 00 02')
        pw.expect(page.get_by_text('Demande envoyée', exact=True)).to_be_visible(timeout=30000)
        pw.expect(page.get_by_role('button', name='Voir l’événement', exact=True)).to_have_count(0)
        shot(page, '01-demande-envoyee')
        assert not sql(f"select 1 from public.event_invites where event_id = '{e}' and user_id = '{other.uid}'")
        assert not errors, errors
    finally:
        context.close()

    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Se connecter', exact=True).click()
        sign_in(page, '079 000 00 04')
        pw.expect(page.get_by_role('button', name='Se connecter', exact=True)).to_have_count(0, timeout=30000)
        page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
        card = page.get_by_label('Invités', exact=True)
        pw.expect(card.get_by_text('Guest B attend ton accord', exact=True)).to_be_visible(timeout=30000)
        card.get_by_text('Guest B attend ton accord', exact=True).scroll_into_view_if_needed()
        shot(page, '02-organisateur-a-accepter')
        card.get_by_role('button', name='Accepter Guest B').click()
        pw.expect(page.get_by_text('Guest B est invité : il voit l’événement', exact=True)).to_be_visible(timeout=15000)
        pw.expect(card.get_by_text('Guest B attend ton accord', exact=True)).to_have_count(0)
        shot(page, '03-organisateur-accepte')
        assert not errors, errors
    finally:
        context.close()

    assert sql(f"select status::text from public.rsvps where event_id = '{e}' and user_id = '{other.uid}'")[0]['status'] == 'yes'
    assert sql(f"select count(*) as n from public.notifications where user_id = '{other.uid}' and event_id = '{e}' "
               "and kind = 'private_invite'")[0]['n'] == 1
