"""Parcours ORGANISATEUR du module Événements, dans le vrai module construit (navigateur, Supabase simulé : aucun SMS,
aucune notification réelle). Chaque bouton du formulaire et de la zone organisateur est touché, et ce qui part vers la
base est vérifié : formulaire simple et avancé, brouillon, publication, sondage de dates, lieu Google, prix, places,
liste d'attente, accompagnants, « Peut-être », date limite, visibilité (groupe / invités / publique + lien), billets QR,
tags, co-organisateurs, mini-sondages, qui amène quoi, modification après publication, annulation, suppression.
Module construit ailleurs que web/events/dist : EVENTS_TEST_DIST=<dossier> (sinon web/events/dist)."""
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from tests.test_events_browser import DIST, EVENT, USER, browser, events_origin, login, mock_services  # noqa: F401

pw = pytest.importorskip('playwright.sync_api')
pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
ROOT = Path(__file__).resolve().parents[1]
REST = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/'
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}
NEW = '5a1e0c3d-0000-4000-8000-00000000a001'
LEA = '7c0ffee0-0000-4000-8000-0000000000aa'
TAG = '3a9e0000-0000-4000-8000-0000000000c1'
CATEGORY = 'ed69d11e-34dd-43fe-b211-10d0dd158ba9'
SHOTS = Path(__import__('os').environ.get('EVENTS_TEST_SHOTS') or ROOT / '.impeccable/review/organisateur')


def full_event(row: dict) -> dict:
    """Ligne « events » telle que la page de l'événement et le formulaire la lisent (enfants vides par défaut)."""
    base = {'id': NEW, 'title': '', 'description': '', 'created_by': USER, 'status': 'draft', 'date_mode': 'fixed',
            'starts_at': None, 'ends_at': None, 'poll_deadline': None, 'members_can_propose_dates': True, 'auto_fix_date': False,
            'created_at': '2026-11-04T08:00:00Z', 'updated_at': '2026-11-04T08:00:00Z', 'location_name': None,
            'location_address': None, 'location_url': None, 'price_chf': None, 'payment_info': None, 'max_participants': None,
            'waitlist_enabled': True, 'allow_plus_ones': True, 'max_plus_ones': 10, 'allow_maybe': True, 'rsvp_deadline': None,
            'visibility': 'all', 'public_link': False, 'show_participants': True, 'pot_enabled': False, 'tickets_enabled': False,
            'forum_enabled': True, 'notify_on_publish': True, 'reminders': [], 'cover_url': None, 'category_id': None,
            'rejection_reason': None}
    out = {**base, **row}
    return {**out, 'category': None, 'author': {'id': out['created_by'], 'display_name': 'Compte de démonstration'},
            'event_tags': [], 'event_organizers': [{'user_id': u} for u in out.get('_organizers', [])],
            'event_invites': [], 'event_groups': [], 'event_phone_invites': [], 'date_options': [], 'polls': [],
            'bring_items': [], 'rsvps': []}


