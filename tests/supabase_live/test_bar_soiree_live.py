"""Bar de la soirée (maquettes v6 validées le 10.11.2026), sur une VRAIE base (base de TEST ou sa copie locale, jamais la
prod) : droits (organisateurs, barmans, présents au profil complet), stock virtuel BLOQUANT sous accès simultanés, maximum
« en attente » par personne, précommande, prix figé, engagement coché (texte exact), service au scan avec annulation 15 s et
correction, remboursements, fermeture qui annule ce qui attend, notifications instantanées.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_bar_soiree_live.py -q"""
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, create_event
from tests.supabase_live.test_invitations_v2_live import terms_version
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def ok(r: httpx.Response):
    assert r.status_code in (200, 204), r.text
    return r.json() if r.content else None


def refused(r: httpx.Response) -> str:
    assert r.status_code >= 400, r.text
    return r.text


@pytest.fixture(scope='module')
def people():
    admin, ga, gb, barman = Session(ADMIN), Session(GUEST_A), Session(GUEST_B), Session(VIP)
    for s in (admin, ga, gb, barman):
        assert s.rpc('accept_terms', p_version=terms_version()).status_code in (200, 204)
    return admin, ga, gb, barman


def present(*who: Session, event: str):
    for s in who:
        r = httpx.post(f'{TEST_URL}/rest/v1/rsvps', headers=s.headers, timeout=30, json={'event_id': event, 'user_id': s.uid, 'status': 'yes'})
        assert r.status_code in (200, 201, 409), r.text


@pytest.fixture
def bar(people):
    """Un événement publié, un bar ouvert : Vodka Red Bull (4.50, stock 5, max 2 en attente) et Coca (2.00, illimité)."""
    admin, ga, gb, barman = people
    event = create_event(admin, 'Test bar de la soirée', visibility='all', public_link=True)
    present(admin, ga, gb, barman, event=event)
    ok(admin.rpc('bar_create', e=event))
    vrb = ok(admin.rpc('bar_save_item', e=event, item={'name': 'Vodka Red Bull', 'emoji': '🍸', 'price_chf': 4.5, 'stock': 5,
                                                         'age_min': 18, 'max_pending': 2}))['id']
    coca = ok(admin.rpc('bar_save_item', e=event, item={'name': 'Coca', 'emoji': '🥤', 'price_chf': 2}))['id']
    ok(admin.rpc('bar_save_settings', e=event, settings={'orders_open': True, 'pay_method': 'revolut',
                                                          'repay_by': (date.today() + timedelta(days=3)).isoformat()}))
    yield event, vrb, coca
    sql(f"delete from public.events where id = '{event}'")


def order(who: Session, event: str, lines: list, pledge: dict | None = None) -> httpx.Response:
    mine = pledge or ok(who.rpc('my_bar', e=event))
    return who.rpc('bar_order', e=event, lines=[{'item': i, 'qty': q} for i, q in lines],
                   pledge_text=mine['pledge_text'], pledge_version=mine['pledge_version'])


def notes(who: Session, event: str, kind: str) -> list:
    return sql(f"select body from public.notifications where user_id = '{who.uid}' and event_id = '{event}' and kind = '{kind}' order by created_at")


