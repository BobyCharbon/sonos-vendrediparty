"""Recette RÉELLE du menu de partage commun (avis 83ebee37aa0f, 11.11.2026) : vrai navigateur, vrai serveur Party, base de
TEST, comptes de test à code fixe, réglages de prod (Invitations v2 allumées, CGU exigées). Un invité « Guest » (Testeur 1)
se connecte par la page normale, ouvre l'événement privé de l'admin : il voit les CHIFFRES (aucun nom), crée son lien
nommé « Collègues », le retrouve dans « Mes liens » et le recopie (le même lien). L'admin voit ce lien chez lui.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de test> python -m pytest <ce fichier>
Captures dans $PARTAGE_SHOTS si la variable est définie."""
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
SHOTS = Path(os.environ['PARTAGE_SHOTS']) if os.environ.get('PARTAGE_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


@pytest.fixture(scope='module')
def event():
    """Événement privé de l'admin : Testeur 1 et Testeur 2 invités, Testeur 2 vient ; un lien de l'admin « Pour Léa »."""
    admin, guest, other = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    for s in (admin, guest, other):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    e = create_event(admin, 'Partage commun recette', visibility='invited', public_link=False)
    assert admin.rpc('invite_people', e=e, people=[guest.uid, other.uid], groups=[]).status_code == 200
    sql(f"insert into public.rsvps (event_id, user_id, status) values ('{e}', '{other.uid}', 'yes') on conflict do nothing")
    admin.rpc('create_event_invite', e=e, places=1, label='Pour Léa')
    yield admin, guest, e
    sql(f"delete from public.events where id = '{e}'")


def test_a_guest_sees_numbers_only_creates_his_named_link_and_copies_it_again(browser, party, event):  # noqa: F811
    admin, guest, e = event
    context, page, errors = phone_page(browser)
    context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=party)
    try:
        page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Se connecter', exact=True).click()  # événement privé : « Connecte-toi pour voir »
        sign_in(page, '079 000 00 01')
        pw.expect(page.get_by_role('button', name='Se connecter', exact=True)).to_have_count(0, timeout=30000)
        shot(page, '00-connecte')
        page.goto(f'{party}/events/event/{e}', wait_until='domcontentloaded')
        card = page.get_by_label('Invités', exact=True)
        pw.expect(card.get_by_text('Invités · 3', exact=True)).to_be_visible(timeout=30000)
        pw.expect(card.get_by_role('tab', name='1 Viennent')).to_be_visible()
        pw.expect(card.get_by_role('tab', name='1 Lien pas ouvert')).to_be_visible()
        # Aucun nom : ni Testeur 2 (qui vient), ni le lien de l'admin.
        assert card.get_by_text('Testeur 2', exact=False).count() == 0
        assert card.get_by_text('Pour Léa', exact=False).count() == 0
        shot(page, '01-invite-carte-chiffres')

        card.get_by_role('button', name='Inviter', exact=True).click()
        sheet = page.get_by_label('Inviter à Partage commun recette')
        sheet.get_by_label('Nom du lien (facultatif)').fill('Collègues')
        shot(page, '02-invite-feuille-lien-nomme')
        sheet.get_by_role('button', name='Copier').click()
        pw.expect(sheet.get_by_text('✓ Lien prêt', exact=False)).to_be_visible(timeout=15000)
        token = sql(f"select token::text from private.invite_links where target = '{e}' and label = 'Collègues' "
                    f"and created_by = '{guest.uid}'")[0]['token']
        sheet.get_by_role('button', name='Fermer').first.click()

        pw.expect(card.get_by_text('MES LIENS · 1', exact=True)).to_be_visible(timeout=15000)
        pw.expect(card.get_by_text('Lien pour Collègues', exact=True)).to_be_visible()
        page.evaluate('navigator.clipboard.writeText("")')
        card.get_by_role('button', name='Copier le lien : Lien pour Collègues').click()
        pw.expect(page.get_by_text('Lien copié', exact=True)).to_be_visible(timeout=10000)
        assert page.evaluate('navigator.clipboard.readText()') == f'{party}/events/invite/{token}'
        shot(page, '03-invite-mes-liens-copie')
        assert not errors, errors
    finally:
        context.close()

    # L'organisatrice voit le lien de son invité, nommé, avec son auteur.
    links = {l['label']: l for l in admin.rpc('event_guest_list', e=e).json()['links']}
    assert links['Collègues']['created_by_id'] == guest.uid