class FakeBase:
    """PostgREST simulé pour le parcours organisateur : garde l'événement créé et note chaque écriture."""

    def __init__(self, page, event: dict | None = None):
        self.event = event  # None tant que rien n'est créé
        self.writes: list[tuple[str, str, str, object]] = []  # (méthode, table, requête, corps)
        page.route(REST + '**', self.handle)
        page.route('https://places.googleapis.com/**', self.places)
        page.route('**/api/wallet/notify', lambda r: r.fulfill(status=200, content_type='application/json', body='{"devices": 0}'))

    def wrote(self, method: str, table: str) -> list[tuple[str, object]]:
        return [(q, b) for m, t, q, b in self.writes if m == method and t == table]

    @staticmethod
    def reply(route, body, status=200):
        route.fulfill(status=status, content_type='application/json', body=json.dumps(body), headers=HEADERS)

    def places(self, route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        if 'autocomplete' in route.request.url:
            return self.reply(route, {'suggestions': [{'placePrediction': {'placeId': 'p1', 'structuredFormat': {
                'mainText': {'text': 'Bar du Lac'}, 'secondaryText': {'text': 'Quai 1, Genève'}}}}]})
        self.reply(route, {'displayName': {'text': 'Bar du Lac'}, 'formattedAddress': 'Quai du Mont-Blanc 1, 1201 Genève',
                           'googleMapsUri': 'https://maps.google.com/?cid=1'})

    def handle(self, route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        url = urlparse(request.url)
        table = url.path.split('/rest/v1/', 1)[1]
        query = unquote(url.query)
        single = 'vnd.pgrst.object' in (request.headers.get('accept') or '')
        body = json.loads(request.post_data) if request.post_data else None
        if request.method in ('POST', 'PATCH', 'DELETE') and not table.startswith('rpc/'):
            self.writes.append((request.method, table, query, body))
        if table == 'events':
            return self.events(route, request.method, query, body, single)
        if table == 'rpc/event_group_names':
            return self.reply(route, [])
        if table == 'rpc/event_attendance':
            return self.reply(route, [])
        if table == 'rpc/event_checkins':
            return self.reply(route, [])
        if table.startswith('rpc/'):
            return route.fallback()  # droits, répertoire… : la simulation commune (mock_services)
        if table == 'tags':
            return self.reply(route, [{'id': TAG, 'name': 'karting', 'color': '#7FD1B9', 'archived': False}])
        if table == 'profiles':
            return self.reply(route, [{'id': USER, 'display_name': 'Compte de démonstration', 'role': 'admin'},
                                      {'id': LEA, 'display_name': 'Léa', 'role': 'member'}])
        if table == 'member_groups':
            return self.reply(route, [{'id': 'g-vip', 'name': 'Vendredi Party', 'created_by': None, 'system_key': 'vip',
                                       'member_group_members': [{'user_id': USER}, {'user_id': LEA}]}])
        if table == 'group_settings':
            return self.reply(route, {'require_approval': True, 'organizers_can_edit_published': True, 'name': 'Groupe',
                                      'timezone': 'Europe/Zurich', 'coadmins_skip_approval': True, 'members_can_create_tags': False})
        if request.method == 'POST' and single:  # insertion « .select('id').single() » : un identifiant neuf
            return self.reply(route, {'id': f'{table}-{len(self.writes)}'}, status=201)
        if request.method in ('POST', 'PATCH', 'DELETE'):
            return self.reply(route, [] if not single else {}, status=201 if request.method == 'POST' else 200)
        route.fallback()

    def events(self, route, method, query, body, single):
        if method == 'POST':
            self.event = full_event({**body, 'id': NEW, 'created_by': USER})
            return self.reply(route, {'id': NEW}, status=201)
        if method == 'PATCH':
            self.event = {**self.event, **body}
            return self.reply(route, [], status=200)
        if method == 'DELETE':
            self.event = None
            return self.reply(route, [], status=200)
        if 'id=eq.' in query or single:
            if self.event and f'id=eq.{self.event["id"]}' in query:
                return self.reply(route, self.event if single else [self.event])
            return route.fallback()
        return self.reply(route, [self.event] if self.event else [])  # la liste


def launch(browser, origin, event=None, width=390):
    context = browser.new_context(viewport={'width': width, 'height': 844})
    page = context.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}])
    base = FakeBase(page, event)
    page.goto(origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    pw.expect(frame.get_by_role('button', name='Proposer un événement', exact=True)).to_be_visible(timeout=15000)
    return context, page, frame, base, errors


def shot(page, name: str):
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=True)


def open_form(frame, mode: str):
    frame.get_by_role('button', name='Proposer un événement', exact=True).click()
    pw.expect(frame.get_by_text('Titre', exact=True)).to_be_visible(timeout=10000)
    frame.get_by_role('tab', name=mode, exact=True).click()


def fill_date(frame, label: str, day: str, time: str):
    frame.get_by_label(f'{label} : jour', exact=True).fill(day)
    frame.get_by_label(f'{label} : heure', exact=True).select_option(time)


def field(frame, label: str):
    return frame.get_by_label(label, exact=True)


