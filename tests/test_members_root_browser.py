"""Section « Membres » pour Root : tous les inscrits, suppression d'un compte (surnom tapé), journal des membres.
Supabase est simulé ; les règles (rang, surnom, journal en ajout seul) sont testées sur un vrai Postgres
dans supabase/tests/member_admin.test.mjs."""
import json
from urllib.parse import urlparse


from tests.test_events_browser import USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

TOM = '11111111-1111-4111-8111-111111111111'
SAM = '22222222-2222-4222-8222-222222222222'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile',
           'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS'}


def person(id, name, role, phone, first='2026-10-20T08:00:00Z', last='2026-10-24T20:00:00Z', logins=1, **extra):
    return {'id': id, 'display_name': name, 'first_name': name, 'last_name': 'Test', 'phone': phone, 'avatar_url': f'{id}/a.jpg', 'role': role,
            'status': 'active', 'created_at': first, 'first_sign_in_at': first, 'last_sign_in_at': last, 'beta': False,
            'sign_in_count': logins, 'last_device': 'iPhone Safari', 'groups': [], 'rsvp_count': 0, 'message_count': 0, **extra}


def member_admin(page, has_migration=True):
    """Fonctions de la migration 20261025120000 (simulées) ; sans elle, la base répond « fonction inconnue »."""
    people = [person(USER, 'Compte de démonstration', 'admin', '41791234567', first='2026-10-01T08:00:00Z', last='2026-10-25T09:00:00Z', logins=40),
              person(SAM, 'Sam', 'admin', '41790000044', first='2026-10-10T08:00:00Z', last='2026-10-22T09:00:00Z', logins=3, groups=['Vendredi Party']),
              person(TOM, 'Tom', 'guest', '41790000000', first='2026-10-21T08:00:00Z', last='2026-10-23T09:00:00Z', logins=12, beta=True, rsvp_count=2, message_count=5)]
    calls = []

    def handle(route):
        request, path = route.request, urlparse(route.request.url).path
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        calls.append((path, request.post_data))
        if not has_migration:
            return route.fulfill(status=404, content_type='application/json', headers=HEADERS,
                                 body=json.dumps({'code': 'PGRST202', 'message': f'Could not find the function public.{path.rsplit("/", 1)[-1]}'}))
        if path.endswith('/rpc/admin_member_list'):
            body = people
        elif path.endswith('/rpc/admin_delete_member'):
            args = json.loads(request.post_data)
            people[:] = [p for p in people if p['id'] != args['member']]
            body = None
        else:  # admin_member_audit
            body = [{'id': 2, 'at': '2026-10-24T20:05:00Z', 'action': 'member.role', 'actor': USER, 'actor_name': 'Boby', 'target': TOM, 'target_name': 'Tom', 'details': {'from': 'guest', 'to': 'member'}},
                    {'id': 1, 'at': '2026-10-24T20:00:00Z', 'action': 'members.viewed', 'actor': USER, 'actor_name': 'Boby', 'target': None, 'target_name': None, 'details': None}]
        route.fulfill(status=200, content_type='application/json', headers=HEADERS, body=json.dumps(body))

    def directory(route):
        # Annuaire habituel : un profil avec .single(), sinon la liste (comme PostgREST).
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        single = 'vnd.pgrst.object' in (route.request.headers.get('accept') or '')
        rows = [{k: v for k, v in p.items() if k not in ('beta', 'last_sign_in_at')} for p in people]
        route.fulfill(status=200, content_type='application/json', headers=HEADERS,
                      body=json.dumps(next(p for p in rows if p['id'] == USER) if single else rows))

    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/get_member_directory*', directory)
    for fn in ('admin_member_list', 'admin_delete_member', 'admin_member_audit'):
        page.route(f'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/{fn}*', handle)
    return calls


def open_members(page, events_origin):
    page.goto(events_origin + '/events/admin/members', wait_until='domcontentloaded')
    login(page)


