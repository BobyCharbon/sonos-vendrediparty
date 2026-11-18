"""Vitesse des Discussions (demande de l'admin du 18.11 : « fluide, rapide, les gens ne doivent pas galérer »), dans un vrai
navigateur (module Événements, Supabase simulé) :
- la bulle s'affiche aussitôt (« Envoi… »), le champ se vide et l'on peut écrire le message suivant sans attendre ;
- réseau coupé : nouveaux essais tout seuls, puis « Pas envoyé · Toucher pour réessayer » ; le message reste (jamais
  perdu), le champ n'est pas réécrit ; un toucher le renvoie avec le MÊME identifiant ;
- réponse perdue en route (la base l'a déjà) : l'essai suivant compte comme envoyé (code 23505) ;
- la conversation s'ouvre en bas du fil (60 messages : le dernier est à l'écran).
Le message reçu en direct (ligne du temps réel montrée aussitôt) est vérifié par la recette réelle
(tests/supabase_live/test_discussions_vitesse_browser_live.py)."""
import json
from datetime import timedelta
from urllib.parse import urlparse

from tests.test_chats_browser import CORS, LEA, SUPABASE, phone  # noqa: F401 (fixtures)
from tests.test_chats_conversation_browser import DM, conversation_services, dm, iso, open_dm
from tests.test_events_browser import USER, browser, events_origin, pw  # noqa: F401 (fixtures)


def long_conversation():
    """60 messages : la fin du fil n'est visible que si la conversation s'ouvre en bas."""
    return [dm(0, LEA if i % 2 else USER, f'Message numéro {i}', iso(timedelta(minutes=i - 120)))
            | {'id': f'd0000000-0000-4000-8000-{i:012d}'} for i in range(60)]


def network(page, state):
    """Coupe (ou rend) le réseau pour l'envoi des messages directs : la requête échoue comme sans connexion."""
    state.update(offline=False, duplicate=False, attempts=[])

    def handle(route):
        request = route.request
        if not (urlparse(request.url).path.endswith('/direct_messages') and request.method == 'POST'):
            return route.fallback()
        body = json.loads(request.post_data)
        state['attempts'].append(body['id'])
        if state['offline']:
            return route.abort('internetdisconnected')
        if state['duplicate']:
            return route.fulfill(status=409, content_type='application/json', headers=CORS,
                                 body=json.dumps({'code': '23505', 'message': 'duplicate key value violates unique constraint'}))
        return route.fallback()

    page.route(SUPABASE, handle)


def test_a_message_sent_without_network_is_kept_retried_and_never_lost(phone, events_origin):
    page, errors = phone
    state = conversation_services(page, messages=long_conversation())
    network(page, state)
    open_dm(page, events_origin)
    # Ouverture en bas du fil : le dernier message est à l'écran.
    pw.expect(page.get_by_text('Message numéro 59', exact=True)).to_be_in_viewport(timeout=10000)

    state['offline'] = True
    field = page.get_by_label('Message', exact=True)
    field.fill('Je prends le pain 🥖')
    page.get_by_role('button', name='Envoyer', exact=True).click()
    # Bulle tout de suite, champ vide : on peut écrire la suite sans attendre.
    pw.expect(page.get_by_text('Je prends le pain 🥖', exact=True)).to_be_visible(timeout=1000)
    pw.expect(field).to_have_value('')
    field.fill('Et les cornichons')
    # Après les nouveaux essais (0,8 s puis 2,5 s) : « Pas envoyé », le message reste, le champ n'est pas réécrit.
    retry = page.get_by_role('button', name='Pas envoyé. Toucher pour réessayer')
    pw.expect(retry).to_be_visible(timeout=8000)
    pw.expect(page.get_by_text('Je prends le pain 🥖', exact=True)).to_be_visible()
    pw.expect(field).to_have_value('Et les cornichons')
    first = state['attempts'][0]
    assert len(state['attempts']) == 3 and set(state['attempts']) == {first}, state['attempts']
    assert not state['dm_posts']

    # Réseau revenu, mais la réponse du premier envoi s'était perdue : la base l'a déjà (23505) → envoyé.
    state['offline'] = False
    state['duplicate'] = True
    retry.click()
    pw.expect(retry).to_have_count(0, timeout=5000)
    assert state['attempts'][-1] == first
    state['duplicate'] = False

    # Le message suivant part normalement, avec son propre identifiant.
    page.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(page.get_by_text('Et les cornichons', exact=True)).to_be_visible()
    page.wait_for_timeout(500)
    assert [p['body'] for p in state['dm_posts']] == ['Et les cornichons'] and state['dm_posts'][0]['id'] != first
    assert not errors, errors


def test_a_refused_message_comes_back_in_the_field(phone, events_origin):
    """Refus de la base (filtre) : pas de nouvel essai, le texte revient dans le champ avec l'explication."""
    page, errors = phone
    state = conversation_services(page, messages=long_conversation())

    def refuse(route):
        request = route.request
        if urlparse(request.url).path.endswith('/direct_messages') and request.method == 'POST':
            state.setdefault('refused', []).append(1)
            return route.fulfill(status=400, content_type='application/json', headers=CORS,
                                 body=json.dumps({'code': 'P0001', 'message': 'content_refused: propos haineux'}))
        return route.fallback()

    page.route(SUPABASE, refuse)
    open_dm(page, events_origin)
    field = page.get_by_label('Message', exact=True)
    field.fill('Texte refusé')
    page.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(field).to_have_value('Texte refusé', timeout=5000)
    pw.expect(page.get_by_role('alert')).to_be_visible()
    pw.expect(page.get_by_role('button', name='Pas envoyé. Toucher pour réessayer')).to_have_count(0)
    assert state['refused'] == [1]
    assert not errors, errors

