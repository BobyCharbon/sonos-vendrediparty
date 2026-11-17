"""Agenda dans Party (17.11.2026, maquettes A « Néon nuit » validées), dans un vrai navigateur, Supabase SIMULÉ :
- entrées : « 📅 Agenda » dans l'en-tête d'Événements et Réglages › Autres apps › Agenda, avec la pastille des demandes ;
- semaine (jours empilés, source écrite, soirée Party « À répondre », « 🌙 Soirée libre »), jour (trous « Libre »), mois ;
- nouveau rendez-vous (titre, jour, heures ; « Va dans Juste pour moi ») ;
- « Partager mes dispos » : tout décoché, groupe par groupe, le bouton compte les groupes, « C'est fait » ;
- « Qui est libre ? » : « Le mieux », Disponible / Occupé en mots, « Les autres membres » grisés sans texte ; « Organiser »
  ouvre la création d'événement remplie (groupe, titre, date) ; « Faire voter » un sondage de 3 dates ;
- liens de dispo : état vide, modèles, « Toute personne qui a ce lien… », réglage, aperçu ; demandes : Accepter, Signaler.
Captures : PARTY_SHOTS=<dossier> (sinon le dossier temporaire)."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pytest

from tests.test_events_browser import EVENT, USER, browser, events_origin, mock_services, pw  # noqa: F401 (fixtures)
from tests.test_groups_browser import CORS, SUPABASE, phone, signed_in  # noqa: F401 (fixtures)

SHOTS = Path(os.environ.get('PARTY_SHOTS') or tempfile.gettempdir())
SWISS = ZoneInfo('Europe/Zurich')
FOOT, FAMILLE, VIP = '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a04', '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a05', '5e0d6a51-8f1c-4c51-9a6b-2b8f1e4c0a01'
YANIS, MARC, LEA, SAM = (f'7a1c2b3d-0000-4000-8000-00000000001{i}' for i in range(4))
PARTY_CAL, PERSONAL_CAL = '9b0c0000-0000-4000-8000-000000000001', '9b0c0000-0000-4000-8000-000000000002'
LINK = '6c0d0000-0000-4000-8000-000000000001'
BOOKING = '6c0d0000-0000-4000-8000-0000000000b1'


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Heure de Suisse, `day` jours après aujourd'hui."""
    base = datetime.now(SWISS).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day)
    return base.replace(hour=hour, minute=minute)


def iso(d: datetime) -> str:
    return d.isoformat()