def test_only_organizers_create_and_manage_the_bar_and_only_present_full_profiles_order(people):
    admin, ga, gb, _barman = people
    event = create_event(admin, 'Test bar droits', visibility='all', public_link=True)
    try:
        assert 'forbidden' in refused(ga.rpc('bar_create', e=event))
        ok(admin.rpc('bar_create', e=event))
        assert 'forbidden' in refused(ga.rpc('bar_overview', e=event))
        assert 'forbidden' in refused(ga.rpc('bar_save_item', e=event, item={'name': 'Bière', 'price_chf': 3}))
        item = ok(admin.rpc('bar_save_item', e=event, item={'name': 'Bière', 'price_chf': 3}))['id']
        ok(admin.rpc('bar_save_settings', e=event, settings={'orders_open': True}))
        # Pas noté Présent : il voit le bar mais ne commande pas, et n'a pas de QR.
        mine = ok(gb.rpc('my_bar', e=event))
        assert mine['eligible'] is False and mine['qr'] is None and mine['phase'] == 'open'
        assert 'forbidden' in refused(order(gb, event, [(item, 1)], mine))
        # Présent : un seul QR pour la soirée (le jeton du billet), même billets éteints.
        present(ga, event=event)
        mine = ok(ga.rpc('my_bar', e=event))
        assert mine['eligible'] is True and len(mine['qr']['token']) == 64 and len(mine['qr']['code']) == 6
        ticket = sql(f"select token from public.event_tickets where event_id = '{event}' and user_id = '{ga.uid}'")
        assert ticket == [{'token': mine['qr']['token']}]
        assert 'Admin test' in mine['pledge_text'] and 'Revolut' in mine['pledge_text']
        # Un barman n'existe que parmi les présents ; un Guest ne scanne pas.
        assert 'présents' in refused(admin.rpc('bar_set_staff', e=event, member=gb.uid, barman=True))
        assert 'forbidden' in refused(ga.rpc('bar_scan', e=event, scanned=mine['qr']['token']))
    finally:
        sql(f"delete from public.events where id = '{event}'")


def test_the_pledge_must_match_and_the_price_is_frozen_at_order_time(people, bar):
    admin, ga, _gb, _barman = people
    event, vrb, _coca = bar
    mine = ok(ga.rpc('my_bar', e=event))
    wrong = {**mine, 'pledge_text': mine['pledge_text'] + ' (modifié)'}
    assert 'terms_changed' in refused(order(ga, event, [(vrb, 1)], wrong))
    ok(order(ga, event, [(vrb, 1)], mine))
    assert sql(f"select text from public.event_bar_pledges where event_id = '{event}' and user_id = '{ga.uid}'") == [{'text': mine['pledge_text']}]
    # Prix changé ensuite : le verre déjà commandé garde 4.50, le suivant prend 6.
    ok(admin.rpc('bar_save_item', e=event, item={'id': vrb, 'name': 'Vodka Red Bull', 'price_chf': 6}))
    ok(order(ga, event, [(vrb, 1)]))
    prices = sorted(float(r['price_chf']) for r in sql(f"select price_chf from public.event_bar_units where user_id = '{ga.uid}' and item_id = '{vrb}'"))
    assert prices == [4.5, 6.0]
    # Conditions changées (date limite) : nouvelle version, l'ancienne case cochée ne vaut plus ; prévenu.
    ok(admin.rpc('bar_save_settings', e=event, settings={'repay_by': (date.today() + timedelta(days=9)).isoformat()}))
    assert 'terms_changed' in refused(order(ga, event, [(vrb, 1)], mine))
    assert any('Conditions du bar changées' in n['body'] for n in notes(ga, event, 'bar_changed'))


def test_virtual_stock_blocks_and_max_pending_frees_up_once_served(people, bar):
    admin, ga, gb, barman = people
    event, vrb, coca = bar
    ok(order(ga, event, [(vrb, 2), (coca, 3)]))
    assert 'max_pending' in refused(order(ga, event, [(vrb, 1)]))  # 2 en attente sur 2 permises
    ok(order(gb, event, [(vrb, 2)]))
    # Stock 5 : 4 réservés, il en reste 1 ; le barman en demande 2 → refusé, 1 → accepté, puis plus rien.
    assert 'plus que 1' in refused(order(barman, event, [(vrb, 2)]))
    ok(order(barman, event, [(vrb, 1)]))
    assert 'plus que 0' in refused(order(admin, event, [(vrb, 1)]))
    item = next(i for i in ok(ga.rpc('my_bar', e=event))['items'] if i['id'] == vrb)
    assert item['available'] == 0 and item['mine_pending'] == 2
    # Un verre servi ne compte plus dans « en attente » : Léa peut en recommander un… si le stock le permet (il est plein).
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    scan = ok(barman.rpc('bar_scan', e=event, scanned=ok(ga.rpc('my_bar', e=event))['qr']['token']))
    assert scan['result'] == 'ok' and {p['name']: p['qty'] for p in scan['pending']} == {'Vodka Red Bull': 2, 'Coca': 3}
    ok(barman.rpc('bar_serve', e=event, member=ga.uid, lines=[{'item': vrb, 'qty': 1}], client_key=str(uuid.uuid4())))
    assert 'plus que 0' in refused(order(ga, event, [(vrb, 1)]))  # stock virtuel toujours plein (4 en attente + 1 servi)
    ok(ga.rpc('bar_cancel_mine', e=event, item=coca, qty=1))  # le Coca est illimité : annuler ne change rien au stock
    ok(gb.rpc('bar_cancel_mine', e=event, item=vrb, qty=1))   # Marc annule une vodka : une place se libère
    ok(order(ga, event, [(vrb, 1)]))                           # Léa (1 en attente sur 2) en reprend une


