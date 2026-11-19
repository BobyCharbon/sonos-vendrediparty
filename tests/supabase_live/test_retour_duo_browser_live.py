"""« Retour » de la barre verticale de l'iPhone Duo (retour de l'admin du 19.11 : « comme si j'allais en haut à gauche »),
recette RÉELLE : base de TEST, vrai navigateur, page Party avec le pont natif simulé, module Événements dans son cadre.
La page dit à l'app qu'il y a un retour (state.back) dès que l'écran du module a un bouton ‹ / Annuler / Fermer, et
PartyTabs.back() le touche : fiche → liste ; « Envoyer à un ami » (Nouveau message, « Annuler ») → fiche.
Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de TEST> python -m pytest
tests/supabase_live/test_retour_duo_browser_live.py -q"""
import json

import httpx

from tests.supabase_live.test_audiences_live import ADMIN, create_event
from tests.supabase_live.test_bar_soiree_browser_live import browser, party, pw  # noqa: F401
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = live
TITLE = 'Soirée recette retour Duo'
UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 27_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
      'PartyApp-iOS/1.0.0')


def session_json(phone: str) -> str:
    r = httpx.post(f'{TEST_URL}/auth/v1/verify', headers={'apikey': KEY_FILE.read_text().strip()}, timeout=30,
                   json={'type': 'sms', 'phone': phone, 'token': '123456'})
    assert r.status_code == 200, r.text
    return json.dumps(r.json())


def test_back_of_the_vertical_bar_presses_the_back_button_of_the_screen(browser, party):  # noqa: F811
    admin = Session(ADMIN)
    sql(f"delete from public.events where title = '{TITLE}'")
    event = create_event(admin, TITLE, visibility='all', public_link=True)
    ref = TEST_URL.split('//')[1].split('.')[0]
    bridge = f"""
    Object.defineProperty(navigator, 'standalone', {{ get: () => true, configurable: true }});
    window.__tabStates = [];
    if (window.top === window) window.PartyNative = {{ platform: 'ios', tabs: {{ update: (s) => window.__tabStates.push(s) }} }};
    localStorage.setItem('vp_install_dismissed', '1');
    localStorage.setItem('sb-{ref}-auth-token', {json.dumps(session_json(ADMIN))});
    """
    context = browser.new_context(viewport={'width': 430, 'height': 800}, user_agent=UA, is_mobile=True, has_touch=True)
    context.add_init_script(bridge)
    page = context.new_page()
    back = "window.__tabStates.length && window.__tabStates[window.__tabStates.length - 1].back"
    try:
        page.goto(f'{party}/?tab=events')
        page.wait_for_function("document.querySelector('#eventsFrame')?.src")
        page.evaluate(f"frameRoute('/events/event/{event}')")
        frame = page.frame_locator('#eventsFrame')
        pw.expect(frame.get_by_text(TITLE).first).to_be_visible(timeout=30000)
        page.wait_for_function(f"{back} === true", timeout=10000)
        frame.get_by_text('Envoyer à un ami').first.click()
        pw.expect(frame.get_by_text('Nouveau message').first).to_be_visible(timeout=15000)
        page.evaluate("PartyTabs.back()")  # « Annuler » de Nouveau message
        pw.expect(frame.get_by_text('Envoyer à un ami').first).to_be_visible(timeout=15000)
        page.evaluate("PartyTabs.back()")  # ‹ Événements de la fiche
        page.wait_for_function(f"{back} === false", timeout=15000)
        inner = next(f for f in page.frames if '/events' in f.url)
        assert inner.url.rstrip('/').endswith('/events'), inner.url
    finally:
        context.close()
        sql(f"delete from public.events where title = '{TITLE}'")
