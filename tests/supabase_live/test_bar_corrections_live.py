"""Bar de la soirée : failles trouvées par le test réel du 10.11.2026 (agents organisateur, barman, clients, client
chaotique), corrigées par la migration 20261110140000_bar_corrections, vérifiées sur la VRAIE base de TEST.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_bar_corrections_live.py -q"""
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

from tests.supabase_live.test_bar_soiree_live import bar, ok, order, people, present, refused  # noqa: F401
from tests.supabase_live.test_member_admin_live import TEST_URL, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def serve(barman, event: str, member: str, lines: list) -> dict:
    return ok(barman.rpc('bar_serve', e=event, member=member, lines=[{'item': i, 'qty': q} for i, q in lines],
                         client_key=str(uuid.uuid4())))


def test_ten_simultaneous_refund_declarations_accept_only_what_is_owed_and_the_balance_never_goes_negative(people, bar):
    # Arrange : Guest A doit 4 Coca = 8 CHF
    admin, ga, _gb, barman = people
    event, _vrb, coca = bar
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    ok(order(ga, event, [(coca, 4)]))
    serve(barman, event, ga.uid, [(coca, 4)])

    # Act : 10 déclarations de 8 CHF en même temps
    with ThreadPoolExecutor(10) as pool:
        answers = list(pool.map(lambda _: ga.rpc('bar_declare_refund', e=event, amount=8), range(10)))

    # Assert : une seule passe ; l'organisateur ne peut pas confirmer plus que le dû
    assert sum(r.status_code == 200 for r in answers) == 1, [r.text for r in answers]
    assert float(ok(ga.rpc('my_bar', e=event))['refund_declared']) == 8.0
    declared = sql(f"select id from public.event_bar_refunds where event_id = '{event}' and user_id = '{ga.uid}'")
    ok(admin.rpc('bar_confirm_refund', e=event, refund=declared[0]['id'], received=True))
    assert float(ok(ga.rpc('my_bar', e=event))['balance']) == 0.0
    sql(f"insert into public.event_bar_refunds (event_id, user_id, amount_chf) values ('{event}', '{ga.uid}', 8)")
    extra = sql(f"select id from public.event_bar_refunds where event_id = '{event}' and user_id = '{ga.uid}' and status = 'declared'")
    assert 'dépasse ce qui reste dû' in refused(admin.rpc('bar_confirm_refund', e=event, refund=extra[0]['id'], received=True))
    assert float(ok(ga.rpc('my_bar', e=event))['balance']) == 0.0


def test_a_huge_order_is_refused_at_once_and_nobody_reserves_more_than_ten_of_an_item_without_maximum(people, bar):
    _admin, ga, gb, _barman = people
    event, _vrb, coca = bar
    lines = [{'item': coca, 'qty': 1}] * 51
    mine = ok(ga.rpc('my_bar', e=event))
    r = ga.rpc('bar_order', e=event, lines=lines, pledge_text=mine['pledge_text'], pledge_version=mine['pledge_version'])
    assert '50 lignes au plus' in refused(r)
    ok(order(ga, event, [(coca, 10)]))
    assert 'max_pending' in refused(order(ga, event, [(coca, 1)]))
    ok(order(gb, event, [(coca, 1)]))  # les autres commandent toujours


def test_saying_absent_cancels_what_was_waiting_and_gives_the_stock_back(people, bar):
    _admin, ga, _gb, _barman = people
    event, vrb, _coca = bar
    ok(order(ga, event, [(vrb, 2)]))
    r = httpx.patch(f'{TEST_URL}/rest/v1/rsvps?event_id=eq.{event}&user_id=eq.{ga.uid}', headers=ga.headers, timeout=30,
                    json={'status': 'no'})
    assert r.status_code in (200, 204), r.text
    left = sql(f"select status, cancel_reason from public.event_bar_units where event_id = '{event}' and user_id = '{ga.uid}'")
    assert left and all(u == {'status': 'cancelled', 'cancel_reason': 'absent'} for u in left)
    present(ga, event=event)


def test_the_barman_sees_the_price_of_the_order_not_the_new_price_of_the_menu(people, bar):
    admin, ga, _gb, barman = people
    event, vrb, _coca = bar
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    ok(order(ga, event, [(vrb, 1)]))
    ok(admin.rpc('bar_save_item', e=event, item={'id': vrb, 'name': 'Vodka Red Bull', 'price_chf': 6}))
    ok(order(ga, event, [(vrb, 1)]))
    scan = ok(barman.rpc('bar_scan', e=event, scanned=ok(ga.rpc('my_bar', e=event))['qr']['token']))
    line = next(x for x in scan['pending'] if x['item'] == vrb)
    assert [float(p) for p in line['prices']] == [4.5, 6.0]
    assert float(next(i for i in ok(ga.rpc('my_bar', e=event))['items'] if i['id'] == vrb)['mine_pending_chf']) == 10.5


def test_a_corrected_glass_stays_out_of_stock_and_no_serve_is_undone_once_the_bar_is_closed(people, bar):
    admin, ga, _gb, barman = people
    event, vrb, _coca = bar
    ok(admin.rpc('bar_set_staff', e=event, member=barman.uid, barman=True))
    ok(order(ga, event, [(vrb, 1)]))
    serve(barman, event, ga.uid, [(vrb, 1)])
    unit = sql(f"select id from public.event_bar_units where event_id = '{event}' and user_id = '{ga.uid}' and status = 'served'")[0]['id']
    ok(admin.rpc('bar_correct_unit', e=event, unit=unit))
    available = next(i for i in ok(ga.rpc('my_bar', e=event))['items'] if i['id'] == vrb)['available']
    assert available == 4  # stock 5 : le verre corrigé est parti quand même
    ok(order(ga, event, [(vrb, 1)]))
    done = serve(barman, event, ga.uid, [(vrb, 1)])
    sql(f"update public.event_bars set closed_at = now() where event_id = '{event}'")
    assert 'fermé' in refused(barman.rpc('bar_undo_serve', e=event, serve=done['serve_id']))
