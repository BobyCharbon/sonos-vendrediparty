"""Contrôle Apple du 26.11, tour 2 (migration 20261126140000) sur la VRAIE base de TEST (jamais la prod) :
- Pot commun : un membre ajouté par la base (pot d'un événement) n'a PAS ses moyens de paiement montrés aux autres, tant
  qu'il ne le décide pas (tc_set_show_payment) ; qui crée le pot ou y entre par le lien les montre ; le nom reste visible ;
  la règle vaut pour tc_state (tc_group_json) ET pour la lecture directe de tc_payment (RLS) ;
- le nom d'un groupe se signale (type 'group') par un membre, jamais par un inconnu ; « Masquer » le remplace ;
- photos d'un événement (chat-photos) : la règle exige d'être dans la discussion (event_chat_member).
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_pot_paiement_geste_live.py -q"""
import httpx
import pytest

from app import accounts as accounts_mod, group_admin as ga, tricount as tcmod
from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B, VIP
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def token(s: Session) -> str:
    return s.headers['Authorization'].removeprefix('Bearer ')


@pytest.fixture
def people(monkeypatch):
    for mod in (accounts_mod, ga, tcmod):
        monkeypatch.setattr(mod, 'SUPABASE_URL', TEST_URL, raising=False)
    monkeypatch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    relay = tcmod.Tricount(ga.GroupAdmin(accounts_mod.Accounts(b'secret', httpx.Client(timeout=30))), lambda: "https://x")
    a, b, c = Session(GUEST_A), Session(GUEST_B), Session(VIP)
    pays = {s.uid: sql(f"select iban, holder, links, note from public.tc_payment where user_id = '{s.uid}'") for s in (a, b)}
    terms = {s.uid: sql(f"select version, accepted_at from public.terms_acceptances where user_id = '{s.uid}'") for s in (a, b, c)}
    created = {"pots": [], "groups": []}
    try:
        for s in (a, b, c):
            s.rpc('accept_terms', p_version=s.rpc('my_terms').json()['version'])
        yield relay, a, b, c, created
    finally:
        for grp in created["pots"]:
            sql(f"delete from public.tc_groups where id = '{grp}'")
        for grp in created["groups"]:
            sql(f"delete from public.content_reports where target_kind = 'group' and target_id = '{grp}'")
            sql(f"delete from public.member_groups where id = '{grp}'")
        for uid, rows in pays.items():
            sql(f"delete from public.tc_payment where user_id = '{uid}'")
            for p in rows:
                sql("insert into public.tc_payment (user_id, iban, holder, links, note) values "
                    f"('{uid}', {q(p['iban'])}, {q(p['holder'])}, '{__import__('json').dumps(p['links'] or {})}'::jsonb, {q(p['note'])})")
        for uid, rows in terms.items():
            sql(f"delete from public.terms_acceptances where user_id = '{uid}'")
            for row in rows:
                sql(f"insert into public.terms_acceptances (user_id, version, accepted_at) values "
                    f"('{uid}', '{row['version']}', '{row['accepted_at']}') on conflict do nothing")


def q(v):
    return "null" if v is None else "'" + str(v).replace("'", "''") + "'"


