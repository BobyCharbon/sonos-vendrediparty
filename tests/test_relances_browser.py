"""Relancer ceux qui n'ont pas répondu (demande de l'admin, 19.11.2026), module web dans un vrai navigateur (Supabase
simulé) : sur la fiche, carte « Invités » REPLIÉE, un bouton « ↻ Relancer les N qui n'ont pas répondu » ; un geste, une
confirmation simple, puis le bilan (« Kevin est prévenu dans Party », « Anaïs n'a pas l'app : envoie-lui le lien ») avec
le message prêt : feuille de partage du téléphone (appelée dans le toucher), WhatsApp, Messages, Copier. Seuls ceux qui
reçoivent les notifications partent à la base ; les autres ne sont notés « relancés » qu'une fois le partage parti.
Événement terminé ou réponses closes : plus de bouton. Captures dans $RELANCES_SHOTS si la variable est définie."""
import json
import os
from pathlib import Path

from tests.test_events_browser import EVENT, browser, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import CORS, GUEST_LIST, IDS, mock_invites, open_event, pytestmark, v2_origin  # noqa: F401

SHOTS = Path(os.environ['RELANCES_SHOTS']) if os.environ.get('RELANCES_SHOTS') else None


def shot(page, name: str):
    if SHOTS:
        page.wait_for_timeout(700)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'))


def route_nudges(page, reply: dict) -> list:
    calls = []

    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        args = json.loads(route.request.post_data or '{}')
        calls.append(args['people'])
        route.fulfill(status=200, content_type='application/json', headers=CORS,
                      body=json.dumps(reply if len(calls) == 1 else {'notified': 0, 'skipped': 0, 'share': args['people']}))
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/nudge_invitees', handle)
    return calls


def test_one_gesture_nudges_everyone_who_did_not_answer_then_shares_the_link_with_the_others(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    # Feuille de partage du téléphone : notée seulement si elle est appelée DANS le toucher (activation de l'utilisateur).
    page.add_init_script("""navigator.share = (data) => { if (!navigator.userActivation.isActive) return Promise.reject(new DOMException('', 'NotAllowedError'));
      window.__shared = data; return Promise.resolve(); };""")
    try:
        mock_services(page)
        mock_invites(page)
        calls = route_nudges(page, {'notified': 1, 'skipped': 0, 'share': []})
        card = open_event(page, v2_origin, expand=False)
        # Carte repliée : le bouton est là, sans ouvrir le détail. Sans réponse : Kevin (notifications) et Anaïs (sans l'app).
        button = card.get_by_role('button', name='↻ Relancer les 2 qui n’ont pas répondu')
        pw.expect(button).to_be_visible()
        card.scroll_into_view_if_needed()
        shot(page, '01-carte-repliee-bouton-relancer')

        button.click()
        sheet = page.get_by_label('Relancer les invités sans réponse', exact=True)
        pw.expect(sheet.get_by_text('Relancer 2 personnes ?', exact=True)).to_be_visible(timeout=5000)
        pw.expect(sheet.get_by_text('Kevin, Anaïs', exact=True)).to_be_visible()
        pw.expect(sheet.get_by_text('1 avec Party : une notification', exact=True)).to_be_visible()
        pw.expect(sheet.get_by_text('« Invitation de Compte de démonstration · Tu viens ? Réponds en un geste. »', exact=True)).to_be_visible()
        pw.expect(sheet.get_by_text('1 sans l’app', exact=True)).to_be_visible()
        assert calls == []  # rien ne part avant la confirmation
        shot(page, '02-confirmation')

        sheet.get_by_role('button', name='Confirmer la relance').click()
        pw.expect(sheet.get_by_text('Kevin est prévenu dans Party', exact=True)).to_be_visible(timeout=5000)
        assert calls == [[IDS[3]]]  # seulement ceux qui reçoivent les notifications
        pw.expect(sheet.get_by_text('Anaïs n’a pas l’app : envoie-lui le lien', exact=True)).to_be_visible()
        message = sheet.get_by_text('Hello Anaïs ! Petit rappel : tu viens à « Sortie de démonstration (test local) »', exact=False)
        pw.expect(message).to_be_visible()
        assert f'/events/event/{EVENT}' in message.inner_text()
        for how in ('WhatsApp', 'Messages', 'Copier le message'):
            pw.expect(sheet.get_by_role('button', name=how)).to_be_visible()
        shot(page, '03-bilan-prevenus-et-partage')

        sheet.get_by_role('button', name='Partager le message…').click()
        page.wait_for_function('window.__shared !== undefined', timeout=5000)
        shared = page.evaluate('window.__shared')
        assert shared['url'].endswith(f'/events/event/{EVENT}') and 'Petit rappel' in shared['text']
        page.wait_for_timeout(300)
        assert calls == [[IDS[3]], [IDS[6]]]  # Anaïs notée « relancée » une fois le partage parti
        sheet.get_by_role('button', name='Fermer', exact=True).last.click()
        pw.expect(sheet).to_have_count(0)
        assert page.locator('html').evaluate('e => e.scrollWidth <= innerWidth')
        assert not errors, errors
    finally:
        context.close()


def test_cancel_sends_nothing_and_closed_answers_offer_no_nudge(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page)
        calls = route_nudges(page, {'notified': 1, 'skipped': 0, 'share': []})
        card = open_event(page, v2_origin, expand=False)
        card.get_by_role('button', name='↻ Relancer les 2 qui n’ont pas répondu').click()
        sheet = page.get_by_label('Relancer les invités sans réponse', exact=True)
        sheet.get_by_role('button', name='Annuler').click()
        pw.expect(sheet).to_have_count(0)
        assert calls == []
    finally:
        context.close()

    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    try:
        # Date limite de réponse passée (comme un événement terminé) : plus de relance, ni en haut ni sur les lignes.
        mock_services(page, event_extra={'rsvp_deadline': '2020-11-14T18:00:00Z'})
        mock_invites(page)
        card = open_event(page, v2_origin)
        pw.expect(card.get_by_role('button', name='↻ Relancer', exact=False)).to_have_count(0)
        card.get_by_role('tab', name='2 Pas répondu').click()
        pw.expect(card.get_by_text('Kevin', exact=True)).to_be_visible()
        pw.expect(card.get_by_role('button', name='↻ Relancer', exact=False)).to_have_count(0)
        pw.expect(card.get_by_role('button', name='Relancer Kevin')).to_have_count(0)
    finally:
        context.close()
