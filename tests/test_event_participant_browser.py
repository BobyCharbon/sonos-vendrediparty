"""Parcours PARTICIPANT dans le vrai module construit (navigateur, Supabase simulé : aucun SMS, aucune notification) :
réponse Absent / Peut-être sur un événement à places limitées (jamais « liste d'attente »), accompagnants réservés à
qui en a le droit, accompagnant de plus en liste d'attente quand l'événement est complet (affichage participant et
liste d'attente), vote du sondage de dates lisible au lecteur d'écran.
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json
import re

import pytest

from tests.test_events_browser import DIST, EVENT, USER, browser, events_origin, login, mock_services  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
REST = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
LEA = '7c0ffee0-0000-4000-8000-0000000000aa'
GUEST_PERMS = ['events.rsvp', 'chat.write', 'games.create', 'music.add']


def event_row(**fields) -> dict:
    base = {'id': EVENT, 'title': 'Soirée de test participant', 'description': '', 'created_by': LEA, 'status': 'published',
            'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'poll_deadline': None,
            'members_can_propose_dates': True, 'location_name': None, 'location_address': None, 'location_url': None,
            'price_chf': None, 'payment_info': None, 'max_participants': 2, 'waitlist_enabled': True, 'allow_plus_ones': True,
            'max_plus_ones': 2, 'allow_maybe': True, 'rsvp_deadline': None, 'visibility': 'all', 'public_link': True,
            'show_participants': True, 'pot_enabled': False, 'tickets_enabled': False, 'forum_enabled': False,
            'cover_url': None, 'category_id': None, 'created_at': '2026-11-01T08:00:00Z', 'updated_at': '2026-11-01T08:00:00Z',
            'category': None, 'author': {'id': LEA, 'display_name': 'Léa'}, 'event_tags': [], 'event_organizers': [],
            'date_options': [], 'polls': [], 'bring_items': [], 'event_groups': [], 'rsvps': []}
    return {**base, **fields}


def rsvp(user: str, status: str, waitlisted: bool = False, plus_ones: int = 0, plus_ones_waitlisted: int | None = None,
         since: str | None = None, updated_at: str = '2026-11-01T08:00:00Z') -> dict:
    row = {'event_id': EVENT, 'user_id': user, 'status': status, 'waitlisted': waitlisted, 'plus_ones': plus_ones,
           'note': None, 'set_by': None, 'updated_at': updated_at}
    if plus_ones_waitlisted is not None:  # base à jour (20261105143000) : accompagnants en liste d'attente
        row |= {'plus_ones_waitlisted': plus_ones_waitlisted, 'plus_ones_waitlisted_since': since}
    return row


def open_event(browser, origin, event: dict, perms: list[str] | None = None):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)

    def events(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        single = 'vnd.pgrst.object' in (route.request.headers.get('accept') or '')
        route.fulfill(status=200, content_type='application/json', body=json.dumps(event if single else [event]), headers=HEADERS)
    page.route(REST + 'events?**', events)
    page.route(REST + 'profiles?**', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS,
                                                          body=json.dumps([{'id': USER, 'display_name': 'Camille'}, {'id': LEA, 'display_name': 'Léa'}])))
    if perms is not None:
        page.route(REST + 'rpc/my_permissions', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS, body=json.dumps(perms)))
    page.goto(origin + '/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_role('button', name='Se connecter', exact=True)).to_have_count(0, timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT}', wait_until='domcontentloaded')
    pw.expect(page.get_by_text('Ta réponse').or_(page.get_by_text('Tu viens ?')).or_(page.get_by_text('Quelle date ?')).first).to_be_visible(timeout=15000)
    return context, page


def test_an_absent_answer_on_a_limited_event_never_says_waitlist(browser, events_origin):
    # La base laisse « waitlisted » à vrai sur une réponse Absent / Peut-être (passée par Présent en attente).
    ev = event_row(rsvps=[rsvp(USER, 'no', waitlisted=True), rsvp(LEA, 'maybe', waitlisted=True)])
    context, page = open_event(browser, events_origin, ev)
    try:
        pw.expect(page.get_by_text('Dommage ! Tu es noté absent.')).to_be_visible()
        assert page.get_by_text('liste d’attente', exact=False).count() == 0
        pw.expect(page.get_by_text('PEUT-ÊTRE · 1')).to_be_visible()  # Léa reste visible dans « Qui vient ? »
    finally:
        context.close()


def test_a_guest_without_the_right_sees_no_extra_guest_stepper(browser, events_origin):
    ev = event_row(rsvps=[rsvp(USER, 'yes')])
    context, page = open_event(browser, events_origin, ev, perms=GUEST_PERMS)
    try:
        pw.expect(page.get_by_text('C’est noté, tu viens !')).to_be_visible()
        assert page.get_by_role('button', name='Ajouter un accompagnant', exact=True).count() == 0
        pw.expect(page.get_by_text('Les accompagnants sont réservés aux membres du groupe', exact=False)).to_be_visible()
    finally:
        context.close()


def test_on_a_full_event_an_extra_guest_goes_on_the_waitlist(browser, events_origin):
    ev = event_row(rsvps=[rsvp(USER, 'yes', plus_ones_waitlisted=0), rsvp(LEA, 'yes')])
    context, page = open_event(browser, events_origin, ev)
    sent: list[dict] = []

    def rsvps(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        sent.append(json.loads(route.request.post_data or '{}'))
        route.fulfill(status=204, headers=HEADERS)
    page.route(REST + 'rsvps?**', rsvps)
    try:
        plus = page.get_by_role('button', name='Ajouter un accompagnant', exact=True)
        pw.expect(plus).to_be_enabled()  # complet : on peut quand même ajouter, l'accompagnant attendra
        pw.expect(page.get_by_text('Complet : un accompagnant de plus passe en liste d’attente', exact=False)).to_be_visible()
        plus.click()
        page.wait_for_timeout(500)
        assert sent and sent[-1]['plus_ones'] == 1 and sent[-1]['plus_ones_waitlisted'] == 0  # le total ; la base répartit
    finally:
        context.close()


def test_the_participant_sees_confirmed_and_waiting_extra_guests(browser, events_origin):
    ev = event_row(max_participants=3, rsvps=[
        rsvp(USER, 'yes', plus_ones=1, plus_ones_waitlisted=1, since='2026-11-02T08:00:00Z'), rsvp(LEA, 'yes')])
    context, page = open_event(browser, events_origin, ev)
    try:
        pw.expect(page.get_by_text('Toi + 1 accompagnant confirmé · 1 en liste d’attente', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('+2', exact=True)).to_be_visible()  # le compteur montre le total voulu
        pw.expect(page.get_by_text('C’est noté, tu viens !')).to_be_visible()  # la personne garde sa place
        pw.expect(page.get_by_text('PRÉSENTS · 3')).to_be_visible()  # confirmés seulement
        pw.expect(page.get_by_text('LISTE D’ATTENTE · 1')).to_be_visible()
        pw.expect(page.get_by_role('button', name='Profil de Ton accompagnant', exact=True)).to_be_visible()
    finally:
        context.close()


def test_the_waitlist_lists_waiting_extra_guests_in_order_of_arrival(browser, events_origin):
    """Vue de l'organisateur (ou de tous si la liste est visible) : l'accompagnant en attente de Léa, puis une personne."""
    other = '7c0ffee0-0000-4000-8000-0000000000bb'
    ev = event_row(max_participants=2, rsvps=[
        rsvp(USER, 'yes'), rsvp(LEA, 'yes', plus_ones_waitlisted=1, since='2026-11-02T08:00:00Z'),
        rsvp(other, 'yes', waitlisted=True, updated_at='2026-11-03T08:00:00Z')])
    context, page = open_event(browser, events_origin, ev)
    try:
        pw.expect(page.get_by_text('PRÉSENTS · 2')).to_be_visible()
        pw.expect(page.get_by_text('LISTE D’ATTENTE · 2')).to_be_visible()
        waiting = page.get_by_label('Liste d’attente : Accompagnant de Léa, ?', exact=True)
        pw.expect(waiting).to_be_visible()
    finally:
        context.close()


def test_date_poll_choices_name_their_date_for_screen_readers(browser, events_origin):
    ev = event_row(date_mode='poll', starts_at=None, max_participants=None,
                   date_options=[{'id': 'd1', 'event_id': EVENT, 'starts_at': '2030-11-20T18:00:00Z', 'proposed_by': None, 'date_votes': []}])
    context, page = open_event(browser, events_origin, ev)
    try:
        pw.expect(page.get_by_role('button', name='Oui : Mer. 20 nov. · 19:00', exact=True)).to_be_visible()
    finally:
        context.close()


def test_list_search_tabs_and_attendance_pill(browser, events_origin):
    """Liste : la recherche trouve par lieu, l'onglet Sondages ne garde que le sondage, la pastille compte présents et peut-être."""
    soiree = event_row(location_name='Bar du Lac', max_participants=None,
                       rsvps=[rsvp(LEA, 'yes', plus_ones=1), rsvp(USER, 'maybe', waitlisted=True)])
    sondage = event_row(id=EVENT[:-2] + '99', title='Week-end à choisir', date_mode='poll', starts_at=None, max_participants=None,
                        date_options=[{'id': 'd1', 'date_votes': []}])
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)
    page.route(REST + 'events?**', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS, body=json.dumps([soiree, sondage])))
    page.route(REST + 'rpc/event_attendance', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS, body=json.dumps(
        [{'event_id': EVENT, 'going': 2, 'maybe': 1, 'waitlist': 0, 'faces': [{'id': LEA, 'name': 'Léa', 'avatar_url': None}]}])))
    try:
        page.goto(events_origin + '/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Soirée de test participant').first).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='3 présents ou peut-être : 2 présents, 1 peut-être', exact=True)).to_be_visible()
        assert page.get_by_text('Liste d’attente', exact=False).count() == 0  # mon « Peut-être » n'est pas une attente
        page.get_by_role('button', name='Rechercher', exact=True).click()
        search = page.get_by_label('Rechercher un événement')
        search.fill('bar du lac')
        pw.expect(page.get_by_text('Week-end à choisir')).to_have_count(0)
        pw.expect(page.get_by_text('Soirée de test participant').first).to_be_visible()
        search.fill('')
        page.get_by_test_id('pill-polls').click()  # « Sondages, 1 en attente de ton vote »
        pw.expect(page.get_by_text('Week-end à choisir').first).to_be_visible()
        pw.expect(page.get_by_text('Soirée de test participant')).to_have_count(0)
    finally:
        context.close()


