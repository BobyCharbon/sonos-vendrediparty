"""Recette de bout en bout du 27.11 (version Apple), correctifs web dans un vrai navigateur (Supabase simulé) :
1. co-organisateurs : un Guest ne se voit proposer que les personnes avec qui il a un lien (co_organizer_suggestions),
   jamais toute l'équipe ; base sans la fonction : personne ; un admin du site garde tout ;
2. feuille des conditions : « 18 ans et plus » visible sans défiler en 390×844, le texte complet déplié vient à l'écran ;
3. invitation à un sondage de dates : c'est l'ORGANISATEUR (host) qui choisira la date, pas l'invité qui a envoyé le lien ;
4. lien d'un groupe sans compte : nom, emoji, couleur du groupe et qui invite (group_invite_preview) ;
5. fiche tout juste publiée : aucune lecture des profils quand seuls moi et l'auteur sont concernés ;
6. « Accepter » une demande : bouton occupé pendant l'envoi, puis la ligne disparaît ;
7. Safari : « Installe Party ! » jamais par-dessus Événements avant la fin de l'inscription."""
import json

import pytest

from tests.test_c2_acces_browser import SUPA, fulfill, mock_terms, new_page
from tests.test_events_browser import DIST, EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import CARD, CORS, GUEST_LIST, IDS, TOKEN, mock_invites, open_event, v2_origin  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
TEAM = 'cccccccc-0000-4000-8000-000000000001'
FRIEND = 'cccccccc-0000-4000-8000-000000000002'
PEOPLE = [{'id': TEAM, 'display_name': 'Équipe Admin', 'role': 'admin'},
          {'id': FRIEND, 'display_name': 'Amie Organisatrice', 'role': 'organizer'}]
GUEST_PERMS = ['events.view', 'events.rsvp', 'events.create', 'polls.create', 'chat.write']
SAFARI = ('Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) '
          'Version/18.1 Mobile/15E148 Safari/604.1')


def rpc(page, name, body, status=200, calls=None):
    def handle(route):
        if route.request.method != 'OPTIONS' and calls is not None:
            calls.append(name)
        fulfill(route, body, status)
    page.route(f'{SUPA}/rest/v1/rpc/{name}', handle)


def open_form(page, origin, perms=None, suggestions=None, status=200):
    mock_services(page, people=PEOPLE)
    if perms is not None:
        rpc(page, 'my_permissions', perms)
    page.route(f'{SUPA}/rest/v1/role_permissions*', lambda r: fulfill(r, [{'role': 'admin'}, {'role': 'organizer'}]))
    calls = []
    rpc(page, 'co_organizer_suggestions', suggestions if suggestions is not None else [], status, calls)
    page.goto(f'{origin}/events/', wait_until='domcontentloaded')
    login(page)
    page.get_by_role('button', name='Proposer un événement').click(timeout=15000)
    page.get_by_text('Avancé', exact=True).first.click(timeout=15000)
    pw.expect(page.get_by_text('Co-organisateurs', exact=True)).to_be_visible(timeout=15000)
    return calls