def test_payment_details_need_the_gesture_of_the_person(people):
    relay, a, b, c, created = people
    relay.set_payment(token(a), "CH93 0076 2011 6238 5295 7", "Léa Test", {}, "")
    relay.set_payment(token(b), "CH56 0483 5012 3456 7800 9", "Tom Test", {}, "")
    g = relay.create(token(a), "Pot geste (test)", "💸", "CHF", "Léa")
    created["pots"].append(g["id"])
    # Tom ajouté par la base (comme tc_event_sync pour un « Présent ») : pas de geste.
    sql(f"insert into public.tc_members (group_id, user_id, name) values ('{g['id']}', '{b.uid}', 'Tom')")

    seen_by_a = {m["name"]: m for m in relay.state(token(a), g["id"])["members"]}
    assert seen_by_a["Tom"]["payment"] is None and seen_by_a["Tom"]["show_payment"] is False
    assert seen_by_a["Léa"]["payment"]["holder"] == "Léa Test" and seen_by_a["Léa"]["show_payment"] is True
    seen_by_b = {m["name"]: m for m in relay.state(token(b), g["id"])["members"]}
    assert seen_by_b["Léa"]["payment"]["holder"] == "Léa Test"     # la créatrice les montre
    assert seen_by_b["Tom"]["payment"]["holder"] == "Tom Test"     # les siens, il les voit toujours
    # Lecture directe (RLS) : rien non plus, sauf si Tom les montre dans un AUTRE pot qu'ils partagent (profil unique).
    elsewhere = sql(f"""select count(*) n from public.tc_members mine join public.tc_members theirs on theirs.group_id = mine.group_id
                        where mine.user_id = '{a.uid}' and mine.left_at is null and theirs.user_id = '{b.uid}'
                          and theirs.left_at is null and theirs.show_payment""")[0]["n"]
    assert (a.get(f"tc_payment?user_id=eq.{b.uid}").json() == []) == (elsewhere == 0)

    # Son geste : « Montrer mes moyens de paiement dans ce pot ».
    st = relay.set_show_payment(token(b), g["id"], True)
    assert next(m for m in st["members"] if m["name"] == "Tom")["show_payment"] is True
    assert {m["name"]: m for m in relay.state(token(a), g["id"])["members"]}["Tom"]["payment"]["holder"] == "Tom Test"
    assert a.get(f"tc_payment?user_id=eq.{b.uid}").json()[0]["holder"] == "Tom Test"
    relay.set_show_payment(token(b), g["id"], False)
    assert {m["name"]: m for m in relay.state(token(a), g["id"])["members"]}["Tom"]["payment"] is None
    # Un inconnu ne règle rien dans un pot qui n'est pas le sien.
    r = c.rpc('tc_set_show_payment', p_group=g["id"], p_on=True)
    assert r.status_code >= 400 and 'forbidden' in r.text

    # Entrer par le lien = son geste ; déjà membre (ajouté d'office) qui rouvre le lien : rien ne change.
    link = g["link"].rsplit("/", 1)[1]
    relay.join(token(b), link, "Tom", None)
    assert sql(f"select show_payment from public.tc_members where group_id = '{g['id']}' and user_id = '{b.uid}'")[0]["show_payment"] is False
    sql(f"delete from public.tc_members where group_id = '{g['id']}' and user_id = '{b.uid}'")
    relay.join(token(b), link, "Tom", None)
    assert sql(f"select show_payment from public.tc_members where group_id = '{g['id']}' and user_id = '{b.uid}'")[0]["show_payment"] is True


def test_a_group_name_can_be_reported_and_hidden(people):
    _, a, b, c, created = people
    grp = sql(f"insert into public.member_groups (name, created_by) values ('Bande signalée (test)', '{a.uid}') returning id::text id")[0]['id']
    created["groups"].append(grp)
    sql(f"insert into public.member_group_members (group_id, user_id) values ('{grp}', '{b.uid}') on conflict do nothing")
    r = c.rpc('report_content', p_kind='group', p_target=grp, p_reason='harassment')
    assert r.status_code >= 400 and 'not_found' in r.text
    r = b.rpc('report_content', p_kind='group', p_target=grp, p_reason='harassment')
    assert r.status_code == 200, r.text
    rep = sql(f"select snapshot, target_user from public.content_reports where id = '{r.json()}'")[0]
    assert rep['target_user'] == a.uid and rep['snapshot']['text'] == 'Bande signalée (test)'
    assert rep['snapshot']['place'] == 'Nom du groupe'
    sql(f"select private.moderation_hide(r) from public.content_reports r where r.id = '{r.json()}'")
    assert sql(f"select name from public.member_groups where id = '{grp}'")[0]['name'] == 'Groupe renommé par la modération'
    # Membres Vendredi Party : jamais signalable.
    vp = sql("select id::text id from public.member_groups where system_key is not null limit 1")
    if vp:
        assert b.rpc('report_content', p_kind='group', p_target=vp[0]['id'], p_reason='spam').status_code >= 400


def test_event_chat_photos_need_to_be_in_the_chat():
    row = sql("select pg_get_expr(polqual, polrelid) q from pg_policy where polrelid = 'storage.objects'::regclass "
              "and polname = 'voir les photos d''un événement'")[0]
    assert 'event_chat_member' in row['q'] and 'can_see_event' not in row['q']
    receipts = sql("select pg_get_expr(polqual, polrelid) q from pg_policy where polrelid = 'storage.objects'::regclass "
                   "and polname = 'modération : voir un ticket signalé'")[0]
    assert 'tc_receipt_reported' in receipts['q']
