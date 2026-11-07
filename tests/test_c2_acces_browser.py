"""Campagne 2 (07.11.2026), lot « accès, connexion, carte d'invitation, forum », module Événements dans un vrai
navigateur (Supabase simulé, aucun SMS réel) :
1. lien public, compte neuf : « Continuer » au prénom → feuille CGU puis enregistrement (403 terms_required sinon) ;
2. l'adresse ouverte prime sur l'intention gardée (/share/B ne montre jamais A ; /events/ ne ressert pas un lien servi) ;
3. invitation refusée (retiré, lien arrêté…) : un seul appel, message clair, plus de « Je viens ! » ;
4. double toucher « Envoyer » au forum pendant l'attente des CGU : un seul message ;
5. événement sur invitation sans session : « Se connecter » au lieu de « Lien indisponible » ;
6. connexion : erreurs en français (504, attente, hors ligne ≠ « Code incorrect ») ;
7. carte d'invitation : panne passagère → « Réessayer », Android sans App Store, organisateur sur son propre lien ;
8. forum : messages d'une personne bloquée masqués, « @ » propose des noms ;
9. public annulé : pas de « Se connecter pour répondre » ; lien /share mal formé : aucune requête."""
import json

import pytest

from tests.test_events_browser import ANDROID_PHONE, EVENT, USER, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import ACCEPTED, CARD, CORS, TOKEN, mock_invites, v2_origin  # noqa: F401

SUPA = 'https://gsuetixzobooggeaubvb.supabase.co'
OTHER_EVENT = '41f18a3b-827f-4123-8cf4-33de06c9a5aa'
GUS = 'eeeeeeee-0000-4000-8000-0000000000a1'
VICTOR = 'eeeeeeee-0000-4000-8000-0000000000a2'
TERMS_REQUIRED = {'code': '42501', 'message': "terms_required: accepte les conditions d'utilisation de Party pour publier."}


def public(event_id=EVENT, title='Soirée publique de test', **more):
    return {'id': event_id, 'title': title, 'description': None, 'status': 'published', 'date_mode': 'fixed',
            'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None, 'location_name': 'Salle du test', 'location_address': None,
            'location_url': None, 'price_chf': None, 'allow_maybe': True, 'rsvp_deadline': None, 'max_participants': None,
            'going': 2, 'mine': None, **more}


def fulfill(route, body, status=200):
    if route.request.method == 'OPTIONS':
        return route.fulfill(status=204, headers=CORS)
    route.fulfill(status=status, content_type='application/json', headers=CORS, body=json.dumps(body))


def new_page(browser, errors=None, **context):  # noqa: F811
    ctx = browser.new_context(**({'viewport': {'width': 390, 'height': 844}} | context))
    page = ctx.new_page()
    if errors is not None:
        page.on('pageerror', lambda e: errors.append(str(e)))
    return ctx, page


def mock_terms(page, calls, accepted=False):
    """my_terms / accept_terms comme la base ; renvoie l'état (accepted)."""
    state = {'accepted': accepted}

    def my_terms(route):
        calls.append(('my_terms', None))
        fulfill(route, {'version': '2026-11-04', 'accepted': state['accepted'], 'accepted_at': None, 'contact_email': None, 'enforced': True})

    def accept_terms(route):
        if route.request.method != 'OPTIONS':
            calls.append(('accept_terms', route.request.post_data))
            state['accepted'] = True
        fulfill(route, {'version': '2026-11-04', 'accepted': True, 'accepted_at': '2026-11-07T10:00:00Z', 'contact_email': None, 'enforced': True})
    page.route(f'{SUPA}/rest/v1/rpc/my_terms', my_terms)
    page.route(f'{SUPA}/rest/v1/rpc/accept_terms', accept_terms)
    return state


def mock_public_events(page, calls, events):
    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        args = json.loads(route.request.post_data or '{}')
        calls.append(('public_event', args.get('e')))
        fulfill(route, events.get(args.get('e')))
    page.route(f'{SUPA}/rest/v1/rpc/public_event', handle)


