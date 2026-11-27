"""Présences à la main (demande de l'admin du 26.11, migration 20261126150000), base simulée : l'organisation ajoute un
membre (prévenu) et « Pote Théo du bar » (sans compte), passe à Peut-être / Absent, retire ; les compteurs suivent ; un
invité ne voit que les nombres (« +1 sans compte »), jamais le nom. Base d'avant (table absente) : l'ancien éditeur.
Captures : PRESENCES_SHOTS=<dossier>."""
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw, pytestmark  # noqa: F401

LEA = '5b0c7e1e-1d3a-4c8e-9a51-6f2f4b9d0a11'
OTHER = '7c1d2e3f-4a5b-4c6d-8e7f-901234567890'
SHOTS = os.environ.get('PRESENCES_SHOTS')
HEADERS = {'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*'}


def shot(page, name, anchor=None):
    if SHOTS:
        if anchor is not None:
            anchor.scroll_into_view_if_needed()
            page.wait_for_timeout(600)  # fin des apparitions en douceur
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f'{name}.png'), full_page=False)


def fake_manual_base(page, calls, rsvps, guests, missing=False, perms=None):
    """event_manual_guests + event_attendance (qui compte les sans compte), par-dessus mock_services."""
    def handle(route):
        req = route.request
        path = urlparse(req.url).path
        if req.method == 'OPTIONS':
            return route.fulfill(status=204, headers=HEADERS)
        if path.endswith('/rest/v1/event_manual_guests'):
            calls.append((req.method, path, req.post_data, req.url))
            if missing:
                return route.fulfill(status=404, content_type='application/json', headers=HEADERS,
                                     body=json.dumps({'code': 'PGRST205', 'message': "Could not find the table 'public.event_manual_guests'"}))
            q = parse_qs(urlparse(req.url).query)
            target = (q.get('id') or [''])[0].removeprefix('eq.')
            if req.method == 'GET':
                body = guests
            elif req.method == 'POST':
                row = json.loads(req.post_data)
                g = {'id': f'0000000{len(guests) + 1}-0000-4000-8000-000000000000', 'name': row['name'].strip(),
                     'status': row['status'], 'created_at': '2026-11-26T20:00:00Z'}
                guests.append(g)
                body = g
            elif req.method == 'PATCH':
                for g in guests:
                    if g['id'] == target:
                        g.update(json.loads(req.post_data))
                body = []
            else:
                guests[:] = [g for g in guests if g['id'] != target]
                body = []
            return route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=HEADERS)
        if path.endswith('/rpc/event_attendance'):
            yes = [r for r in rsvps if r['status'] == 'yes' and not r.get('waitlisted')]
            body = [{'event_id': EVENT, 'going': sum(1 + r.get('plus_ones', 0) for r in yes) + sum(g['status'] == 'yes' for g in guests),
                     'maybe': sum(r['status'] == 'maybe' for r in rsvps) + sum(g['status'] == 'maybe' for g in guests),
                     'waitlist': 0, 'faces': []}]
            return route.fulfill(status=200, content_type='application/json', body=json.dumps(body), headers=HEADERS)
        if path.endswith('/rpc/set_rsvp_for'):  # mock_services remplace sa liste : on suit ici pour les totaux
            args = json.loads(req.post_data)
            rsvps[:] = [r for r in rsvps if r['user_id'] != args['member']] + (
                [] if args['answer'] is None else [{'user_id': args['member'], 'status': args['answer'], 'plus_ones': 0, 'waitlisted': False}])
        if perms is not None and path.endswith('/rpc/my_permissions'):
            return route.fulfill(status=200, content_type='application/json', body=json.dumps(perms), headers=HEADERS)
        route.fallback()
    page.route('https://gsuetixzobooggeaubvb.supabase.co/**', handle)


def invite_lea(page):
    """Léa est invitée (event_invites) : c'est ainsi qu'elle figure dans « Ajouter quelqu'un » (noms lus après la fiche, 27.11)."""
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/event_invites*', lambda r: r.fulfill(
        status=204 if r.request.method == 'OPTIONS' else 200, content_type='application/json',
        headers={'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': 'GET, OPTIONS'},
        body=json.dumps([{'user_id': LEA, 'via_link': False}])))


def open_event(page, events_origin):
    invite_lea(page)
    page.goto(events_origin, wait_until='domcontentloaded')
    page.get_by_role('button', name='Événements', exact=True).click()
    frame = page.frame_locator('#eventsFrame')
    login(frame)
    frame.get_by_text('Sortie de démonstration (test local)', exact=True).click()
    return frame


