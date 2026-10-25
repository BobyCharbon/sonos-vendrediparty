"""Vrai navigateur + VRAIE base de test : un Admin crée une sortie « Vendredi Party + un numéro » avec le formulaire,
le Guest invité par numéro la voit (avec la confirmation de connexion), un autre Guest ne la voit pas."""
import time
from urllib.parse import quote

import httpx
import pytest

from tests.supabase_live.test_admin_pages_live import origin, pytestmark  # noqa: F401 (fixture, conditions)
from tests.supabase_live.test_audiences_live import complete_profile
from tests.supabase_live.test_member_admin_live import TEST_URL, Session

pw = pytest.importorskip('playwright.sync_api')


def sign_in(page, local_number: str):
    page.get_by_label('Ton numéro de téléphone', exact=True).fill(local_number)
    code = page.get_by_placeholder('123456', exact=True)
    for _ in range(3):  # un code par minute et par numéro : on attend si les tests précédents viennent d'en demander un
        page.get_by_role('button', name='Recevoir un code par SMS').click()
        try:
            code.wait_for(timeout=8000)
            break
        except pw.TimeoutError:
            page.wait_for_timeout(31000)
    code.fill('123456')
    page.get_by_role('button', name='Se connecter', exact=True).click()


def test_admin_invites_vip_group_plus_a_phone_and_only_that_guest_sees_it(browser, origin):
    title = f'Live VIP + numéro {int(time.time())}'
    admin = browser.new_context(viewport={'width': 390, 'height': 844}).new_page()
    errors = []; admin.on('pageerror', lambda e: errors.append(str(e)))
    admin.goto(origin + '/events/', wait_until='domcontentloaded')
    sign_in(admin, '079 000 00 04')
    pw.expect(admin.get_by_text('À venir', exact=True)).to_be_visible(timeout=30000)
    admin.goto(origin + '/events/event/new', wait_until='domcontentloaded')
    admin.get_by_label('Titre', exact=True).fill(title)
    admin.get_by_label('Début', exact=True).fill('2030-11-14T19:00')
    pw.expect(admin.get_by_role('button', name='👥 Vendredi Party', exact=False)).to_be_visible()  # coché par défaut (vérifié à l'enregistrement)
    admin.get_by_label('Inviter par numéro de téléphone').fill('079 000 00 02')
    admin.get_by_role('button', name='Inviter', exact=True).click()
    pw.expect(admin.get_by_text('✕ +41790000002', exact=True)).to_be_visible()
    admin.get_by_role('button', name='Publier', exact=True).click()
    pw.expect(admin.get_by_text(title, exact=True).first).to_be_visible(timeout=30000)
    pw.expect(admin.get_by_text('👥 Groupe Vendredi Party', exact=False)).to_be_visible()
    assert not errors, errors

    api = Session('41790000004')
    event = api.get(f'events?select=id,visibility,public_link,event_phone_invites(phone)&title=eq.{quote(title)}').json()[0]
    try:
        assert event['visibility'] == 'all' and not event['public_link']
        assert [p['phone'] for p in event['event_phone_invites']] == ['41790000002']
        for phone, name in (('41790000002', 'Guest B'), ('41790000001', 'Guest A')):
            complete_profile(Session(phone), name)  # règle : profil complet avant de voir les sorties
        for number, sees in (('079 000 00 02', True), ('079 000 00 01', False)):
            guest = browser.new_context(viewport={'width': 390, 'height': 844}).new_page()
            guest.goto(origin + '/events/', wait_until='domcontentloaded')
            sign_in(guest, number)
            pw.expect(guest.get_by_text('Tu es connecté à ton compte ✓', exact=True)).to_be_visible(timeout=30000)
            if sees:
                pw.expect(guest.get_by_text(title, exact=True)).to_be_visible(timeout=15000)
            else:
                guest.wait_for_timeout(3000)
                pw.expect(guest.get_by_text(title, exact=True)).to_have_count(0)
            guest.context.close()
    finally:
        httpx.delete(f"{TEST_URL}/rest/v1/events?id=eq.{event['id']}", headers=api.headers, timeout=30)
        admin.context.close()