def _bottom_line(page, pattern: str):
    """La dernière ligne de la fiche (l'année n'apparaît que hors de l'année en cours)."""
    line = page.get_by_text(re.compile(pattern))
    pw.expect(line).to_be_visible()
    last = page.evaluate("""(text) => {
        const all = [...document.querySelectorAll('div[dir="auto"]')].filter((n) => n.offsetParent && n.textContent.trim());
        return all[all.length - 1].textContent.trim();
    }""", None)
    assert re.fullmatch(pattern, last), last


def test_the_date_poll_says_when_it_was_created_and_last_changed(browser, events_origin):  # noqa: F811
    """Avis de l'admin (10.11 puis 13.11) : tout en bas de la fiche, la date de création et celle de la dernière
    modification (l'événement, ou la dernière date proposée)."""
    option = {'id': '0d0d0d0d-0000-4000-8000-000000000001', 'event_id': EVENT, 'starts_at': '2030-11-20T18:00:00Z',
              'ends_at': None, 'proposed_by': LEA, 'created_at': '2026-11-03T16:45:00Z', 'date_votes': []}
    ev = event_row(date_mode='poll', starts_at=None, date_options=[option], updated_at='2026-11-02T09:00:00Z')
    context, page = open_event(browser, events_origin, ev)
    try:
        _bottom_line(page, r'Sondage créé le 1 nov\.( 2026)? à 09:00 · modifié le 3 nov\.( 2026)? à 17:45')
    finally:
        context.close()
    ev = event_row(date_mode='poll', starts_at=None, date_options=[{**option, 'created_at': '2026-11-01T08:00:20Z'}])
    context, page = open_event(browser, events_origin, ev)
    try:
        _bottom_line(page, r'Sondage créé le 1 nov\.( 2026)? à 09:00')  # rien changé depuis
    finally:
        context.close()


def test_every_event_says_when_it_was_created_at_the_very_bottom(browser, events_origin):  # noqa: F811
    """Avis de l'admin (13.11) : chaque événement, pas seulement les sondages, dit tout en bas quand il a été créé."""
    context, page = open_event(browser, events_origin, event_row(updated_at='2026-11-05T17:10:00Z'))
    try:
        _bottom_line(page, r'Événement créé le 1 nov\.( 2026)? à 09:00 · modifié le 5 nov\.( 2026)? à 18:10')
    finally:
        context.close()


def test_a_place_to_be_defined_says_so_without_a_route(browser, events_origin):  # noqa: F811
    """Avis 2237524ab14b (13.11) : « Lieu à définir » (dit à l'IA) s'affiche tel quel, sans « Itinéraire »."""
    ev = event_row(location_name='Lieu à définir', location_address=None, location_url=None)
    context, page = open_event(browser, events_origin, ev)
    try:
        pw.expect(page.get_by_text('Lieu à définir', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('L’organisateur l’ajoutera plus tard.')).to_be_visible()
        pw.expect(page.get_by_text('Itinéraire ›')).to_have_count(0)
    finally:
        context.close()