def agenda_services(page, links=None, pending=1, welcome_seen=False):
    """Base simulée de l'Agenda, posée par-dessus mock_services (les routes posées après passent d'abord)."""
    calls = mock_services(page)
    state = {'calls': [], 'items': [{
        'id': '8a000000-0000-4000-8000-000000000001', 'calendar_id': PERSONAL_CAL, 'title': 'Dentiste', 'place': None, 'notes': None,
        'starts_at': iso(at(0, 12, 15)), 'ends_at': iso(at(0, 13, 0)), 'all_day': False, 'repeat': 'none', 'repeat_until': None,
        'alert_minutes': None, 'busy': True, 'series_start': iso(at(0, 12, 15)), 'booking': None}],
        'prefs': {'welcome_seen': welcome_seen}, 'shared': [], 'links': links if links is not None else [], 'pending': pending, 'handle': None,
        'bookings': [{
            'id': BOOKING, 'link_id': LINK, 'link_name': 'Rendez-vous pro', 'link_emoji': '💼', 'starts_at': iso(at(3, 10)),
            'ends_at': iso(at(3, 11)), 'status': 'pending', 'created_at': iso(at(0, 0)), 'expires_at': iso(at(2, 0)), 'decided_at': None,
            'item_id': None, 'first_name': 'Marc', 'last_name': 'Rochat', 'email': 'marc@example.com', 'phone': None,
            'message': 'Un appel d’une heure vous irait ?', 'message_label': 'Message', 'verified': False}]}
    party = [{'event_id': EVENT, 'title': 'Apéro de l’équipe bar', 'starts_at': iso(at(0, 18, 30)), 'ends_at': None, 'all_day': False,
              'location_name': 'Le Bourg', 'status': 'published', 'icon': '🍹', 'organizer': False, 'answer': None}]
    groups = [
        {'id': FOOT, 'name': 'Potes du foot', 'emoji': '⚽', 'color': 'mint', 'system': False, 'members': 5},
        {'id': FAMILLE, 'name': 'La famille', 'emoji': '🏡', 'color': 'coral', 'system': False, 'members': 6},
        {'id': VIP, 'name': 'Vendredi Party', 'emoji': '🎉', 'color': 'lavender', 'system': True, 'members': 128},
    ]

    def sharing():
        return {'share_party': bool(state['shared']), 'share_manual': False, 'busy_updated_at': None, 'busy_count': 0,
                'links_active': 0, 'groups': [{**g, 'shared': g['id'] in state['shared'],
                                               'consented_at': iso(at(0, 9)) if g['id'] in state['shared'] else None} for g in groups]}

    def evenings(skip):
        return [[iso(at(d, 18)), iso(at(d, 23, 59))] for d in range(0, 31) if d not in skip]

    def link_row(body, lid=LINK):
        return {'id': lid, 'token': 'k7Qm2xV9abcdefghijklmnop', 'path': '/d/k7Qm2xV9abcdefghijklmnop', 'name': body.get('name', 'Mes dispos'),
                'emoji': body.get('emoji'), 'display_name': body.get('display_name') or 'Camille', 'rules': body['rules'],
                'horizon_days': body.get('horizon_days', 28), 'duration_min': body.get('duration_min', 60),
                'booking_enabled': body.get('booking_enabled', False), 'booking_fields': body.get('booking_fields'),
                'message_label': body.get('message_label'), 'status': 'active',
                'expires_at': None if body.get('permanent') else iso(at(90, 0)), 'permanent': bool(body.get('permanent')),
                'calendars': body.get('calendars'), 'stopped_at': None, 'slug': None, 'nice_path': None,
                'buffer_before_min': body.get('buffer_before_min', 0), 'buffer_after_min': body.get('buffer_after_min', 0),
                'views': 0, 'last_viewed_at': None, 'pending': 0, 'created_at': iso(at(0, 9))}

    def handle(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        path = urlparse(request.url).path
        body = json.loads(request.post_data) if request.post_data else {}
        name = path.rsplit('/', 1)[-1]
        if path.endswith(f'/rpc/{name}') and name.startswith('agenda_'):
            state['calls'].append((name, body))
        if name == 'agenda_window':
            result = {'items': state['items'], 'party': party, 'polls': []}
        elif name == 'agenda_calendars_list':
            result = [{'id': PARTY_CAL, 'kind': 'party', 'name': 'Mes soirées Party', 'color': 'pink', 'visible': True, 'counts_busy': False,
                       'ics_url': None, 'fetched_at': None, 'fetch_error': None, 'created_at': iso(at(0, 0))},
                      {'id': PERSONAL_CAL, 'kind': 'personal', 'name': 'Juste pour moi', 'color': 'mint', 'visible': True, 'counts_busy': False,
                       'ics_url': None, 'fetched_at': None, 'fetch_error': None, 'created_at': iso(at(0, 0))}]
        elif name == 'agenda_prefs_get':
            result = state['prefs']
        elif name == 'agenda_prefs_save':
            state['prefs'] = {**state['prefs'], **body['prefs']}
            result = state['prefs']
        elif name == 'agenda_badge':
            result = {'pending': state['pending']}
        elif name == 'agenda_item_save':
            item = {**body['item'], 'id': '8a000000-0000-4000-8000-000000000099', 'calendar_id': PERSONAL_CAL, 'booking': None}
            state['items'].append(item)
            result = item
        elif name == 'agenda_sharing':
            result = sharing()
        elif name == 'agenda_set_sharing':
            state['shared'] = body['groups']
            result = sharing()
        elif name == 'agenda_stop_sharing':
            state['shared'] = []
            result = sharing()
        elif name == 'agenda_set_busy':
            result = {'saved': 0, 'updated_at': None}
        elif name == 'agenda_group_free':
            me = {'id': USER, 'name': 'Compte de démonstration', 'avatar_url': None, 'me': True, 'shares': True, 'busy': []}
            result = {'group': {'id': FOOT, 'name': 'Potes du foot', 'emoji': '⚽', 'color': 'mint', 'system': False},
                      'from': iso(datetime.now(SWISS)), 'to': iso(at(30, 0)), 'i_share': True, 'members': [
                          me,
                          {'id': YANIS, 'name': 'Yanis', 'avatar_url': None, 'me': False, 'shares': True, 'busy': [[iso(at(2, 18)), iso(at(2, 18, 30))]]},
                          {'id': MARC, 'name': 'Marc', 'avatar_url': None, 'me': False, 'shares': True, 'busy': [[iso(at(3, 19)), iso(at(3, 21))]]},
                          {'id': LEA, 'name': 'Léa', 'avatar_url': None, 'me': False, 'shares': True, 'busy': evenings({2, 3})},
                          {'id': SAM, 'name': 'Sam', 'avatar_url': None, 'me': False, 'shares': False}]}
        elif name == 'agenda_links':
            result = {'links': state['links'], 'max': 10, 'missing': None, 'notify': True, 'pending': state['pending'], 'handle': state['handle']}
        elif name == 'agenda_handle_set':
            state['handle'] = body['handle'] or None
            result = {'handle': state['handle']}
        elif name == 'agenda_link_set_slug':
            row = state['links'][0]
            row['slug'] = body['slug']
            row['nice_path'] = f"/agenda/{state['handle']}/{body['slug']}" if body['slug'] else None
            result = row
        elif name == 'agenda_link_preview':
            result = {'slots': [[iso(at(1, 18)), iso(at(1, 19))], [iso(at(1, 20, 30)), iso(at(1, 23))], [iso(at(2, 18)), iso(at(2, 20))]], 'tz': 'Europe/Zurich'}
        elif name == 'agenda_link_save':
            row = link_row(body['link'])
            state['links'] = [row]
            result = row
        elif name == 'agenda_link_set':
            result = state['links'][0] if state['links'] else {}
        elif name == 'agenda_booking_requests':
            result = state['bookings']
        elif name == 'agenda_booking_decide':
            state['bookings'][0]['status'] = 'accepted' if body['accept'] else 'refused'
            state['pending'] = 0
            result = state['bookings'][0]
        elif name == 'agenda_booking_report':
            state['bookings'][0]['status'] = 'refused'
            state['pending'] = 0
            result = '11111111-0000-4000-8000-000000000001'
        elif name == 'my_terms':
            result = {'version': '2026-11-16', 'accepted': True, 'accepted_at': None, 'contact_email': None, 'enforced': True}
        elif name == 'my_groups_overview':
            result = []
        else:
            return route.fallback()
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result), headers=CORS)

    page.route(SUPABASE, handle)
    page.route('**/api/account/agenda/ics', lambda route: route.fulfill(status=200, content_type='application/json', body='{"events": []}'))
    state['base'] = calls
    return state


