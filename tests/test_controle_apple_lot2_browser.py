"""Contrôle Apple (tour 1, 26.11), module Événements dans un vrai navigateur, Supabase simulé :
- Souvenirs et Couverture éteints (<html data-souvenirs="off" data-covers="off">, comme la prod et l'app App Store) :
  « Modifier » marche avec une base qui REFUSE leurs colonnes (absentes en prod), rien n'est lu ni écrit, rien ne se voit ;
- pot commun : passé de Présent à Pas présent, la fiche dit « Tu es toujours dans le pot commun » et comment en sortir ;
  la page d'invitation « Je viens ! » dit le pot commun (invite_preview.pot_enabled, migration 20261126120000) ;
- bloquer depuis le mini-profil d'une discussion : les messages de la personne disparaissent aussitôt (signal relu) ;
- feuille des CGU : « Tolérance zéro » et « Les points des jeux »."""
import json
from urllib.parse import parse_qs, urlparse

from tests.test_c2_acces_browser import SUPA, VICTOR, chat_routes, fulfill, message, mock_terms, new_page, open_chat
from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)
from tests.test_invitations_v2_browser import v2_origin  # noqa: F401

OTHER = '11111111-2222-4333-8444-555555555555'
TITLE = 'Sortie de démonstration (test local)'
FORM_ROWS = {'event_tags': [], 'event_invites': [], 'event_groups': [], 'event_phone_invites': [], 'date_options': [], 'public_link': True}
ABSENT = ('cover_credit', 'souvenirs_')


def features_off(page):
    """Comme le serveur de prod : la page du module porte data-souvenirs="off" data-covers="off"."""
    def handle(route):
        if route.request.resource_type != 'document':
            return route.fallback()
        response = route.fetch()
        body = response.text().replace('<html', '<html data-souvenirs="off" data-covers="off"', 1)
        route.fulfill(response=response, body=body)
    page.route('**/events/**', handle)


def prod_columns(page, seen):
    """Base de prod : une colonne inconnue demandée ou écrite → 400 (PostgREST 42703), comme en vrai."""
    def handle(route):
        request = route.request
        url = urlparse(request.url)
        select = ','.join(parse_qs(url.query).get('select', []))
        seen.append((request.method, select, request.post_data or ''))
        if any(c in select or c in (request.post_data or '') for c in ABSENT):
            return route.fulfill(status=400, content_type='application/json', headers={'Access-Control-Allow-Origin': '*'},
                                 body=json.dumps({'code': '42703', 'message': 'column events.cover_credit does not exist'}))
        return route.fallback()
    page.route(f'{SUPA}/rest/v1/events*', handle)


def test_with_souvenirs_and_covers_off_edit_works_without_their_columns_and_nothing_shows(browser, events_origin):  # noqa: F811
    ctx, page = new_page(browser)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    seen = []
    try:
        mock_services(page, event_extra=FORM_ROWS)
        prod_columns(page, seen)
        features_off(page)
        page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_text(TITLE, exact=True).first.click(timeout=15000)
        pw.expect(page.get_by_role('heading', name=TITLE).first).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='🖼️  Ajouter une couverture')).to_have_count(0)
        pw.expect(page.get_by_test_id('cover-tip')).to_have_count(0)
        page.goto(f'{events_origin}/events/event/{EVENT}/edit', wait_until='domcontentloaded')
        pw.expect(page.get_by_label('Titre', exact=True).first).to_be_visible(timeout=15000)
        pw.expect(page.get_by_test_id('souvenirs-settings')).to_have_count(0)
        pw.expect(page.get_by_role('button', name='🖼️  Ajouter une couverture')).to_have_count(0)
        page.get_by_role('button', name='Enregistrer', exact=True).first.click()
        page.wait_for_timeout(1500)
        assert any(m == 'PATCH' for m, _, _ in seen), seen
        assert not [s for s in seen if any(c in s[1] or c in s[2] for c in ABSENT)], seen
        pw.expect(page.get_by_text('does not exist', exact=False)).to_have_count(0)
        assert not errors, errors
    finally:
        ctx.close()