# 1 --------------------------------------------------------------------------------------------------------------------
def test_a_guest_only_sees_people_he_is_linked_to_as_co_organizers(browser, events_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        calls = open_form(page, events_origin, perms=GUEST_PERMS, suggestions=[{**PEOPLE[1]}])
        pw.expect(page.get_by_text('Amie Organisatrice', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Équipe Admin', exact=True)).to_have_count(0)
        assert calls == ['co_organizer_suggestions']
        assert not errors, errors
    finally:
        ctx.close()


def test_without_the_function_a_guest_gets_no_suggestion_never_the_whole_team(browser, events_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        open_form(page, events_origin, perms=GUEST_PERMS,
                  suggestions={'code': 'PGRST202', 'message': 'Could not find the function public.co_organizer_suggestions'}, status=404)
        pw.expect(page.get_by_text('Personne à proposer pour l’instant', exact=False)).to_be_visible()
        pw.expect(page.get_by_text('Équipe Admin', exact=True)).to_have_count(0)
        pw.expect(page.get_by_text('Amie Organisatrice', exact=True)).to_have_count(0)
        assert not errors, errors
    finally:
        ctx.close()


def test_a_site_admin_keeps_every_account_that_can_edit(browser, events_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        calls = open_form(page, events_origin)  # droits d'admin du simulateur (events.manage_all)
        pw.expect(page.get_by_text('Amie Organisatrice', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Équipe Admin', exact=True)).to_be_visible()
        assert not calls  # aucune limite pour l'admin : la fonction n'est pas appelée
        assert not errors, errors
    finally:
        ctx.close()


# 2 --------------------------------------------------------------------------------------------------------------------
def test_the_terms_sheet_shows_the_age_line_without_scrolling_then_scrolls_to_the_full_text(browser, events_origin):  # noqa: F811
    errors, calls = [], []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page)
        mock_terms(page, calls, accepted=False)
        page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_role('button', name='Proposer un événement').click(timeout=15000)
        page.get_by_label('Titre', exact=True).fill('Soirée de recette')
        page.get_by_label('Début : jour', exact=True).fill('2030-12-12')
        page.get_by_role('button', name='Publier', exact=True).click()
        sheet = page.get_by_label('Conditions d’utilisation')
        adult = sheet.get_by_test_id('terms-adult')
        pw.expect(adult).to_contain_text('Party est réservée aux 18 ans et plus', timeout=15000)
        box, accept = adult.bounding_box(), sheet.get_by_role('button', name='J’accepte les conditions').bounding_box()
        assert box['y'] >= 0 and box['y'] + box['height'] <= accept['y'] + 1, (box, accept)  # entière, au-dessus du bouton
        sheet.get_by_role('button', name='Lire les conditions complètes').click()
        full = sheet.get_by_test_id('terms-full')
        pw.expect(full).to_be_visible()
        page.wait_for_timeout(800)  # défilement animé
        top = full.bounding_box()['y']
        assert 0 <= top < accept['y'], f'texte complet hors de vue : {top}'
        assert not errors, errors
    finally:
        ctx.close()


def test_on_a_small_phone_the_read_link_sits_in_the_fixed_bottom_next_to_later(browser, events_origin):  # noqa: F811
    """Contrôle Apple tour 6 : en 375×667, « Lire les conditions complètes » défile hors de vue ; un lien « Lire les
    conditions » reste dans le bas fixe, à côté de « Plus tard » (comme terms-read-all-bottom de la feuille iPhone)."""
    errors, calls = [], []
    ctx, page = new_page(browser, errors)
    try:
        page.set_viewport_size({'width': 375, 'height': 667})
        mock_services(page)
        mock_terms(page, calls, accepted=False)
        page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_role('button', name='Proposer un événement').click(timeout=15000)
        page.get_by_label('Titre', exact=True).fill('Soirée de recette')
        page.get_by_label('Début : jour', exact=True).fill('2030-12-12')
        page.get_by_role('button', name='Publier', exact=True).click()
        sheet = page.get_by_label('Conditions d’utilisation')
        read = sheet.get_by_role('button', name='Lire les conditions', exact=True)
        pw.expect(read).to_be_visible(timeout=15000)
        box, later = read.bounding_box(), sheet.get_by_role('button', name='Plus tard', exact=True).bounding_box()
        assert box['y'] >= 0 and box['y'] + box['height'] <= 667, box  # dans l'écran, sans défiler
        assert abs((box['y'] + box['height'] / 2) - (later['y'] + later['height'] / 2)) < 12, (box, later)  # même ligne
        read.click()
        full = sheet.get_by_test_id('terms-full')
        pw.expect(full).to_be_visible()
        page.wait_for_timeout(800)  # défilement animé
        assert 0 <= full.bounding_box()['y'] < 667
        assert not errors, errors
    finally:
        ctx.close()


# 3 --------------------------------------------------------------------------------------------------------------------
def test_a_poll_invitation_names_the_organizer_who_picks_the_date(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors, color_scheme='dark')
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'date_mode': 'poll', 'starts_at': None, 'inviter': 'Julien', 'host': 'Ludo'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ludo choisira celle qui arrange le plus de monde', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Julien choisira', exact=False)).to_have_count(0)
        assert not errors, errors
    finally:
        ctx.close()


# 4 --------------------------------------------------------------------------------------------------------------------
def test_a_group_link_without_account_shows_the_group_and_who_invites(browser, events_origin):  # noqa: F811
    errors, asked = [], []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page)

        def preview(route):
            if route.request.method != 'OPTIONS':
                asked.append(json.loads(route.request.post_data))
            fulfill(route, {'name': 'Les Copains du jeudi', 'emoji': '🎸', 'color': 'sky', 'inviter': 'Chloé'})
        page.route(f'{SUPA}/rest/v1/rpc/group_invite_preview', preview)
        page.goto(f'{events_origin}/events/group-invite/{TOKEN}', wait_until='domcontentloaded')
        teaser = page.get_by_test_id('group-invite-teaser')
        pw.expect(teaser.get_by_text('Chloé t’invite dans son groupe', exact=True)).to_be_visible(timeout=15000)
        pw.expect(teaser.get_by_text('Les Copains du jeudi', exact=True)).to_be_visible()
        pw.expect(teaser.get_by_text('🎸', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='M’inscrire ou me connecter')).to_be_visible()
        assert asked == [{'token': TOKEN}]
        assert not errors, errors
    finally:
        ctx.close()
    # Lien mort ou base d'avant : l'écran générique.
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page)
        page.route(f'{SUPA}/rest/v1/rpc/group_invite_preview', lambda r: fulfill(r, None))
        page.goto(f'{events_origin}/events/group-invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Tu es invité !', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_test_id('group-invite-teaser')).to_have_count(0)
        assert not errors, errors
    finally:
        ctx.close()


# 5 --------------------------------------------------------------------------------------------------------------------
def test_a_just_published_event_opens_without_reading_profiles(browser, events_origin):  # noqa: F811
    """Recette du 27.11 : la lecture des profils (lente pour un Guest) gardait la fiche en squelette ; moi et l'auteur
    sont déjà connus, aucune requête de plus."""
    errors, reads = [], []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page, event_extra={'author': {'id': USER, 'display_name': 'Compte de démonstration'}})
        page.on('request', lambda r: reads.append(r.url) if '/rest/v1/profiles' in r.url and 'id=in.' in r.url else None)
        page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_text('Sortie de démonstration (test local)', exact=True).first.click(timeout=15000)
        pw.expect(page.get_by_role('heading', name='Sortie de démonstration (test local)').first).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        assert not reads, reads
        assert not errors, errors
    finally:
        ctx.close()


# 6 --------------------------------------------------------------------------------------------------------------------
def test_accepting_a_request_shows_busy_then_the_row_leaves(browser, v2_origin):  # noqa: F811
    request = {'id': IDS[8], 'name': 'Nina', 'avatar_url': None, 'answer': 'yes', 'created_at': '2030-11-02T10:00:00Z',
               'invited_by': 'Julien', 'invited_by_id': IDS[1], 'link_label': 'Collègues'}
    errors, held = [], []
    ctx, page = new_page(browser, errors, color_scheme='dark')
    try:
        mock_services(page)
        mock_invites(page, guest_list={**GUEST_LIST, 'requests': [request]})

        def decide(route):
            if route.request.method == 'OPTIONS':
                return route.fulfill(status=204, headers=CORS)
            held.append(route)  # réponse retenue : on regarde l'écran pendant l'attente
        page.route(f'{SUPA}/rest/v1/rpc/decide_join_request', decide)
        card = open_event(page, v2_origin)
        accept = card.get_by_role('button', name='Accepter Nina')
        accept.click()
        for _ in range(50):
            if held:
                break
            page.wait_for_timeout(100)
        assert held, 'decide_join_request jamais appelé'
        pw.expect(accept).to_be_disabled()
        pw.expect(card.get_by_role('progressbar')).to_have_count(1)
        # La liste à jour revient : la ligne part, même si la relecture renvoie encore l'ancienne liste.
        page.route(f'{SUPA}/rest/v1/rpc/event_guest_list', lambda r: fulfill(r, {**GUEST_LIST, 'requests': []}))
        held[0].fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps({**GUEST_LIST, 'requests': []}))
        pw.expect(card.get_by_text('Nina attend ton accord', exact=True)).to_have_count(0, timeout=5000)
        pw.expect(page.get_by_text('Nina est invité : il voit l’événement', exact=True)).to_be_visible()
        assert not errors, errors
    finally:
        ctx.close()


# 7 --------------------------------------------------------------------------------------------------------------------
def test_safari_install_sheet_waits_for_music_and_never_covers_events(browser, events_origin):  # noqa: F811
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, user_agent=SAFARI, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        page.goto(f'{events_origin}/?tab=events', wait_until='domcontentloaded')
        page.wait_for_timeout(3500)  # bandeau prévu à 1,5 s, fenêtre à l'écran du prénom
        assert page.evaluate("document.getElementById('installSheet').classList.contains('hidden')")
        assert page.evaluate("document.getElementById('install').classList.contains('hidden')")
        # L'écran du prénom (Musique) se prépare derrière Événements : toujours rien par-dessus Événements.
        page.evaluate("show('hello')")
        page.wait_for_timeout(1000)
        assert page.evaluate("document.getElementById('installSheet').classList.contains('hidden')")
        # Dans Musique, là où l'on demande le prénom, la fenêtre d'installation peut venir.
        page.evaluate("showTab('music')")
        page.wait_for_function("!document.getElementById('installSheet').classList.contains('hidden')", timeout=5000)
        assert not errors, errors
    finally:
        ctx.close()
