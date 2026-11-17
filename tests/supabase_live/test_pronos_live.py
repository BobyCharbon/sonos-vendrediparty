"""Pronos entre amis (avis f071c5f46e3d, migration 20261117180000) sur la VRAIE base de TEST, comptes de test à code fixe :
pour l'honneur (argent, mise, alcool refusés), réponses cachées par la base jusqu'au dévoilement, résultat et gagnants,
points et classement du groupe, lien, blocage, signalement et masquage, rappel à l'organisateur.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_pronos_live.py -q"""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tests.supabase_live.test_agenda_live import ok, refused
from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A, GUEST_B, complete_profile
from tests.supabase_live.test_member_admin_live import TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def later(minutes=60) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def close_now(pid: str):
    """La fin passe (comme si l'heure était arrivée), sans attendre."""
    sql(f"update private.pronos set closes_at = now() - interval '1 second' where id = '{pid}'")


@pytest.fixture(scope='module')
def people():
    owner, friend, third = Session(GUEST_A), Session(GUEST_B), Session(ADMIN)
    complete_profile(owner, 'Prono Léa')
    complete_profile(friend, 'Prono Marc')
    for a, b in ((owner, friend), (owner, third), (friend, third)):
        a.rpc('set_direct_block', target=b.uid, blocked=False)
        b.rpc('set_direct_block', target=a.uid, blocked=False)
    yield owner, friend, third
    sql(f"delete from private.pronos where created_by in ('{owner.uid}', '{friend.uid}', '{third.uid}')")
    sql(f"delete from public.notifications where kind like 'prono%' and user_id in ('{owner.uid}', '{friend.uid}', '{third.uid}')")


@pytest.fixture(scope='module')
def group(people):
    owner, friend, third = people
    r = httpx.post(f'{TEST_URL}/rest/v1/member_groups', headers={**owner.headers, 'Prefer': 'return=representation'},
                   json={'name': 'Pronos recette'}, timeout=30)
    assert r.status_code == 201, r.text
    gid = r.json()[0]['id']
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{gid}', '{friend.uid}') on conflict do nothing")
    yield gid
    sql(f"delete from public.member_groups where id = '{gid}'")


def create(who, **body):
    return who.rpc('prono_create', body={'closes_at': later(), 'points': 3, **body})


def test_answers_stay_hidden_from_everyone_until_the_result_then_winners_score(people, group):
    owner, friend, third = people
    p = ok(create(owner, question='Qui marque le premier but samedi ?', kind='choice', options=['Max', 'Jo', 'Personne'],
                  group_id=group, reveal='result'))
    assert p['state'] == 'open' and p['revealed'] is False and p['mine'] and p['can_edit']
    assert p['players'] == 2 and p['group']['id'] == group
    # Prévenu, sauf l'organisateur ; un compte hors du groupe ne voit rien.
    assert sql(f"select count(*) as n from public.notifications where kind = 'prono_new' and data->>'prono_id' = '{p['id']}' and user_id = '{friend.uid}'")[0]['n'] == 1
    assert sql(f"select count(*) as n from public.notifications where kind = 'prono_new' and data->>'prono_id' = '{p['id']}' and user_id = '{owner.uid}'")[0]['n'] == 0
    refused(third.rpc('prono_get', id=p['id']), 'not_found')
    refused(third.rpc('prono_answer', id=p['id'], answer={'option_id': p['options'][0]['id']}), 'not_found')

    jo, maxi = p['options'][1]['id'], p['options'][0]['id']
    ok(friend.rpc('prono_answer', id=p['id'], answer={'option_id': maxi}))
    mine = ok(friend.rpc('prono_answer', id=p['id'], answer={'option_id': jo}))  # change d'avis jusqu'à la fin
    assert mine['my_answer']['option_id'] == jo
    ok(owner.rpc('prono_answer', id=p['id'], answer={'option_id': maxi}))
    seen = ok(owner.rpc('prono_get', id=p['id']))
    # L'organisateur voit QUI a joué, jamais QUOI : ni réponses, ni comptes par choix.
    assert {f['id'] for f in seen['answered']} == {owner.uid, friend.uid}
    assert seen['answers'] is None and all(o['count'] is None for o in seen['options'])
    assert seen['locked'] and not seen['can_edit']
    refused(owner.rpc('prono_update', id=p['id'], body={'question': 'Autre question ?'}), 'locked')
    moved = ok(owner.rpc('prono_update', id=p['id'], body={'closes_at': later(120)}))
    assert moved['closes_at'] != p['closes_at']

    refused(owner.rpc('prono_result', id=p['id'], body={'option_id': jo}), 'invalid')  # pas avant la fin
    close_now(p['id'])
    shut = ok(friend.rpc('prono_get', id=p['id']))
    assert shut['state'] == 'closed' and shut['answers'] is None  # « à la fin » non choisi : toujours caché
    refused(friend.rpc('prono_answer', id=p['id'], answer={'option_id': maxi}), 'closed')
    refused(friend.rpc('prono_result', id=p['id'], body={'option_id': jo}), 'forbidden')
    done = ok(owner.rpc('prono_result', id=p['id'], body={'option_id': jo}))
    assert done['state'] == 'done' and done['revealed']
    assert [w['id'] for w in done['winners']] == [friend.uid]
    assert {o['label']: o['count'] for o in done['options']} == {'Max': 1, 'Jo': 1, 'Personne': 0}
    note = sql(f"select body from public.notifications where kind = 'prono_result' and user_id = '{friend.uid}' and data->>'prono_id' = '{p['id']}'")
    assert note and note[0]['body'].startswith('Tu avais vu juste : +3 points')

    board = ok(friend.rpc('prono_board', group_id=group))
    assert board['pronos'] == 1 and board['rows'][0]['user']['id'] == friend.uid and board['rows'][0]['points'] == 3
    refused(friend.rpc('prono_board_reset', group_id=group), 'forbidden')
    assert ok(owner.rpc('prono_board_reset', group_id=group))['rows'] == []