def test_still_in_the_pot_after_answering_not_present_the_event_says_how_to_leave(browser, events_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        no = {'event_id': EVENT, 'user_id': USER, 'status': 'no', 'plus_ones': 0, 'note': None, 'waitlisted': False, 'updated_at': '2026-11-20T10:00:00Z'}
        mock_services(page, event_extra={'created_by': OTHER, 'pot_enabled': True, 'rsvps': [no]})
        page.route(f'{SUPA}/rest/v1/tc_groups*', lambda r: fulfill(r, [{'id': 'f0000000-0000-4000-8000-000000000001'}]))
        page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_text(TITLE, exact=True).first.click(timeout=15000)
        notice = page.get_by_test_id('pot-notice')
        pw.expect(notice).to_contain_text('Tu es toujours dans le pot commun : Réglages › Pot commun › Quitter ce pot commun.', timeout=15000)
        pw.expect(notice).not_to_contain_text('tu n’y entres pas')
    finally:
        ctx.close()


def test_the_invitation_page_says_the_common_pot_before_i_come(browser, v2_origin):  # noqa: F811
    token = '0a0b0c0d-0000-4000-8000-00000000beef'
    card = {'state': 'pending', 'version': 1, 'label': None, 'places_left': None, 'inviter': 'Olga', 'title': 'Raclette',
            'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'all_day': False,
            'location_name': 'Chez Olga', 'cover_url': None, 'description': None, 'allow_maybe': True, 'closed': False, 'going': 2,
            'going_names': ['Olga'], 'mine': None, 'event_id': None, 'location_address': None, 'location_url': None,
            'me_named': False, 'pot_enabled': True}
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        page.route(f'{SUPA}/rest/v1/rpc/invite_preview', lambda r: fulfill(r, card))
        page.goto(f'{v2_origin}/events/invite/{token}', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='Je viens !')).to_be_visible(timeout=15000)
        notice = page.get_by_test_id('pot-notice')
        pw.expect(notice).to_contain_text('en répondant Présent, ou si l’organisateur te note Présent, tu y es ajouté.')
    finally:
        ctx.close()


def test_blocking_from_a_chat_hides_their_messages_at_once(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        page.route(f'{SUPA}/rest/v1/rpc/event_chat_state', lambda r: fulfill(r, {
            'title': TITLE, 'forum': True, 'status': 'published', 'write': True, 'staff': False, 'moderate': False, 'muted': False}))
        messages = [message(2, VICTOR, 'Message de Victor'), message(1, USER, 'Salut')]
        chat_routes(page, messages)
        blocked = []

        def set_block(route):
            if route.request.method != 'OPTIONS':
                blocked.append(json.loads(route.request.post_data))
                messages[:] = [m for m in messages if m['user_id'] != VICTOR]   # la base masque ses messages
            fulfill(route, None)
        page.route(f'{SUPA}/rest/v1/rpc/set_block', set_block)
        page.route(f'{SUPA}/rest/v1/rpc/member_mini', lambda r: fulfill(r, {
            'id': VICTOR, 'name': 'Bot Victor', 'nickname': 'Victor', 'photo': None, 'since': '2026-10-02T10:00:00Z', 'link': 'direct',
            'blocked': False, 'blocked_me': False, 'chat': None, 'met_count': 0, 'met': [], 'events': [], 'groups': [],
            'events_count': 0, 'groups_count': 0}))
        open_chat(page, v2_origin)
        pw.expect(page.get_by_text('Message de Victor', exact=True)).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Profil de Bot Victor').first.click()
        sheet = page.get_by_test_id('mini-profile')
        pw.expect(sheet).to_be_visible(timeout=10000)
        sheet.get_by_role('button', name='Bloquer Victor').click()
        sheet.get_by_role('button', name='Confirmer le blocage de Victor').click()
        pw.expect(page.get_by_text('Message de Victor', exact=True)).to_have_count(0, timeout=3000)
        assert blocked == [{'target': VICTOR, 'blocked': True}], blocked
        assert not errors, errors
    finally:
        ctx.close()


def test_the_big_terms_sheet_says_zero_tolerance_and_game_points():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / 'web/events/src/components/TermsSheet.tsx').read_text(encoding='utf-8')
    assert 'Tolérance zéro : un contenu choquant est retiré et son auteur peut être banni.' in text
    assert 'Les points des jeux n’ont aucune valeur en argent.' in text and 'Les objets du jeu' not in text