# 1 -------------------------------------------------------------------------------------------------------------------
def test_new_account_on_a_public_link_accepts_the_terms_then_its_first_name_is_saved(browser, v2_origin):  # noqa: F811
    errors = []
    ctx, page = new_page(browser, errors)
    try:
        mock_services(page)
        calls = []
        terms = mock_terms(page, calls)
        mock_public_events(page, calls, {EVENT: public()})
        profile = {'id': USER, 'display_name': '', 'phone': '41791234567', 'role': 'guest', 'status': 'active', 'avatar_url': None,
                   'first_name': None, 'last_name': None, 'created_at': '2026-11-07T08:00:00Z'}
        page.route(f'{SUPA}/rest/v1/rpc/get_member_directory*', lambda r: fulfill(r, profile))

        def profiles(route):  # comme la base : le prénom (contenu visible) exige les CGU
            if route.request.method == 'PATCH':
                calls.append(('profiles', route.request.post_data))
                if not terms['accepted']:
                    return fulfill(route, TERMS_REQUIRED, 403)
                profile['display_name'] = json.loads(route.request.post_data)['display_name']
                return fulfill(route, [])
            fulfill(route, [{'id': USER, 'display_name': profile['display_name']}])
        page.route(f'{SUPA}/rest/v1/profiles*', profiles)

        page.goto(f'{v2_origin}/events/share/{EVENT}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Se connecter pour répondre').click()
        login(page)
        page.goto(f'{v2_origin}/events/share/{EVENT}', wait_until='domcontentloaded')
        page.get_by_label('Ton prénom, pour que l’organisateur sache qui vient').fill('Noé')
        page.get_by_role('button', name='Continuer').click()
        pw.expect(page.get_by_text('Avant de publier', exact=True)).to_be_visible(timeout=10000)
        page.get_by_role('button', name='J’accepte').click()
        pw.expect(page.get_by_role('button', name='Présent', exact=False).first).to_be_visible(timeout=10000)
        names = [c[0] for c in calls]
        assert 'accept_terms' in names and names.index('accept_terms') < names.index('profiles'), names
        pw.expect(page.get_by_text('n’a pas été enregistré', exact=False)).to_have_count(0)
        assert not errors, errors
    finally:
        ctx.close()


# 2 -------------------------------------------------------------------------------------------------------------------
def test_the_opened_address_wins_over_the_remembered_link(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        calls = []
        mock_public_events(page, calls, {EVENT: public(title='Soirée A'), OTHER_EVENT: public(OTHER_EVENT, 'Soirée B')})
        # Lien A ouvert sans compte : la page publique de A (l'intention est gardée pour l'après-connexion).
        page.goto(f'{v2_origin}/events/event/{EVENT}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Soirée A', exact=True)).to_be_visible(timeout=15000)
        # Puis le lien public B : B, jamais A.
        page.goto(f'{v2_origin}/events/share/{OTHER_EVENT}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Soirée B', exact=True)).to_be_visible(timeout=15000)
        page.wait_for_timeout(1500)
        pw.expect(page.get_by_text('Soirée A', exact=True)).to_have_count(0)
        # L'onglet Événements ensuite : la connexion, plus le lien A déjà servi.
        page.goto(f'{v2_origin}/events/event/{EVENT}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Soirée A', exact=True)).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='Recevoir un code par SMS')).to_be_visible(timeout=15000)
        page.wait_for_timeout(1500)
        pw.expect(page.get_by_text('Soirée A', exact=True)).to_have_count(0)
    finally:
        ctx.close()


# 3 -------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('refusal,shown', [
    ("removed: l'organisateur t'a retiré de la liste des invités", 'retiré de la liste des invités'),
    ('Tu ne peux pas répondre à cette invitation.', 'Tu ne peux pas répondre à cette invitation.'),  # personne bloquée
    ('Cet événement est annulé', 'Cet événement est annulé'),
])
def test_a_refused_answer_stops_at_the_first_refusal_and_offers_no_answer(browser, v2_origin, refusal, shown):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        calls = mock_invites(page, card={**CARD, 'inviter': 'Olga', 'me_named': True, 'state': 'mine', 'mine': 'yes'})
        refused = []

        def accept(route):
            if route.request.method != 'OPTIONS':
                refused.append(1)
            fulfill(route, {'code': 'P0001', 'message': refusal}, 400)
        page.route(f'{SUPA}/rest/v1/rpc/accept_invite', accept)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Je viens !').click()
        pw.expect(page.get_by_text(shown, exact=False)).to_be_visible(timeout=10000)
        page.wait_for_timeout(3000)
        assert len(refused) == 1, f'{len(refused)} appels accept_invite refusés'
        pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
        assert calls is not None
    finally:
        ctx.close()


