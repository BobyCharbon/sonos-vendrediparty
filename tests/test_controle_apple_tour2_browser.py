"""Contrôle Apple du 26.11, tour 2 (module Événements, vrai navigateur, Supabase simulé) :
- Pot commun (migration 20261126140000) : ajouté d'office par l'événement, tes moyens de paiement restent cachés ;
  « Montrer mes moyens de paiement dans ce pot » (tc_members.show_payment, tc_set_show_payment) sur la fiche ;
  base d'avant (colonne ou fonction absente) : l'interrupteur se cache sans erreur ;
- « Signaler le groupe » (type group, cible = le groupe) sur la page d'un groupe ;
- feuille des CGU : sous « Plus tard », ce que la personne garde sans elles."""
import json

from tests.test_c2_acces_browser import SUPA, fulfill, new_page
from tests.test_events_browser import EVENT, USER, browser, events_origin, login, mock_services, pw  # noqa: F401 (fixtures)

OTHER = '11111111-2222-4333-8444-555555555555'
TITLE = 'Sortie de démonstration (test local)'
POT = 'f0000000-0000-4000-8000-000000000001'
YES = {'event_id': EVENT, 'user_id': USER, 'status': 'yes', 'plus_ones': 0, 'note': None, 'waitlisted': False, 'updated_at': '2026-11-20T10:00:00Z'}
COLUMN_MISSING = {'code': '42703', 'message': 'column tc_members.show_payment does not exist'}
FUNCTION_MISSING = {'code': 'PGRST202', 'message': 'Could not find the function public.tc_set_show_payment(p_group, p_on) in the schema cache'}


def open_fiche(browser, events_origin, state, rpc_status=200):  # noqa: F811
    ctx, page = new_page(browser)
    errors, calls = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    mock_services(page, event_extra={'created_by': OTHER, 'pot_enabled': True, 'rsvps': [YES]})
    page.route(f'{SUPA}/rest/v1/tc_groups*', lambda r: fulfill(r, [{'id': POT}]))

    def members(route):
        if state.get('missing'):
            return fulfill(route, COLUMN_MISSING, 400)
        fulfill(route, [{'show_payment': state['on']}])
    page.route(f'{SUPA}/rest/v1/tc_members*', members)

    def toggle(route):
        if route.request.method == 'OPTIONS':
            return fulfill(route, None)
        args = json.loads(route.request.post_data)
        calls.append(args)
        if rpc_status != 200:
            return fulfill(route, FUNCTION_MISSING, rpc_status)
        state['on'] = args['p_on']
        fulfill(route, None)
    page.route(f'{SUPA}/rest/v1/rpc/tc_set_show_payment', toggle)
    page.goto(f'{events_origin}/events/', wait_until='domcontentloaded')
    login(page)
    page.get_by_text(TITLE, exact=True).first.click(timeout=15000)
    pw.expect(page.get_by_role('heading', name=TITLE).first).to_be_visible(timeout=15000)
    return ctx, page, errors, calls


def test_added_by_the_event_my_payment_details_stay_hidden_until_i_show_them(browser, events_origin):  # noqa: F811
    state = {'on': False}
    ctx, page, errors, calls = open_fiche(browser, events_origin, state)
    try:
        notice = page.get_by_test_id('pot-notice')
        pw.expect(notice).to_contain_text('tes moyens de paiement restent cachés tant que tu ne choisis pas de les montrer', timeout=15000)
        switch = page.get_by_role('switch', name='Montrer mes moyens de paiement dans ce pot')
        pw.expect(switch).to_have_attribute('aria-checked', 'false')
        pw.expect(page.get_by_test_id('pot-payment')).to_contain_text('Les membres verront ton IBAN et tes liens de paiement.')
        switch.click()
        pw.expect(switch).to_have_attribute('aria-checked', 'true')
        assert calls == [{'p_group': POT, 'p_on': True}]
        pw.expect(page.get_by_test_id('pot-payment')).to_contain_text('Les membres de ce pot voient ton IBAN et tes liens de paiement.')
        switch.click()
        pw.expect(switch).to_have_attribute('aria-checked', 'false')
        assert calls[-1] == {'p_group': POT, 'p_on': False}
        assert not errors, errors
    finally:
        ctx.close()


def test_old_base_hides_the_payment_switch_without_any_error(browser, events_origin):  # noqa: F811
    ctx, page, errors, calls = open_fiche(browser, events_origin, {'on': False, 'missing': True})
    try:
        pw.expect(page.get_by_test_id('pot-notice')).to_be_visible(timeout=15000)
        page.wait_for_timeout(800)
        pw.expect(page.get_by_test_id('pot-payment')).to_have_count(0)
        assert not errors, errors
    finally:
        ctx.close()
    # Colonne là, fonction pas encore : le premier toucher cache l'interrupteur, sans message d'erreur.
    ctx, page, errors, calls = open_fiche(browser, events_origin, {'on': False}, rpc_status=404)
    try:
        page.get_by_role('switch', name='Montrer mes moyens de paiement dans ce pot').click(timeout=15000)
        pw.expect(page.get_by_test_id('pot-payment')).to_have_count(0)
        pw.expect(page.get_by_text('Could not find', exact=False)).to_have_count(0)
        assert len(calls) == 1 and not errors, errors
    finally:
        ctx.close()


def test_a_member_reports_the_group_from_its_page(browser, events_origin):  # noqa: F811
    from tests.test_groups_browser import CHLOE, DISCO, group_row, group_services, signed_in
    ctx, page = new_page(browser)
    errors, reports = [], []
    page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        group_services(page, row_for=lambda gid: group_row(gid, created_by=CHLOE), rank=2)

        def report(route):
            if route.request.method == 'OPTIONS':
                return fulfill(route, None)
            reports.append(json.loads(route.request.post_data))
            fulfill(route, None)
        page.route(f'{SUPA}/rest/v1/rpc/report_content', report)
        signed_in(page, events_origin, f'/group/{DISCO}')
        pw.expect(page.get_by_role('heading', name='Soirées du vendredi')).to_be_visible(timeout=15000)
        page.get_by_role('button', name='Signaler le groupe', exact=True).click()
        pw.expect(page.get_by_text('Signaler le groupe', exact=True).last).to_be_visible()
        page.get_by_role('radio', name='Contenu choquant').click()
        page.get_by_role('button', name='Envoyer', exact=True).click()
        page.wait_for_timeout(500)
        assert [(r['p_kind'], r['p_target'], r['p_reason']) for r in reports] == [('group', DISCO, 'shocking')]
        assert not errors, errors
    finally:
        ctx.close()
