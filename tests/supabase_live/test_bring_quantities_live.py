"""Qui amène quoi en quantités partagées, sur la VRAIE base de test (jamais la prod) : « 15 bouteilles » se partage
entre plusieurs personnes, sans jamais dépasser 15, et seul l'organisateur change la quantité demandée.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live -q"""
import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, create_event
from tests.supabase_live.test_admin_pages_live import origin, pytestmark as needs_test_build  # noqa: F401 (fixture)
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture(scope='module')
def wine():
    admin, a, b = Session(ADMIN), Session(GUEST_A), Session(GUEST_B)
    eid = create_event(admin, 'Test quantités à amener', public_link=True)
    r = httpx.post(f'{TEST_URL}/rest/v1/bring_items', timeout=30, headers={**admin.headers, 'Prefer': 'return=representation'},
                   json={'event_id': eid, 'label': 'Bouteilles de vin', 'quantity': 15, 'sort': 0})
    assert r.status_code == 201, r.text
    yield admin, a, b, r.json()[0]['id']
    httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)


def claim(who: Session, item: str, quantity: int) -> httpx.Response:
    return httpx.post(f'{TEST_URL}/rest/v1/bring_claims', timeout=30,
                      headers={**who.headers, 'Prefer': 'resolution=merge-duplicates'},
                      json={'item_id': item, 'user_id': who.uid, 'quantity': quantity})


def taken(who: Session, item: str) -> dict:
    return {r['user_id']: r['quantity'] for r in who.get(f'bring_claims?item_id=eq.{item}&select=user_id,quantity').json()}


def test_several_people_share_the_bottles_without_ever_going_over(wine):
    admin, a, b, item = wine
    assert claim(a, item, 2).status_code == 201
    over = claim(b, item, 14)
    assert over.status_code >= 400 and "Il n'en reste que 13" in over.text
    assert claim(b, item, 13).status_code == 201
    assert taken(admin, item) == {a.uid: 2, b.uid: 13}
    assert claim(a, item, 3).status_code >= 400  # changer d'avis ne dépasse pas non plus
    assert claim(a, item, 1).status_code in (200, 201)
    assert taken(a, item) == {a.uid: 1, b.uid: 13}  # tout le monde voit qui amène combien


def test_nobody_answers_for_someone_else_nor_changes_the_requested_quantity(wine):
    admin, a, b, item = wine
    r = httpx.post(f'{TEST_URL}/rest/v1/bring_claims', headers=a.headers, timeout=30,
                   json={'item_id': item, 'user_id': b.uid, 'quantity': 1})
    assert r.status_code >= 400
    httpx.patch(f'{TEST_URL}/rest/v1/bring_items?id=eq.{item}', headers=a.headers, json={'quantity': 999}, timeout=30)
    assert admin.get(f'bring_items?id=eq.{item}&select=quantity').json()[0]['quantity'] == 15


def test_a_person_takes_back_only_their_own_share(wine):
    admin, a, b, item = wine
    httpx.delete(f'{TEST_URL}/rest/v1/bring_claims?item_id=eq.{item}&user_id=eq.{b.uid}', headers=a.headers, timeout=30)
    assert b.uid in taken(admin, item)
    r = httpx.delete(f'{TEST_URL}/rest/v1/bring_claims?item_id=eq.{item}&user_id=eq.{a.uid}', headers=a.headers, timeout=30)
    assert r.status_code in (200, 204)
    assert taken(admin, item) == {b.uid: 13}


@needs_test_build  # module Événements construit pour la base de TEST (sinon le code SMS de test est refusé)
def test_in_the_browser_a_guest_says_she_brings_two_of_the_fifteen_bottles(browser, origin, tmp_path):
    pw = pytest.importorskip('playwright.sync_api')
    from tests.supabase_live.test_audience_form_live import sign_in
    from tests.supabase_live.test_audiences_live import complete_profile
    admin, guest = Session(ADMIN), Session(GUEST_A)
    complete_profile(guest, 'Guest A')
    eid = create_event(admin, 'Test bouteilles navigateur', public_link=True)
    httpx.post(f'{TEST_URL}/rest/v1/bring_items', headers=admin.headers, timeout=30,
               json={'event_id': eid, 'label': 'Bouteilles de vin', 'quantity': 15, 'sort': 0}).raise_for_status()
    try:
        page = browser.new_context(viewport={'width': 390, 'height': 844}).new_page()
        errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(origin + '/events/', wait_until='domcontentloaded')
        sign_in(page, '079 000 00 01')
        pw.expect(page.get_by_text('À venir', exact=True)).to_be_visible(timeout=30000)
        page.goto(f'{origin}/events/event/{eid}', wait_until='domcontentloaded')
        pw.expect(page.get_by_text('0 / 15', exact=True)).to_be_visible(timeout=30000)
        plus = page.get_by_role('button', name='+', exact=True)
        plus.click()
        pw.expect(page.get_by_text('1 / 15', exact=True)).to_be_visible(timeout=15000)
        plus.click()
        pw.expect(page.get_by_text('J’en amène 2', exact=True)).to_be_visible(timeout=15000)
        pw.expect(page.get_by_text('2 / 15', exact=True)).to_be_visible()
        page.screenshot(path=str(tmp_path / 'bring.png'), full_page=True)
        assert not errors, errors
        item = admin.get(f'bring_items?event_id=eq.{eid}&select=bring_claims(user_id,quantity)').json()[0]
        assert item['bring_claims'] == [{'user_id': guest.uid, 'quantity': 2}]
    finally:
        httpx.delete(f'{TEST_URL}/rest/v1/events?id=eq.{eid}', headers=admin.headers, timeout=30)