def counter(frame, label, n):
    pw.expect(frame.get_by_label(f'{label} : {n}', exact=True)).to_be_visible(timeout=10000)


def test_the_organizer_adds_a_member_and_someone_without_account_and_counts_follow(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    rsvps: list = []
    guests: list = []
    calls = mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}], rsvps=rsvps)
    fake_manual_base(page, calls, rsvps, guests)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        frame = open_event(page, events_origin)
        pw.expect(frame.get_by_text('Une personne sans compte n’est pas prévenue et ne voit rien. Les invités voient seulement les nombres.', exact=True)).to_be_visible(timeout=15000)
        counter(frame, 'Présents', 0)
        field = frame.get_by_label('Ajouter quelqu’un', exact=True)

        # Un membre : suggestion « A un compte », noté présent par set_rsvp_for.
        field.fill('lé')
        pw.expect(frame.get_by_text('A un compte · sera prévenu', exact=True)).to_be_visible()
        pw.expect(frame.get_by_role('button', name='Ajouter « lé » sans compte, Présent', exact=True)).to_be_visible()
        frame.get_by_role('button', name='Noter présent', exact=True).click()
        counter(frame, 'Présents', 1)

        # Sans compte : la ligne « Ajouter « … » », toujours là ; Entrée l'ajoute en Présent.
        field.fill('Pote Théo du bar')
        shot(page, '1-organisateur-suggestions', frame.get_by_role('button', name='Ajouter « Pote Théo du bar » sans compte, Présent', exact=True))
        field.press('Enter')
        pw.expect(frame.get_by_text('Sans compte', exact=True)).to_be_visible(timeout=10000)
        counter(frame, 'Présents', 2)
        assert guests == [{'id': guests[0]['id'], 'name': 'Pote Théo du bar', 'status': 'yes', 'created_at': guests[0]['created_at']}]
        assert field.input_value() == ''
        pw.expect(frame.get_by_text('+1 sans compte', exact=True)).to_be_visible()
        shot(page, '2-organisateur-carte', frame.get_by_text('Une personne sans compte n’est pas prévenue et ne voit rien. Les invités voient seulement les nombres.', exact=True))

        # Peut-être, puis Absent : compteurs à jour.
        frame.get_by_role('button', name='Pote Théo du bar : Peut-être', exact=True).click()
        counter(frame, 'Peut-être', 1)
        counter(frame, 'Présents', 1)
        frame.get_by_role('button', name='Pote Théo du bar : Absent', exact=True).click()
        counter(frame, 'Absents', 1)
        assert guests[0]['status'] == 'no'

        # ✕ : la question d'abord, puis retiré.
        frame.get_by_role('button', name='Retirer Pote Théo du bar', exact=True).click()
        frame.get_by_role('button', name='Retirer', exact=True).click()
        counter(frame, 'Absents', 0)
        assert guests == []
        sent = [json.loads(b) for _, p, b, *_ in calls if p.endswith('/rpc/set_rsvp_for')]
        assert sent == [{'event': EVENT, 'member': LEA, 'answer': 'yes'}]
        assert not errors
    finally:
        context.close()


