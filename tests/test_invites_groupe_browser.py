"""« Réunir les invités dans un groupe » (17.11), module web dans un vrai navigateur (Supabase simulé) :
- la carte d'invitation montre la case « Rejoindre aussi le groupe » DÉCOCHÉE, grande, sous les réponses, avec le nombre de
  membres et ce que voient les membres ; cochée, elle part AVEC la réponse (même « Je ne peux pas »), après la connexion ;
- décochée : la réponse part avec join_group false ; sans groupe : la réponse habituelle (accept_invite), sans paramètre ;
- l'organisateur voit « 2 dans « … » », le badge 👥 par personne, et « Régler » enregistre un groupe qu'il gère."""
import json
import os
from pathlib import Path

import pytest

from tests.test_events_browser import DIST, EVENT, browser, login, mock_services, pw  # noqa: F401
from tests.test_invitations_v2_browser import (  # noqa: F401
    ACCEPTED, CARD, CORS, GUEST_LIST, IDS, TOKEN, guest, mock_invites, open_event, v2_origin)

pytestmark = pytest.mark.skipif(not (DIST / 'index.html').exists(), reason='Construire web/events avant les tests navigateur')
RPC = 'https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/'
SHOTS = Path(os.environ['GUEST_GROUP_SHOTS']) if os.environ.get('GUEST_GROUP_SHOTS') else None
GROUP = {'id': IDS[9], 'name': 'Raclette chez Ludo', 'emoji': '🎉', 'members': 5, 'owner': 'Ludo'}
TITLE = 'Rejoindre aussi le groupe « 🎉 Raclette chez Ludo » de Ludo'


def reply(page, name: str, body, calls: list):
    def handle(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        calls.append((name, json.loads(route.request.post_data or '{}')))
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))
    page.route(RPC + name, handle)


def shot(page, name: str, full: bool = False):
    if SHOTS:
        page.wait_for_timeout(900)
        SHOTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOTS / f'{name}.png'), full_page=full)


def new_page(browser):  # noqa: F811
    context = browser.new_context(viewport={'width': 390, 'height': 844}, color_scheme='dark', device_scale_factor=2)
    return context, context.new_page()


@pytest.mark.parametrize('tick', [True, False])
def test_the_box_is_unticked_and_its_state_leaves_with_the_answer(browser, v2_origin, tick):  # noqa: F811
    context, page = new_page(browser)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        mock_invites(page, card={**CARD, 'inviter': 'Ludo', 'guest_group': GROUP})
        calls = []
        status = 'joined' if tick else 'declined'
        reply(page, 'accept_invite_group', {**ACCEPTED, 'status': 'no', 'guest_group': {'status': status, 'group': GROUP}}, calls)
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        box = page.get_by_role('checkbox', name=TITLE)
        pw.expect(box).to_be_visible(timeout=15000)
        pw.expect(box).to_have_attribute('aria-checked', 'false')  # décochée par défaut (avis de conformité du 17.11)
        pw.expect(page.get_by_text('👥 5 membres', exact=True)).to_be_visible()
        pw.expect(page.get_by_text('Ton numéro reste caché. Tu quittes le groupe quand tu veux.', exact=False)).to_be_visible()
        # Juste sous les boutons de réponse.
        assert box.bounding_box()['y'] > page.get_by_role('button', name='Je ne peux pas').bounding_box()['y']
        if tick:
            shot(page, '01-carte-case-decochee', full=True)
            box.click()
            pw.expect(box).to_have_attribute('aria-checked', 'true')
            shot(page, '02-carte-case-cochee', full=True)
        page.get_by_role('button', name='Je ne peux pas').click()
        login(page)
        pw.expect(page.get_by_text('C’est noté', exact=False)).to_be_visible(timeout=15000)
        assert calls == [('accept_invite_group', {'token': TOKEN, 'answer': 'no', 'join_group': tick})]
        joined = page.get_by_text('👥 Tu es dans le groupe « 🎉 Raclette chez Ludo ». Tu peux le quitter quand tu veux.', exact=True)
        pw.expect(joined).to_have_count(1 if tick else 0)
        if tick:
            shot(page, '03-reponse-pas-present-dans-le-groupe', full=True)
        assert not errors, errors
    finally:
        context.close()


