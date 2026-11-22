"""Discussion d'un événement façon WhatsApp (demande de l'admin du 16.11.2026), module Événements dans un vrai navigateur
(Supabase simulé) :
- l'organisation voit 📣 (annonce) et les citations @toutlemonde / @present ; un invité ne les voit pas et est prévenu ;
- annonce en carte dans le fil et en bandeau ; séparateur de jour ; heure dans la bulle ; envoi d'une annonce ;
- dans l'app iPhone (pont PartyNative.chat), « Discussion » ouvre l'écran natif au lieu de la page web ;
- 17.11 (discussion native, migration 20261117190000) : en-tête WhatsApp (titre, « date · N participants »), cloche
  (Mentions seulement par défaut, Tout / Rien, sourdine), « Nouveaux messages », « Seule l'organisation peut écrire »,
  infos de la discussion (Qui peut écrire, recherche qui montre le message, « Signaler la description »).
La base (guard_message_change) décide pour de vrai : tests/supabase_live/test_discussion_evenement_live.py."""
import json

from tests.test_c2_acces_browser import SUPA, VICTOR, chat_routes, fulfill, message, mock_terms, new_page, open_chat
from tests.test_events_browser import EVENT, USER, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import v2_origin  # noqa: F401


def chat_state(page, staff, **more):
    page.route(f'{SUPA}/rest/v1/rpc/event_chat_state', lambda r: fulfill(r, {
        'title': 'Sortie de démonstration (test local)', 'forum': True, 'status': 'published', 'write': True,
        'staff': staff, 'moderate': False, 'muted': False, **more}))
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


def test_a_guest_tags_the_people_the_base_allows_including_invitees_without_answer(browser, v2_origin):  # noqa: F811
    """Avis f0e2fd838ab8 (22.11) : tout participant cite des @surnoms ; les suggestions sont celles de la base
    (event_chat_taggable : organisation, Présent, Peut-être, invités sans réponse hors événement public)."""
    ctx, page = new_page(browser)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_state(page, staff=False)
        nina = '99999999-0000-4000-8000-000000000009'
        page.route(f'{SUPA}/rest/v1/rpc/event_chat_taggable', lambda r: fulfill(r, [
            {'id': VICTOR, 'display_name': 'Bot Victor', 'avatar_url': None},
            {'id': nina, 'display_name': 'Nina Sans Réponse', 'avatar_url': None}]))
        posts = chat_routes(page, [message(1, VICTOR, 'Coucou')])
        open_chat(page, v2_origin)
        field = page.get_by_label('Message', exact=True)
        pw.expect(field).to_be_visible(timeout=15000)
        field.fill('@ni')
        pw.expect(page.get_by_role('menuitem', name='Citer Nina Sans Réponse')).to_be_visible()
        page.get_by_role('menuitem', name='Citer Nina Sans Réponse').click()
        field.press_sequentially('tu viens ?')
        page.get_by_role('button', name='Envoyer', exact=True).click()
        page.wait_for_timeout(1000)
        sent = json.loads(posts[-1])
        assert sent['mentions'] == [nina] and sent['body'].startswith('@Nina Sans Réponse'), sent
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


def chat_rpcs(page, prefs=None, hits=()):
    """Fonctions de la discussion native (agent A) ; renvoie les appels (nom, arguments)."""
    calls = []
    state = {'level': 'mentions', 'muted_until': None, 'last_read_at': None, 'unread': 0, **(prefs or {})}

    def handle(route):
        if route.request.method == 'OPTIONS':
            return fulfill(route, None)
        name = route.request.url.rsplit('/', 1)[1].split('?')[0]
        args = json.loads(route.request.post_data or '{}')
        calls.append((name, args))
        if name == 'event_chat_set_level':
            state['level'] = args['level']
        elif name == 'event_chat_mute':
            state['muted_until'] = args['until']
        result = {'event_chat_search': list(hits), 'event_chat_media': [], 'event_chat_mark_read': {'unread': 0}}.get(name, state)
        fulfill(route, result)
    for name in ('event_chat_prefs_get', 'event_chat_set_level', 'event_chat_mute', 'event_chat_mark_read', 'event_chat_set_settings',
                 'event_chat_media', 'event_chat_search'):
        page.route(f'{SUPA}/rest/v1/rpc/{name}', handle)
    return calls


