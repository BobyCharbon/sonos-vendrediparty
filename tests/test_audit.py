"""Journal des actions admin côté Party : qui a fait quoi, sur qui, quand. Ajout seul, jamais modifiable depuis l'app."""
import json

import pytest
from fastapi.testclient import TestClient

from app import accounts as accounts_mod, audit, main
from tests.test_accounts import ROOT_PERMS, fake_supabase


@pytest.fixture
def journal(tmp_path, monkeypatch):
    log = audit.AuditLog(tmp_path / 'audit.jsonl')
    monkeypatch.setattr(main, 'journal', log)
    return log


def test_entries_are_appended_newest_first_and_survive_a_restart(tmp_path):
    log = audit.AuditLog(tmp_path / 'audit.jsonl')
    log.record('admin.ban', actor='Code PIN', target={'id': 'g1', 'name': 'Léa'}, details={'minutes': 10})
    log.record('admin.kick', actor='Code PIN', target={'id': 'g2', 'name': 'Tom'})
    again = audit.AuditLog(tmp_path / 'audit.jsonl')  # serveur relancé
    entries = again.read()
    assert [e['action'] for e in entries] == ['admin.kick', 'admin.ban']
    assert entries[1]['target'] == {'id': 'g1', 'name': 'Léa'} and entries[1]['details'] == {'minutes': 10}
    assert all(isinstance(e['at'], float) and e['id'] for e in entries)


def test_read_is_paginated_and_a_corrupt_line_does_not_hide_the_rest(tmp_path):
    path = tmp_path / 'audit.jsonl'
    log = audit.AuditLog(path)
    for i in range(5):
        log.record('admin.kick', actor='Code PIN', target={'id': f'g{i}', 'name': f'N{i}'})
    with path.open('a') as f:
        f.write('{pas du json\n')
    page = log.read(limit=2)
    assert [e['target']['id'] for e in page] == ['g4', 'g3']
    older = log.read(limit=10, before=page[-1]['id'])
    assert [e['target']['id'] for e in older] == ['g2', 'g1', 'g0']


def test_free_text_is_truncated_so_the_journal_stays_small(tmp_path):
    log = audit.AuditLog(tmp_path / 'audit.jsonl')
    log.record('admin.rename', actor='x' * 500, target={'id': 'g', 'name': 'y' * 500}, details={'to': 'z' * 500})
    e = log.read()[0]
    assert len(e['actor']) <= 80 and len(e['target']['name']) <= 80 and len(e['details']['to']) <= 200


def test_pin_admin_actions_on_guests_are_logged_with_the_pin_as_author(journal):
    main.store.register_guest('g-lea', 'Léa', '10.0.0.5')
    with TestClient(main.app) as c:
        assert c.post('/api/admin/login', json={'pin': '9999'}).status_code == 200
        c.post('/api/admin/rename', json={'guest_id': 'g-lea', 'name': 'Léa B'})
        c.post('/api/admin/ban', json={'guest_id': 'g-lea', 'minutes': 10})
        c.post('/api/admin/unban', json={'guest_id': 'g-lea'})
        c.post('/api/admin/kick', json={'guest_id': 'g-lea'})
        entries = c.get('/api/admin/audit').json()['entries']
    actions = [e['action'] for e in entries]
    assert actions[:5] == ['admin.kick', 'admin.unban', 'admin.ban', 'admin.rename', 'admin.login']
    rename = entries[3]
    assert rename['actor'] == 'Code PIN' and rename['target'] == {'id': 'g-lea', 'name': 'Léa'} and rename['details'] == {'to': 'Léa B'}
    assert entries[2]['details'] == {'minutes': 10} and entries[2]['target']['name'] == 'Léa B'


def test_wrong_pin_attempts_are_logged_with_the_address(journal):
    with TestClient(main.app) as c:
        assert c.post('/api/admin/login', json={'pin': '0000'}).status_code == 401
    e = journal.read()[0]
    assert e['action'] == 'admin.login_failed' and e['actor'] == 'Inconnu' and e['ip']


def test_account_admin_is_named_in_the_journal_and_a_refused_account_is_logged(monkeypatch, journal):
    monkeypatch.setattr(main, 'ADMIN_PIN', '8462')
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', fake_supabase('root', perms=ROOT_PERMS)[0]))
    with TestClient(main.app) as c:
        assert c.post('/api/account/admin', json={'token': 'r' * 40}).status_code == 200
        c.post('/api/admin/pin', json={'pin': '4321'})
        entries = c.get('/api/admin/audit').json()['entries']
    assert entries[0]['action'] == 'admin.pin' and entries[0]['actor'] == 'Lulu'
    assert entries[1]['action'] == 'admin.login' and entries[1]['details'] == {'method': 'compte'}
    assert '4321' not in json.dumps(entries)  # jamais de code en clair dans le journal
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', fake_supabase('membre', perms=('events.view',))[0]))
    with TestClient(main.app) as c:
        assert c.post('/api/account/admin', json={'token': 'm' * 40}).status_code == 403
    assert journal.read()[0]['action'] == 'admin.denied' and journal.read()[0]['actor'] == 'Lulu'


def test_a_forged_author_cookie_falls_back_to_the_pin(journal):
    with TestClient(main.app) as c:
        c.post('/api/admin/login', json={'pin': '9999'})
        c.cookies.set('vp_admin_by', 'Faux%20Root.abcdef')
        c.post('/api/admin/kick', json={'guest_id': 'g-x'})
    assert journal.read()[0]['actor'] == 'Code PIN'


def test_the_journal_is_admin_only_and_has_no_write_route(journal):
    with TestClient(main.app) as c:
        assert c.get('/api/admin/audit').status_code == 401
        c.post('/api/admin/login', json={'pin': '9999'})
        assert c.get('/api/admin/audit').status_code == 200
        for method in ('post', 'put', 'delete', 'patch'):
            assert getattr(c, method)('/api/admin/audit').status_code == 405


def test_account_logins_are_logged_once_per_half_hour(monkeypatch, journal):
    monkeypatch.setattr(main, 'accounts', accounts_mod.Accounts(b'secret', fake_supabase('u-9')[0]))
    with TestClient(main.app) as c:
        for _ in range(3):
            assert c.post('/api/account/link', json={'token': 'z' * 40}).status_code == 200
    links = [e for e in journal.read() if e['action'] == 'account.link']
    assert len(links) == 1 and links[0]['actor'] == 'Lulu' and links[0]['target']['id'].startswith('acct-')
