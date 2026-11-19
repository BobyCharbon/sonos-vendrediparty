"""Entrée « Discussion » de la fiche d'un événement façon WhatsApp (demande de l'admin du 17.11.2026), module Événements dans
un vrai navigateur (Supabase simulé) :
- en haut de la fiche, « 💬 Discussion » et la pastille verte des non-lus (event_chat_prefs_get) ;
- la carte : dernier message (auteur : texte, heure), pastille, cloche du niveau (Tout / Mentions seulement / Rien, sourdine)
  qui appelle event_chat_set_level / event_chat_mute ; toucher la carte ouvre la page de la discussion ;
- dans l'app iPhone (pont PartyNative.chat), l'écran natif s'ouvre, et en version 2 « Réglages de la discussion… » aussi ;
- sans réponse de la base (ancienne base) : ni pastille ni cloche, la carte reste.
La base décide pour de vrai : tests/supabase_live/test_discussion_native_live.py."""
import json

from tests.test_c2_acces_browser import CORS, SUPA, VICTOR, chat_routes, fulfill, message, mock_terms, new_page
from tests.test_events_browser import EVENT, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import v2_origin  # noqa: F401


def chat_prefs(page, unread=3, level='mentions', missing=False):
    """Fonctions de la cloche, comme la base ; renvoie les appels (nom, arguments)."""
    calls = []
    state = {'level': level, 'muted_until': None, 'last_read_at': None, 'unread': unread}

    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        name = route.request.url.split('?')[0].rsplit('/', 1)[-1]
        args = json.loads(route.request.post_data or '{}')
        calls.append((name, args))
        if missing:
            return fulfill(route, {'code': 'PGRST202', 'message': f'Could not find the function public.{name}'}, 404)
        if name == 'event_chat_set_level':
            state['level'] = args['level']
        elif name == 'event_chat_mute':
            state['muted_until'] = args['until']
        fulfill(route, state)
    for name in ('event_chat_prefs_get', 'event_chat_set_level', 'event_chat_mute'):
        page.route(f'{SUPA}/rest/v1/rpc/{name}', handle)
    return calls


def open_event_page(page, origin):
    page.goto(f'{origin}/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT}', wait_until='domcontentloaded')


def test_the_event_page_shows_the_discussion_like_whatsapp_with_unread_and_bell(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_routes(page, [message(2, VICTOR, 'On se retrouve devant ?'), message(1, VICTOR, 'Salut')])  # du plus récent au plus ancien
        calls = chat_prefs(page, unread=3)
        open_event_page(page, v2_origin)
        # En haut de la fiche : « 💬 Discussion » et ses 3 non-lus.
        pw.expect(page.get_by_role('button', name='Discussion, 3 non lus')).to_be_visible(timeout=15000)
        # La carte : dernier message « auteur : texte », pastille verte, cloche « Mentions » (défaut).
        card = page.get_by_role('link', name='Ouvrir la discussion, 3 non lus')
        pw.expect(card).to_be_visible()
        pw.expect(card.get_by_text('Bot Victor : On se retrouve devant ?', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('3', exact=True)).to_be_visible()
        assert ('event_chat_prefs_get', {'e': EVENT}) in calls
        bell = page.get_by_role('button', name='Notifications de la discussion : Mentions')
        bell.click()
        pw.expect(page.get_by_role('radio', name='Mentions seulement')).to_have_attribute('aria-checked', 'true')
        page.get_by_role('radio', name='Tout').click()
        pw.expect(page.get_by_role('button', name='Notifications de la discussion : Tout')).to_be_visible()
        assert ('event_chat_set_level', {'e': EVENT, 'level': 'all'}) in calls, calls
        # Sourdine 8 h, puis Réactiver.
        page.get_by_role('button', name='Sourdine 8 h').click()
        pw.expect(page.get_by_role('button', name='Notifications de la discussion : Sourdine')).to_be_visible()
        until = [a['until'] for n, a in calls if n == 'event_chat_mute'][-1]
        assert until and until.endswith('Z'), calls
        page.get_by_role('button', name='Réactiver', exact=True).click()
        pw.expect(page.get_by_role('button', name='Notifications de la discussion : Tout')).to_be_visible()
        assert ('event_chat_mute', {'e': EVENT, 'until': None}) in calls, calls
        # Toucher la carte : la page de la discussion (navigateur).
        card.click()
        page.wait_for_url(f'**/events/event/{EVENT}/chat', timeout=10000)
        assert not errors, errors
    finally:
        ctx.close()


def test_inside_the_iphone_app_the_entry_opens_the_native_screen_and_its_settings(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        page.add_init_script("window.__opened = []; window.__settings = []; window.PartyNative = { chat: { version: 2, "
                             "openEvent: (id) => window.__opened.push(id), openEventSettings: (id) => window.__settings.push(id) } };")
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_routes(page, [message(1, VICTOR, 'Coucou')])
        chat_prefs(page, unread=1)
        open_event_page(page, v2_origin)
        top = page.get_by_role('button', name='Discussion, 1 non lu')
        pw.expect(top).to_be_visible(timeout=15000)
        top.click()
        page.wait_for_function('window.__opened.length > 0', timeout=10000)
        assert page.evaluate('window.__opened') == [EVENT]
        assert page.url.endswith(f'/events/event/{EVENT}')  # la fiche reste derrière l'écran natif
        # Ouverte, la discussion est lue : plus de pastille.
        pw.expect(page.get_by_role('button', name='Discussion', exact=True)).to_be_visible()
        page.get_by_role('button', name='Notifications de la discussion : Mentions').click()
        page.get_by_role('button', name='Réglages de la discussion…').click()
        assert page.evaluate('window.__settings') == [EVENT]
    finally:
        ctx.close()


def test_without_an_answer_from_the_base_the_card_stays_without_badge_or_bell(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_routes(page, [])
        chat_prefs(page, missing=True)
        open_event_page(page, v2_origin)
        card = page.get_by_role('link', name='Ouvrir la discussion', exact=True)
        pw.expect(card).to_be_visible(timeout=15000)
        pw.expect(card.get_by_text('Aucun message. Lance la discussion !', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Discussion', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Notifications de la discussion', exact=False)).to_have_count(0)
        assert not errors, errors
    finally:
        ctx.close()