def test_simple_form_publishes_with_the_usual_defaults(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin)
    try:
        open_form(frame, 'Simple')
        field(frame, 'Titre').fill('Karting du vendredi')
        fill_date(frame, 'Début', '2030-12-12', '19:00')
        # Lieu Google : choisir une proposition remplit nom, adresse et lien.
        field(frame, 'Chercher un lieu sur Google Maps').fill('Bar du')
        frame.get_by_role('button', name='Bar du Lac, Quai 1, Genève', exact=True).click()
        pw.expect(field(frame, 'Lieu')).to_have_value('Bar du Lac')
        # Mode simple : l'adresse et le lien remplis par Google sont rappelés (« Actifs : adresse »).
        pw.expect(frame.get_by_text('Actifs : adresse', exact=True)).to_be_visible()
        shot(page, 'formulaire-simple')
        frame.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Modifier', exact=True)).to_be_visible(timeout=10000)
        (_, row), = base.wrote('POST', 'events')
        assert row['status'] == 'draft' and row['title'] == 'Karting du vendredi'
        assert row['starts_at'] == '2030-12-12T18:00:00.000Z'  # 19:00 à Zurich
        assert row['location_address'] == 'Quai du Mont-Blanc 1, 1201 Genève' and row['location_url'] == 'https://maps.google.com/?cid=1'
        # Réglages habituels : groupe Vendredi Party, billets QR éteints, annonce au groupe, +1 sans limite, tous les rappels.
        assert (row['visibility'], row['public_link'], row['tickets_enabled'], row['notify_on_publish']) == ('all', False, False, True)
        assert row['allow_plus_ones'] is True and row['max_plus_ones'] == 10 and row['allow_maybe'] is True
        assert row['reminders'] == ['7d', '1d', '2h', '0h'] and row['max_participants'] is None and row['price_chf'] is None
        # Publication APRÈS les enfants (tags, invités…) : un seul PATCH de statut, à la fin.
        assert [b for _, b in base.wrote('PATCH', 'events')][-1] == {'status': 'published'}
        assert base.event['status'] == 'published'
        assert not errors
    finally:
        context.close()


def test_advanced_form_sends_every_option(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin)
    try:
        open_form(frame, 'Avancé')
        field(frame, 'Titre').fill('Raclette au chalet')
        field(frame, 'Description').fill('Fromage à volonté')
        frame.get_by_role('button', name='Soirée', exact=True).click()
        frame.get_by_role('button', name='#karting', exact=True).click()
        fill_date(frame, 'Début', '2030-12-20', '18:30')
        fill_date(frame, 'Fin (optionnel)', '2030-12-20', '23:00')
        field(frame, 'Lieu').fill('Chalet')
        field(frame, 'Adresse').fill('Route du Col 3')
        field(frame, 'Lien (site, carte…)').fill('https://chalet.example')
        field(frame, 'Prix / pers. (CHF)').fill('25,50')
        field(frame, 'Paiement').fill('TWINT')
        frame.get_by_role('switch', name='Billets QR', exact=True).click()
        frame.get_by_role('button', name='Publique + lien', exact=True).click()
        field(frame, 'Nombre de places (vide = illimité)').fill('12')
        frame.get_by_role('switch', name='Liste d’attente', exact=True).click()
        frame.get_by_role('switch', name='Réponse « Peut-être » autorisée', exact=True).click()
        field(frame, 'Accompagnants max par personne (vide = illimité)').fill('2')
        fill_date(frame, 'Date limite de réponse (optionnel)', '2030-12-15', '12:00')
        frame.get_by_role('button', name='Léa', exact=True).click()  # co-organisatrice
        frame.get_by_role('switch', name='Pot commun', exact=True).click()
        frame.get_by_role('button', name='+ Ajouter un sondage', exact=True).click()
        field(frame, 'Question du sondage 1').fill('Vin ou bière ?')
        field(frame, 'Sondage 1, option 1').fill('Vin')
        field(frame, 'Sondage 1, option 2').fill('Bière')
        frame.get_by_role('button', name='Anonyme', exact=True).click()
        frame.get_by_role('button', name='+ Ajouter un objet', exact=True).click()
        frame.get_by_placeholder('Fromage, pain…').fill('Pain')
        frame.get_by_placeholder('Qté', exact=True).fill('3')
        frame.get_by_role('switch', name='Forum de l’événement', exact=True).click()
        frame.get_by_role('switch', name='Prévenir le groupe à la publication', exact=True).click()
        shot(page, 'formulaire-avance')
        frame.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Modifier', exact=True)).to_be_visible(timeout=10000)
        (_, row), = base.wrote('POST', 'events')
        assert row['category_id'] == CATEGORY and row['description'] == 'Fromage à volonté'
        assert row['ends_at'] == '2030-12-20T22:00:00.000Z' and row['rsvp_deadline'] == '2030-12-15T11:00:00.000Z'
        assert (row['price_chf'], row['payment_info'], row['max_participants']) == (25.5, 'TWINT', 12)
        assert row['waitlist_enabled'] is False and row['allow_maybe'] is False and row['max_plus_ones'] == 2
        assert (row['visibility'], row['public_link'], row['tickets_enabled']) == ('all', True, True)
        assert row['pot_enabled'] is True and row['forum_enabled'] is False and row['notify_on_publish'] is False
        assert row['location_url'] == 'https://chalet.example'
        assert [b for _, b in base.wrote('POST', 'event_tags')] == [[{'event_id': NEW, 'tag_id': TAG}]]
        assert [b for _, b in base.wrote('POST', 'event_organizers')] == [[{'event_id': NEW, 'user_id': LEA}]]
        (_, poll), = base.wrote('POST', 'polls')
        assert poll['question'] == 'Vin ou bière ?' and poll['anonymous'] is True
        assert [b['label'] for _, b in base.wrote('POST', 'poll_options')] == ['Vin', 'Bière']
        (_, bring), = base.wrote('POST', 'bring_items')
        assert bring['label'] == 'Pain' and bring['quantity'] == 3
        # Publique : ni groupes ni invités un à un enregistrés.
        assert not base.wrote('POST', 'event_groups') and not base.wrote('POST', 'event_invites')
        assert not errors
    finally:
        context.close()