def test_serving_debits_the_balance_once_with_undo_within_15_seconds_and_correction_later(people, bar):
    admin, ga, _gb, barman = people
    event, vrb, coca = bar
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    assert any('barman' in n['body'] for n in notes(barman, event, 'bar_changed'))
    ok(order(ga, event, [(vrb, 2), (coca, 1)]))
    token = ok(ga.rpc('my_bar', e=event))['qr']['token']
    assert ok(barman.rpc('bar_scan', e=event, scanned=f'https://party.bobycharbon.ch/events/x?ticket={token}'))['result'] == 'ok'
    key = str(uuid.uuid4())
    served = ok(barman.rpc('bar_serve', e=event, member=ga.uid, lines=[{'item': vrb, 'qty': 1}, {'item': coca, 'qty': 1}], client_key=key))
    assert float(served['total']) == 6.5 and float(served['balance']) == 6.5
    again = ok(barman.rpc('bar_serve', e=event, member=ga.uid, lines=[{'item': vrb, 'qty': 1}], client_key=key))
    assert again['replayed'] is True and float(ok(ga.rpc('my_bar', e=event))['balance']) == 6.5  # rien de servi deux fois
    note = notes(ga, event, 'bar_served')
    assert len(note) == 1 and '1 Vodka Red Bull' in note[0]['body'] and 'À rembourser : 6.50 CHF' in note[0]['body']
    # Annuler pendant 15 s : les verres repassent en attente, le solde revient.
    ok(barman.rpc('bar_undo_serve', e=event, serve=served['serve_id']))
    mine = ok(ga.rpc('my_bar', e=event))
    assert float(mine['balance']) == 0 and float(mine['pending_total']) == 11.0
    # Trop tard (plus de 15 s) : le barman ne peut plus ; l'organisateur corrige un verre servi par erreur.
    served = ok(barman.rpc('bar_serve', e=event, member=ga.uid, lines=[{'item': vrb, 'qty': 1}], client_key=str(uuid.uuid4())))
    sql(f"update public.event_bar_serves set served_at = now() - interval '1 minute' where id = '{served['serve_id']}'")
    assert 'trop tard' in refused(barman.rpc('bar_undo_serve', e=event, serve=served['serve_id']))
    unit = sql(f"select id from public.event_bar_units where serve_id = '{served['serve_id']}'")[0]['id']
    assert 'forbidden' in refused(barman.rpc('bar_correct_unit', e=event, unit=unit))
    ok(admin.rpc('bar_correct_unit', e=event, unit=unit))
    assert float(ok(ga.rpc('my_bar', e=event))['balance']) == 0
    assert any('servi par erreur' in n['body'] for n in notes(ga, event, 'bar_changed'))
    # Le barman ne voit ni les soldes des autres ni la gestion.
    assert 'forbidden' in refused(barman.rpc('bar_overview', e=event))


