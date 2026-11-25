"""Recette RÉELLE du refus Apple 1.4.3 (25.11) : vrai serveur Party réglé comme la prod (bar allumé, Zicou éteint),
vraie base de TEST, vrai navigateur. Un même événement avec un bar (Bière + Coca) :
- vu par l'app App Store (« PartyStore ») : aucune carte du bar sur la fiche, aucun réglage « Bar : … » dans les notifications ;
- vu par un navigateur : la carte du bar et ses réglages sont là (le web garde le bar).
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<dist construit contre la base de test> python -m pytest \
  tests/supabase_live/test_refus_143_browser_live.py -q   (captures dans $REFUS_SHOTS si défini)"""
import os
import time
from pathlib import Path

import httpx
import pytest

from tests.supabase_live.party_shell import ALONE_INIT
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, VIP, complete_profile, create_event
from tests.supabase_live.test_bar_soiree_browser_live import DIST, PHONES, browser, party  # noqa: F401
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import LOCAL_TEST, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pw = pytest.importorskip('playwright.sync_api')
SHOTS = Path(os.environ['REFUS_SHOTS']) if os.environ.get('REFUS_SHOTS') else None
STORE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
            'PartyApp-iOS/1.0.0 PartyStore')
WEB_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 '
          'Mobile/15E148 Safari/604.1')
pytestmark = [live, pytest.mark.skipif(not (DIST / 'index.html').exists(),
                                       reason='PARTY_TEST_EVENTS_DIST : module construit contre la base de test')]


def shot(page, name: str, full: bool = False):
    if SHOTS:
        page.wait_for_timeout(800)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=full)


@pytest.fixture(scope='module')
def event_with_bar():
    admin, guest, other = Session(ADMIN), Session(GUEST_A), Session(VIP)
    for s in (admin, guest, other):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    complete_profile(other, 'VIP test')
    event = create_event(admin, 'Soirée recette 1.4.3', visibility='all', public_link=True)
    for s in (admin, guest, other):
        r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=s.headers, timeout=30, json={'event_id': event, 'user_id': s.uid, 'status': 'yes'})
        assert r.status_code in (200, 201, 409), r.text
    assert admin.rpc('bar_create', e=event).status_code == 200
    admin.rpc('bar_save_item', e=event, item={'name': 'Bière', 'emoji': '🍺', 'price_chf': 3, 'age_min': 18})
    admin.rpc('bar_save_item', e=event, item={'name': 'Coca', 'emoji': '🥤', 'price_chf': 2})
    admin.rpc('bar_save_settings', e=event, settings={'orders_open': True, 'pay_method': 'revolut'})
    if not LOCAL_TEST:
        time.sleep(61)  # base de TEST : un code SMS par minute et par numéro
    yield event
    sql(f"delete from public.events where id = '{event}'")


def open_event(browser, origin, phone, ua, event, errors):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', locale='fr-CH', user_agent=ua)
    context.add_init_script(ALONE_INIT)  # le module reste seul (sans renvoi dans Party) : party_shell.py
    page = context.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(f'{origin}/events/sign-in')
    pw.expect(page.get_by_text('Ton compte Party', exact=True)).to_be_visible(timeout=20000)
    page.get_by_label('Ton numéro de téléphone', exact=True).fill(phone)
    page.get_by_role('button', name='Recevoir un code par SMS').click()
    page.get_by_placeholder('123456', exact=True).fill('123456')
    page.get_by_role('button', name='Se connecter', exact=True).click()
    page.wait_for_timeout(3000)
    page.goto(f'{origin}/events/event/{event}')
    pw.expect(page.get_by_text('Soirée recette 1.4.3').first).to_be_visible(timeout=30000)
    return context, page


def test_the_store_app_has_no_bar_and_the_web_keeps_it(browser, party, event_with_bar):  # noqa: F811
    errors: list = []
    sctx, s = open_event(browser, party, PHONES[GUEST_A], STORE_UA, event_with_bar, errors)
    try:
        assert s.evaluate("document.documentElement.dataset.bar") == 'off'
        s.wait_for_timeout(2500)
        shot(s, 'web-store-fiche-sans-bar', full=True)
        body = s.inner_text('body')
        assert 'Bar de la soirée' not in body and 'Bière' not in body and '🍹' not in body
        s.goto(f'{party}/events/settings/notifications')
        pw.expect(s.get_by_text('Invitation à un événement privé')).to_be_visible(timeout=20000)
        assert 'Bar : verres servis' not in s.inner_text('body')
        shot(s, 'web-store-notifications-sans-bar')
    finally:
        sctx.close()
    wctx, w = open_event(browser, party, PHONES[VIP], WEB_UA, event_with_bar, errors)
    try:
        pw.expect(w.get_by_text('🍹 Bar de la soirée')).to_be_visible(timeout=30000)
        w.get_by_text('🍹 Bar de la soirée').scroll_into_view_if_needed()
        shot(w, 'web-navigateur-fiche-avec-bar')
    finally:
        wctx.close()
    assert not errors, errors