def test_date_poll_and_draft_then_publish_from_the_draft(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin)
    try:
        open_form(frame, 'Avancé')
        field(frame, 'Titre').fill('Escape game')
        frame.get_by_role('tab', name='Date à définir', exact=True).click()
        # Sondage de dates : le mode simple est verrouillé (rien n'est caché).
        pw.expect(frame.get_by_role('tab', name='Simple', exact=True)).to_be_disabled()
        fill_date(frame, 'Créneau 1', '2030-12-05', '19:00')
        fill_date(frame, 'Créneau 2', '2030-12-06', '20:00')
        frame.get_by_role('button', name='+ Ajouter un créneau', exact=True).click()
        fill_date(frame, 'Créneau 3', '2030-12-07', '21:00')
        frame.get_by_role('switch', name='Fixer la date automatiquement', exact=True).click()
        fill_date(frame, 'Fin du vote (optionnel)', '2030-12-01', '12:00')
        frame.get_by_role('button', name='Enregistrer en brouillon', exact=True).click()
        pw.expect(frame.get_by_text('Brouillon', exact=True)).to_be_visible(timeout=10000)
        (_, row), = base.wrote('POST', 'events')
        assert row['date_mode'] == 'poll' and row['starts_at'] is None and row['auto_fix_date'] is True
        assert row['poll_deadline'] == '2030-12-01T11:00:00.000Z'
        assert [b['starts_at'] for _, b in base.wrote('POST', 'date_options')] == [
            '2030-12-05T18:00:00.000Z', '2030-12-06T19:00:00.000Z', '2030-12-07T20:00:00.000Z']
        assert not base.wrote('PATCH', 'events')  # brouillon : jamais publié
        assert base.event['status'] == 'draft'
        # Le brouillon se publie depuis « Modifier ».
        frame.get_by_role('button', name='Modifier', exact=True).click()
        frame.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Modifier', exact=True).filter(visible=True)).to_be_visible(timeout=10000)
        pw.expect(frame.get_by_text('Brouillon', exact=True).filter(visible=True)).to_have_count(0)
        assert base.event['status'] == 'published'
        assert [b for _, b in base.wrote('PATCH', 'events')][-1] == {'status': 'published'}
        assert not errors
    finally:
        context.close()