def test_ten_simultaneous_orders_for_five_in_stock_give_exactly_five(people):
    admin, ga, gb, barman = people
    event = create_event(admin, 'Test bar concurrence', visibility='all', public_link=True)
    try:
        present(admin, ga, gb, barman, event=event)
        ok(admin.rpc('bar_create', e=event))
        item = ok(admin.rpc('bar_save_item', e=event, item={'name': 'Dernières bières', 'price_chf': 3, 'stock': 5}))['id']
        ok(admin.rpc('bar_save_settings', e=event, settings={'orders_open': True}))
        pledges = {s.uid: ok(s.rpc('my_bar', e=event)) for s in (admin, ga, gb, barman)}
        who = [admin, ga, gb, barman, admin, ga, gb, barman, admin, ga]
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(lambda s: order(s, event, [(item, 1)], pledges[s.uid]).status_code, who))
        assert results.count(200) == 5, results
        assert sql(f"select count(*) n from public.event_bar_units where item_id = '{item}'") == [{'n': 5}]
    finally:
        sql(f"delete from public.events where id = '{event}'")


def test_two_barmen_serving_the_same_last_glass_at_once_serve_it_once(people, bar):
    admin, ga, _gb, barman = people
    event, vrb, _coca = bar
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    ok(order(ga, event, [(vrb, 1)]))
    serve = lambda s: s.rpc('bar_serve', e=event, member=ga.uid, lines=[{'item': vrb, 'qty': 1}], client_key=str(uuid.uuid4()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(serve, [admin, barman]))
    codes = sorted(r.status_code for r in results)
    assert codes[0] == 200 and codes[1] >= 400, [r.text for r in results]
    assert any('already_served' in r.text for r in results)
    assert float(ok(ga.rpc('my_bar', e=event))['balance']) == 4.5


def test_preorder_has_no_per_person_maximum_but_respects_the_stock(people, bar):
    admin, ga, _gb, _barman = people
    event, vrb, _coca = bar
    ok(admin.rpc('bar_save_settings', e=event, settings={'orders_open': False, 'preorder_enabled': True}))
    assert ok(ga.rpc('my_bar', e=event))['phase'] == 'preorder'
    ok(order(ga, event, [(vrb, 4)]))  # max 2 en attente… mais pas en précommande
    assert 'plus que 1' in refused(order(ga, event, [(vrb, 2)]))  # le stock, lui, compte toujours
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ok(admin.rpc('bar_save_settings', e=event, settings={'preorder_until': past}))
    assert ok(ga.rpc('my_bar', e=event))['phase'] == 'waiting'
    assert 'pas encore ouvertes' in refused(order(ga, event, [(vrb, 1)]))


def test_organizer_sees_reservations_cancels_them_and_confirms_refunds(people, bar):
    admin, ga, gb, barman = people
    event, vrb, coca = bar
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    ok(order(ga, event, [(vrb, 2), (coca, 1)]))
    ok(order(gb, event, [(vrb, 1)]))
    ok(barman.rpc('bar_serve', e=event, member=ga.uid, lines=[{'item': vrb, 'qty': 1}], client_key=str(uuid.uuid4())))
    overview = ok(admin.rpc('bar_overview', e=event))
    stock = {i['name']: (i['served'], i['pending'], i['available']) for i in overview['items']}
    assert stock['Vodka Red Bull'] == (1, 2, 2) and stock['Coca'] == (0, 1, None)
    # Annuler le verre réservé de Marc : la place revient, Marc est prévenu.
    ok(admin.rpc('bar_cancel_units', e=event, member=gb.uid, item=vrb, qty=1))
    assert any('annulé' in n['body'] for n in notes(gb, event, 'bar_changed'))
    assert ok(admin.rpc('bar_overview', e=event))['cancellations'][0]['name'] == 'Testeur 2'
    # Remboursement : jamais plus que le solde ; annoncé, puis confirmé par l'organisateur.
    assert 'invalide' in refused(ga.rpc('bar_declare_refund', e=event, amount=10))
    ok(ga.rpc('bar_declare_refund', e=event, amount=4.5))
    assert notes(admin, event, 'bar_refund_declared')
    refund = ok(admin.rpc('bar_overview', e=event))
    declared = next(p for p in refund['people'] if p['id'] == ga.uid)['declared'][0]['id']
    ok(admin.rpc('bar_confirm_refund', e=event, refund=declared, received=True))
    assert float(ok(ga.rpc('my_bar', e=event))['balance']) == 0
    assert any('reçu' in n['body'] for n in notes(ga, event, 'bar_refund_confirmed'))
    # Guests prévenus (types autorisés pour un compte hors du groupe).
    assert sql(f"select private.may_receive_push('{ga.uid}', 'bar_served') ok") == [{'ok': True}]


def test_closing_the_bar_cancels_what_still_waits_and_refuses_new_orders(people, bar):
    admin, ga, _gb, _barman = people
    event, vrb, _coca = bar
    ok(order(ga, event, [(vrb, 2)]))
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    ok(admin.rpc('bar_save_settings', e=event, settings={'closes_at': past}))
    mine = ok(ga.rpc('my_bar', e=event))  # la lecture ferme le bar à l'heure (pg_cron le fait aussi chaque minute)
    assert mine['phase'] == 'closed' and float(mine['pending_total']) == 0
    assert all(c['reason'] == 'closed' for c in mine['cancelled'])
    assert any('rien à payer' in n['body'] for n in notes(ga, event, 'bar_changed'))
    assert 'fermé' in refused(order(ga, event, [(vrb, 1)], mine))


def test_pledges_and_journal_are_append_only(people, bar):
    _admin, ga, _gb, _barman = people
    event, vrb, _coca = bar
    ok(order(ga, event, [(vrb, 1)]))
    with pytest.raises(RuntimeError, match='ajout seul'):
        sql(f"update public.event_bar_pledges set text = 'autre' where event_id = '{event}'")
    with pytest.raises(RuntimeError, match='ajout seul'):
        sql(f"delete from public.event_bar_log where event_id = '{event}'")
    with pytest.raises(RuntimeError, match='forbidden'):
        sql(f"update public.event_bar_units set price_chf = 0 where event_id = '{event}'")


def test_the_single_qr_goes_to_apple_wallet_with_the_bar_balance_even_with_tickets_off(people, bar):
    """Demande de l'admin (10.11) : un seul QR, aussi dans l'app Cartes Apple ; billets QR éteints, le bar suffit."""
    admin, ga, gb, barman = people
    event, vrb, _coca = bar
    assert not sql(f"select tickets_enabled from public.events where id = '{event}'")[0]['tickets_enabled']
    ok(order(ga, event, [(vrb, 2)]))
    issued = ok(ga.rpc('wallet_pass_issue', e=event))
    assert issued['valid'] is True and issued['bar']['pending'] == 2 and float(issued['bar']['balance']) == 0
    assert issued['ticket']['token'] == ok(ga.rpc('my_bar', e=event))['qr']['token']  # le même QR qu'à l'écran
    before = sql(f"select updated_at from public.wallet_passes where event_id = '{event}' and user_id = '{ga.uid}'")[0]['updated_at']
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    ok(barman.rpc('bar_serve', e=event, member=ga.uid, lines=[{'item': vrb, 'qty': 1}], client_key=str(uuid.uuid4())))
    after = sql(f"select updated_at from public.wallet_passes where event_id = '{event}' and user_id = '{ga.uid}'")[0]['updated_at']
    assert after > before  # l'iPhone redemande le pass : « Nouveau solde : 4.50 CHF »
    assert float(ok(ga.rpc('wallet_pass_issue', e=event))['bar']['balance']) == 4.5
    # Le barman peut prévenir l'iPhone de la personne qu'il sert ; un autre invité, non.
    assert barman.rpc('wallet_push_targets', e=event, member=ga.uid).status_code == 200
    assert gb.rpc('wallet_push_targets', e=event, member=ga.uid).status_code >= 400
    # Pas Présent : ni bar ni pass.
    assert gb.rpc('wallet_pass_issue', e=event).status_code == 200  # gb est Présent dans ce bar (fixture)
