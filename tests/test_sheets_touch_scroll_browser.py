"""Feuilles et fenêtres du module Événements : le DOIGT les fait défiler jusqu'au dernier élément (retour de l'admin du
06.11 : la feuille « Inviter » ne défilait pas dans l'app iPhone). Vrai navigateur (Supabase simulé), vrais gestes
tactiles de Chrome (CDP Input.synthesizeScrollGesture, source « touch » : défilement imbriqué, touch-action,
overscroll-behavior compris), jamais de défilement programmé :
- iPhone : la page Party dans l'app (html.native-tabs, pont natif simulé, module dans son cadre), 390 px ;
- Android : Chrome, module seul ;
- écran bas (petit iPhone, clavier ouvert, paysage) pour les fenêtres courtes : Signaler, billet, payer, QR.
Essai réel iPhone (simulateur + base de TEST) : ios/PartyUITests/InviteSheetScrollUITests.swift.
Captures : $SHEETS_SHOTS."""
import os
from pathlib import Path

import pytest

from tests.e2e.test_native_tabs import IPHONE, NATIVE_BRIDGE
from tests.test_compliance_0511_browser import OTHER, SUPABASE, event_row, json_route
from tests.test_event_tickets_browser import MINE_YES, tickets_backend, with_rsvps
from tests.test_event_tickets_issued_browser import issued_backend
from tests.test_wallet_browser import wallet_server
from tests.test_events_browser import ANDROID_PHONE, DIST, browser, login, mock_services, pw  # noqa: F401 (fixture browser)
from tests.test_invitations_v2_browser import mock_invites, v2_origin  # noqa: F401 (fixture)

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
SHOTS = Path(os.environ['SHEETS_SHOTS']) if os.environ.get('SHEETS_SHOTS') else None
TITLE = 'Sortie de démonstration (test local)'
# App iPhone : la vue web s'arrête au-dessus de la barre d'onglets native (écran 844 px).
IPHONE_APP = {**IPHONE, 'viewport': {'width': 390, 'height': 791}}
PEOPLE = [{'id': f'cccccccc-0000-4000-8000-{i:012d}', 'display_name': f'Marc {i}'} for i in range(12)]
SHORT = {'width': 390, 'height': 520}  # petit écran, clavier ouvert ou paysage


def shot(page, name: str):
    if SHOTS:
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


def visible(page, target) -> bool:
    """Entièrement dans l'écran (et pas caché sous le bas de la vue)."""
    try:
        box = target.bounding_box(timeout=3000)
    except pw.Error:
        return False
    return bool(box) and box['height'] > 0 and box['y'] >= 0 and box['y'] + box['height'] <= page.viewport_size['height']


def finger_up(page, cdp, x: float, y: float, distance: float = 320):
    """Un vrai glisser du doigt vers le haut (le contenu monte), parti du point (x, y)."""
    cdp.send('Input.synthesizeScrollGesture', {'x': x, 'y': y, 'yDistance': -distance, 'gestureSourceType': 'touch', 'speed': 1200})
    page.wait_for_timeout(250)


def finger_reaches(page, cdp, target, start, tries: int = 14) -> bool:
    """Glisse depuis `start` (un élément de la feuille ou un point) jusqu'à ce que `target` soit visible."""
    for _ in range(tries):
        if visible(page, target):
            return True
        if isinstance(start, tuple):
            x, y = start
        else:
            box = start.bounding_box()
            x, y = box['x'] + box['width'] / 2, box['y'] + min(box['height'] / 2, 20)
        finger_up(page, cdp, x, min(y, page.viewport_size['height'] - 30), min(320, page.viewport_size['height'] * 0.5))
    return visible(page, target)