def test_root_sees_every_signup_and_deletes_one_after_typing_the_nickname(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); mock_services(page); calls = member_admin(page)
    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        open_members(page, events_origin)
        pw.expect(page.get_by_text('3 compte(s) inscrit(s)', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Guest (1)', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Guest · 🧪 Bêta-testeur · +41790000000', exact=True)).to_be_visible()  # numéro visible pour Root
        pw.expect(page.get_by_text('Inscrit le', exact=False).first).to_be_visible()
        # Root peut supprimer Sam (admin) et Tom (Guest), pas son propre compte.
        delete = page.get_by_role('button', name='Supprimer le compte')
        pw.expect(delete).to_have_count(2)
        delete.last.click()
        confirm = page.get_by_role('button', name='Supprimer définitivement')
        pw.expect(confirm).to_be_disabled()
        page.get_by_label('Surnom de Tom pour confirmer').fill('to')
        pw.expect(confirm).to_be_disabled()
        page.get_by_label('Surnom de Tom pour confirmer').fill(' tom ')
        confirm.click()
        pw.expect(page.get_by_text('2 compte(s) inscrit(s)', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Guest (1)', exact=True)).to_have_count(0)
        sent = next(json.loads(body) for path, body in calls if path.endswith('/admin_delete_member'))
        assert sent == {'member': TOM, 'confirm_name': ' tom '}
        assert not errors
    finally:
        context.close()


def test_root_reads_the_members_journal_in_plain_words(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); mock_services(page); calls = member_admin(page)
    try:
        open_members(page, events_origin)
        page.get_by_text('📜 Journal des membres', exact=True).click()
        pw.expect(page.get_by_text('Boby a passé Tom de Guest à Membre VIP', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Boby a ouvert la liste des membres (numéros compris)', exact=True)).to_be_visible()
        assert any(path.endswith('/admin_member_audit') for path, _ in calls)
    finally:
        context.close()


def test_before_the_database_update_the_members_page_keeps_working_without_delete(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); mock_services(page); member_admin(page, has_migration=False)
    try:
        open_members(page, events_origin)
        pw.expect(page.get_by_text('liste complète et suppression après la mise à jour de la base', exact=False)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('Compte de démonstration (toi)', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Tom', exact=True)).to_be_visible()
        pw.expect(page.get_by_role('button', name='Supprimer le compte')).to_have_count(0)
        pw.expect(page.get_by_text('📜 Journal des membres', exact=True)).to_be_visible()
    finally:
        context.close()


def order(page):
    return [el.get_attribute('aria-label').removeprefix('Utilisateur ') for el in page.locator('[aria-label^="Utilisateur "]').all()]


def test_root_sees_every_user_with_first_and_last_connection_and_sorts_them(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); mock_services(page); member_admin(page)
    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(events_origin + '/events/admin/users', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('3 personne(s) inscrite(s) avec leur numéro', exact=False)).to_be_visible(timeout=15000)
        tom = page.get_by_label('Utilisateur Tom')
        pw.expect(tom).to_contain_text('1re connexion : ')
        pw.expect(tom).to_contain_text('Dernière connexion : ')
        pw.expect(tom).to_contain_text('12 connexion(s) notée(s) · dernier appareil : iPhone Safari')
        pw.expect(tom).to_contain_text('2 événement(s) « je viens » · 5 message(s)')
        pw.expect(tom).to_contain_text('Guest · 🧪 Bêta')
        pw.expect(page.get_by_label('Utilisateur Sam')).to_contain_text('👥 Vendredi Party')
        # Par défaut : dernière connexion, la plus récente d'abord ; un 2e appui inverse.
        assert order(page) == ['Compte de démonstration', 'Tom', 'Sam']
        page.get_by_role('button', name='Dernière connexion ↓').click()
        assert order(page) == ['Sam', 'Tom', 'Compte de démonstration']
        page.get_by_role('button', name='Première connexion', exact=True).click()
        assert order(page) == ['Tom', 'Sam', 'Compte de démonstration']
        page.get_by_role('button', name='Nom', exact=True).click()
        assert order(page) == ['Compte de démonstration', 'Sam', 'Tom']  # A → Z
        page.get_by_role('button', name='Nb de connexions', exact=True).click()
        assert order(page) == ['Compte de démonstration', 'Tom', 'Sam']
        page.get_by_role('button', name='Activité', exact=True).click()
        assert order(page)[0] == 'Tom'
        page.get_by_role('button', name='Guest', exact=True).click()
        assert order(page) == ['Tom']
        page.get_by_role('button', name='Tous', exact=True).click()
        page.get_by_label('Rechercher un utilisateur').fill('000044')
        assert order(page) == ['Sam']
        assert not errors
    finally:
        context.close()


def test_users_section_waits_for_the_database_update_without_breaking(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page(); mock_services(page); member_admin(page, has_migration=False)
    try:
        page.goto(events_origin + '/events/admin/users', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Cette liste s’ouvrira après la mise à jour de la base', exact=False)).to_be_visible(timeout=15000)
    finally:
        context.close()
