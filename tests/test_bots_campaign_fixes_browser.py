"""Bugs trouvés par la campagne des bots (06.11.2026, base TEST réglée comme la prod), module Événements dans un vrai
navigateur (Supabase simulé) :
2. « + Proposer » seulement avec events.create ; jamais d'erreur RLS anglaise brute à l'écran ;
3. « + Proposer » effacé au défilement : sorti de l'arbre d'accessibilité (VoiceOver ne l'active plus) ;
6. retirer un invité : « Confirmer » à taille de doigt (≥ 44 px), texte entier ;
7. événement annulé : « Rouvrir » (events.manage_all) et « Supprimer » (organisateur, avec confirmation) ;
8. boutons selon les droits (Présent, sondage), /edit d'un autre, photos des autres demandées seulement si permis,
   surnom complet, titre de niveau 1, badge « SANS L'APP » seulement pour les personnes sans compte."""
import copy
import json

import pytest

from tests.test_events_browser import EVENT, USER, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import CORS, GUEST_LIST, expand_guests, guest, mock_invites, v2_origin  # noqa: F401

BASE = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1'
OTHER = 'eeeeeeee-0000-4000-8000-000000000001'
MEMBER = ['events.view', 'events.rsvp', 'events.plus_ones', 'events.see_participants']
RLS = 'new row violates row-level security policy for table "events"'
CATEGORY = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
EVENT_ROW = {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'description': 'Données fictives réservées aux tests.',
             'created_by': USER, 'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
             'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu de démonstration',
             'category_id': CATEGORY['id'], 'category': CATEGORY, 'event_tags': [], 'date_options': [], 'rsvps': [],
             'event_organizers': [], 'polls': [], 'bring_items': [], 'author': {'display_name': 'Compte de démonstration'},
             'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None,
             'rsvp_deadline': None, 'forum_enabled': True, 'all_day': False, 'price_chf': None, 'visibility': 'all'}


def reply(route, body, status=200):
    if route.request.method == 'OPTIONS':
        return route.fulfill(status=204, headers=CORS)
    route.fulfill(status=status, content_type='application/json', headers=CORS, body=json.dumps(body))


def as_perms(page, perms):
    page.route(f'{BASE}/rpc/my_permissions', lambda r: reply(r, perms))


def with_event(page, calls=None, count=1, **changes):
    """Liste et fiche d'événement (après mock_services : cette route passe devant) ; PATCH / DELETE notés."""
    event = {**copy.deepcopy(EVENT_ROW), **changes}

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        if calls is not None and request.method in ('PATCH', 'DELETE', 'POST'):
            calls.append((request.method, request.url, request.post_data))
        if request.method in ('PATCH', 'DELETE'):
            return reply(route, [])
        single = 'id=' in request.url
        rows = [event] + [{**event, 'id': f'{EVENT[:-2]}{i:02d}', 'title': f'Sortie de démonstration {i}'} for i in range(1, count)]
        reply(route, event if single else rows)
    page.route(f'{BASE}/events*', handle)
    return event