def test_a_guest_sees_only_the_numbers(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    rsvps = [{'event_id': EVENT, 'user_id': LEA, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False,
              'updated_at': '2026-11-26T19:00:00Z'}]
    guests = [{'id': '00000001-0000-4000-8000-000000000000', 'name': 'Pote Théo du bar', 'status': 'yes', 'created_at': 'x'},
              {'id': '00000002-0000-4000-8000-000000000000', 'name': 'Cousin Max', 'status': 'maybe', 'created_at': 'x'}]
    calls = mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}], rsvps=rsvps,
                          event_extra={'created_by': OTHER, 'max_participants': 10})
    # Simple invité : ni organisation ni droit « tous les événements » ; la base ne lui rend jamais la table.
    fake_manual_base(page, calls, rsvps, guests, perms=['events.view', 'events.rsvp'])
    try:
        frame = open_event(page, events_origin)
        pw.expect(frame.get_by_text('PRÉSENTS · 2', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text('+1 sans compte', exact=True)).to_have_count(2)  # Présents et Peut-être
        pw.expect(frame.get_by_text('PEUT-ÊTRE · 1', exact=True)).to_be_visible()
        pw.expect(frame.get_by_role('progressbar', name='2 sur 10 places prises')).to_be_visible()
        pw.expect(frame.get_by_label('Ajouter quelqu’un', exact=True)).to_have_count(0)
        pw.expect(frame.get_by_text('Pote Théo du bar')).to_have_count(0)
        pw.expect(frame.get_by_text('Cousin Max')).to_have_count(0)
        assert not any(p.endswith('/event_manual_guests') for _, p, *_ in calls)
        shot(page, '3-invite-nombres', frame.get_by_text('PEUT-ÊTRE · 1', exact=True))
    finally:
        context.close()


def test_an_older_base_keeps_the_member_editor_without_error(browser, events_origin):
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    rsvps: list = []
    calls = mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}], rsvps=rsvps)
    fake_manual_base(page, calls, rsvps, [], missing=True)
    try:
        frame = open_event(page, events_origin)
        field = frame.get_by_label('Ajouter quelqu’un', exact=True)
        pw.expect(field).to_be_visible(timeout=15000)
        field.fill('lea')
        pw.expect(frame.get_by_role('button', name='Noter présent', exact=True)).to_be_visible()
        pw.expect(frame.get_by_role('button', name='Ajouter « lea » sans compte, Présent', exact=True)).to_have_count(0)
        pw.expect(frame.get_by_text('Une personne sans compte n’est pas prévenue et ne voit rien. Les invités voient seulement les nombres.', exact=True)).to_have_count(0)
        pw.expect(frame.get_by_text('La connexion a échoué. Réessaie.')).to_have_count(0)
    finally:
        context.close()


