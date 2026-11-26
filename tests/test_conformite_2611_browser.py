"""Contrôle du 26.11 (module Événements, vrai navigateur, Supabase simulé) :
- Pot commun (décision de l'admin) : l'entrée reste automatique pour qui répond Présent, mais la fiche le DIT là où l'on
  répond (avant : ce qui arrive en répondant Présent ; après : comment en sortir) ;
- étiquette à boisson (« #bar ») jamais montrée sur la fiche dans l'app App Store, toujours sur le site ;
- admin ouvert SEUL puis connexion par SMS : il reste sur sa page (avant : renvoyé dans Party)."""
from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)
from tests.test_members_root_browser import member_admin

STORE_UA = ('Mozilla/5.0 (iPhone; CPU iPhone OS 26_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 '
            'PartyApp-iOS/1.0.0 PartyStore')
OTHER = '11111111-2222-4333-8444-555555555555'
TITLE = 'Sortie de démonstration (test local)'
YES = {'event_id': EVENT, 'user_id': USER, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False, 'updated_at': '2026-11-20T10:00:00Z'}


def open_fiche(browser, events_origin, extra, ua=None):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, **({'user_agent': ua} if ua else {}))
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page, event_extra=extra)
    page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
    login(page)
    page.get_by_text(TITLE, exact=True).first.click(timeout=15000)
    pw.expect(page.get_by_role('heading', name=TITLE).first).to_be_visible(timeout=15000)
    return context, page, errors


def test_the_event_says_present_joins_its_common_pot_before_and_how_to_leave_after(browser, events_origin):  # noqa: F811
    context, page, errors = open_fiche(browser, events_origin, {'created_by': OTHER, 'pot_enabled': True})
    try:
        notice = page.get_by_test_id('pot-notice')
        pw.expect(notice).to_contain_text('Cet événement a un pot commun : en répondant Présent, ou si l’organisateur te note Présent, tu y es ajouté.', timeout=15000)
        pw.expect(notice).to_contain_text('Ses membres voient ton nom et les moyens de paiement que tu as indiqués.')
        pw.expect(notice).to_contain_text('Pas présent : tu n’y entres pas.')
        assert not errors, errors
    finally:
        context.close()
    context, page, errors = open_fiche(browser, events_origin, {'created_by': OTHER, 'pot_enabled': True, 'rsvps': [YES]})
    try:
        notice = page.get_by_test_id('pot-notice')
        pw.expect(notice).to_contain_text('Tu es dans le pot commun de cet événement', timeout=15000)
        pw.expect(notice).to_contain_text('Pour en sortir : Réglages › Pot commun › Quitter ce pot commun.')
        assert not errors, errors
    finally:
        context.close()
    context, page, errors = open_fiche(browser, events_origin, {'created_by': OTHER, 'pot_enabled': False})
    try:
        pw.expect(page.get_by_text('Tu viens ?', exact=True).first).to_be_visible(timeout=15000)
        pw.expect(page.get_by_test_id('pot-notice')).to_have_count(0)
    finally:
        context.close()


BAR_TAG = {'id': 'aaaaaaaa-0000-4000-8000-000000000001', 'name': 'bar', 'color': '#FF4F9A', 'archived': False}
GAME_TAG = {'id': 'aaaaaaaa-0000-4000-8000-000000000002', 'name': 'jeux', 'color': '#7B6CF6', 'archived': False}
TAGS = {'event_tags': [{'tag_id': BAR_TAG['id'], 'tags': BAR_TAG}, {'tag_id': GAME_TAG['id'], 'tags': GAME_TAG}]}


def test_a_drink_tag_never_shows_on_the_event_in_the_app_store_app_but_the_site_keeps_it(browser, events_origin):  # noqa: F811
    context, page, errors = open_fiche(browser, events_origin, TAGS, ua=STORE_UA)
    try:
        pw.expect(page.get_by_text('#jeux', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('#bar', exact=True)).to_have_count(0)
        assert not errors, errors
    finally:
        context.close()
    context, page, errors = open_fiche(browser, events_origin, TAGS)
    try:
        pw.expect(page.get_by_text('#bar', exact=True)).to_be_visible(timeout=15000)
    finally:
        context.close()


def test_the_admin_page_opened_alone_stays_there_after_the_sms_sign_in(browser, events_origin):  # noqa: F811
    """Recette du 26.11 : /events/admin/users ouvert seul, connexion SMS, puis la page Party s'ouvrait à la place."""
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    mock_services(page)
    member_admin(page)
    page.add_init_script("try { localStorage.removeItem('party_module_alone'); } catch (e) {}")  # vrai module seul
    try:
        page.goto(events_origin + '/events/admin/users', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('3 personne(s) inscrite(s) avec leur numéro', exact=False)).to_be_visible(timeout=15000)
        page.wait_for_timeout(1000)
        assert '/events/admin/users' in page.url, page.url
        assert page.locator('#eventsFrame').count() == 0
    finally:
        context.close()