def test_invite_only_event_saves_people_and_phone_numbers(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin)
    try:
        open_form(frame, 'Simple')
        field(frame, 'Titre').fill('Anniversaire surprise')
        fill_date(frame, 'Début', '2030-12-12', '20:00')
        frame.get_by_role('button', name='✓ 👥 Vendredi Party · 2', exact=True).click()  # décoché : sur invitation seulement
        frame.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(frame.get_by_text('Choisis qui inviter : le groupe Vendredi Party, un groupe ou des personnes', exact=True)).to_be_visible()
        assert not base.wrote('POST', 'events')
        field(frame, 'Chercher une personne à inviter').fill('lé')
        frame.get_by_role('button', name='+ Léa', exact=True).click()
        field(frame, 'Inviter par numéro de téléphone').fill('079 555 66 77')
        frame.get_by_role('button', name='Inviter', exact=True).click()
        pw.expect(frame.get_by_text('Ajoute l’indicatif du pays. Numéro suisse ? Écris +41 79 555 66 77. Étranger : +33, +34…', exact=True)).to_be_visible()
        field(frame, 'Inviter par numéro de téléphone').fill('+41 79 555 66 77')
        frame.get_by_role('button', name='Inviter', exact=True).click()
        frame.get_by_role('button', name='Publier', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Modifier', exact=True)).to_be_visible(timeout=10000)
        (_, row), = base.wrote('POST', 'events')
        assert (row['visibility'], row['public_link']) == ('invited', False)
        assert [b for _, b in base.wrote('POST', 'event_invites')] == [[{'event_id': NEW, 'user_id': LEA}]]
        assert [b for _, b in base.wrote('POST', 'event_phone_invites')] == [[{'event_id': NEW, 'phone': '41795556677'}]]
        assert not errors
    finally:
        context.close()


def test_form_refuses_bad_values_before_writing(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin)
    try:
        open_form(frame, 'Avancé')
        publish = frame.get_by_role('button', name='Publier', exact=True)
        publish.click()
        pw.expect(frame.get_by_text('Il manque un titre', exact=True)).to_be_visible()
        field(frame, 'Titre').fill('Test erreurs')
        publish.click()
        pw.expect(frame.get_by_text('Début : obligatoire', exact=True)).to_be_visible()
        fill_date(frame, 'Début', '2030-12-12', '20:00')
        fill_date(frame, 'Fin (optionnel)', '2030-12-12', '19:00')
        publish.click()
        pw.expect(frame.get_by_text('La fin doit être après le début', exact=True)).to_be_visible()
        frame.get_by_role('button', name='Effacer : Fin (optionnel)', exact=True).click()
        field(frame, 'Nombre de places (vide = illimité)').fill('0')
        publish.click()
        pw.expect(frame.get_by_text('Nombre de places invalide', exact=True)).to_be_visible()
        field(frame, 'Nombre de places (vide = illimité)').fill('')
        field(frame, 'Prix / pers. (CHF)').fill('-3')
        publish.click()
        pw.expect(frame.get_by_text('Le prix doit être un montant positif ou zéro', exact=True)).to_be_visible()
        field(frame, 'Prix / pers. (CHF)').fill('')
        field(frame, 'Lien (site, carte…)').fill('javascript:alert(1)')
        publish.click()
        pw.expect(frame.get_by_text('Le lien doit commencer par https:// ou http://', exact=True)).to_be_visible()
        assert not base.wrote('POST', 'events')
        assert not errors
    finally:
        context.close()


def published(**row) -> dict:
    return full_event({'title': 'Soirée publiée', 'status': 'published', 'starts_at': '2030-11-14T18:00:00Z', **row})


def open_event(frame, title='Soirée publiée'):
    frame.get_by_text(title, exact=True).first.click()


def test_edit_after_publication_keeps_it_published_and_updates_wallet(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin, event=published())
    wallet = []
    page.on('request', lambda r: wallet.append(r.url) if '/api/wallet/notify' in r.url else None)
    try:
        open_event(frame)
        frame.get_by_role('button', name='Modifier', exact=True).click()
        pw.expect(field(frame, 'Titre')).to_have_value('Soirée publiée', timeout=10000)
        field(frame, 'Titre').fill('Soirée publiée (nouvelle heure)')
        # Publié : « Enregistrer », pas de brouillon possible.
        assert frame.get_by_role('button', name='Enregistrer en brouillon', exact=True).count() == 0
        frame.get_by_role('button', name='Enregistrer', exact=True).click()
        pw.expect(frame.get_by_text('Soirée publiée (nouvelle heure)', exact=True)).to_be_visible(timeout=10000)
        patches = [b for _, b in base.wrote('PATCH', 'events')]
        assert patches and all('status' not in b for b in patches)
        assert base.event['status'] == 'published'
        page.wait_for_timeout(300)
        assert wallet  # les billets déjà dans Cartes se mettent à jour
        assert not errors
    finally:
        context.close()


def test_cancel_asks_for_confirmation(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin, event=published())
    try:
        open_event(frame)
        frame.get_by_role('button', name='Annuler l’événement', exact=True).click()
        frame.get_by_role('button', name='Garder', exact=True).click()
        assert not base.wrote('PATCH', 'events')
        frame.get_by_role('button', name='Annuler l’événement', exact=True).click()
        frame.get_by_role('button', name='Oui, annuler', exact=True).click()
        pw.expect(frame.get_by_text('Cet événement a été annulé.', exact=True)).to_be_visible(timeout=10000)
        assert [b for _, b in base.wrote('PATCH', 'events')] == [{'status': 'cancelled'}]
        shot(page, 'evenement-annule')
        assert not errors
    finally:
        context.close()


def test_delete_a_draft(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin, event=full_event({'title': 'Brouillon à jeter', 'status': 'draft', 'starts_at': '2030-11-14T18:00:00Z'}))
    try:
        frame.get_by_role('tab', name='Brouillons', exact=True).click()
        open_event(frame, 'Brouillon à jeter')
        frame.get_by_role('button', name='Supprimer la proposition', exact=True).click()
        frame.get_by_role('button', name='Oui, supprimer', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Proposer un événement', exact=True)).to_be_visible(timeout=10000)
        assert [q for q, _ in base.wrote('DELETE', 'events')] == [f'id=eq.{NEW}']
        assert not errors
    finally:
        context.close()


def test_a_co_organizer_keeps_his_role_when_he_saves(browser, events_origin):
    """Bug : la sauvegarde effaçait TOUS les co-organisateurs puis les réinscrivait sans soi-même. Un co-organisateur
    (pas le créateur) se retirait donc lui-même ; la base (RLS « gérer organisateurs ») refusait ensuite la réinsertion
    des autres : erreur, plus aucun co-organisateur, et il perdait la main sur l'événement."""
    other = '9b9b9b9b-0000-4000-8000-0000000000bb'
    event = published(created_by=other, _organizers=[USER, LEA])
    context, page, frame, base, errors = launch(browser, events_origin, event=event)
    try:
        open_event(frame)
        frame.get_by_role('button', name='Modifier', exact=True).click()
        pw.expect(field(frame, 'Titre')).to_have_value('Soirée publiée', timeout=10000)
        frame.get_by_role('tab', name='Avancé', exact=True).click()
        frame.get_by_role('button', name='Enregistrer', exact=True).click()
        pw.expect(frame.get_by_role('button', name='Modifier', exact=True)).to_be_visible(timeout=10000)
        deletes = [q for q, _ in base.wrote('DELETE', 'event_organizers')]
        assert deletes and all(f'user_id=neq.{USER}' in q for q in deletes), deletes
        inserted = [row for _, rows in base.wrote('POST', 'event_organizers') for row in rows]
        assert inserted == [{'event_id': NEW, 'user_id': LEA}]
        assert not errors
    finally:
        context.close()


def test_editing_a_pending_proposal_never_says_publish(browser, events_origin):
    """Bug : un admin qui modifie une proposition en attente voyait « Publier », mais l'enregistrement la laissait en
    attente (seul « Approuver » la publie). Le bouton dit maintenant ce qu'il fait : « Enregistrer »."""
    context, page, frame, base, errors = launch(browser, events_origin, event=full_event(
        {'title': 'Proposition', 'status': 'pending', 'starts_at': '2030-11-14T18:00:00Z'}))
    try:
        frame.get_by_role('tab', name='En attente', exact=True).click()
        open_event(frame, 'Proposition')
        frame.get_by_role('button', name='Modifier', exact=True).click()
        pw.expect(field(frame, 'Titre')).to_have_value('Proposition', timeout=10000)
        assert frame.get_by_role('button', name='Publier', exact=True).count() == 0
        frame.get_by_role('button', name='Enregistrer', exact=True).click()
        pw.expect(frame.get_by_text('Cette proposition attend ta validation.', exact=True).filter(visible=True)).to_be_visible(timeout=10000)
        assert base.event['status'] == 'pending'
        assert not errors
    finally:
        context.close()


@pytest.fixture(scope='module')
def origin_compagnon_off(tmp_path_factory):
    """Party comme en production : Compagnon (Zicou) éteint."""
    import os
    import socket
    import subprocess
    import sys
    import time

    import httpx
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('party-orga-off')), 'EVENTS_WEB_DIR': str(DIST),
           'ADMIN_PIN': '8462', 'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'COMPAGNON_ENABLED': '0',
           'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port),
                                '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                if httpx.get(origin, timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.05)
        yield origin
    finally:
        process.terminate()
        process.wait(timeout=10)


def gifts_backend(page):
    drop = {'event': {'id': NEW, 'title': 'Soirée publiée', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
                      'status': 'published', 'started': False},
            'role': 'organizer', 'drop': None, 'eligible_now': 3, 'bounds': None, 'catalog': [], 'mine': []}
    page.route(REST + 'rpc/pet_event_drop_get', lambda r: FakeBase.reply(r, drop) if r.request.method != 'OPTIONS'
               else r.fulfill(status=204, headers=HEADERS))
    page.route(REST + 'rpc/pet_event_coins_get', lambda r: FakeBase.reply(r, {'allowed': False, 'mine': None, 'setting': None})
               if r.request.method != 'OPTIONS' else r.fulfill(status=204, headers=HEADERS))


@pytest.mark.parametrize('compagnon', [True, False])
def test_zicou_gifts_only_when_the_companion_is_on(browser, events_origin, origin_compagnon_off, compagnon):
    origin = events_origin if compagnon else origin_compagnon_off
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    errors: list[str] = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}])
    FakeBase(page, published())
    gifts_backend(page)
    try:
        page.goto(f'{origin}/events/', wait_until='domcontentloaded')
        login(page)
        page.get_by_text('Soirée publiée', exact=True).first.click()
        pw.expect(page.get_by_text('ZONE ORGANISATEUR', exact=True)).to_be_visible(timeout=15000)
        link = page.get_by_text('🎁 Cadeaux Zicou de l’événement', exact=True)
        if compagnon:
            pw.expect(link).to_be_visible(timeout=10000)
        else:
            page.wait_for_timeout(800)
            assert link.count() == 0
            # Adresse directe : retour à l'événement, jamais la page des cadeaux.
            page.goto(f'{origin}/events/event/{NEW}/gifts', wait_until='domcontentloaded')
            pw.expect(page.get_by_text('ZONE ORGANISATEUR', exact=True)).to_be_visible(timeout=15000)
            assert page.get_by_text('Règlement', exact=True).count() == 0
        assert not errors
    finally:
        context.close()


def test_public_event_link_is_copied_for_sharing(browser, events_origin):
    context, page, frame, base, errors = launch(browser, events_origin, event=published(public_link=True))
    try:
        context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=events_origin)
        page.add_init_script('Object.defineProperty(navigator, "share", { value: undefined })')
        event_frame = page.frame(url=f'{events_origin}/events/')
        event_frame.evaluate('Object.defineProperty(navigator, "share", { value: undefined, configurable: true })')
        open_event(frame)
        pw.expect(frame.get_by_text('🌍 Publique : tous les comptes Party et toute personne qui a le lien', exact=True)).to_be_visible(timeout=10000)
        frame.get_by_role('button', name='Partager le lien', exact=True).click()
        pw.expect(frame.get_by_text('Lien copié', exact=True)).to_be_visible(timeout=5000)
        copied = event_frame.evaluate('navigator.clipboard.readText()')
        assert copied == f'{events_origin}/?tab=events&event={NEW}'
        assert not errors
    finally:
        context.close()