def open_app(browser, origin, profile: dict, in_party: bool, **services):  # noqa: F811
    """Le module comme dans l'app iPhone (page Party, cadre, html.native-tabs) ou seul (Android)."""
    context = browser.new_context(**profile)
    if in_party:
        context.add_init_script(NATIVE_BRIDGE)
    page = context.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page, people=services.pop('people', ()))
    for setup in services.pop('setup', ()):
        setup(page)
    if in_party:
        page.goto(origin + '/', wait_until='domcontentloaded')
        page.wait_for_function('window.__tabStates.length > 0')
        assert page.evaluate("document.documentElement.classList.contains('native-tabs')")
        page.evaluate("PartyTabs.select('events')")
        frame = page.frame_locator('#eventsFrame')
    else:
        page.goto(origin + '/events/', wait_until='domcontentloaded')
        frame = page
    login(frame)
    return context, page, frame, errors


def open_invite_sheet(frame):
    frame.get_by_text(TITLE, exact=True).click()
    frame.get_by_role('button', name='Inviter', exact=True).click()
    # La fenêtre (role=dialog) porte le nom, une seule fois (campagne 2) ; la feuille elle-même est le panneau intérieur.
    dialog = frame.get_by_role('dialog', name=f'Inviter à {TITLE}', exact=True)
    pw.expect(frame.get_by_label(f'Inviter à {TITLE}', exact=True)).to_have_count(1)
    sheet = dialog.get_by_test_id('invite-sheet')
    pw.expect(sheet.get_by_text('🔗 Envoyer le lien', exact=True)).to_be_visible(timeout=15000)
    return sheet


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_finger_scrolls_the_invite_sheet_to_the_people_and_its_bottom(browser, v2_origin, device):  # noqa: F811
    """Feuille « Inviter » : du lien (Une personne / Plusieurs, places, date, aperçu, Partager) jusqu'aux groupes,
    aux personnes trouvées et à la règle tout en bas ; doigt posé sur les boutons du lien, comme un pouce."""
    profile, in_party = (IPHONE_APP, True) if device == 'iphone-app' else (ANDROID_PHONE, False)
    context, page, frame, errors = open_app(browser, v2_origin, profile, in_party, people=PEOPLE, setup=[mock_invites])
    try:
        sheet = open_invite_sheet(frame)
        sheet.get_by_label('Chercher une personne ou un groupe').fill('marc')
        page.wait_for_timeout(700)  # la feuille finit de monter
        shot(page, f'inviter-{device}-1-ouverte')
        cdp = context.new_cdp_session(page)
        last_person = sheet.get_by_text('Marc 11', exact=True)
        bottom = sheet.get_by_text('sans entrer dans le groupe', exact=False)
        assert not visible(page, bottom), 'feuille trop courte pour l’essai'
        # Le pouce se pose sur « Partager le lien… » puis sur le bloc du lien, pas dans un vide.
        for start in (sheet.get_by_role('button', name='Partager le lien…'), sheet.get_by_role('tab', name='Plusieurs')):
            if visible(page, start):
                before = last_person.bounding_box()['y']
                box = start.bounding_box()
                finger_up(page, cdp, box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, 260)
                assert last_person.bounding_box()['y'] < before - 100, 'le doigt posé sur un bouton ne fait pas défiler la feuille'
        assert finger_reaches(page, cdp, last_person, (195, page.viewport_size['height'] * 0.7)), 'les personnes trouvées restent hors d’atteinte'
        assert finger_reaches(page, cdp, bottom, (195, page.viewport_size['height'] * 0.7)), 'le bas de la feuille reste hors d’atteinte'
        shot(page, f'inviter-{device}-2-bas')
        # La feuille marche toujours : ajouter Marc 11, puis la fermer.
        sheet.get_by_role('button', name='Ajouter Marc 11').click()
        pw.expect(sheet.get_by_role('button', name='Retirer Marc 11')).to_be_visible()
        frame.get_by_role('button', name='Fermer', exact=True).first.click()
        pw.expect(sheet).to_have_count(0, timeout=5000)
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_on_a_short_screen_the_finger_reaches_the_invitation_qr_close_button(browser, v2_origin, device):  # noqa: F811
    """QR code de l'invitation sur un écran bas (petit iPhone, paysage) : « Fermer » s'atteint au doigt."""
    base, in_party = (IPHONE_APP, True) if device == 'iphone-app' else (ANDROID_PHONE, False)
    context, page, frame, errors = open_app(browser, v2_origin, {**base, 'viewport': SHORT}, in_party, setup=[mock_invites])
    try:
        sheet = open_invite_sheet(frame)
        cdp = context.new_cdp_session(page)
        qr_button = sheet.get_by_role('button', name='QR code')
        assert finger_reaches(page, cdp, qr_button, (195, SHORT['height'] * 0.7))
        qr_button.click()
        qr = frame.get_by_label('QR code de l’invitation', exact=True)
        pw.expect(qr.get_by_text('Montre ce code', exact=True)).to_be_visible(timeout=5000)
        page.wait_for_timeout(400)
        close = qr.get_by_role('button', name='Fermer', exact=True)
        assert finger_reaches(page, cdp, close, (195, SHORT['height'] * 0.6)), '« Fermer » du QR reste hors d’atteinte'
        # Le haut de la fenêtre aussi : rien n'est coupé au-dessus de l'écran.
        top = qr.get_by_text('Montre ce code', exact=True)
        for _ in range(6):
            if visible(page, top):
                break
            cdp.send('Input.synthesizeScrollGesture', {'x': 195, 'y': SHORT['height'] * 0.3, 'yDistance': 300, 'gestureSourceType': 'touch', 'speed': 1200})
            page.wait_for_timeout(250)
        assert visible(page, top), 'le haut du QR est coupé'
        shot(page, f'qr-{device}-ecran-bas')
        close.click()
        pw.expect(qr).to_have_count(0)
        assert not errors, errors
    finally:
        context.close()