def test_whatsapp_header_bell_and_new_messages_divider(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_state(page, staff=False)
        calls = chat_rpcs(page, prefs={'last_read_at': '2030-11-01T10:01:30Z', 'unread': 2})
        chat_routes(page, [message(3, VICTOR, 'Et la musique ?'), message(2, VICTOR, 'Qui vient ?'), message(1, USER, 'Salut')])
        open_chat(page, v2_origin)
        # En-tête : titre, « date · N participants » (1 présent : le compte de démonstration).
        header = page.get_by_role('button', name='Sortie de démonstration (test local), ', exact=False).first
        pw.expect(header).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('1 participant', exact=False).first).to_be_visible()
        # Premier non-lu : « 2 nouveaux messages » juste avant « Qui vient ? » ; la discussion est notée lue.
        pw.expect(page.get_by_role('heading', name='2 nouveaux messages')).to_be_visible()
        page.wait_for_timeout(500)
        assert any(c[0] == 'event_chat_mark_read' and c[1] == {'e': EVENT} for c in calls), calls
        # Cloche : Mentions seulement par défaut ; « Tout » puis sourdine 8 h.
        bell = page.get_by_role('button', name='Notifications : Mentions seulement')
        bell.click()
        menu = page.get_by_role('menu', name='Notifications de la discussion')
        pw.expect(menu.get_by_role('menuitemradio', name='Mentions seulement')).to_have_attribute('aria-checked', 'true')
        menu.get_by_role('menuitemradio', name='Tout', exact=True).click()
        pw.expect(page.get_by_role('button', name='Notifications : Tout')).to_be_visible()
        assert ('event_chat_set_level', {'e': EVENT, 'level': 'all'}) in calls, calls
        page.get_by_role('button', name='Notifications : Tout').click()
        page.get_by_role('menuitem', name='Sourdine 8 heures').click()
        pw.expect(page.get_by_role('button', name='Notifications : Tout, en sourdine')).to_be_visible()
        until = next(c[1]['until'] for c in calls if c[0] == 'event_chat_mute')
        assert until.startswith('20') and until != 'infinity', until
        assert not errors, errors
    finally:
        ctx.close()


def test_only_the_organisation_writes_when_the_organiser_chose_so(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_state(page, staff=False, write_mode='staff', can_write=False, description='Pas de spam, merci !')
        calls = chat_rpcs(page)
        chat_routes(page, [message(1, VICTOR, 'Bienvenue')])
        open_chat(page, v2_origin)
        pw.expect(page.get_by_text('Seule l’organisation peut écrire dans cette discussion.', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_label('Message', exact=True)).to_have_count(0)
        # Infos : la description et « Signaler la description » (Apple 1.2), pas de réglages de l'organisation.
        page.get_by_role('button', name='Sortie de démonstration (test local), ', exact=False).first.click()
        pw.expect(page.get_by_text('Pas de spam, merci !', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Réglages de l’organisation', exact=True)).to_have_count(0)
        page.get_by_role('button', name='Signaler la description').click()
        pw.expect(page.get_by_text('la description de la discussion', exact=False).first).to_be_visible()
        assert not [c for c in calls if c[0] == 'event_chat_set_settings']
    finally:
        ctx.close()


def test_the_organisation_chooses_who_writes_and_search_shows_the_message(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        chat_state(page, staff=True)
        hit = message(1, VICTOR, 'Le code de la porte est 1234')
        calls = chat_rpcs(page, hits=[{'message_id': hit['id'], 'at': hit['created_at'], 'author': VICTOR, 'snippet': 'code de la porte'}])
        chat_routes(page, [message(2, VICTOR, 'À tout à l’heure'), hit])
        open_chat(page, v2_origin)
        page.get_by_role('button', name='Sortie de démonstration (test local), ', exact=False).first.click(timeout=15000)
        pw.expect(page.get_by_text('Réglages de l’organisation', exact=True)).to_be_visible()
        page.get_by_role('tab', name='Organisation seulement').click()
        page.wait_for_timeout(500)
        assert ('event_chat_set_settings', {'e': EVENT, 'write': 'staff', 'description': None}) in calls, calls
        # Recherche : le résultat ramène au message dans le fil.
        page.get_by_label('Rechercher dans la discussion', exact=True).fill('porte')
        result = page.get_by_role('button', name='Bot Victor : code de la porte, voir le message')
        pw.expect(result).to_be_visible(timeout=5000)
        assert ('event_chat_search', {'e': EVENT, 'q': 'porte'}) in calls, calls
        result.click()
        pw.expect(page.get_by_text('Le code de la porte est 1234', exact=True)).to_be_in_viewport()
        pw.expect(page.get_by_label('Message', exact=True)).to_be_visible()
        assert not errors, errors
    finally:
        ctx.close()