def test_without_a_group_the_usual_answer_is_sent(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        calls = mock_invites(page, card={**CARD, 'inviter': 'Ludo'})
        page.goto(f'{v2_origin}/events/invite/{TOKEN}', wait_until='domcontentloaded')
        pw.expect(page.get_by_role('button', name='Je viens !')).to_be_visible(timeout=15000)
        pw.expect(page.get_by_role('checkbox')).to_have_count(0)
        page.get_by_role('button', name='Je viens !').click()
        login(page)
        pw.expect(page.get_by_text('C’est noté', exact=False)).to_be_visible(timeout=15000)
        sent = [c for c in calls if c[0].startswith('accept_invite')]
        assert sent == [('accept_invite', {'token': TOKEN, 'answer': 'yes', 'first_name': None})]
    finally:
        context.close()


def test_the_organizer_sees_who_is_in_the_group_and_sets_it(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page)
        people = [{**p, 'in_group': p['name'] in ('Marco Costa', 'Mariana')} for p in GUEST_LIST['people']]
        mock_invites(page, guest_list={**GUEST_LIST, 'people': people, 'guest_group': GROUP})
        managed = [{'id': GROUP['id'], 'name': GROUP['name'], 'emoji': '🎉', 'members': 5},
                   {'id': IDS[8], 'name': 'Les footeux', 'emoji': None, 'members': 8}]
        state = {'group': GROUP, 'in_group': True, 'offer': False, 'answered': False, 'choice': None, 'manage': True,
                 'groups': managed, 'band': None}
        calls = []
        reply(page, 'event_guest_group', state, calls)
        reply(page, 'set_event_guest_group', {**state, 'group': {**managed[1], 'owner': 'Ludo'}}, calls)
        card = open_event(page, v2_origin, expand=False)
        line = card.get_by_role('button', name='Régler le groupe 🎉 Raclette chez Ludo')
        pw.expect(line).to_be_visible()
        pw.expect(card.get_by_text('2 dans « 🎉 Raclette chez Ludo »', exact=True)).to_be_visible()
        card.get_by_role('button', name='Voir le détail des invités').click()
        # Marco (« En plus ») porte le badge ; Mariana est dans le bloc Vendredi Party, replié.
        pw.expect(card.get_by_label('Dans le groupe')).to_have_count(1)
        shot(page, '10-organisateur-carte-invites', full=True)
        line.click()
        pw.expect(card.get_by_role('radio', name='Les footeux')).to_be_visible()
        card.get_by_role('radio', name='Les footeux').click()
        shot(page, '11-organisateur-regler', full=True)
        card.get_by_role('button', name='Enregistrer').click()
        pw.expect(card.get_by_role('button', name='Enregistrer')).to_have_count(0, timeout=5000)
        assert ('set_event_guest_group', {'e': calls[0][1]['e'], 'grp': IDS[8], 'new_name': None}) in calls
        assert not errors, errors
    finally:
        context.close()


def test_keep_the_band_sends_invitations_once(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    try:
        mock_services(page)
        mock_invites(page)
        state = {'group': None, 'in_group': False, 'offer': False, 'answered': False, 'choice': None, 'manage': True,
                 'groups': [], 'band': {'present': 5, 'all': 9, 'names': ['Léa', 'Marco', 'Sarah', 'Tom', 'Zoé']}}
        calls = []
        reply(page, 'event_guest_group', state, calls)
        reply(page, 'keep_band', {'invited': 5, 'group_id': IDS[7]}, calls)
        card = open_event(page, v2_origin, expand=False)
        pw.expect(card.get_by_text('🎉 Garder cette bande ?', exact=True)).to_be_visible(timeout=15000)
        pw.expect(card.get_by_role('radio', name='Les 5 présents')).to_have_attribute('aria-checked', 'true')
        card.get_by_text('🎉 Garder cette bande ?', exact=True).scroll_into_view_if_needed()
        shot(page, '20-garder-cette-bande')
        card.get_by_role('button', name='Créer « Sortie de démonstration (test local) » et inviter').click()
        pw.expect(card.get_by_text('5 invitations envoyées : chacun entre s’il accepte.', exact=True)).to_be_visible(timeout=5000)
        assert ('keep_band', {'e': calls[0][1]['e'], 'who': 'present', 'grp': None,
                              'new_name': 'Sortie de démonstration (test local)'}) in calls
    finally:
        context.close()


def test_on_the_event_page_the_box_is_unticked_and_follows_the_first_answer(browser, v2_origin):  # noqa: F811
    context, page = new_page(browser)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        mock_services(page, event_extra={'created_by': IDS[1], 'guest_group': GROUP['id'], 'visibility': 'invited'})
        mock_invites(page)
        state = {'group': GROUP, 'in_group': False, 'offer': True, 'answered': False, 'choice': None, 'manage': False,
                 'groups': None, 'band': None}
        calls = []
        reply(page, 'event_guest_group', state, calls)
        reply(page, 'set_guest_group_choice', {'status': 'joined', 'group': GROUP}, calls)
        page.goto(f'{v2_origin}/events/', wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Sortie de démonstration (test local)', exact=True)).to_be_visible(timeout=15000)
        page.goto(f'{v2_origin}/events/event/{EVENT}', wait_until='domcontentloaded')
        box = page.get_by_role('checkbox', name=TITLE)
        pw.expect(box).to_be_visible(timeout=15000)
        pw.expect(box).to_have_attribute('aria-checked', 'false')
        box.scroll_into_view_if_needed()
        box.click()
        shot(page, '05-fiche-case-cochee')
        page.get_by_role('button', name='Absent', exact=True).click()
        pw.expect(page.get_by_role('checkbox', name=TITLE)).to_have_count(0, timeout=10000)
        assert ('set_guest_group_choice', {'e': EVENT, 'join_group': True}) in calls
        assert not errors, errors
    finally:
        context.close()