def report_setup(page):
    ev = event_row(OTHER)
    json_route(page, f'{SUPABASE}/rest/v1/events?**', lambda r: ev if 'id=eq.' in r.url else [ev])
    json_route(page, f'{SUPABASE}/rest/v1/rpc/report_content', 'a1b2c3d4-0000-4000-8000-000000000001')


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_on_a_short_screen_the_finger_reaches_the_report_send_button(browser, v2_origin, device):  # noqa: F811
    """« Signaler cet événement » (raisons, commentaire, Envoyer) sur un écran bas : tout s'atteint au doigt."""
    base, in_party = (IPHONE_APP, True) if device == 'iphone-app' else (ANDROID_PHONE, False)
    context, page, frame, errors = open_app(browser, v2_origin, {**base, 'viewport': SHORT}, in_party, setup=[report_setup, mock_invites])
    try:
        frame.get_by_text('Soirée signalable (test local)', exact=True).first.click()
        report = frame.get_by_role('button', name='Signaler cet événement')
        cdp = context.new_cdp_session(page)
        pw.expect(report).to_be_attached(timeout=15000)
        assert finger_reaches(page, cdp, report, (195, SHORT['height'] * 0.6))
        report.click()
        sheet = frame.get_by_label('Signaler', exact=True)
        pw.expect(sheet.get_by_role('radio').first).to_be_visible(timeout=5000)
        page.wait_for_timeout(400)
        reason = sheet.get_by_role('radio').first
        reason.click()
        send = sheet.get_by_role('button', name='Envoyer', exact=True)
        assert not visible(page, send), 'fenêtre trop courte pour l’essai'
        assert finger_reaches(page, cdp, send, reason), '« Envoyer » du signalement reste hors d’atteinte'
        shot(page, f'signaler-{device}-ecran-bas')
        send.click()
        pw.expect(sheet.get_by_text('Merci, c’est envoyé', exact=True)).to_be_visible(timeout=5000)
        assert not errors, errors
    finally:
        context.close()


