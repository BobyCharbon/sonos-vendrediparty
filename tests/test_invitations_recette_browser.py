"""Invitations : corrections d'écran de la recette réelle du 10.11.2026 (agents « groupes » et « app iPhone »), dans un
vrai navigateur, Supabase simulé :
- un membre quitte lui-même un groupe (jamais celui qu'il a créé, jamais Vendredi Party) ;
- créer un groupe sans les CGU : la feuille CGU d'abord (avant : un texte d'erreur et rien d'autre) ;
- dans Party installée (app iPhone), l'invitation ne propose jamais d'installer Party."""
import json
from urllib.parse import parse_qs, urlparse

from tests.test_c2_acces_browser import mock_terms
from tests.test_events_browser import USER, browser, events_origin, mock_services, pw  # noqa: F401 (fixtures)
from tests.test_groups_browser import INSIDE, MINE, VIP, open_groups, phone  # noqa: F401 (fixture phone)
from tests.test_invitations_v2_browser import CARD, TOKEN, mock_invites, v2_origin  # noqa: F401 (fixture)
from tests.test_events_browser import login


def test_a_member_leaves_a_group_he_did_not_create(phone, events_origin):  # noqa: F811
    page, errors = phone
    deletes = []
    frame = open_groups(page, events_origin, rank=1, groups=[MINE, INSIDE, {**VIP, 'member_group_members': [{'user_id': USER}]}])
    # Déclarée après les simulations communes : c'est elle qui répond.
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/member_group_members*',
               lambda route: (deletes.append(parse_qs(urlparse(route.request.url).query)) if route.request.method == 'DELETE' else None,
                              route.fulfill(status=200, content_type='application/json', body=json.dumps({'user_id': USER}),
                                            headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*',
                                                     'Access-Control-Allow-Methods': '*'})))
    # Rando (créé par Tom, j'en fais partie) : « Quitter » ; Mes potes (le mien) et Vendredi Party : jamais.
    pw.expect(frame.get_by_role('button', name='Quitter le groupe', exact=True)).to_have_count(1)
    frame.get_by_role('button', name='Quitter le groupe', exact=True).click()
    frame.get_by_role('button', name='Confirmer : quitter le groupe', exact=True).click()
    page.wait_for_timeout(800)
    assert deletes and deletes[0]['group_id'] == [f'eq.{INSIDE["id"]}'] and deletes[0]['user_id'] == [f'eq.{USER}'], deletes
    assert not errors, errors


def test_creating_a_group_without_the_terms_shows_the_terms_sheet_first(phone, events_origin):  # noqa: F811
    page, errors = phone
    calls, created = [], []
    # CGU pas encore acceptées, dès l'ouverture (posée après les simulations communes : c'est elle qui répond).
    frame = open_groups(page, events_origin, rank=1, groups=[MINE], before_open=lambda p: mock_terms(p, calls, accepted=False))
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/member_groups*',
               lambda route: (created.append(1), route.fallback()) if route.request.method == 'POST' else route.fallback())
    frame.get_by_placeholder('Ex. Les footeux').press_sequentially('Les footeux')
    frame.get_by_role('button', name='Créer', exact=True).click()
    pw.expect(frame.get_by_role('button', name='J’accepte')).to_be_visible(timeout=10000)
    assert not created, 'rien n’est créé avant les CGU'
    assert not errors, errors


def test_inside_the_installed_app_the_invitation_never_offers_to_install_party(browser, v2_origin):  # noqa: F811
    context = browser.new_context(viewport={'width': 402, 'height': 874})
    context.add_init_script('window.PartyNative = { tabs: { update() {} } };')  # pont de l'app iPhone (WKWebView)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'inviter': 'Ludo'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Halloween chez Ludo', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Pas besoin d’installer l’app.', exact=True)).to_have_count(0)
        page.get_by_role('button', name='Je viens !').click()
        login(page)
        pw.expect(page.get_by_text('C’est noté, Camille !', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('button', name='Installer Party')).to_have_count(0)
        pw.expect(page.get_by_text('Reçois les nouvelles de la soirée', exact=True)).to_have_count(0)
        assert not errors, errors
    finally:
        context.close()


def test_a_new_invite_only_event_from_the_form_opens_the_invite_sheet_right_away(browser, v2_origin):  # noqa: F811
    """Invitations v2 (prod) : « Sur invitation » sans groupe se publie, puis la feuille « Inviter » s'ouvre, lien prêt
    (avant : refus « Choisis qui inviter… » alors que le choix des personnes est caché)."""
    from tests.test_event_organizer_browser import field, fill_date, launch, open_form
    context, page, frame, base, errors = launch(browser, v2_origin)
    mock_invites(page)  # liste des invités et liens de la feuille « Inviter »
    try:
        open_form(frame, 'Simple')
        field(frame, 'Titre').fill('Anniversaire surprise')
        fill_date(frame, 'Début', '2030-12-12', '20:00')
        frame.get_by_role('button', name='Sur invitation', exact=True).click()
        frame.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(frame.get_by_text('Choisis qui inviter : le groupe Vendredi Party, un groupe ou des personnes', exact=True)).to_have_count(0)
        pw.expect(frame.get_by_text('C’est en ligne : envoie le lien à tes invités').first).to_be_visible(timeout=10000)
        (_, row), = base.wrote('POST', 'events')
        assert (row['visibility'], row['public_link']) == ('invited', False)
        assert not errors, errors
    finally:
        context.close()


def test_a_link_already_answered_says_the_answer_with_clean_punctuation(browser, v2_origin):  # noqa: F811
    """Recette du 10.11 : « Ta réponse : Je viens !. » puis « Je viens . » ; attendu « Ta réponse : Je viens. »."""
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'mine': 'yes'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('Ta réponse : Je viens. Tu peux la changer.', exact=True)).to_be_visible(timeout=15000)
    finally:
        context.close()