# 4 -------------------------------------------------------------------------------------------------------------------
def chat_routes(page, messages, blocked=()):
    posts = []

    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        if route.request.method == 'POST':
            posts.append(route.request.post_data)
            return fulfill(route, None, 201)
        fulfill(route, [] if 'pinned=eq.true' in route.request.url else messages)
    page.route(f'{SUPA}/rest/v1/messages*', handle)
    page.route(f'{SUPA}/rest/v1/direct_blocks*', lambda r: fulfill(r, [{'blocked_id': b} for b in blocked]))
    return posts


def message(i, user, body):
    return {'id': f'cccccccc-0000-4000-8000-00000000000{i}', 'event_id': EVENT, 'user_id': user, 'body': body, 'reply_to': None,
            'mentions': [], 'pinned': False, 'created_at': f'2030-11-01T10:0{i}:00Z', 'deleted_at': None}


def open_chat(page, origin):
    page.goto(f'{origin}/events/', wait_until='domcontentloaded')
    login(page)
    pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
    page.goto(f'{origin}/events/event/{EVENT}/chat', wait_until='domcontentloaded')


def test_a_double_tap_on_send_while_the_terms_are_read_sends_one_message(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page, people=[{'id': VICTOR, 'display_name': 'Bot Victor'}])
        calls = []
        state = mock_terms(page, calls)
        posts = chat_routes(page, [message(1, VICTOR, 'Salut tout le monde')])
        open_chat(page, v2_origin)
        pw.expect(page.get_by_text('Salut tout le monde', exact=True)).to_be_visible(timeout=15000)
        state['accepted'] = True  # acceptées ailleurs entre-temps : la relecture des CGU laisse passer les deux touchers
        page.get_by_label('Message', exact=True).fill('Coucou')
        page.get_by_role('button', name='Envoyer').dblclick()
        page.wait_for_timeout(2500)
        assert len(posts) == 1, posts
    finally:
        ctx.close()