def ticket_setup(page):
    """Comme test_event_tickets_issued_browser : billet remis, place à 20 CHF pas encore payée."""
    event = with_rsvps(page, [MINE_YES], tickets_enabled=True)
    tickets_backend(page)
    wallet_server(page, True)
    issued_backend(page, 'ok', True, event=event)


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_on_a_short_screen_the_finger_reaches_the_bottom_of_the_ticket_and_pay_windows(browser, v2_origin, device):  # noqa: F811
    """Billet (QR, code, Fermer, Nouveau QR) et « Payer l'organisateur » (Twint, IBAN, J'ai payé, Fermer) sur un écran bas."""
    base, in_party = (IPHONE_APP, True) if device == 'iphone-app' else (ANDROID_PHONE, False)
    context, page, frame, errors = open_app(browser, v2_origin, {**base, 'viewport': SHORT}, in_party, setup=[ticket_setup, mock_invites])
    try:
        frame.get_by_text(TITLE, exact=True).click()
        cdp = context.new_cdp_session(page)
        show = frame.get_by_role('button', name='Afficher ton billet à montrer à l’entrée', exact=True)
        shot(page, f'billet-{device}-0-fiche')
        pw.expect(show).to_be_attached(timeout=15000)
        assert finger_reaches(page, cdp, show, (195, SHORT['height'] * 0.6))
        show.click()
        ticket = frame.get_by_label('Ton billet', exact=True)
        pw.expect(ticket.get_by_label('QR code de ton billet', exact=True)).to_be_visible(timeout=5000)
        page.wait_for_timeout(600)
        renew = ticket.get_by_role('button', name='Nouveau QR (l’ancien ne marchera plus)')
        assert not visible(page, renew), 'fenêtre trop courte pour l’essai'
        assert finger_reaches(page, cdp, renew, ticket.get_by_label('QR code de ton billet', exact=True)), 'le bas du billet reste hors d’atteinte'
        shot(page, f'billet-{device}-ecran-bas')
        ticket.get_by_role('button', name='Fermer', exact=True).click()
        pw.expect(ticket).to_have_count(0)

        pay = frame.get_by_role('button', name='Payer l’organisateur · 20 CHF', exact=True)
        assert finger_reaches(page, cdp, pay, (195, SHORT['height'] * 0.6))
        pay.click()
        declare = frame.get_by_role('button', name='J’ai payé', exact=True)
        pw.expect(declare).to_be_attached(timeout=10000)
        page.wait_for_timeout(400)
        close = frame.get_by_role('button', name='Fermer', exact=True).last
        assert finger_reaches(page, cdp, close, frame.get_by_text('CH93 0076 2011 6238 5295 7', exact=True)), '« Fermer » du paiement reste hors d’atteinte'
        shot(page, f'payer-{device}-ecran-bas')
        close.click()
        assert not errors, errors
    finally:
        context.close()


# ── Fermer une feuille comme sur iPhone (vidéo de l'admin du 06.11 : « je ne peux pas abaisser la fiche ») ──────────

def finger_down(page, x: float, y0: float, distance: float, steps: int = 14, hold_ms: int = 0):
    """Vrai glisser du doigt vers le BAS (événements tactiles CDP, comme un pouce qui tire la feuille)."""
    cdp = page.context.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y0}]})
    for i in range(1, steps + 1):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y0 + distance * i / steps}]})
        page.wait_for_timeout(16)
    if hold_ms:
        page.wait_for_timeout(hold_ms)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    page.wait_for_timeout(500)


def sheet_open_signal(page) -> bool:
    """La page Party sait qu'une feuille est ouverte (elle cache la pastille de Zicou qui couvrait le ✕)."""
    return page.evaluate("document.documentElement.classList.contains('events-sheet')")


