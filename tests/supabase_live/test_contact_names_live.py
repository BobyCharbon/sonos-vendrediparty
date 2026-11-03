"""Noms des contacts sur la VRAIE base de TEST : l'empreinte d'un numéro retrouve le compte, sans jamais renvoyer ni
garder de numéro ou d'empreinte ; limite de débit. Lancement :
SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_contact_names_live.py -q"""
import hashlib
import hmac
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.supabase_live.test_member_admin_live import GUESTS, Session, pytestmark  # noqa: F401

SBQ = Path(__file__).resolve().parents[2] / "supabase/tools/sbq.py"


def sql(query: str, rw: bool = False) -> list:
    out = subprocess.run([sys.executable, str(SBQ), "test", *(["rw"] if rw else [])], input=query,
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def digest(key: str, e164: str) -> str:
    return hmac.new(key.encode(), e164.encode(), hashlib.sha256).hexdigest()


@pytest.fixture(scope="module")
def pair():
    a, b = Session(GUESTS[0]), Session(GUESTS[1])
    sql(f"delete from private.contact_match_calls where user_id in ('{a.uid}', '{b.uid}')", rw=True)
    return a, b


def test_a_number_in_my_contacts_finds_the_account_and_nothing_else(pair):
    a, b = pair
    key = a.rpc("contacts_key").json()
    assert isinstance(key, str) and len(key) == 64
    mine, theirs, stranger = (digest(key, "+" + GUESTS[0]), digest(key, "+" + GUESTS[1]), digest(key, "+41790009999"))
    r = a.rpc("contacts_match", hashes=[theirs, mine, stranger])
    assert r.status_code == 200, r.text
    assert r.json() == [{"user_id": b.uid, "hash": theirs}]  # pas moi, pas l'inconnu, aucun numéro
    assert GUESTS[1] not in r.text


def test_nothing_sent_is_kept(pair):
    a, _ = pair
    key = a.rpc("contacts_key").json()
    probe = digest(key, "+41790000002")
    a.rpc("contacts_match", hashes=[probe])
    rows = sql(f"select c::text as row from private.contact_match_calls c where c.user_id = '{a.uid}'")
    assert rows and all(probe not in r["row"] and GUESTS[1] not in r["row"] for r in rows)
    cols = sql("select string_agg(column_name, ',' order by column_name) c from information_schema.columns "
               "where table_schema = 'private' and table_name = 'contact_match_calls'")
    assert cols[0]["c"] == "at,hashes,user_id"


def test_invalid_hashes_and_anonymous_calls_are_refused(pair):
    a, _ = pair
    assert a.rpc("contacts_match", hashes=["+41790000002"]).status_code == 400
    anon = {k: v for k, v in a.headers.items() if k != "Authorization"}
    import httpx
    from tests.supabase_live.test_member_admin_live import TEST_URL
    assert httpx.post(f"{TEST_URL}/rest/v1/rpc/contacts_key", headers=anon, json={}, timeout=30).status_code in (401, 403)


def test_rate_limit_after_twelve_calls_an_hour(pair):
    _, b = pair
    sql(f"delete from private.contact_match_calls where user_id = '{b.uid}'", rw=True)
    for _ in range(12):
        assert b.rpc("contacts_match", hashes=[]).status_code == 200
    limited = b.rpc("contacts_match", hashes=[])
    assert limited.status_code >= 400 and "Trop de demandes" in limited.text
    sql(f"delete from private.contact_match_calls where user_id = '{b.uid}'", rw=True)
