"""Menu de partage commun (avis 83ebee37aa0f de l'admin, 11.11.2026), module web dans un vrai navigateur (Supabase simulé) :
- un invité a la même carte « Invités » que l'organisateur, avec les CHIFFRES seulement (aucun nom, aucune relance),
  ses liens à lui (« Mes liens »), qu'il recopie, et il crée ses propres liens nommés (« Collègues ») ;
- l'organisateur nomme aussi un lien « Plusieurs » et recopie un lien déjà envoyé (le même, jamais un nouveau)."""
import json

import pytest

from tests.test_event_participant_browser import GUEST_PERMS, LEA, event_row, rsvp
from tests.test_events_browser import DIST, EVENT, USER, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import IDS, TOKEN, mock_invites, open_event, shot, v2_origin  # noqa: F401

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
REST = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
MINE = IDS[9]

GUEST_VIEW = {
    'guest': True, 'poll': False, 'vip': False, 'public': True, 'vip_name': 'Vendredi Party', 'groups': [], 'people': [],
    'counts': {'yes': 3, 'maybe': 1, 'no': 2, 'none': 4, 'unopened': 1, 'total': 10},
    'links': [{'token': MINE, 'label': 'Groupe foot', 'max_uses': 10000, 'uses': 2, 'created_at': '2030-11-01T10:00:00Z',
               'expires_at': '2030-11-15T10:00:00Z', 'opened_at': '2030-11-01T12:00:00Z', 'state': 'opened', 'version': 2,
               'created_by': 'Camille', 'created_by_id': USER, 'nudged_today': False,
               'arrivals': [{'id': None, 'name': None, 'status': 'yes'}, {'id': None, 'name': None, 'status': 'maybe'}]}],
}


def open_as_guest(browser, origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    context.grant_permissions(['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    mock_services(page)
    event = event_row(title='Soirée de Léa', rsvps=[rsvp(USER, 'yes'), rsvp(LEA, 'yes')])

    def events(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        single = 'vnd.pgrst.object' in (route.request.headers.get('accept') or '')
        route.fulfill(status=200, content_type='application/json', body=json.dumps(event if single else [event]), headers=HEADERS)
    page.route(REST + 'events?**', events)
    page.route(REST + 'rpc/my_permissions', lambda r: r.fulfill(status=200, content_type='application/json', headers=HEADERS,
                                                               body=json.dumps(GUEST_PERMS)))
    calls = mock_invites(page, guest_list=GUEST_VIEW)
    page.goto(origin + '/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_role('button', name='Se connecter', exact=True)).to_have_count(0, timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT}', wait_until='domcontentloaded')
    card = page.get_by_label('Invités', exact=True)
    pw.expect(card.get_by_text('Invités · 10', exact=True)).to_be_visible(timeout=15000)
    return context, page, card, calls


def test_a_guest_sees_the_numbers_and_his_own_links_never_a_name(browser, v2_origin):  # noqa: F811
    context, page, card, calls = open_as_guest(browser, v2_origin)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        for label in ('3 Viennent', '1 Peut-être', '2 Absents', '4 Pas répondu', '1 Lien pas ouvert'):
            pw.expect(card.get_by_role('tab', name=label)).to_be_visible()
        pw.expect(card.get_by_text('MES LIENS · 1', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('Lien pour Groupe foot', exact=True)).to_be_visible()
        pw.expect(card.get_by_text('2 personnes · sans limite', exact=False)).to_be_visible()
        # Ni relance ni noms : ce sont des outils d'organisateur.
        assert card.get_by_text('Relancer', exact=False).count() == 0
        assert card.get_by_text('Léa', exact=False).count() == 0
        card.scroll_into_view_if_needed()
        shot(page, '20-invite-carte-chiffres', full=True)

        # Le même lien, recopié (perdu) : aucun nouveau lien créé.
        card.get_by_role('button', name='Copier le lien : Lien pour Groupe foot').click()
        pw.expect(page.get_by_text('Lien copié', exact=True)).to_be_visible(timeout=5000)
        assert page.evaluate('navigator.clipboard.readText()') == f'{v2_origin}/events/invite/{MINE}'
        assert not [c for c in calls if c[0] == 'create_event_invite']
        assert not errors, errors
    finally:
        context.close()


def test_a_guest_creates_his_own_named_link_without_the_organizer_tools(browser, v2_origin):  # noqa: F811
    context, page, card, calls = open_as_guest(browser, v2_origin)
    try:
        card.get_by_role('button', name='Inviter', exact=True).click()
        sheet = page.get_by_label('Inviter à Soirée de Léa')
        pw.expect(sheet.get_by_text('🔗 Envoyer le lien', exact=True)).to_be_visible(timeout=5000)
        # Pas d'ajout de gens de Party ni de groupe : un invité envoie ses liens à lui.
        assert sheet.get_by_text('Ajouter des gens de Party', exact=True).count() == 0
        assert sheet.get_by_label('Chercher une personne ou un groupe').count() == 0
        sheet.get_by_label('Nom du lien (facultatif)').fill('Collègues')
        pw.expect(sheet.get_by_text('« Mes liens »', exact=False)).to_be_visible()
        page.wait_for_timeout(600)
        shot(page, '21-invite-feuille-lien-nomme')
        sheet.get_by_role('button', name='Copier').click()
        pw.expect(sheet.get_by_text('✓ Lien prêt', exact=False)).to_be_visible(timeout=5000)
        created = [c for c in calls if c[0] == 'create_event_invite']
        assert created == [('create_event_invite', {'e': EVENT, 'places': 0, 'until': None, 'label': 'Collègues'})]
    finally:
        context.close()


def test_the_organizer_names_a_several_link_and_copies_an_existing_one_again(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark')
    context.grant_permissions(['clipboard-read', 'clipboard-write'])
    page = context.new_page()
    try:
        mock_services(page)
        calls = mock_invites(page)
        card = open_event(page, v2_origin)
        card.get_by_role('button', name='Copier le lien : Lien pour Tom').click()
        pw.expect(page.get_by_text('Lien copié', exact=True)).to_be_visible(timeout=5000)
        assert page.evaluate('navigator.clipboard.readText()') == f'{v2_origin}/events/invite/{TOKEN}'
        assert not [c for c in calls if c[0] == 'create_event_invite']

        card.get_by_role('button', name='Inviter', exact=True).click()
        sheet = page.get_by_label('Inviter à Sortie de démonstration (test local)')
        sheet.get_by_label('Nom du lien (facultatif)').fill('Groupe foot')
        sheet.get_by_role('button', name='Copier').click()
        pw.expect(sheet.get_by_text('✓ Lien prêt', exact=False)).to_be_visible(timeout=5000)
        args = [c for c in calls if c[0] == 'create_event_invite'][-1][1]
        assert args == {'e': EVENT, 'places': 0, 'until': None, 'label': 'Groupe foot'}
        # L'organisateur garde l'ajout de gens de Party.
        pw.expect(sheet.get_by_text('Ajouter des gens de Party', exact=True)).to_be_visible()
    finally:
        context.close()