def shot(page, name):
    page.wait_for_timeout(700)  # animations d'entrée finies
    page.screenshot(path=str(SHOTS / name))


def rpc_calls(state, name):
    return [b for n, b in state['calls'] if n == name]


def test_the_events_header_opens_the_week_with_party_evenings_free_evenings_and_the_badge(phone, events_origin):
    page, errors = phone
    agenda_services(page)
    signed_in(page, events_origin)
    button = page.get_by_role('button', name='Agenda, 1 demande de rendez-vous')
    pw.expect(button).to_be_visible(timeout=15000)
    pw.expect(page.get_by_test_id('home-agenda-badge')).to_have_text('1')
    shot(page, 'agenda-00-evenements-bouton.png')
    button.click()
    pw.expect(page.get_by_test_id('agenda-week')).to_be_visible(timeout=15000)
    pw.expect(page.get_by_role('button', name='Retour : Événements')).to_be_visible()
    # Premier lancement : une seule carte, sans demande d'iOS ni partage.
    pw.expect(page.get_by_test_id('agenda-welcome')).to_contain_text('Bienvenue dans ton agenda')
    # Le rendez-vous dit sa source en mots ; la soirée Party dit la réponse.
    today = page.get_by_test_id(f"week-day-{at(0, 0).date().isoformat()}")
    pw.expect(today.get_by_text('Dentiste')).to_be_visible()
    pw.expect(today.get_by_text('Juste pour moi')).to_be_visible()
    pw.expect(today.get_by_text('Apéro de l’équipe bar')).to_be_visible()
    pw.expect(today.get_by_text('À répondre')).to_be_visible()
    pw.expect(page.get_by_text('🌙 Soirée libre').first).to_be_visible()
    pw.expect(page.get_by_role('button', name='Calendriers, 1 demande de rendez-vous')).to_be_visible()
    shot(page, 'agenda-01-semaine.png')
    page.get_by_role('button', name='Plus tard').click()
    pw.expect(page.get_by_test_id('agenda-welcome')).to_have_count(0)
    page.get_by_role('tab', name='Mois').click()
    pw.expect(page.get_by_test_id('agenda-month')).to_be_visible()
    pw.expect(page.get_by_test_id('month-day').get_by_text('Dentiste')).to_be_visible()
    shot(page, 'agenda-02-mois.png')
    page.get_by_role('tab', name='Jour').click()
    pw.expect(page.get_by_test_id('agenda-day')).to_be_visible()
    shot(page, 'agenda-03-jour.png')
    assert errors == [], errors