# 5 & 9 ---------------------------------------------------------------------------------------------------------------
def test_an_invitation_only_event_without_session_offers_to_sign_in(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        calls = []
        mock_public_events(page, calls, {})
        page.goto(f'{v2_origin}/events/share/{EVENT}', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='Se connecter', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Lien indisponible', exact=True)).to_have_count(0)
        page.get_by_role('button', name='Se connecter', exact=True).click()
        pw.expect(page.get_by_role('button', name='Recevoir un code par SMS')).to_be_visible(timeout=10000)
    finally:
        ctx.close()


def test_a_cancelled_public_event_offers_no_sign_in_and_a_broken_link_makes_no_request(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        calls = []
        mock_public_events(page, calls, {EVENT: public(status='cancelled')})
        page.goto(f'{v2_origin}/events/share/{EVENT}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Cet événement a été annulé.', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Se connecter pour répondre')).to_have_count(0)
        calls.clear()
        page.goto(f'{v2_origin}/events/share/pas-un-uuid', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Lien indisponible', exact=True)).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        assert not [c for c in calls if c[0] == 'public_event'], calls
    finally:
        ctx.close()


# 6 -------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('status,body,expected', [
    (504, {'code': 504, 'msg': 'HTTP 504'}, 'Le service de connexion ne répond pas'),
    (429, {'code': 429, 'error_code': 'over_request_rate_limit', 'msg': 'For security purposes, you can only request this after 0 seconds.'},
     'Attends quelques secondes avant de redemander un code.'),
])
def test_sign_in_send_errors_are_in_french(browser, v2_origin, status, body, expected):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        page.route(f'{SUPA}/auth/v1/otp', lambda r: fulfill(r, body, status))
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        page.get_by_label('Ton numéro de téléphone', exact=True).fill('079 123 45 67')
        page.get_by_role('button', name='Recevoir un code par SMS').click()
        pw.expect(page.get_by_text(expected, exact=False)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('HTTP 504', exact=False)).to_have_count(0)
        pw.expect(page.get_by_text('For security purposes', exact=False)).to_have_count(0)
    finally:
        ctx.close()


def test_sign_in_offline_with_the_right_code_says_no_connection(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        page.route(f'{SUPA}/auth/v1/verify', lambda r: r.abort('internetdisconnected') if r.request.method != 'OPTIONS' else r.fulfill(status=204, headers=CORS))
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Pas de connexion', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Code incorrect', exact=False)).to_have_count(0)
    finally:
        ctx.close()


# 7 -------------------------------------------------------------------------------------------------------------------
def test_a_passing_outage_offers_to_retry_instead_of_a_dead_link(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        mock_invites(page)
        outage = {'on': True}

        def preview(route):
            if outage['on']:
                return fulfill(route, {'code': '57014', 'message': 'canceling statement due to statement timeout'}, 500)
            fulfill(route, {**CARD, 'inviter': 'Ludo'})
        page.route(f'{SUPA}/rest/v1/rpc/invite_preview', preview)
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Connexion difficile', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('n’existe plus', exact=False)).to_have_count(0)
        pw.expect(page.get_by_text('statement timeout', exact=False)).to_have_count(0)
        outage['on'] = False
        page.get_by_role('button', name='Réessayer').click()
        pw.expect(page.get_by_role('button', name='Je viens !')).to_be_visible(timeout=10000)
    finally:
        ctx.close()


def test_android_is_never_sent_to_the_app_store(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser, **ANDROID_PHONE)
    try:
        mock_services(page)
        mock_terms(page, [], accepted=True)
        mock_invites(page, card={**CARD, 'inviter': 'Ludo'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Je viens !').click()
        page.get_by_label('Prénom', exact=True).fill('Sara')
        page.get_by_label('Numéro de portable').fill('079 456 12 38')
        page.get_by_role('button', name='Recevoir mon code par SMS').click()
        page.get_by_placeholder('123456', exact=True).fill('123456')
        page.get_by_role('button', name='Confirmer', exact=True).click()
        pw.expect(page.get_by_text('C’est noté, Sara !', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_role('button', name='Installer Party')).to_have_count(0)
        pw.expect(page.get_by_text('Garde ce lien', exact=False)).to_be_visible()
    finally:
        ctx.close()


def test_the_organizer_opening_their_own_link_is_told_so(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'inviter': 'Olga', 'organizer': True})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('C’est ton lien d’invitation', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Je viens !')).to_have_count(0)
    finally:
        ctx.close()


def test_the_organizer_who_answers_through_their_link_is_not_thanked_as_a_guest(browser, v2_origin):  # noqa: F811
    """La base ne consomme pas le lien de l'organisateur et renvoie organizer: true (migration 20261107100000)."""
    ctx, page = new_page(browser)
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'inviter': 'Olga', 'me_named': True})
        page.route(f'{SUPA}/rest/v1/rpc/accept_invite', lambda r: fulfill(r, {**ACCEPTED, 'organizer': True}))
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        page.get_by_role('button', name='Je viens !').click()
        pw.expect(page.get_by_text('C’est ton lien d’invitation', exact=True)).to_be_visible(timeout=10000)
        pw.expect(page.get_by_text('est prévenu', exact=False)).to_have_count(0)
    finally:
        ctx.close()


# 8 -------------------------------------------------------------------------------------------------------------------
def test_forum_hides_blocked_people_and_suggests_names_after_at(browser, v2_origin):  # noqa: F811
    ctx, page = new_page(browser)
    try:
        mock_services(page, people=[{'id': GUS, 'display_name': 'Bot Gus'}, {'id': VICTOR, 'display_name': 'Bot Victor'}])
        mock_terms(page, [], accepted=True)
        posts = chat_routes(page, [message(1, GUS, 'Message de Gus bloqué'), message(2, VICTOR, 'Message de Victor')], blocked=[GUS])
        open_chat(page, v2_origin)
        pw.expect(page.get_by_text('Message de Victor', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Message de Gus bloqué', exact=True)).to_have_count(0)
        pw.expect(page.get_by_text('Message masqué (personne bloquée)', exact=True)).to_be_visible()
        field = page.get_by_label('Message', exact=True)
        field.fill('Salut @Vic')
        suggestion = page.get_by_role('menuitem', name='Citer Bot Victor')
        pw.expect(suggestion).to_be_visible(timeout=5000)
        pw.expect(page.get_by_role('menuitem', name='Citer Bot Gus')).to_have_count(0)
        suggestion.click()
        assert field.input_value() == 'Salut @Bot Victor '
        page.get_by_role('button', name='Envoyer').click()
        page.wait_for_timeout(1000)
        assert posts and VICTOR in posts[0], posts
    finally:
        ctx.close()