def test_honour_only_money_bets_and_drinks_are_refused(people, group):
    owner, _, _ = people
    for q in ('Qui paie la tournée ?', 'Mise de 10 CHF sur Max ?', 'On parie 5 € ?', 'Qui sera le plus bourré ?',
              'Le perdant fait un TWINT ?'):
        refused(create(owner, question=q, kind='number', group_id=group), 'content_refused')
    refused(create(owner, question='Qui gagne ?', kind='choice', options=['Max', 'Jo paie 20.-'], group_id=group), 'content_refused')
    # « Paris » la ville reste permise (seuls « pari / parier » sont refusés).
    ok(create(owner, question='Paris ou Marseille en finale ?', kind='choice', options=['Paris', 'Marseille'], group_id=group))


def test_reveal_at_the_end_number_closest_and_person(people, group):
    owner, friend, _ = people
    n = ok(create(owner, question='Combien de minutes de retard pour Marc ?', kind='number', group_id=group, reveal='close', points=5))
    ok(friend.rpc('prono_answer', id=n['id'], answer={'number': 12}))
    ok(owner.rpc('prono_answer', id=n['id'], answer={'number': 30}))
    assert ok(friend.rpc('prono_get', id=n['id']))['answers'] is None
    close_now(n['id'])
    shown = ok(friend.rpc('prono_get', id=n['id']))
    assert shown['revealed'] and {a['user']['id']: float(a['number']) for a in shown['answers']} == {friend.uid: 12, owner.uid: 30}
    done = ok(owner.rpc('prono_result', id=n['id'], body={'number': 25}))
    assert [w['id'] for w in done['winners']] == [owner.uid]  # le plus proche ; l'organisateur joue aussi

    who = ok(create(owner, question='Qui arrive en dernier ?', kind='person', group_id=group))
    assert {c['id'] for c in who['candidates']} == {owner.uid, friend.uid}
    refused(friend.rpc('prono_answer', id=who['id'], answer={'person_id': people[2].uid}), 'invalid')
    ok(friend.rpc('prono_answer', id=who['id'], answer={'person_id': owner.uid}))
    close_now(who['id'])
    assert [w['id'] for w in ok(owner.rpc('prono_result', id=who['id'], body={'person_id': owner.uid}))['winners']] == [friend.uid]


def test_free_text_reveals_at_the_end_and_the_organizer_ticks_winners(people, group):
    owner, friend, _ = people
    t = ok(create(owner, question='Le score de la finale ?', kind='text', group_id=group, reveal='result'))
    assert t['reveal'] == 'close'  # réponse libre : l'organisateur doit lire les réponses
    ok(friend.rpc('prono_answer', id=t['id'], answer={'text': '2-1 pour Servette'}))
    assert not ok(owner.rpc('prono_get', id=t['id']))['can_result']
    close_now(t['id'])
    refused(owner.rpc('prono_result', id=t['id'], body={}), 'invalid')
    assert ok(owner.rpc('prono_result', id=t['id'], body={'winners': [friend.uid]}))['winners'][0]['id'] == friend.uid