def test_settings_other_apps_row_opens_the_agenda_with_back_to_settings(phone, events_origin):
    page, errors = phone
    agenda_services(page, welcome_seen=True)
    signed_in(page, events_origin, '/account')
    apps = page.get_by_test_id('settings-other-apps')
    pw.expect(apps.get_by_text('AUTRES APPS')).to_be_visible(timeout=15000)
    row = apps.get_by_role('button', name='Agenda, 1 à voir')
    pw.expect(row).to_be_visible()
    shot(page, 'agenda-04-reglages-autres-apps.png')
    row.click()
    pw.expect(page.get_by_role('button', name='Retour : Réglages')).to_be_visible(timeout=15000)
    assert errors == [], errors


def test_a_new_appointment_needs_only_a_title_and_goes_to_just_for_me(phone, events_origin):
    page, errors = phone
    state = agenda_services(page, welcome_seen=True)
    signed_in(page, events_origin, '/agenda')
    page.get_by_role('button', name='Nouveau rendez-vous').click()
    pw.expect(page.get_by_label('Titre du rendez-vous')).to_be_visible(timeout=15000)
    pw.expect(page.get_by_text('Va dans « Juste pour moi »')).to_be_visible()
    pw.expect(page.get_by_text('Tu veux inviter du monde ?')).to_be_visible()
    page.get_by_label('Titre du rendez-vous').fill('Apéro avec Inès')
    page.get_by_role('button', name='Demain', exact=True).click()
    page.get_by_label('Heure de début').select_option('18:30')
    pw.expect(page.get_by_label('Heure de fin')).to_have_value('20:30')   # le soir : 2 h proposées
    shot(page, 'agenda-05-nouveau-rendez-vous.png')
    page.get_by_role('button', name='Ajouter le rendez-vous').click()
    pw.expect(page.get_by_test_id('agenda-week')).to_be_visible(timeout=15000)
    saved = rpc_calls(state, 'agenda_item_save')[-1]['item']
    assert saved['title'] == 'Apéro avec Inès' and saved['busy'] is True and saved['repeat'] == 'none'
    assert datetime.fromisoformat(saved['starts_at'].replace('Z', '+00:00')) == at(1, 18, 30)
    assert datetime.fromisoformat(saved['ends_at'].replace('Z', '+00:00')) == at(1, 20, 30)
    assert errors == [], errors


