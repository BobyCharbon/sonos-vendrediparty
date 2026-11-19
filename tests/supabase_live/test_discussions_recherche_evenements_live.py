"""Discussions › recherche « Événements » (demande de l'admin du 19.11 : « je ne trouve pas les événements, je dois démarrer
la première discussion tout en bas de la fiche ») sur la VRAIE base de TEST : chat_event_search trouve MES événements
encore sans message (pas ceux des autres), sans accents ; le relais de l'app iPhone l'accepte ; après le premier message,
l'événement entre dans chat_list. Événements de test supprimés à la fin.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_discussions_recherche_evenements_live.py -q"""
import uuid

import httpx
import pytest

from app.chat_rpc import RELAY
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_B, create_event
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture
def events():
    admin = Session(ADMIN)
    tag = uuid.uuid4().hex[:6]
    mine = create_event(admin, f'Soirée Récré {tag}')
    yield admin, tag, mine
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{mine}', headers=admin.headers, timeout=30)


def test_my_event_without_message_is_found_and_joins_the_list_after_the_first_message(events):
    admin, tag, mine = events
    assert 'chat_event_search' in RELAY  # l'app iPhone passe par le serveur
    found = admin.rpc('chat_event_search', q=f'recre {tag}').json()  # sans accent ni majuscule
    assert [e['id'] for e in found] == [mine]
    assert found[0]['kind'] == 'event' and found[0]['last'] is None and found[0]['unread'] == 0
    assert mine not in {c['id'] for c in admin.rpc('chat_list').json()}  # pas encore de message : pas dans la liste
    # Personne d'autre : un compte sans lien avec l'événement ne le trouve pas.
    assert Session(GUEST_B).rpc('chat_event_search', q=f'recre {tag}').json() == []
    assert admin.rpc('chat_event_search', q='r').json() == []  # 2 caractères au moins
    # Premier message : la discussion entre dans la liste.
    r = httpx.post(f'{TEST_URL}/rest/v1/messages', headers=admin.headers, timeout=30,
                   json={'event_id': mine, 'user_id': admin.uid, 'body': 'On lance la discussion'})
    assert r.status_code == 201, r.text
    assert mine in {c['id'] for c in admin.rpc('chat_list').json() if c['kind'] == 'event'}
