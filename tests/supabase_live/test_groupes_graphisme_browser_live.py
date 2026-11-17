"""Recette RÉELLE du nouveau graphisme des groupes (17.11.2026) : vrai navigateur, vrai serveur Party, base de TEST,
compte de test à code fixe (Guest A), CGU exigées. Guest A crée « Recette graphisme » (🍕, citron) en 2 étapes :
la base garde emoji et couleur ; l'étape Inviter montre le lien du groupe et son code QR ; « Plus tard » ouvre la page
du groupe ; la liste des groupes et les bulles de l'onglet Événements le montrent. Le groupe est supprimé à la fin.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $GROUPS_SHOTS si la variable est définie."""
import os
from pathlib import Path

import pytest

from tests.supabase_live.test_audiences_live import GUEST_A
from tests.supabase_live.test_inscription_complete_browser_live import browser, party, phone_page, sign_in  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
DIST = Path(os.environ.get('PARTY_TEST_EVENTS_DIST') or '/nonexistent')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                        reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]
SHOTS = Path(os.environ['GROUPS_SHOTS']) if os.environ.get('GROUPS_SHOTS') else None
NAME = 'Recette graphisme'


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


@pytest.fixture
def guest():
    s = Session(GUEST_A)
    assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    sql(f"delete from public.member_groups where name = '{NAME}' and created_by = '{s.uid}'")
    yield s
    sql(f"delete from public.member_groups where name = '{NAME}' and created_by = '{s.uid}'")


def test_a_guest_creates_a_group_in_two_steps_and_finds_it_everywhere(browser, party, guest):  # noqa: F811
    context, page, errors = phone_page(browser)
    try:
        page.goto(f'{party}/events/sign-in', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 01')
        pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_have_count(0, timeout=30000)
        page.goto(f'{party}/events/group/new', wait_until='domcontentloaded')
        page.get_by_label('Nom du groupe').fill(NAME, timeout=30000)
        page.get_by_role('radio', name='Emoji 🍕').click()
        page.get_by_role('radio', name='Couleur Citron').click()
        shot(page, 'live-01-creer')
        page.get_by_role('button', name='Continuer').click()
        panel = page.get_by_test_id('group-invite-panel')
        pw.expect(panel.get_by_text('Invite ta bande', exact=True)).to_be_visible(timeout=15000)
        pw.expect(panel.get_by_text('/events/group-invite/', exact=False)).to_be_visible(timeout=15000)
        pw.expect(panel.get_by_label('Code QR du lien du groupe')).to_be_visible()
        shot(page, 'live-02-inviter')
        rows = sql(f"select id::text, emoji, color from public.member_groups where name = '{NAME}' and created_by = '{guest.uid}'")
        assert [(r['emoji'], r['color']) for r in rows] == [('🍕', 'lemon')], rows
        gid = rows[0]['id']
        page.get_by_role('button', name='Plus tard').click()
        pw.expect(page.get_by_role('heading', name=NAME)).to_be_visible(timeout=15000)
        assert page.url.endswith(f'/events/group/{gid}')
        shot(page, 'live-03-page')
        page.goto(f'{party}/events/groups', wait_until='domcontentloaded')
        pw.expect(page.get_by_test_id(f'group-row-{gid}')).to_be_visible(timeout=30000)
        shot(page, 'live-04-liste')
        page.goto(f'{party}/events/', wait_until='domcontentloaded')
        pw.expect(page.get_by_test_id('group-bubbles').get_by_role('link', name=f'Groupe {NAME}')).to_be_visible(timeout=30000)
        shot(page, 'live-05-bulles')
        assert not errors, errors
    finally:
        context.close()
