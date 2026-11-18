"""Pronos v2 (migration 20261118090000) sur la VRAIE base de TEST, comptes de test à code fixe : nouveaux types (oui / non,
plus / moins, quand, majorité, trophée), patates (sac par terrain, remontée du lundi, plafond 20, jamais négatif, partage
exact au plus fort reste, tout rendu dans les cas prévus), contestation et vote, réactions, saison, historique à soi,
filtre étendu, motif « money », interrupteur des patates en base, aucun accès direct aux tables.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_pronos_v2_live.py -q"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_agenda_live import ok, refused
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, VIP, complete_profile
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def later(minutes=60) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def close_now(pid: str):
    sql(f"update private.pronos set closes_at = now() - interval '1 second' where id = '{pid}'")


def end_contest(pid: str):
    """Les 12 h de contestation sont passées, puis pronos-tick tourne."""
    sql(f"update private.pronos set contest_until = now() - interval '1 second' where id = '{pid}'")
    tick()


def tick():
    sql('select private.prono_tick()')


def set_patates(on: bool):
    sql(f"update private.prono_settings set patates_enabled = {'true' if on else 'false'} where id = 1")


@pytest.fixture(scope='module')
def people():
    a, b, c, d = Session(GUEST_A), Session(GUEST_B), Session(VIP), Session(ADMIN)
    complete_profile(a, 'Prono Léa')
    complete_profile(b, 'Prono Marc')
    complete_profile(c, 'Prono Zoé')
    everyone = (a, b, c, d)
    for x in everyone:
        for y in everyone:
            if x is not y:
                x.rpc('set_direct_block', target=y.uid, blocked=False)
    set_patates(True)
    yield everyone
    set_patates(True)  # base de TEST : allumé
    ids = "', '".join(x.uid for x in everyone)
    sql(f"delete from private.pronos where created_by in ('{ids}')")
    sql(f"delete from public.notifications where kind like 'prono%' and user_id in ('{ids}')")


@pytest.fixture
def group(people):
    """Un groupe neuf par test (sacs neufs à 100), les quatre comptes dedans."""
    a = people[0]
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**a.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Pronos v2 recette'}, timeout=30)
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    for x in people[1:]:
        sql(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{x.uid}') on conflict do nothing")
    yield gid
    ids = "', '".join(x.uid for x in people)
    sql(f"delete from private.pronos where created_by in ('{ids}')")
    sql(f"delete from public.member_groups where id = '{gid}'")


def create(who, **body):
    return who.rpc('prono_create', body={'closes_at': later(), 'points': 3, **body})


def bag(who, gid) -> int:
    return ok(who.rpc('prono_bag', group_id=gid))['balance']


def opt(p, label):
    return next(o['id'] for o in p['options'] if o['label'] == label)


def test_yes_no_and_over_under_lines(people, group):
    a, b, c, _ = people
    yn = ok(create(a, question='Il va pleuvoir samedi ?', kind='yesno', group_id=group))
    assert [o['label'] for o in yn['options']] == ['Oui', 'Non'] and yn['patates_on'] is True
    refused(create(a, question='Plus ou moins de buts ?', kind='overunder', line=7, group_id=group), 'invalid')
    ou = ok(create(a, question='Plus ou moins de buts ?', kind='overunder', line=7.5, group_id=group, template='buts'))
    assert [o['label'] for o in ou['options']] == ['Plus de 7,5', 'Moins de 7,5']
    assert float(ou['line']) == 7.5 and ou['template'] == 'buts'
    # iPhone : libellés avec l'unité gardés ; oui / non : libellés envoyés ignorés.
    unit = ok(create(b, question='Plus ou moins de cartons ?', kind='overunder', line=3.5, group_id=group,
                     options=['Plus de 3,5 cartons', 'Moins de 3,5 cartons']))
    assert [o['label'] for o in unit['options']] == ['Plus de 3,5 cartons', 'Moins de 3,5 cartons']
    yn2 = ok(create(b, question='Il neige ?', kind='yesno', group_id=group, options=['Ouais', 'Nan']))
    assert [o['label'] for o in yn2['options']] == ['Oui', 'Non']
    ok(b.rpc('prono_answer', id=ou['id'], answer={'option_id': opt(ou, 'Plus de 7,5')}))
    ok(c.rpc('prono_answer', id=ou['id'], answer={'option_id': opt(ou, 'Moins de 7,5')}))
    close_now(ou['id'])
    done = ok(a.rpc('prono_result', id=ou['id'], body={'number': 9}))  # la valeur réelle choisit « Plus »
    assert done['result']['option_id'] == opt(ou, 'Plus de 7,5') and [w['id'] for w in done['winners']] == [b.uid]
    assert done['rarity'] == {'right': 1, 'of': 2} and done['settled'] and done['contest']['open']


def test_patates_are_shared_exactly_with_the_largest_remainder(people, group):
    a, b, c, d = people
    p = ok(create(a, question='Qui marque en premier ?', kind='choice', options=['Max', 'Jo', 'Personne'], group_id=group,
                  patates=True))
    assert p['patates'] and p['bag'] == {'balance': 100, 'refill_at': p['bag']['refill_at'], 'max_stake': 20}
    refused(b.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Max'), 'stake': 21}), 'invalid')  # plafond 20
    ok(a.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Max'), 'stake': 7}))
    ok(b.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Max'), 'stake': 20}))
    ok(b.rpc('prono_answer', id=p['id'], answer={'stake': 5}))  # reprise : 15 rendues aussitôt, la réponse reste
    ok(c.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Jo'), 'stake': 10}))
    seen = ok(d.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Personne'), 'stake': 1}))
    assert bag(b, group) == 95 and seen['my_answer']['stake'] == 1
    # Avant le dévoilement : le champ et le nombre de planteurs, rien par choix, aucune réponse.
    assert seen['field'] == {'total': 23, 'planters': 4, 'by_option': None} and seen['answers'] is None
    listed = next(x for x in ok(c.rpc('prono_list', group_id=group)) if x['id'] == p['id'])
    assert listed['field_total'] == 23 and listed['my_stake'] == 10 and listed['patates_on'] and listed['cover'] is not None
    assert listed['planters'] == 4 and [o['label'] for o in listed['options']] == ['Max', 'Jo', 'Personne']
    assert all('count' not in o for o in listed['options']) and listed['candidates'] is None
    close_now(p['id'])
    done = ok(a.rpc('prono_result', id=p['id'], body={'option_id': opt(p, 'Max')}))
    # 23 dans le champ, 12 sur Max : Léa 7 × 23 / 12 = 13,42 → 13 ; Marc 5 × 23 / 12 = 9,58 → 9 + le reste = 10.
    assert not done['settled'] and all(x['harvest'] is None for x in done['answers'])  # en attente 12 h
    assert done['my_harvest_pending'] == 13
    card = next(x for x in ok(b.rpc('prono_list', group_id=group)) if x['id'] == p['id'])
    assert card['my_harvest_pending'] == 10 and card['my_harvest'] is None
    assert card['my_answer']['option_id'] == opt(p, 'Max') and card['my_answer']['stake'] == 5
    assert {x['option_id']: x['total'] for x in done['field']['by_option']} == {opt(p, 'Max'): 12, opt(p, 'Jo'): 10, opt(p, 'Personne'): 1}
    note = sql(f"select body from public.notifications where kind = 'prono_result' and user_id = '{b.uid}' and data->>'prono_id' = '{p['id']}'")
    assert note[0]['body'].startswith("🔮 Tu l'avais vu ! +10 🎊"), note
    lost = sql(f"select body from public.notifications where kind = 'prono_result' and user_id = '{c.uid}' and data->>'prono_id' = '{p['id']}'")
    assert lost[0]['body'].startswith('La réponse était Max') and '🎊' not in lost[0]['body']  # rien après une perte
    end_contest(p['id'])
    after = ok(a.rpc('prono_get', id=p['id']))
    assert after['settled'] and {x['user']['id']: x['harvest'] for x in after['answers']} == {a.uid: 13, b.uid: 10, c.uid: 0, d.uid: 0}
    assert sum(x['harvest'] for x in after['answers']) == 23  # aucune patate créée ni perdue
    assert [bag(x, group) for x in (a, b, c, d)] == [106, 105, 90, 99]
    # Historique : le sien seulement.
    hist = ok(b.rpc('prono_bag_history', group_id=group))
    assert [(h['reason'], h['delta']) for h in hist] == [('harvest', 10), ('unplant', 15), ('plant', -20), ('start', 100)]
    assert all(h['prono'] is None or h['prono']['id'] == p['id'] for h in hist)
    # Saison : récolte nette du mois, jamais le sac.
    season = ok(c.rpc('prono_season', group_id=group))
    rows = {r['user']['id']: (r['harvest_net'], r['rank'], r['right'], r['played']) for r in season['rows']}
    assert rows == {a.uid: (6, 1, 1, 1), b.uid: (5, 2, 1, 1), d.uid: (-1, 3, 0, 1), c.uid: (-10, 4, 0, 1)}
    assert season['me']['user']['id'] == c.uid and season['me']['harvest_net'] == -10
    assert ok(a.rpc('prono_bag', group_id=group))['season']['harvest_net'] == 6


def test_everything_is_given_back_unanimous_nobody_right_single_planter_cancel(people, group):
    a, b, c, d = people
    u = ok(create(a, question='Il fait beau demain ?', kind='yesno', group_id=group, patates=True))
    ok(a.rpc('prono_answer', id=u['id'], answer={'option_id': opt(u, 'Oui'), 'stake': 5}))
    ok(b.rpc('prono_answer', id=u['id'], answer={'option_id': opt(u, 'Oui'), 'stake': 8}))
    close_now(u['id'])
    done = ok(a.rpc('prono_result', id=u['id'], body={'option_id': opt(u, 'Oui')}))
    assert done['unanimous']
    end_contest(u['id'])
    assert {x['user']['id']: x['harvest'] for x in ok(a.rpc('prono_get', id=u['id']))['answers']} == {a.uid: 5, b.uid: 8}

    n = ok(create(b, question='Le train part à l\'heure ?', kind='yesno', group_id=group, patates=True))
    ok(a.rpc('prono_answer', id=n['id'], answer={'option_id': opt(n, 'Oui'), 'stake': 3}))
    ok(c.rpc('prono_answer', id=n['id'], answer={'option_id': opt(n, 'Oui'), 'stake': 4}))
    ok(d.rpc('prono_answer', id=n['id'], answer={'option_id': opt(n, 'Non')}))  # juste, mais sans patate
    close_now(n['id'])
    ok(b.rpc('prono_result', id=n['id'], body={'option_id': opt(n, 'Non')}))
    end_contest(n['id'])
    got = {x['user']['id']: x['harvest'] for x in ok(c.rpc('prono_get', id=n['id']))['answers']}
    assert got == {a.uid: 3, c.uid: 4, d.uid: 0}  # personne n'avait planté sur la bonne réponse : tout rendu

    s = ok(create(c, question='Il neige à Noël ?', kind='yesno', group_id=group, patates=True))
    ok(a.rpc('prono_answer', id=s['id'], answer={'option_id': opt(s, 'Oui'), 'stake': 6}))
    ok(b.rpc('prono_answer', id=s['id'], answer={'option_id': opt(s, 'Non')}))
    close_now(s['id'])
    ok(c.rpc('prono_result', id=s['id'], body={'option_id': opt(s, 'Non')}))
    end_contest(s['id'])
    assert next(x for x in ok(a.rpc('prono_get', id=s['id']))['answers'] if x['user']['id'] == a.uid)['harvest'] == 6  # un seul planteur

    k = ok(create(d, question='La soirée finit après 2 h ?', kind='yesno', group_id=group, patates=True))
    ok(a.rpc('prono_answer', id=k['id'], answer={'option_id': opt(k, 'Oui'), 'stake': 9}))
    ok(b.rpc('prono_answer', id=k['id'], answer={'option_id': opt(k, 'Non'), 'stake': 9}))
    gone = ok(d.rpc('prono_cancel', id=k['id']))
    assert gone['state'] == 'cancelled' and gone['settled'] and gone['cancel_reason'] == 'organizer'
    assert [bag(x, group) for x in (a, b, c, d)] == [100, 100, 100, 100]


def test_weekly_refill_cap_and_never_negative(people, group):
    a, b, _, d = people
    assert bag(d, group) == 100
    # Remontée paresseuse du lundi : sous 100 → 100 ; au-dessus, rien ne bouge.
    sql(f"update private.prono_bags set balance = 40, refill_week = refill_week - 7 where terrain = 'g:{group}' and user_id = '{d.uid}'")
    assert bag(d, group) == 100
    assert [(h['reason'], h['delta']) for h in ok(d.rpc('prono_bag_history', group_id=group))][0] == ('refill', 60)
    sql(f"update private.prono_bags set balance = 130, refill_week = refill_week - 7 where terrain = 'g:{group}' and user_id = '{d.uid}'")
    assert bag(d, group) == 130
    assert ok(d.rpc('prono_bag', group_id=group))['refill_at'] > datetime.now(timezone.utc).isoformat()
    p = ok(create(a, question='Qui gagne au baby-foot ?', kind='person', group_id=group, patates=True))
    sql(f"update private.prono_bags set balance = 3 where terrain = 'g:{group}' and user_id = '{d.uid}'")
    refused(d.rpc('prono_answer', id=p['id'], answer={'person_id': a.uid, 'stake': 5}), 'not_enough')
    ok(d.rpc('prono_answer', id=p['id'], answer={'person_id': a.uid, 'stake': 3}))
    assert bag(d, group) == 0
    with pytest.raises(Exception):
        sql(f"update private.prono_bags set balance = -1 where terrain = 'g:{group}' and user_id = '{d.uid}'")
    # Pas de patates sans groupe ni événement, ni sur un trophée ou une réponse libre.
    refused(create(a, question='Combien de buts ?', kind='number', link=True, patates=True), 'invalid')
    refused(create(a, question='Le mot du soir ?', kind='text', group_id=group, patates=True), 'invalid')
    honour = ok(create(a, question='Combien de buts ?', kind='number', group_id=group))
    refused(b.rpc('prono_answer', id=honour['id'], answer={'number': 3, 'stake': 2}), 'invalid')
    assert honour['bag'] is None and honour['field'] is None


def test_contest_majority_unfair_cancels_and_gives_everything_back(people, group):
    a, b, c, d = people
    p = ok(create(a, question='Qui a gagné la pétanque ?', kind='choice', options=['Léa', 'Marc'], group_id=group, patates=True))
    ok(a.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Léa'), 'stake': 10}))
    ok(b.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Marc'), 'stake': 10}))
    ok(c.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Marc'), 'stake': 4}))
    ok(d.rpc('prono_answer', id=p['id'], answer={'option_id': opt(p, 'Léa')}))
    close_now(p['id'])
    done = ok(a.rpc('prono_result', id=p['id'], body={'option_id': opt(p, 'Léa')}))
    assert done['result']['by_player'] and done['contest']['open'] and not done['contest']['can_contest']  # l'organisateur
    refused(a.rpc('prono_contest', id=p['id'], reason='Non'), 'forbidden')
    refused(b.rpc('prono_contest', id=p['id'], reason='On paie 10 balles'), 'content_refused')
    seen = ok(b.rpc('prono_contest', id=p['id'], reason='Marc a gagné la 2e manche'))
    assert seen['contest']['contested'] and seen['contest']['unfair'] == 1 and seen['contest']['my_vote'] is False
    refused(b.rpc('prono_contest', id=p['id'], reason='Encore'), 'already')
    told = sql(f"select user_id from public.notifications where kind = 'prono_contest' and data->>'prono_id' = '{p['id']}'")
    assert {r['user_id'] for r in told} == {a.uid, c.uid, d.uid}
    refused(a.rpc('prono_contest_vote', id=p['id'], fair=True), 'forbidden')
    ok(d.rpc('prono_contest_vote', id=p['id'], fair=True))
    gone = ok(c.rpc('prono_contest_vote', id=p['id'], fair=False))  # 2 « pas juste » contre 1 : annulé, tout rendu
    assert gone['state'] == 'cancelled' and gone['cancel_reason'] == 'contest' and gone['settled']
    assert [bag(x, group) for x in (a, b, c)] == [100, 100, 100]
    assert ok(b.rpc('prono_board', group_id=group))['pronos'] == 0  # aucun point


def test_contest_confirmed_then_paid_and_late_contest_closed(people, group):
    a, b, c, d = people
    p = ok(create(a, question='Qui finit la rando en premier ?', kind='person', group_id=group, patates=True))
    ok(b.rpc('prono_answer', id=p['id'], answer={'person_id': c.uid, 'stake': 10}))
    ok(c.rpc('prono_answer', id=p['id'], answer={'person_id': d.uid, 'stake': 10}))
    ok(d.rpc('prono_answer', id=p['id'], answer={'person_id': c.uid, 'stake': 10}))
    close_now(p['id'])
    ok(a.rpc('prono_result', id=p['id'], body={'person_id': c.uid}))
    ok(c.rpc('prono_contest', id=p['id'], reason='Zoé a coupé par le chemin'))
    ok(b.rpc('prono_contest_vote', id=p['id'], fair=True))
    kept = ok(d.rpc('prono_contest_vote', id=p['id'], fair=True))  # 2 « juste » contre 1 : versé tout de suite
    assert kept['state'] == 'done' and kept['settled'] and not kept['contest']['vote_open']
    assert {x['user']['id']: x['harvest'] for x in kept['answers']} == {b.uid: 15, c.uid: 0, d.uid: 15}
    refused(d.rpc('prono_contest', id=p['id'], reason='Trop tard'), 'closed')

    q = ok(create(b, question='Qui arrive le premier ?', kind='person', group_id=group))
    ok(c.rpc('prono_answer', id=q['id'], answer={'person_id': a.uid}))
    close_now(q['id'])
    ok(b.rpc('prono_result', id=q['id'], body={'person_id': d.uid}))
    sql(f"update private.pronos set contest_until = now() - interval '1 second' where id = '{q['id']}'")
    refused(c.rpc('prono_contest', id=q['id'], reason='Pas vu'), 'closed')


def test_reactions_toggle(people, group):
    a, b, _, _ = people
    p = ok(create(a, question='Qui chante le mieux ?', kind='person', group_id=group))
    ok(a.rpc('prono_react', id=p['id'], emoji='🔥'))
    r = ok(b.rpc('prono_react', id=p['id'], emoji='🔥'))
    assert r['reactions'] == [{'emoji': '🔥', 'count': 2, 'mine': True}]
    r = ok(b.rpc('prono_react', id=p['id'], emoji='🔥'))
    assert r['reactions'] == [{'emoji': '🔥', 'count': 1, 'mine': False}]
    refused(b.rpc('prono_react', id=p['id'], emoji='💰'), 'invalid')
    assert ok(b.rpc('prono_react', id=p['id'], emoji='🎊'))['reactions'][0]['emoji'] in ('🔥', '🎊')  # 🎊 (ex-🥔)


def test_award_needs_three_voters_and_people_can_opt_out(people, group):
    a, b, c, d = people
    refused(create(a, kind='award', award='plus_bourre', group_id=group), 'invalid')
    refused(create(a, kind='award', award='ambiance', group_id=group, patates=True), 'invalid')
    t = ok(create(a, kind='award', award='voix', group_id=group, points=1, question=''))
    assert t['question'] == 'Qui mérite le trophée « Voix d\'or » ?' and t['award'] == 'voix' and t['award_emoji'] == '🎤'
    assert t['award_label'] == "🎤 Voix d'or" and t['award_name'] == "Voix d'or" and t['points'] == 1
    assert [r['id'] for r in sql('select id from private.prono_award_categories order by position')] == \
        ['ambiance', 'piste', 'fou_rire', 'look', 'chef', 'voix', 'accueil', 'danse']
    assert t['reveal'] == 'result' and a.uid not in {x['id'] for x in t['candidates']} and t['optout'] is False
    refused(a.rpc('prono_answer', id=t['id'], answer={'person_id': a.uid}), 'invalid')  # pas pour soi
    ok(a.rpc('prono_answer', id=t['id'], answer={'person_id': b.uid}))
    out = ok(b.rpc('prono_optout', id=t['id'], out=True))  # Marc se retire : le vote reçu part
    assert out['optout'] and len(out['answered']) == 0
    card = next(x for x in ok(c.rpc('prono_list', group_id=group)) if x['id'] == t['id'])
    assert {f['id'] for f in card['candidates']} == {a.uid, d.uid}  # ni soi-même, ni Marc (retiré)
    refused(c.rpc('prono_answer', id=t['id'], answer={'person_id': b.uid}), 'invalid')
    ok(b.rpc('prono_optout', id=t['id'], out=False))
    ok(a.rpc('prono_answer', id=t['id'], answer={'person_id': b.uid}))
    ok(c.rpc('prono_answer', id=t['id'], answer={'person_id': b.uid}))
    ok(d.rpc('prono_answer', id=t['id'], answer={'person_id': c.uid}))
    assert ok(c.rpc('prono_get', id=t['id']))['answers'] is None  # caché jusqu'au dévoilement
    refused(a.rpc('prono_result', id=t['id'], body={'person_id': b.uid}), 'invalid')  # tranché par les votes
    done = ok(a.rpc('prono_close_now', id=t['id']))
    assert done['state'] == 'done' and [(x['id'], x['votes']) for x in done['result']['people']] == [(b.uid, 2)]
    mine = {x['user']['id']: x['person'] for x in ok(c.rpc('prono_get', id=t['id']))['answers']}
    assert mine[c.uid]['id'] == b.uid and mine[a.uid] is None  # les votes des autres restent secrets
    assert done['contest'] is None and done['rarity'] is None
    note = sql(f"select body from public.notifications where kind = 'prono_result' and user_id = '{b.uid}' and data->>'prono_id' = '{t['id']}'")
    assert note and note[0]['body'].startswith("C'est toi")

    few = ok(create(b, kind='award', award='look', group_id=group))
    ok(a.rpc('prono_answer', id=few['id'], answer={'person_id': c.uid}))
    ok(c.rpc('prono_answer', id=few['id'], answer={'person_id': a.uid}))
    gone = ok(b.rpc('prono_close_now', id=few['id']))
    assert gone['state'] == 'cancelled' and gone['cancel_reason'] == 'few' and gone['answers'] is None


def test_majority_resolves_alone_and_a_tie_gives_back(people, group):
    a, b, c, d = people
    m = ok(create(b, question='Fondue ou raclette : que choisira la bande ?', kind='majority', options=['Fondue', 'Raclette'],
                  group_id=group, patates=True, reveal='result'))
    assert m['reveal'] == 'close'
    ok(a.rpc('prono_answer', id=m['id'], answer={'option_id': opt(m, 'Fondue'), 'stake': 4}))
    ok(b.rpc('prono_answer', id=m['id'], answer={'option_id': opt(m, 'Fondue'), 'stake': 6}))
    ok(c.rpc('prono_answer', id=m['id'], answer={'option_id': opt(m, 'Raclette'), 'stake': 5}))
    close_now(m['id'])
    tick()
    done = ok(c.rpc('prono_get', id=m['id']))
    assert done['state'] == 'done' and done['result']['option_id'] == opt(m, 'Fondue') and done['settled']
    assert done['contest'] is None and not done['can_result']
    # 15 dans le champ, 10 sur Fondue : 4 × 1,5 = 6 ; 6 × 1,5 = 9.
    assert {x['user']['id']: x['harvest'] for x in done['answers']} == {a.uid: 6, b.uid: 9, c.uid: 0}
    refused(a.rpc('prono_contest', id=m['id'], reason='Bof'), 'invalid')

    t = ok(create(d, question='Montagne ou mer ?', kind='majority', options=['Montagne', 'Mer'], group_id=group, patates=True))
    ok(a.rpc('prono_answer', id=t['id'], answer={'option_id': opt(t, 'Montagne'), 'stake': 7}))
    ok(c.rpc('prono_answer', id=t['id'], answer={'option_id': opt(t, 'Mer'), 'stake': 2}))
    close_now(t['id'])
    tick()
    tie = ok(a.rpc('prono_get', id=t['id']))
    assert tie['state'] == 'cancelled' and tie['cancel_reason'] == 'tie' and tie['settled']
    assert {x['user']['id']: x['harvest'] for x in tie['answers']} == {a.uid: 7, c.uid: 2}


def test_when_it_happened_and_number_without_going_over(people, group):
    a, b, c, d = people
    w = ok(create(c, question='À quelle heure Max arrive ?', kind='when', group_id=group, not_over=True, patates=True,
                  rules="D'après la sonnette."))
    assert w['can_happen'] and w['not_over'] and w['rules'] == "D'après la sonnette."
    base = datetime.now(timezone.utc)
    ok(a.rpc('prono_answer', id=w['id'], answer={'answer_at': (base + timedelta(hours=1)).isoformat(), 'stake': 5}))
    ok(b.rpc('prono_answer', id=w['id'], answer={'answer_at': (base + timedelta(minutes=90)).isoformat(), 'stake': 5}))
    ok(d.rpc('prono_answer', id=w['id'], answer={'answer_at': (base + timedelta(minutes=110)).isoformat(), 'stake': 5}))
    refused(c.rpc('prono_update', id=w['id'], body={'rules': 'Autre règle'}), 'locked')
    more = ok(c.rpc('prono_update', id=w['id'], body={'rules': "D'après la sonnette. Pas la fenêtre."}))
    assert more['rules'].endswith('Pas la fenêtre.')
    happened = (base + timedelta(minutes=105)).isoformat()
    done = ok(c.rpc('prono_result', id=w['id'], body={'time': happened}))  # « C'est arrivé ! » pendant que c'est ouvert
    assert done['state'] == 'done' and done['result']['time'] and [x['id'] for x in done['winners']] == [b.uid]

    n = ok(create(d, question='Combien de crêpes ce soir ?', kind='number', group_id=group, not_over=True))
    for who, v in ((a, 10), (b, 14), (c, 16)):
        ok(who.rpc('prono_answer', id=n['id'], answer={'number': v}))
    close_now(n['id'])
    assert [x['id'] for x in ok(d.rpc('prono_result', id=n['id'], body={'number': 15}))['winners']] == [b.uid]


def test_words_money_betting_sites_and_selling_patates_are_refused(people, group):
    a = people[0]
    for q in ('Qui vend ses confettis ?', 'Je te rachète tes confettis ?', 'Confettis à vendre ?', 'Qui vend ses patates ?', 'Betclic ou Winamax ?', 'On joue au casino ?',
              'Mise de 10 CHF ?', 'Qui paie la tournée ?'):
        refused(create(a, question=q, kind='yesno', group_id=group), 'content_refused')
    ok(create(a, question='Purée ou frites de patates ?', kind='majority', options=['Purée', 'Frites'], group_id=group))


def test_report_with_the_money_reason(people, group):
    a, b, _, _ = people
    p = ok(create(a, question='Le mot de la soirée ?', kind='text', group_id=group))
    r = b.rpc('report_content', p_kind='prono', p_target=p['id'], p_reason='money')
    assert r.status_code == 200, r.text
    ok(b.rpc('prono_answer', id=p['id'], answer={'text': 'Banane'}))
    close_now(p['id'])
    r2 = a.rpc('prono_report_answer', id=p['id'], author=b.uid, reason='money')
    assert r2.status_code == 200, r2.text
    sql(f"delete from public.content_reports where id in ('{r.json()}', '{r2.json()}')")


def test_templates_are_clean(people):
    t = ok(people[0].rpc('prono_templates'))
    assert len(t) >= 20 and {x['kind'] for x in t} >= {'yesno', 'overunder', 'when', 'majority', 'award', 'person', 'number', 'choice', 'text'}
    award = next(x for x in t if x['kind'] == 'award')
    assert len(award['awards']) == 8 and all(set(x) == {'id', 'emoji', 'label'} for x in award['awards'])
    assert all(x['family'] in ('soiree', 'sport', 'bande', 'votes') for x in t) and award['family'] == 'votes'
    assert len({x['id'] for x in t}) == len(t) and sum(1 for x in t if x.get('rules')) >= 8
    sql("select private.prono_text(t->>'question', 'q'), private.prono_text(coalesce(t->>'rules', 'ok'), 'r') "
        "from jsonb_array_elements(public.prono_templates()) t")
    text = str(t).lower()
    for word in ('mise', 'pari ', 'cote', 'gain', 'jackpot', 'alcool', 'bière', 'shot', 'chf'):
        assert word not in text, word


def test_every_template_is_created_as_the_creation_screen_sends_it(people, group):
    """Corps exact de l'écran de création (W3) pour chaque modèle : options [] sauf choice / majority, question « »
    pour un trophée (la base l'écrit), rules et template ; retour : id et link.path."""
    who = people[1:]  # 21 modèles : répartis (30 créations par jour et par personne au plus)
    for i, tpl in enumerate(ok(people[0].rpc('prono_templates'))):
        body = {'question': '' if tpl['kind'] == 'award' else tpl['question'], 'kind': tpl['kind'],
                'options': tpl.get('options', []) if tpl['kind'] in ('choice', 'majority') else [],
                'points': 3, 'closes_at': later(), 'reveal': 'close', 'group_id': group, 'event_id': None,
                'people': [], 'link': i == 0, 'template': tpl['id'], 'rules': tpl.get('rules') or '',
                'patates': tpl['kind'] not in ('award', 'text'), 'line': tpl.get('line'), 'not_over': False,
                'award': tpl.get('award')}
        p = ok(who[i % 3].rpc('prono_create', body=body))
        assert p['id'] and p['template'] == tpl['id'] and p['rules'] == tpl.get('rules')
        assert (p['link']['path'] or '').startswith('/prono/') if i == 0 else p['link']['path'] is None
        if tpl['kind'] == 'yesno':
            assert [o['label'] for o in p['options']] == ['Oui', 'Non']
        if tpl['kind'] == 'overunder':
            assert len(p['options']) == 2 and p['options'][0]['label'].startswith('Plus de ')
        if tpl['kind'] == 'award':
            assert p['question'] == 'Qui mérite le trophée « Ambianceur·euse » ?' and not p['patates']
    assert ok(people[1].rpc('prono_bag', group_id=group))['balance'] == 100  # patates allumées : le sac existe


def test_no_direct_access_to_tables_or_bag_functions(people):
    a = people[0]
    for table in ('prono_bags', 'prono_bag_moves', 'prono_contests', 'prono_contest_votes', 'prono_reactions',
                  'prono_optouts', 'prono_settings', 'prono_award_categories'):
        assert a.get(table).status_code >= 400
        assert sql(f"select has_table_privilege('authenticated', 'private.{table}', 'select') as s")[0]['s'] is False
    assert a.rpc('prono_bag_add', t='g:x', uid=a.uid, pid=None, delta=100, why='harvest').status_code >= 400
    assert sql("select has_function_privilege('authenticated', 'private.prono_bag_add(text,uuid,uuid,int,text)', 'execute') as s")[0]['s'] is False
    assert sql("select count(*) as n from pg_proc where proname ~ '(give|transfer|gift|send)' and proname like 'prono%'")[0]['n'] == 0


def test_patates_switch_in_the_database(people, group):
    a, b, _, _ = people
    p = ok(create(a, question='Qui gagne aux fléchettes ?', kind='person', group_id=group, patates=True))
    set_patates(False)
    try:
        refused(create(a, question='Qui gagne au ping-pong ?', kind='person', group_id=group, patates=True), 'forbidden')
        honour = ok(create(a, question='Qui gagne au ping-pong ?', kind='person', group_id=group))
        refused(a.rpc('prono_update', id=honour['id'], body={'patates': True}), 'forbidden')
        refused(b.rpc('prono_answer', id=p['id'], answer={'person_id': a.uid, 'stake': 5}), 'forbidden')
        off = ok(b.rpc('prono_answer', id=p['id'], answer={'person_id': a.uid}))  # pour l'honneur, toujours
        assert off['patates_on'] is False
        assert all(x['patates_on'] is False for x in ok(b.rpc('prono_list', group_id=group)))
        assert ok(b.rpc('prono_bag', group_id=group)) is None
        assert ok(b.rpc('prono_bag_history', group_id=group)) == []
        assert ok(b.rpc('prono_season', group_id=group)) is None
    finally:
        set_patates(True)
    on = ok(b.rpc('prono_answer', id=p['id'], answer={'stake': 5}))
    assert on['patates_on'] and on['my_answer']['stake'] == 5 and bag(b, group) == 95


def test_one_hour_before_the_end_only_those_who_have_not_played_are_reminded(people, group):
    a, b, c, d = people
    p = ok(create(a, question="Qui arrive à l'heure ?", kind='person', group_id=group))
    ok(b.rpc('prono_answer', id=p['id'], answer={'person_id': c.uid}))
    sql(f"update private.pronos set created_at = now() - interval '2 hours', closes_at = now() + interval '30 minutes' where id = '{p['id']}'")
    tick()
    tick()  # une seule fois
    rows = sql(f"select user_id from public.notifications where kind = 'prono_soon' and data->>'prono_id' = '{p['id']}'")
    assert sorted(r['user_id'] for r in rows) == sorted([c.uid, d.uid])
