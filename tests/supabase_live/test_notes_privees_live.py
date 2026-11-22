"""Notes privées sur un profil (avis ede29a5bb24e, migration 20261122132000) sur la VRAIE base de TEST, par l'API REST
comme l'app : l'auteur lit, modifie et efface sa note ; la personne notée et un autre compte ne la lisent JAMAIS (ni par
la fonction, ni par la table) ; 500 caractères au plus ; pas de note sur soi ; cascade à la suppression d'un compte.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_notes_privees_live.py -q"""
import httpx
import pytest

from tests.supabase_live.test_contact_names_live import sql
from tests.supabase_live.test_member_admin_live import GUESTS, TEST_URL, Session, pytestmark  # noqa: F401


@pytest.fixture(scope="module")
def trio():
    a, b, c = (Session(p) for p in GUESTS)
    clean = f"delete from public.member_notes where author_id in ('{a.uid}', '{b.uid}', '{c.uid}')"
    sql(clean, rw=True)
    yield a, b, c
    sql(clean, rw=True)


def test_only_the_author_reads_the_note(trio):
    a, b, c = trio
    r = a.rpc("member_note_set", target=b.uid, body="  Rencontré au paintball  ")
    assert r.status_code == 200, r.text
    assert r.json()["body"] == "Rencontré au paintball"
    assert a.rpc("member_note_get", target=b.uid).json()["body"] == "Rencontré au paintball"
    # La personne notée et un autre compte : rien, ni par la fonction ni par la table.
    assert b.rpc("member_note_get", target=b.uid).json() is None
    assert c.rpc("member_note_get", target=b.uid).json() is None
    for other in (b, c):
        rows = other.get(f"member_notes?select=*&target_id=eq.{b.uid}")
        assert rows.status_code == 200 and rows.json() == [], rows.text
        assert "paintball" not in other.get("member_notes?select=*").text
    # Personne n'écrit une note au nom d'un autre.
    forged = httpx.post(f"{TEST_URL}/rest/v1/member_notes", headers=c.headers,
                        json={"author_id": a.uid, "target_id": b.uid, "body": "piraté"}, timeout=30)
    assert forged.status_code >= 400
    assert a.rpc("member_note_get", target=b.uid).json()["body"] == "Rencontré au paintball"
    anon = {k: v for k, v in a.headers.items() if k != "Authorization"}
    assert "paintball" not in httpx.get(f"{TEST_URL}/rest/v1/member_notes?select=*", headers=anon, timeout=30).text


def test_edit_erase_and_limits(trio):
    a, b, _ = trio
    assert a.rpc("member_note_set", target=b.uid, body="v2").json()["body"] == "v2"
    assert a.rpc("member_note_set", target=b.uid, body="x" * 501).status_code >= 400
    assert a.rpc("member_note_set", target=a.uid, body="moi").status_code >= 400
    assert a.rpc("member_note_set", target=b.uid, body="   ").json() is None
    assert a.rpc("member_note_get", target=b.uid).json() is None


def test_notes_go_with_either_account():
    fks = sql("select confdeltype::text d, a.attname::text n from pg_constraint k join pg_attribute a "
              "on a.attrelid = k.conrelid and a.attnum = any(k.conkey) "
              "where k.conrelid = 'public.member_notes'::regclass and k.contype = 'f' order by n")
    assert [(r["n"], r["d"]) for r in fks] == [("author_id", "c"), ("target_id", "c")]