def open_event(page, origin):
    """Connexion puis fiche ouverte par son adresse (un événement annulé n'est plus dans la liste)."""
    page.goto(f'{origin}/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_text('Événements', exact=False).first).to_be_visible(timeout=15000)
    page.wait_for_timeout(800)
    page.goto(f'{origin}/events/event/{EVENT}', wait_until='domcontentloaded')


def new_page(browser, errors=None):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    page = context.new_page()
    if errors is not None:
        page.on('pageerror', lambda e: errors.append(str(e)))
    return context, page


# 2 --------------------------------------------------------------------------------------------------------------------
def test_member_without_events_create_sees_no_propose_button_and_no_form(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        as_perms(page, MEMBER)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('+ Proposer', exact=True)).to_have_count(0)
        pw.expect(page.get_by_role('button', name='Proposer un événement')).to_have_count(0)
        # Le formulaire ouvert par son adresse ne laisse pas tout remplir pour rien.
        page.goto(f'{v2_origin}/events/event/new', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Tu ne peux pas proposer d’événement', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_label('Titre', exact=False)).to_have_count(0)
    finally:
        context.close()


def test_a_row_level_security_refusal_is_shown_in_plain_french(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        as_perms(page, MEMBER)
        with_event(page, created_by=OTHER, author={'display_name': 'Bot Olga'})
        page.route(f'{BASE}/rsvps*', lambda r: reply(r, {'code': '42501', 'message': RLS.replace('"events"', '"rsvps"')}, 403))
        open_event(page, v2_origin)
        page.get_by_role('button', name='Présent', exact=False).first.click()
        pw.expect(page.get_by_text('Tu n’as pas le droit de faire ça', exact=False)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('row-level security', exact=False)).to_have_count(0)
    finally:
        context.close()


# 3 --------------------------------------------------------------------------------------------------------------------
def test_hidden_propose_button_leaves_the_accessibility_tree(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page, events=14)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        fab = page.get_by_role('button', name='Proposer un événement')
        pw.expect(fab).to_have_count(1, timeout=15000)
        page.mouse.move(195, 500)
        for _ in range(6):
            page.mouse.wheel(0, 400)
            page.wait_for_timeout(120)
        page.wait_for_timeout(600)
        # Effacé : ni visible, ni annoncé, ni activable (VoiceOver « activer » toucherait ce qui est derrière).
        pw.expect(fab).to_have_count(0)
        hidden = page.locator('[aria-label="Proposer un événement"]')
        assert hidden.count() == 1
        assert hidden.evaluate('e => !!e.closest("[aria-hidden=true]")')
        assert hidden.evaluate('e => e.tabIndex < 0 || e.closest("[inert]") !== null || getComputedStyle(e).pointerEvents === "none"')
        page.mouse.wheel(0, -300)
        pw.expect(fab).to_have_count(1, timeout=5000)
    finally:
        context.close()


# 6 --------------------------------------------------------------------------------------------------------------------
def test_remove_guest_confirm_button_is_finger_sized_with_its_whole_label(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        calls = mock_invites(page)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        expand_guests(page.get_by_label('Invités', exact=True))
        remove = page.get_by_role('button', name='Retirer Marco Costa')
        pw.expect(remove).to_have_count(1, timeout=15000)
        remove.scroll_into_view_if_needed()
        remove.evaluate('e => { let s = e; while (s && !(s.scrollWidth > s.clientWidth && getComputedStyle(s).overflowX !== "visible")) s = s.parentElement; s.scrollLeft = s.scrollWidth; }')
        page.wait_for_timeout(400)
        remove.click()
        confirm = page.get_by_role('button', name='Confirmer Marco Costa')
        pw.expect(confirm).to_be_visible(timeout=5000)
        page.wait_for_timeout(400)
        box = confirm.bounding_box()
        assert box['height'] >= 44 and box['width'] >= 44, box
        assert confirm.evaluate('e => [...e.querySelectorAll("*")].every(c => c.scrollWidth <= c.clientWidth + 1)'), 'texte coupé'
        assert box['x'] >= 0 and box['x'] + box['width'] <= 391, box
        confirm.click()
        pw.expect(page.get_by_text('Marco Costa', exact=True)).to_have_count(1)  # liste relue (simulée), appel parti
        assert any(c[0] == 'remove_invitee' for c in calls)
    finally:
        context.close()


# 7 --------------------------------------------------------------------------------------------------------------------
def test_admin_reopens_a_cancelled_event(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    calls = []
    try:
        mock_services(page)
        with_event(page, calls, status='cancelled', created_by=OTHER, author={'display_name': 'Bot Olga'})
        open_event(page, v2_origin)
        page.get_by_role('button', name='Rouvrir l’événement').click()
        page.get_by_role('button', name='Oui, rouvrir').click()
        page.wait_for_timeout(500)
        assert any(m == 'PATCH' and json.loads(body) == {'status': 'published'} for m, _, body in calls), calls
    finally:
        context.close()


def test_organizer_deletes_a_cancelled_event_after_confirming_and_cannot_reopen_it(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    calls = []
    try:
        mock_services(page)
        as_perms(page, MEMBER + ['events.create'])
        with_event(page, calls, status='cancelled')
        open_event(page, v2_origin)
        pw.expect(page.get_by_role('button', name='Rouvrir l’événement')).to_have_count(0)
        page.get_by_role('button', name='Supprimer l’événement').click()
        assert not [c for c in calls if c[0] == 'DELETE']  # rien avant la confirmation
        page.get_by_role('button', name='Oui, supprimer').click()
        page.wait_for_timeout(500)
        assert any(m == 'DELETE' for m, _, _ in calls), calls
    finally:
        context.close()


# 8 --------------------------------------------------------------------------------------------------------------------
def test_buttons_follow_rights_and_the_page_has_a_real_title(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    signed = []
    try:
        mock_services(page)
        as_perms(page, ['games.create', 'music.add'])  # Guest : ni events.view, ni events.rsvp
        with_event(page, created_by=OTHER, author={'display_name': 'Bot Olga'}, visibility='invited',
                   rsvps=[{'event_id': EVENT, 'user_id': OTHER, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False}])
        page.route('https://gsuetixzobooggeaubvb.supabase.co/storage/v1/object/sign/**', lambda r: (signed.append(r.request.url), reply(r, {'signedURL': '/x'}))[1])
        page.route(f'{BASE}/rpc/event_attendance*', lambda r: reply(r, []))
        open_event(page, v2_origin)
        pw.expect(page.get_by_role('heading', level=1, name='Sortie de démonstration (test local)')).to_have_count(1, timeout=15000)
        pw.expect(page.get_by_text('Tu viens ?', exact=True)).to_have_count(0)  # carte de réponse absente
        pw.expect(page.get_by_role('button', name='Présent', exact=True)).to_have_count(0)
        pw.expect(page.get_by_role('button', name='Modifier')).to_have_count(0)
        assert not [u for u in signed if f'/{USER}/' not in u], signed
        # /edit d'un événement qu'on n'organise pas : une page claire, pas le formulaire.
        page.goto(f'{v2_origin}/events/event/{EVENT}/edit', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Tu ne peux pas modifier cet événement', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Enregistrer', exact=False)).to_have_count(0)
    finally:
        context.close()


def test_add_poll_button_needs_polls_create(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        as_perms(page, MEMBER + ['events.create'])
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.evaluate("localStorage.setItem('party-event-form-mode', 'advanced')")
        page.goto(f'{v2_origin}/events/event/new', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Qui amène quoi', exact=False).first).to_be_attached(timeout=15000)
        pw.expect(page.get_by_role('button', name='+ Ajouter un sondage')).to_have_count(0)
    finally:
        context.close()


def test_guest_list_uses_whole_nicknames_and_marks_only_people_without_account(browser, v2_origin):  # noqa: F811
    people = [guest(4, 'Bot Max', None, 'person', has_app=False, light=False),
              guest(5, 'Bot Marc', None, 'person', has_app=False, light=False),
              guest(6, 'Léa', 'yes', 'link', has_app=False, light=True)]
    context, page = new_page(browser)
    try:
        mock_services(page, people=[{'id': 'aaaaaaaa-0000-4000-8000-000000000008', 'display_name': 'Bot Zoé'}])
        mock_invites(page, guest_list={**GUEST_LIST, 'people': people, 'links': []})
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_text('Sortie de démonstration (test local)', exact=True).click()
        expand_guests(page.get_by_label('Invités', exact=True))
        card = page.get_by_label('Invités', exact=True)
        pw.expect(card.get_by_text('Bot Max', exact=True)).to_be_visible(timeout=15000)
        # « SANS L'APP » : seulement Léa (arrivée par un lien, sans compte Party) ; un membre qui passe par le site, non.
        pw.expect(card.get_by_text('SANS L’APP', exact=True)).to_have_count(1)
        # Relancer les deux : surnom complet (« Bot Max », pas « Bot »).
        pw.expect(card.get_by_text('les 2 qui n’ont pas répondu', exact=False)).to_be_visible()
        card.get_by_role('button', name='Inviter', exact=True).click()
        sheet = page.get_by_label('Inviter à Sortie de démonstration (test local)')
        sheet.get_by_label('Chercher une personne ou un groupe').fill('zo')
        sheet.get_by_role('button', name='Ajouter Bot Zoé').click()
        pw.expect(sheet.get_by_role('button', name='Inviter Bot Zoé')).to_be_visible(timeout=5000)
        pw.expect(sheet.get_by_text('groupe.Ils', exact=False)).to_have_count(0)
    finally:
        context.close()


# 9 (décision de l'admin, 06.11) -----------------------------------------------------------------------------------------
def test_new_event_is_public_by_default_and_a_public_event_never_announces_itself(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.evaluate("localStorage.setItem('party-event-form-mode', 'advanced')")
        page.goto(f'{v2_origin}/events/event/new', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='✓ Publique + lien')).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Les événements publics ne préviennent personne : partage le lien.', exact=False)).to_be_visible()
        pw.expect(page.get_by_role('switch', name='Prévenir le groupe')).to_have_count(0)
        # Sur invitation, un groupe choisi (ici Vendredi Party) : « Prévenir le groupe » apparaît, éteint (annonces, 06.11).
        page.get_by_role('button', name='Sur invitation', exact=True).click()
        pw.expect(page.get_by_role('switch', name='Prévenir le groupe')).to_have_count(0)
        page.get_by_role('button', name='👥 Vendredi Party').click()
        # Vendredi Party seul : le libellé le dit (recette du 10.11 : « Prévenir le groupe » prêtait à confusion).
        pw.expect(page.get_by_role('switch', name='Prévenir les Membres Vendredi Party')).to_have_count(1)
        pw.expect(page.get_by_role('switch', name='Prévenir les Membres Vendredi Party')).not_to_be_checked()
    finally:
        context.close()
