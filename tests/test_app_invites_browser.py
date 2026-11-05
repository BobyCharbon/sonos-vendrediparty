"""Invitations dans Party, module web (Supabase simulé, aucun SMS réel) : page « X t'invite sur Party » lisible avant
connexion (surnom échappé), App Store ou « Continuer sur le web », lien réclamé une fois après l'inscription ;
Réglages › Inviter dans Party (lien personnel, partage, nombre d'arrivées) ; « Invité par » sur la fiche, admins seulement."""
import json

import pytest

from tests.test_events_browser import ROOT, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

pytestmark = pytest.mark.skipif(not (ROOT / 'web/events/dist/index.html').exists(), reason='Construire web/events avant les tests navigateur')
TOKEN = '6b1f6f0e-4a8e-4c55-9d43-2f0b7c1d9e21'
CORS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile',
        'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS'}
SNEAKY = '<img src=x onerror="window.__xss=1">Ludo'


def mock_invites(page, perms: list[str] | None = None) -> list:
    """app_invite_preview, claim_app_invite, my_app_invite (et les droits), comme la base."""
    calls = []

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        name = request.url.split('?')[0].rsplit('/', 1)[-1]
        calls.append((name, json.loads(request.post_data or '{}')))
        result = {
            'app_invite_preview': {'inviter': SNEAKY, 'avatar_url': None},
            'claim_app_invite': {'new': True},
            'my_app_invite': {'token': TOKEN, 'created_at': '2026-11-03T10:00:00Z', 'joined': 2},
            'my_permissions': perms,
        }[name]
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(result))
    for name in ('app_invite_preview', 'claim_app_invite', 'my_app_invite') + (('my_permissions',) if perms else ()):
        page.route(f'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/{name}', handle)
    return calls


def test_join_page_shows_who_invites_escaped_then_claims_once_after_sign_in(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        calls = mock_invites(page)
        page.goto(f'{events_origin}/events/join/{TOKEN}', wait_until='domcontentloaded')
        # Le surnom s'affiche tel quel : du texte, jamais du HTML.
        pw.expect(page.get_by_text(f'{SNEAKY} t’invite sur Party', exact=True)).to_be_visible(timeout=15000)
        assert page.evaluate('window.__xss') is None
        assert page.locator('img[src="x"]').count() == 0
        pw.expect(page.get_by_role('button', name='Télécharger sur l’App Store')).to_be_visible()  # site principal
        assert ('app_invite_preview', {'token': TOKEN}) in calls
        # Continuer sur le web : le lien est gardé pendant l'inscription par SMS.
        page.get_by_role('button', name='Continuer sur le web').click()
        login(page)
        pw.expect(page.get_by_text('Bienvenue sur Party', exact=False)).to_be_visible(timeout=15000)
        assert [c for c in calls if c[0] == 'claim_app_invite'] == [('claim_app_invite', {'token': TOKEN})]
        assert page.evaluate("localStorage.getItem('party-app-invite')") is None  # réclamé : oublié
        assert page.locator('html').evaluate('e => e.scrollWidth <= innerWidth')
        assert not errors, errors
    finally:
        context.close()


def test_unknown_link_says_it_is_no_longer_valid(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        page.goto(f'{events_origin}/events/join/pas-un-lien', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Lien indisponible', exact=True)).to_be_visible(timeout=15000)
    finally:
        context.close()


def test_settings_share_my_personal_link_and_who_joined_thanks_to_it(browser, events_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        calls = mock_invites(page, perms=['events.view', 'members.invite'])
        page.add_init_script("Object.defineProperty(Navigator.prototype, 'share', { value: undefined, configurable: true })")
        page.goto(events_origin, wait_until='domcontentloaded')
        page.locator('#accountTab').click()
        frame = page.frame_locator('#eventsFrame')
        login(frame)
        pw.expect(frame.get_by_text('Inviter dans Party', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text(f'/events/join/{TOKEN}', exact=False)).to_be_visible()
        pw.expect(frame.get_by_text('2 personnes ont rejoint Party grâce à toi', exact=True)).to_be_visible()
        # Sans feuille de partage (ordinateur) : WhatsApp, Telegram, SMS, e-mail, et copie pour Instagram / Snapchat.
        frame.get_by_role('button', name='⬆︎ Partager').click()
        whatsapp = frame.get_by_role('menuitem', name='Partager par WhatsApp')
        pw.expect(whatsapp).to_be_visible()
        for label in ('Partager par Telegram', 'Partager par SMS', 'Partager par E-mail', 'Copier pour Instagram ou Snapchat'):
            pw.expect(frame.get_by_role('menuitem', name=label)).to_be_visible()
        frame.get_by_role('button', name='Nouveau lien').click()
        frame.get_by_role('button', name='L’ancien ne marchera plus : confirmer').click()
        pw.expect(frame.get_by_text('Nouveau lien prêt', exact=True)).to_be_visible()
        assert ('my_app_invite', {'renew': True}) in calls
    finally:
        context.close()


MEMBER = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'


def mock_member(page, invited_by):
    card = {'id': MEMBER, 'display_name': 'Léa', 'avatar_url': None, 'role': 'guest', 'role_label': 'Guest', 'root': False,
            'me': False, 'first_name': None, 'last_name': None, 'phone': None, 'groups': []}

    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        body = card if route.request.url.endswith('/member_card') else invited_by
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/member_card', handle)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/member_invited_by', handle)


@pytest.mark.parametrize('rows', [None, [{'inviter': 'Ludo', 'via': 'group', 'target_name': 'Les amis', 'at': '2026-11-03T10:00:00Z'},
                                         {'inviter': 'Max', 'via': 'app', 'target_name': None, 'at': '2026-11-02T10:00:00Z'}]])
def test_member_card_shows_who_invited_only_with_the_right(browser, events_origin, rows):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        mock_member(page, rows)
        page.goto(events_origin + '/events/', wait_until='domcontentloaded')
        login(page)
        page.wait_for_timeout(500)
        page.goto(f'{events_origin}/events/member/{MEMBER}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Léa', exact=True).first).to_be_visible(timeout=15000)
        if rows is None:  # sans le droit, la base renvoie null : rien ne s'affiche
            page.wait_for_timeout(500)
            pw.expect(page.get_by_text('Invité par', exact=True)).to_have_count(0)
        else:
            pw.expect(page.get_by_text('Invité par', exact=True)).to_be_visible()
            pw.expect(page.get_by_text('via le groupe Les amis', exact=False)).to_be_visible()
            pw.expect(page.get_by_text('avec son lien Party', exact=False)).to_be_visible()
    finally:
        context.close()
