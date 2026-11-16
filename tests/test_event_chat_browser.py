"""Discussion d'un événement façon WhatsApp (demande de l'admin du 16.11.2026), module Événements dans un vrai navigateur
(Supabase simulé) :
- l'organisation voit 📣 (annonce) et les citations @toutlemonde / @present ; un invité ne les voit pas et est prévenu ;
- annonce en carte dans le fil et en bandeau ; séparateur de jour ; heure dans la bulle ; envoi d'une annonce ;
- dans l'app iPhone (pont PartyNative.chat), « Discussion » ouvre l'écran natif au lieu de la page web.
La base (guard_message_change) décide pour de vrai : tests/supabase_live/test_discussion_evenement_live.py."""
import json

from tests.test_c2_acces_browser import SUPA, VICTOR, chat_routes, fulfill, message, mock_terms, new_page, open_chat
from tests.test_events_browser import EVENT, USER, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import v2_origin  # noqa: F401


def chat_state(page, staff):
    page.route(f'{SUPA}/rest/v1/rpc/event_chat_state', lambda r: fulfill(r, {
        'title': 'Sortie de démonstration (test local)', 'forum': True, 'status': 'published', 'write': True,
        'staff': staff, 'moderate': False, 'muted': False}))
    page.route(f'{SUPA}/rest/v1/rpc/event_chat_people', lambda r: fulfill(r, [
        {'id': USER, 'display_name': 'Compte de démonstration', 'avatar_url': None, 'rsvp': 'yes', 'organizer': staff, 'invited': False},
        {'id': VICTOR, 'display_name': 'Bot Victor', 'avatar_url': None, 'rsvp': 'maybe', 'organizer': False, 'invited': False}]))


def announced(i, user, body):
    return {**message(i, user, body), 'pinned': True, 'announcement': True}


def test_the_organisation_announces_and_tags_everyone(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_state(page, staff=True)
        posts = chat_routes(page, [message(2, VICTOR, 'Salut @Compte de démonstration'), announced(1, VICTOR, '@annonce Rendez-vous devant la salle')])  # du plus récent au plus ancien, comme la base
        open_chat(page, v2_origin)
        # Annonce : carte dans le fil (sans « @annonce ») ; séparateur du jour ; l'heure dans la bulle.
        pw.expect(page.get_by_text('📣 ANNONCE', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Rendez-vous devant la salle', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('heading', name='1 novembre 2030')).to_be_visible()
        bubble = page.get_by_text('Salut @Compte de démonstration', exact=True)
        pw.expect(bubble).to_be_visible()
        assert page.get_by_text('Salut @Compte de démonstration', exact=True).locator('xpath=../..').inner_text().strip().endswith('11:02')
        # Citations de l'organisation proposées après l'@.
        field = page.get_by_label('Message', exact=True)
        field.fill('@tou')
        pw.expect(page.get_by_role('menuitem', name='@toutlemonde : Tout le monde : invités et participants')).to_be_visible()
        field.fill('@pre')
        pw.expect(page.get_by_role('menuitem', name='@present : Les présents et les peut-être')).to_be_visible()
        # 📣 : le message part en annonce.
        page.get_by_role('button', name='Faire une annonce').click()
        field.fill('Parking derrière la salle')
        page.get_by_role('button', name='Publier l’annonce').click()
        page.wait_for_timeout(1000)
        sent = json.loads(posts[-1])
        assert sent['announcement'] is True and sent['event_id'] == EVENT and sent['body'] == 'Parking derrière la salle', sent
        assert not errors, errors
    finally:
        ctx.close()


def test_a_guest_has_no_announcement_and_is_told_before_tagging_everyone(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_state(page, staff=False)
        chat_routes(page, [message(1, VICTOR, 'Coucou')])
        open_chat(page, v2_origin)
        field = page.get_by_label('Message', exact=True)
        pw.expect(field).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Faire une annonce')).to_have_count(0)
        field.fill('@tou')
        pw.expect(page.get_by_role('menuitem', name='@toutlemonde : Tout le monde : invités et participants')).to_have_count(0)
        field.fill('@toutlemonde venez !')
        pw.expect(page.get_by_text('réservés à l’organisation de l’événement', exact=False)).to_be_visible()
    finally:
        ctx.close()


def test_inside_the_iphone_app_the_discussion_opens_the_native_screen(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        page.add_init_script("window.__opened = []; window.PartyNative = { chat: { openEvent: (id) => window.__opened.push(id) } };")
        mock_services(page)
        mock_terms(page, [], accepted=True)
        chat_routes(page, [message(1, VICTOR, 'Coucou')])
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        # Lien direct vers la page web de la discussion (notification, ancien lien) : l'écran natif, la fiche derrière.
        page.goto(f'{v2_origin}/events/event/{EVENT}/chat', wait_until='domcontentloaded')
        page.wait_for_function('window.__opened && window.__opened.length > 0', timeout=15000)
        assert page.evaluate('window.__opened') == [EVENT]
        page.wait_for_url(f'**/events/event/{EVENT}', timeout=10000)
    finally:
        ctx.close()