def test_where_it_lives_groups_people_and_link(people, group):
    owner, friend, third = people
    vp = sql("select id from public.member_groups where system_key is not null limit 1")[0]['id']
    refused(create(owner, question='Qui vient ?', kind='number', group_id=vp), 'forbidden')
    refused(create(third, question='Qui vient ?', kind='number', group_id=group), 'forbidden')  # pas membre
    refused(create(owner, question='Qui vient ?', kind='number'), 'invalid')  # personne ne joue
    # Par lien : la personne se connecte puis joue ; l'organisateur arrête le lien.
    p = ok(create(owner, question='Combien de buts ce soir ?', kind='number', link=True))
    token = p['link']['token']
    assert token and p['link']['path'] == f'/prono/{token}'
    info = ok(third.rpc('prono_link_info', token=token))
    assert info['id'] == p['id'] and info['joined'] is False
    joined = ok(third.rpc('prono_join', token=token))
    assert joined['can_answer']
    ok(third.rpc('prono_answer', id=p['id'], answer={'number': 3}))
    assert any(c['id'] == p['id'] for c in ok(third.rpc('prono_list')))
    ok(owner.rpc('prono_set_link', id=p['id'], active=False))
    refused(friend.rpc('prono_join', token=token), 'not_found')


def test_a_block_keeps_people_out_of_each_others_pronos(people, group):
    owner, friend, _ = people
    p = ok(create(owner, question='Qui gagne le baby-foot ?', kind='choice', options=['Léa', 'Marc'], group_id=group))
    assert friend.rpc('set_direct_block', target=owner.uid, blocked=True).status_code == 204
    try:
        refused(friend.rpc('prono_get', id=p['id']), 'not_found')
        assert all(c['id'] != p['id'] for c in ok(friend.rpc('prono_list', group_id=group)))
    finally:
        assert friend.rpc('set_direct_block', target=owner.uid, blocked=False).status_code == 204


def test_report_and_hide_a_prono_and_a_free_answer(people, group):
    owner, friend, admin = people
    p = ok(create(owner, question='Le mot de la soirée ?', kind='text', group_id=group))
    ok(friend.rpc('prono_answer', id=p['id'], answer={'text': 'Banane'}))
    refused(owner.rpc('prono_report_answer', id=p['id'], author=friend.uid, reason='other'), 'not_found')  # pas dévoilée
    close_now(p['id'])
    rid = owner.rpc('prono_report_answer', id=p['id'], author=friend.uid, reason='other')
    assert rid.status_code == 200, rid.text
    ok(admin.rpc('moderation_act', p_report=rid.json(), p_action='hide'))
    a = ok(owner.rpc('prono_get', id=p['id']))['answers'][0]
    assert a['hidden'] and a['text'] is None
    rq = friend.rpc('report_content', p_kind='prono', p_target=p['id'], p_reason='spam')
    assert rq.status_code == 200, rq.text
    ok(admin.rpc('moderation_act', p_report=rq.json(), p_action='hide'))
    refused(friend.rpc('prono_get', id=p['id']), 'not_found')


def test_cancel_scores_nothing_and_the_organizer_is_reminded_after_the_end(people, group):
    owner, friend, _ = people
    p = ok(create(owner, question='Il pleut samedi ?', kind='choice', options=['Oui', 'Non'], group_id=group, reveal='result'))
    ok(friend.rpc('prono_answer', id=p['id'], answer={'option_id': p['options'][0]['id']}))
    refused(owner.rpc('prono_delete', id=p['id']), 'locked')
    close_now(p['id'])
    sql('select private.prono_tick()')
    due = sql(f"select title from public.notifications where kind = 'prono_due' and user_id = '{owner.uid}' and data->>'prono_id' = '{p['id']}'")
    assert due and due[0]['title'] == '🔮 Les pronos sont fermés'
    assert ok(owner.rpc('prono_badge'))['to_result'] >= 1
    gone = ok(owner.rpc('prono_cancel', id=p['id']))
    assert gone['state'] == 'cancelled' and gone['answers'] is None  # jamais dévoilées : elles restent cachées
    owner.rpc('prono_delete', id=p['id']).raise_for_status()