def test_sharing_starts_unchecked_group_by_group_and_says_it_is_done(phone, events_origin):
    page, errors = phone
    state = agenda_services(page, welcome_seen=True)
    signed_in(page, events_origin, '/agenda/calendars?tab=share')
    pw.expect(page.get_by_text('Personne ne voit tes dispos.')).to_be_visible(timeout=15000)
    page.get_by_role('button', name='Partager mes dispos').click()
    pw.expect(page.get_by_role('heading', name='Partager mes dispos')).to_be_visible(timeout=15000)
    boxes = page.get_by_role('checkbox')
    pw.expect(boxes.first).to_be_visible()
    assert all(boxes.nth(i).get_attribute('aria-checked') == 'false' for i in range(boxes.count()))   # tout décoché
    pw.expect(page.get_by_text('Tout Party · jamais coché d’office')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Partager mes dispos')).to_be_disabled()
    shot(page, 'agenda-06-partager-decoche.png')
    page.get_by_test_id(f'share-group-{FOOT}').click()
    page.get_by_test_id('share-party').click()
    pw.expect(page.get_by_role('button', name='Partager avec 1 groupe')).to_be_enabled()
    shot(page, 'agenda-07-partager-un-groupe.png')
    page.get_by_role('button', name='Partager avec 1 groupe').click()
    pw.expect(page.get_by_test_id('share-done')).to_contain_text('Potes du foot voit tes heures occupées, jamais pourquoi', timeout=15000)
    assert rpc_calls(state, 'agenda_set_sharing')[-1] == {'groups': [FOOT], 'share_party': True, 'share_manual': False}
    pw.expect(page.get_by_role('button', name='Arrêter de partager')).to_be_visible()
    shot(page, 'agenda-08-partage-fait.png')
    assert errors == [], errors


def test_who_is_free_shows_the_best_evening_words_and_greyed_others_then_organises(phone, events_origin):
    page, errors = phone
    agenda_services(page, welcome_seen=True)
    signed_in(page, events_origin, f'/agenda/free?group={FOOT}')
    best = page.get_by_test_id(f"free-card-{at(2, 0).date().isoformat()}")
    pw.expect(best).to_contain_text('LE MIEUX', timeout=15000)
    pw.expect(best).to_contain_text('4 disponibles')
    pw.expect(page.get_by_test_id(f'free-person-{YANIS}')).to_contain_text('Disponible dès 18 h 30')
    others = page.get_by_test_id('free-others')
    pw.expect(others).to_contain_text('Sam')
    # Ceux qui ne partagent pas : grisés, aucun texte de refus.
    assert 'partag' not in others.inner_text().lower() and 'pas d' not in others.inner_text().lower()
    shot(page, 'agenda-09-qui-est-libre.png')
    # Un autre soir : Marc occupé jusqu'à 21 h, écrit et rayé.
    page.get_by_test_id(f"free-card-{at(3, 0).date().isoformat()}").click()
    pw.expect(page.get_by_test_id(f'free-person-{MARC}')).to_contain_text('Occupé')
    pw.expect(page.get_by_test_id(f'free-person-{MARC}')).to_contain_text('jusqu’à 21 h')
    shot(page, 'agenda-10-qui-est-libre-occupe.png')
    page.get_by_test_id(f"free-card-{at(2, 0).date().isoformat()}").click()
    page.get_by_role('button', name='Organiser le', exact=False).click()
    pw.expect(page.get_by_label('Titre', exact=False).first).to_have_value('Soirée Potes du foot', timeout=15000)
    assert f'group={FOOT}' in page.url and 'start=' in page.url
    shot(page, 'agenda-11-organiser.png')
    assert errors == [], errors


def test_vote_opens_a_date_poll_with_the_three_best_dates(phone, events_origin):
    page, errors = phone
    agenda_services(page, welcome_seen=True)
    signed_in(page, events_origin, f'/agenda/free?group={FOOT}')
    page.get_by_role('button', name='🗳️ Faire voter le groupe (3 dates)').click(timeout=15000)
    pw.expect(page.get_by_text('Créneau 3', exact=False).first).to_be_visible(timeout=15000)
    assert 'poll=' in page.url and f'group={FOOT}' in page.url
    assert errors == [], errors


def test_links_empty_state_model_explainer_settings_and_preview(phone, events_origin):
    page, errors = phone
    state = agenda_services(page, welcome_seen=True, pending=0)
    signed_in(page, events_origin, '/agenda/links')
    pw.expect(page.get_by_text('Aucun lien pour l’instant')).to_be_visible(timeout=15000)
    shot(page, 'agenda-12-liens-vide.png')
    page.get_by_test_id('empty-model-evening').click()
    pw.expect(page.get_by_test_id('link-intro')).to_contain_text('Toute personne qui a ce lien voit quand tu es libre', timeout=15000)
    shot(page, 'agenda-13-lien-explication.png')
    page.get_by_role('button', name='J’ai compris, continuer').click()
    pw.expect(page.get_by_label('Nom du lien (pour toi)')).to_have_value('Après le travail')
    pw.expect(page.get_by_role('radio', name='Après le travail, Lun → ven · 18 h – 23 h')).to_have_attribute('aria-checked', 'true')
    pw.expect(page.get_by_test_id('link-preview')).to_contain_text('Aujourd’hui n’est jamais montré')
    pw.expect(page.get_by_test_id('link-preview')).to_contain_text('20 h 30 – 23 h')
    # Demandes éteintes au départ ; allumées : durée et champs, le prénom toujours obligatoire.
    page.get_by_role('switch', name='Demandes de rendez-vous').click()
    pw.expect(page.get_by_role('radio', name='Prénom : Obligatoire')).to_have_attribute('aria-checked', 'true')
    page.get_by_role('radio', name='Téléphone : Facultatif').click()
    shot(page, 'agenda-14-lien-reglage.png')
    # Ce qui rend occupé (17.11) : tout coché au départ ; on retire « Juste pour moi ». Permanent par défaut.
    party_cal, personal_cal = page.get_by_test_id('link-cal-party'), page.get_by_test_id('link-cal-personal')
    pw.expect(party_cal).to_have_attribute('aria-checked', 'true', timeout=15000)
    pw.expect(personal_cal).to_have_attribute('aria-checked', 'true')
    personal_cal.click()
    pw.expect(personal_cal).to_have_attribute('aria-checked', 'false')
    pw.expect(page.get_by_role('tab', name='Permanent')).to_have_attribute('aria-selected', 'true')
    # Marges (17.11) : 30 min avant et après chaque rendez-vous.
    page.get_by_role('radiogroup', name='Marge avant chaque rendez-vous').get_by_role('button', name='30 min').click()
    page.get_by_role('radiogroup', name='Marge après chaque rendez-vous').get_by_role('button', name='30 min').click()
    pw.expect(page.get_by_text('Pas disponible 30 min avant et 30 min après chaque rendez-vous', exact=False)).to_be_visible()
    pw.expect(page.get_by_text('Il marche jusqu’à ce que tu l’arrêtes.')).to_be_visible()
    page.wait_for_timeout(1000)  # l'aperçu est relu 350 ms après chaque changement
    assert rpc_calls(state, 'agenda_link_preview')[-1]['link']['calendars'] == [PARTY_CAL]
    page.get_by_text('Ce qui te rend occupé').scroll_into_view_if_needed()
    shot(page, 'agenda-14b-lien-calendriers.png')
    # Adresse lisible (17.11) : lisible au départ ; le nom vient du surnom, le nom du lien du nom choisi (sans accent).
    pw.expect(page.get_by_role('tab', name='Lisible')).to_have_attribute('aria-selected', 'true')
    page.get_by_label('Ton nom d’adresse').fill('Ludovic')
    pw.expect(page.get_by_label('Ton nom d’adresse')).to_have_value('ludovic')
    page.get_by_label('Nom du lien dans l’adresse').fill('Général Soir')
    pw.expect(page.get_by_test_id('link-nice-address')).to_contain_text('/agenda/ludovic/general-soir')
    page.get_by_test_id('link-nice-address').scroll_into_view_if_needed()
    shot(page, 'agenda-14c-lien-adresse.png')
    page.get_by_role('button', name='Créer le lien').click()
    pw.expect(page.get_by_test_id('link-address')).to_contain_text('/agenda/ludovic/general-soir', timeout=15000)
    assert rpc_calls(state, 'agenda_handle_set')[-1] == {'handle': 'ludovic'}
    assert rpc_calls(state, 'agenda_link_set_slug')[-1]['slug'] == 'general-soir'
    saved = rpc_calls(state, 'agenda_link_save')[-1]['link']
    assert saved['calendars'] == [PARTY_CAL] and saved['permanent'] is True and saved['buffer_before_min'] == 30 and saved['buffer_after_min'] == 30
    assert saved['rules'] == [{'days': [1, 2, 3, 4, 5], 'from': '18:00', 'to': '23:00'}]
    assert saved['booking_enabled'] is True and saved['booking_fields']['phone'] == 'optional' and saved['booking_fields']['first_name'] == 'required'
    shot(page, 'agenda-15-lien-cree.png')
    assert errors == [], errors


IPHONE_AGENDA = """
window.__synced = 0;
window.PartyNative = { agenda: {
  status: async () => ({ access: 'full' }), requestAccess: async () => ({ access: 'full' }),
  calendars: async () => [
    { id: 'CAL-TRAVAIL', title: 'Travail', color: '#2E86FF', source: 'iCloud', shown: true, countsBusy: false },
    { id: 'CAL-PERSO', title: 'Perso', color: '#34C759', source: 'Google', shown: true, countsBusy: true },
    { id: 'CAL-ANNIV', title: 'Anniversaires', color: '#888888', source: 'Anniversaires', shown: true, countsBusy: false, excluded: 'birthdays' },
  ],
  setCalendar: async () => ({ ok: true }), events: async () => [],
  syncBusy: async () => { window.__synced += 1; return { sent: 2, updatedAt: new Date().toISOString() }; },
  addToPhone: async () => ({ saved: false }),
} };
"""


def test_in_the_iphone_app_a_link_picks_iphone_calendars_and_sends_them_at_once(phone, events_origin):
    """App iPhone : les calendriers de l'iPhone (jamais les anniversaires) se cochent par lien ; enregistrer renvoie
    aussitôt les plages « pris » (pont syncBusy). Lien en 90 jours : « Prolonger » reste possible."""
    page, errors = phone
    page.add_init_script(IPHONE_AGENDA)
    state = agenda_services(page, welcome_seen=True, pending=0)
    signed_in(page, events_origin, '/agenda/links')
    page.get_by_test_id('empty-model-week').click()
    page.get_by_role('button', name='J’ai compris, continuer').click()
    work = page.get_by_role('checkbox', name='Travail, iPhone · iCloud')
    pw.expect(work).to_have_attribute('aria-checked', 'true', timeout=15000)
    pw.expect(page.get_by_role('checkbox', name='Perso, iPhone · Google')).to_have_attribute('aria-checked', 'true')
    assert page.get_by_text('Anniversaires').count() == 0
    page.get_by_role('checkbox', name='Perso, iPhone · Google').click()
    page.get_by_role('tab', name='90 jours').click()
    page.get_by_text('Ce qui te rend occupé').scroll_into_view_if_needed()
    shot(page, 'agenda-16-lien-calendriers-iphone.png')
    page.get_by_role('button', name='Créer le lien').click()
    pw.expect(page.get_by_test_id('link-address')).to_be_visible(timeout=15000)
    saved = rpc_calls(state, 'agenda_link_save')[-1]['link']
    assert sorted(saved['calendars']) == sorted([PARTY_CAL, PERSONAL_CAL, 'ios:CAL-TRAVAIL']) and saved['permanent'] is False
    assert page.evaluate('window.__synced') == 1
    assert errors == [], errors


def test_a_request_is_accepted_or_reported_from_party(phone, events_origin):
    page, errors = phone
    link = {'id': LINK, 'token': 'k7Qm2xV9abcdefghijklmnop', 'path': '/d/k7Qm2xV9abcdefghijklmnop', 'name': 'Rendez-vous pro', 'emoji': '💼',
            'display_name': 'Camille', 'rules': [{'days': [1, 2, 3, 4, 5], 'from': '09:00', 'to': '18:00'}], 'horizon_days': 28,
            'duration_min': 60, 'booking_enabled': True, 'booking_fields': None, 'message_label': None, 'status': 'active',
            'expires_at': iso(at(80, 0)), 'stopped_at': None, 'views': 12, 'last_viewed_at': iso(at(0, 8)), 'pending': 1, 'created_at': iso(at(-3, 9))}
    state = agenda_services(page, welcome_seen=True, links=[link])
    signed_in(page, events_origin, '/agenda/links')
    pw.expect(page.get_by_test_id(f'link-requests-{LINK}')).to_contain_text('1 demande de rendez-vous', timeout=15000)
    pw.expect(page.get_by_text('Vu 12 fois', exact=False)).to_be_visible()
    shot(page, 'agenda-16-mes-liens.png')
    page.get_by_test_id(f'link-requests-{LINK}').click()
    card = page.get_by_test_id(f'request-{BOOKING}')
    pw.expect(card).to_contain_text('« Marc Rochat » · nom écrit par la personne', timeout=15000)
    card.get_by_role('link').click()
    detail = page.get_by_test_id('request-detail')
    pw.expect(detail).to_contain_text('non vérifié')
    pw.expect(detail).to_contain_text('Écrit par la personne, pas par Party.')
    pw.expect(detail.get_by_role('button', name='⊘ Bloquer l’expéditeur')).to_be_visible()
    shot(page, 'agenda-17-demande-recue.png')
    detail.get_by_role('button', name='Signaler la demande de Marc').click()
    page.get_by_role('radio', name='Spam').click()
    page.get_by_role('button', name='Envoyer').click()
    pw.expect(page.get_by_text('Merci, c’est envoyé')).to_be_visible()
    assert rpc_calls(state, 'agenda_booking_report')[-1] == {'id': BOOKING, 'reason': 'spam', 'comment': None}
    page.get_by_role('button', name='Fermer', exact=True).click()
    state['bookings'][0]['status'] = 'pending'
    page.goto(f'{events_origin}/events/agenda/requests/{BOOKING}', wait_until='domcontentloaded')
    page.get_by_role('button', name='Accepter la demande de Marc').click(timeout=15000)
    pw.expect(page.get_by_test_id('request-detail').get_by_text('✓ Accepté · dans ton agenda')).to_be_visible(timeout=15000)
    assert rpc_calls(state, 'agenda_booking_decide')[-1] == {'id': BOOKING, 'accept': True}
    assert errors == [], errors


@pytest.mark.parametrize('width', [320, 375])
def test_narrow_phones_keep_the_headers_on_screen(browser, events_origin, width):
    """Petit téléphone : « Événements » + « 📅 Agenda » et l'en-tête de l'agenda tiennent, sans défilement de côté."""
    context = browser.new_context(viewport={'width': width, 'height': 740}, device_scale_factor=2)
    page = context.new_page()
    try:
        agenda_services(page, welcome_seen=True)
        signed_in(page, events_origin)
        pw.expect(page.get_by_test_id('home-agenda')).to_be_visible(timeout=15000)
        title = page.get_by_role('heading', name='Événements')
        assert title.bounding_box()['height'] < 50                     # sur une ligne (jamais « Événement / s »)
        shot(page, f'agenda-18-evenements-{width}.png')
        page.get_by_test_id('home-agenda').click()
        pw.expect(page.get_by_test_id('agenda-week')).to_be_visible(timeout=15000)
        add = page.get_by_role('button', name='Nouveau rendez-vous').bounding_box()
        cal = page.get_by_test_id('agenda-calendars').bounding_box()
        assert add['x'] + add['width'] <= width and abs(add['y'] - cal['y']) < 4   # même ligne, dans l'écran
        assert page.evaluate('document.scrollingElement.scrollWidth') <= width
        shot(page, f'agenda-19-semaine-{width}.png')
    finally:
        context.close()