def open_invite(browser, origin, device):  # noqa: F811
    profile, in_party = (IPHONE_APP, True) if device == 'iphone-app' else (ANDROID_PHONE, False)
    context, page, frame, errors = open_app(browser, origin, profile, in_party, people=PEOPLE, setup=[mock_invites])
    sheet = open_invite_sheet(frame)
    page.wait_for_timeout(600)  # la feuille finit de monter
    return context, page, frame, errors, sheet


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
@pytest.mark.parametrize('start', ['poignée', 'titre', 'contenu en haut'])
def test_pulling_the_invite_sheet_down_closes_it(browser, v2_origin, device, start):  # noqa: F811
    """Doigt sur la poignée, le titre « Inviter », ou le contenu (tout en haut) : tiré vers le bas, la feuille se ferme."""
    context, page, frame, errors, sheet = open_invite(browser, v2_origin, device)
    try:
        if device == 'iphone-app':
            assert sheet_open_signal(page)
        target = {'poignée': None, 'titre': sheet.get_by_text('Inviter', exact=True),
                  'contenu en haut': sheet.get_by_text('🔗 Envoyer le lien', exact=True)}[start]
        box = sheet.bounding_box()
        if target is None:
            x, y = box['x'] + box['width'] / 2, box['y'] + 12  # la poignée, tout en haut de la feuille
        else:
            b = target.bounding_box()
            x, y = b['x'] + min(b['width'] / 2, 60), b['y'] + b['height'] / 2
        shot(page, f'fermer-{device}-{start}-1-avant')
        finger_down(page, x, y, 420)
        pw.expect(sheet).to_have_count(0, timeout=3000)
        shot(page, f'fermer-{device}-{start}-2-apres')
        if device == 'iphone-app':
            assert not sheet_open_signal(page)
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_a_small_pull_brings_the_sheet_back_and_scrolled_content_scrolls_instead(browser, v2_origin, device):  # noqa: F811
    """Un petit glisser lent ne ferme pas (la feuille revient) ; contenu défilé, tirer vers le bas le fait remonter."""
    context, page, frame, errors, sheet = open_invite(browser, v2_origin, device)
    try:
        box = sheet.bounding_box()
        finger_down(page, box['x'] + box['width'] / 2, box['y'] + 12, 60, steps=20, hold_ms=200)
        pw.expect(sheet).to_be_visible()
        assert abs(sheet.bounding_box()['y'] - box['y']) < 2, 'la feuille n’est pas revenue en place'
        sheet.get_by_label('Chercher une personne ou un groupe').fill('marc')   # un contenu bien plus haut que l'écran
        cdp = context.new_cdp_session(page)
        title = sheet.get_by_text('🔗 Envoyer le lien', exact=True)
        for _ in range(3):
            finger_up(page, cdp, 195, page.viewport_size['height'] * 0.7)
        assert not visible(page, title)
        finger_down(page, 195, page.viewport_size['height'] * 0.4, 250)
        pw.expect(sheet).to_be_visible()  # le contenu a défilé, la feuille est restée
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_the_close_button_and_the_dimmed_background_close_the_invite_sheet(browser, v2_origin, device):  # noqa: F811
    context, page, frame, errors, sheet = open_invite(browser, v2_origin, device)
    try:
        close = sheet.get_by_role('button', name='Fermer', exact=True)
        b = close.bounding_box()
        assert visible(page, close) and b['x'] + b['width'] <= page.viewport_size['width'] - 8
        if device == 'iphone-app':
            # Vidéo de l'admin : la pastille de Zicou (page Party, en haut à droite) couvrait le ✕. Pastille affichée de
            # force (compte avec un Zicou) : cachée tant que la feuille est ouverte, de retour après.
            page.evaluate("document.getElementById('zicouFloat').classList.remove('hidden')")
            assert page.evaluate("getComputedStyle(document.getElementById('zicouFloat')).display") == 'none'
            hit = page.evaluate(f"document.elementFromPoint({b['x'] + b['width'] / 2}, {b['y'] + b['height'] / 2})?.id")
            assert hit == 'eventsFrame', f'le ✕ est couvert par #{hit}'
            # La feuille reste sous la barre d'état (sa poignée s'attrape) : marge du haut de l'iPhone respectée.
            assert sheet.bounding_box()['y'] >= page.evaluate("PartyEvents.frameInsets().top")
        close.click()
        pw.expect(sheet).to_have_count(0, timeout=3000)
        if device == 'iphone-app':
            assert page.evaluate("getComputedStyle(document.getElementById('zicouFloat')).display") != 'none'
        frame.get_by_role('button', name='Inviter', exact=True).click()
        pw.expect(sheet).to_be_visible(timeout=5000)
        page.wait_for_timeout(500)
        page.touchscreen.tap(195, sheet.bounding_box()['y'] - 12)   # le fond assombri, au-dessus de la feuille
        pw.expect(sheet).to_have_count(0, timeout=3000)
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_every_window_has_a_close_button_and_closes_when_pulled_down(browser, v2_origin, device):  # noqa: F811
    """QR de l'invitation, billet, payer l'organisateur : ✕ en haut à droite, et tirées vers le bas elles se ferment."""
    base, in_party = (IPHONE_APP, True) if device == 'iphone-app' else (ANDROID_PHONE, False)
    context, page, frame, errors = open_app(browser, v2_origin, base, in_party, setup=[ticket_setup, mock_invites])
    try:
        frame.get_by_text(TITLE, exact=True).click()
        cdp = context.new_cdp_session(page)
        # Billet : tiré vers le bas depuis sa poignée.
        show = frame.get_by_role('button', name='Afficher ton billet à montrer à l’entrée', exact=True)
        pw.expect(show).to_be_attached(timeout=15000)
        assert finger_reaches(page, cdp, show, (195, page.viewport_size['height'] * 0.6))
        show.click()
        ticket = frame.get_by_label('Ton billet', exact=True)
        pw.expect(ticket.get_by_role('button', name='Fermer la fenêtre')).to_be_visible(timeout=5000)
        page.wait_for_timeout(500)
        x_box = ticket.get_by_role('button', name='Fermer la fenêtre').bounding_box()
        finger_down(page, 195, x_box['y'] + x_box['height'] / 2, 400)
        pw.expect(ticket).to_have_count(0, timeout=3000)
        # Payer l'organisateur : ✕.
        pay = frame.get_by_role('button', name='Payer l’organisateur · 20 CHF', exact=True)
        assert finger_reaches(page, cdp, pay, (195, page.viewport_size['height'] * 0.6))
        pay.click()
        window = frame.get_by_label('Payer l’organisateur', exact=True)
        pw.expect(window.get_by_role('button', name='Fermer la fenêtre')).to_be_visible(timeout=10000)
        page.wait_for_timeout(400)
        window.get_by_role('button', name='Fermer la fenêtre').click()
        pw.expect(window).to_have_count(0, timeout=3000)
        assert not errors, errors
    finally:
        context.close()