def test_two_groups_and_the_field_searches_both(browser, events_origin):
    """Demande de l'admin (26.11) : « Avec un compte » puis « Sans compte », chacun avec son nombre ; le champ cherche
    dans les deux groupes ; les compteurs du haut restent le total."""
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    rsvps = [{'event_id': EVENT, 'user_id': LEA, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False,
              'updated_at': '2026-11-26T19:00:00Z'}]
    guests = [{'id': '00000001-0000-4000-8000-000000000000', 'name': 'Pote Théo du bar', 'status': 'yes', 'created_at': 'x'},
              {'id': '00000002-0000-4000-8000-000000000000', 'name': 'Cousin Max', 'status': 'no', 'created_at': 'y'}]
    calls = mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}], rsvps=rsvps)
    fake_manual_base(page, calls, rsvps, guests)
    try:
        frame = open_event(page, events_origin)
        pw.expect(frame.get_by_text('AVEC UN COMPTE · 1', exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text('SANS COMPTE · 2', exact=True)).to_be_visible()
        member_box = frame.get_by_test_id('presences-member').bounding_box()
        manual_box = frame.get_by_test_id('presences-manual').bounding_box()
        assert member_box['y'] < manual_box['y']  # avec un compte d'abord
        counter(frame, 'Présents', 2)
        counter(frame, 'Absents', 1)
        shot(page, '5-organisateur-deux-groupes', frame.get_by_test_id('presences-manual'))
        frame.get_by_label('Ajouter quelqu’un', exact=True).fill('MAX')
        pw.expect(frame.get_by_text('SANS COMPTE · 1 sur 2', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('AVEC UN COMPTE · 0 sur 1', exact=True)).to_be_visible()
        pw.expect(frame.get_by_role('button', name='Cousin Max : Absent', exact=True)).to_be_visible()
        pw.expect(frame.get_by_role('button', name='Pote Théo du bar : Présent', exact=True)).to_have_count(0)
        counter(frame, 'Présents', 2)  # le filtre ne change pas les totaux
        frame.get_by_label('Ajouter quelqu’un', exact=True).fill('lea')
        pw.expect(frame.get_by_role('button', name='Léa : Présent', exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('SANS COMPTE · 0 sur 2', exact=True)).to_be_visible()
    finally:
        context.close()


def test_a_likely_duplicate_is_flagged_and_removed_in_two_touches(browser, events_origin):
    """Théo, noté sans compte, a ensuite créé son compte et répondu : la ligne sans compte le signale et se retire."""
    theo = '9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a'
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    rsvps = [{'event_id': EVENT, 'user_id': theo, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False,
              'updated_at': '2026-11-26T19:00:00Z'}]
    guests = [{'id': '00000001-0000-4000-8000-000000000000', 'name': 'Pote Théo du bar', 'status': 'yes', 'created_at': 'x'},
              {'id': '00000002-0000-4000-8000-000000000000', 'name': 'Cousin Max', 'status': 'yes', 'created_at': 'y'}]
    calls = mock_services(page, people=[{'id': theo, 'display_name': 'theo Martin'}], rsvps=rsvps)
    fake_manual_base(page, calls, rsvps, guests)
    try:
        frame = open_event(page, events_origin)
        hint = frame.get_by_text('Peut-être la même personne que theo Martin ?', exact=True)
        pw.expect(hint).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_test_id('presences-twin')).to_have_count(1)  # Cousin Max : rien
        counter(frame, 'Présents', 3)
        shot(page, '4-organisateur-doublon', hint)
        frame.get_by_role('button', name='Retirer cette ligne', exact=True).click()
        frame.get_by_role('button', name='Retirer', exact=True).click()
        counter(frame, 'Présents', 2)
        pw.expect(hint).to_have_count(0)
        assert [g['name'] for g in guests] == ['Cousin Max']
    finally:
        context.close()


def test_every_remove_asks_first_cancel_keeps_and_remove_removes(browser, events_origin):
    """Retour de l'admin du 27.11 (prod) : le ✕ d'une présence partait au premier toucher, « sans faire exprès ». Membre
    ET sans compte : « Retirer <nom> des présences ? » (Retirer / Annuler) ; Annuler (ou le fond) ne retire rien."""
    context = browser.new_context(viewport={'width': 390, 'height': 844})
    page = context.new_page()
    rsvps = [{'event_id': EVENT, 'user_id': LEA, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False,
              'updated_at': '2026-11-26T19:00:00Z'}]
    guests = [{'id': '00000001-0000-4000-8000-000000000000', 'name': 'Pote Théo du bar', 'status': 'yes', 'created_at': 'x'}]
    calls = mock_services(page, people=[{'id': LEA, 'display_name': 'Léa'}], rsvps=rsvps)
    fake_manual_base(page, calls, rsvps, guests)
    rpc = lambda: [json.loads(b) for _, p, b, *_ in calls if p.endswith('/rpc/set_rsvp_for')]  # noqa: E731
    deletes = lambda: [c for c in calls if c[0] == 'DELETE' and c[1].endswith('/event_manual_guests')]  # noqa: E731
    try:
        frame = open_event(page, events_origin)
        counter(frame, 'Présents', 2)
        for name in ('Léa', 'Pote Théo du bar'):
            frame.get_by_role('button', name=f'Retirer {name}', exact=True).click()
            question = frame.get_by_text(f'Retirer {name} des présences ?', exact=True)
            pw.expect(question).to_be_visible(timeout=5000)
            if name == 'Léa':
                # Dans le cadre de Party (comme l'app) : la question et ses boutons sont DANS l'écran, au-dessus des onglets.
                page.wait_for_timeout(800)
                tabs_top = page.locator('#tabs').bounding_box()['y']
                for target in (question, frame.get_by_role('button', name='Retirer', exact=True),
                               frame.get_by_role('button', name='Annuler', exact=True)):
                    box = target.bounding_box()
                    assert box and box['y'] >= 0 and box['y'] + box['height'] <= tabs_top, (box, tabs_top)
                if SHOTS:
                    Path(SHOTS).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(SHOTS) / '6-question-retirer.png'))
            page.wait_for_timeout(500)
            assert rpc() == [] and deletes() == []  # rien au premier toucher
            frame.get_by_role('button', name='Annuler', exact=True).click()
            pw.expect(question).to_have_count(0)
            counter(frame, 'Présents', 2)
            assert rpc() == [] and deletes() == []

        # Membre : Retirer → set_rsvp_for(null), la ligne part, les compteurs suivent.
        frame.get_by_role('button', name='Retirer Léa', exact=True).click()
        frame.get_by_role('button', name='Retirer', exact=True).click()
        counter(frame, 'Présents', 1)
        pw.expect(frame.get_by_role('button', name='Retirer Léa', exact=True)).to_have_count(0)
        assert rpc() == [{'event': EVENT, 'member': LEA, 'answer': None}]

        # Sans compte : Retirer → la ligne est effacée.
        frame.get_by_role('button', name='Retirer Pote Théo du bar', exact=True).click()
        frame.get_by_role('button', name='Retirer', exact=True).click()
        counter(frame, 'Présents', 0)
        assert guests == [] and len(deletes()) == 1
    finally:
        context.close()