@pytest.mark.parametrize('device', ['iphone-app', 'android'])
def test_the_invitation_qr_and_the_report_window_close_by_pulling_down(browser, v2_origin, device):  # noqa: F811
    context, page, frame, errors, sheet = open_invite(browser, v2_origin, device)
    try:
        cdp = context.new_cdp_session(page)
        qr_button = sheet.get_by_role('button', name='QR code')
        assert finger_reaches(page, cdp, qr_button, (195, page.viewport_size['height'] * 0.7))
        qr_button.click()
        qr = frame.get_by_label('QR code de l’invitation', exact=True)
        pw.expect(qr.get_by_role('button', name='Fermer la fenêtre')).to_be_visible(timeout=5000)
        page.wait_for_timeout(400)
        top = qr.get_by_text('Montre ce code', exact=True).bounding_box()
        finger_down(page, 195, top['y'] - 20, 400)
        pw.expect(qr).to_have_count(0, timeout=3000)
        pw.expect(sheet).to_be_visible()  # seule la fenêtre du QR s'est fermée
        assert not errors, errors
    finally:
        context.close()
    base, in_party = (IPHONE_APP, True) if device == 'iphone-app' else (ANDROID_PHONE, False)
    context, page, frame, errors = open_app(browser, v2_origin, base, in_party, setup=[report_setup, mock_invites])
    try:
        frame.get_by_text('Soirée signalable (test local)', exact=True).first.click()
        cdp = context.new_cdp_session(page)
        report = frame.get_by_role('button', name='Signaler cet événement')
        pw.expect(report).to_be_attached(timeout=15000)
        assert finger_reaches(page, cdp, report, (195, page.viewport_size['height'] * 0.6))
        report.click()
        window = frame.get_by_label('Signaler', exact=True)
        close = window.get_by_role('button', name='Fermer la fenêtre')
        pw.expect(close).to_be_visible(timeout=5000)
        page.wait_for_timeout(400)
        b = close.bounding_box()
        finger_down(page, b['x'] - 120, b['y'] + b['height'] / 2, 420)
        pw.expect(window).to_have_count(0, timeout=3000)
        assert not errors, errors
    finally:
        context.close()
