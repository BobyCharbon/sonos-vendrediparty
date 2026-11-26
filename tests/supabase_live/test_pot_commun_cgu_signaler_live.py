"""Pot commun (contrôle Apple du 26.11, migration 20261126130000) sur la VRAIE base de TEST (jamais la prod) :
- sans CGU acceptées, créer un pot ou y écrire une dépense est refusé (terms_required → TermsRequired, 403 au serveur) ;
- une dépense se signale (type 'tc_expense') par un membre du pot, jamais par un inconnu ; « Masquer » efface titre,
  note et photo, le montant reste ;
- « complète ton profil » ne demande plus de photo.
Le réglage et les acceptations du compte sont remis tels quels.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_pot_commun_cgu_signaler_live.py -q"""
import httpx
import pytest

from app import accounts as accounts_mod, group_admin as ga, tricount as tcmod
from tests.supabase_live.test_audiences_live import GUEST_A, GUEST_B, VIP
from tests.supabase_live.test_member_admin_live import KEY_FILE, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


@pytest.fixture
def pot(monkeypatch):
    for mod in (accounts_mod, ga, tcmod):
        monkeypatch.setattr(mod, 'SUPABASE_URL', TEST_URL, raising=False)
    monkeypatch.setattr(accounts_mod, 'SUPABASE_ANON_KEY', KEY_FILE.read_text().strip())
    relay = tcmod.Tricount(ga.GroupAdmin(accounts_mod.Accounts(b'secret', httpx.Client(timeout=30))), lambda: "https://x")
    a, b, c = Session(GUEST_A), Session(GUEST_B), Session(VIP)
    was = sql("select terms_enforced from private.moderation_settings where id = 1")[0]['terms_enforced']
    kept = sql(f"select version, accepted_at from public.terms_acceptances where user_id = '{a.uid}'")
    created = []
    try:
        sql(f"delete from public.terms_acceptances where user_id = '{a.uid}'")
        sql("update private.moderation_settings set terms_enforced = true where id = 1")
        yield relay, a, b, c, created
    finally:
        sql(f"update private.moderation_settings set terms_enforced = {'true' if was else 'false'} where id = 1")
        sql(f"delete from public.terms_acceptances where user_id = '{a.uid}'")
        for row in kept:
            sql(f"insert into public.terms_acceptances (user_id, version, accepted_at) values "
                f"('{a.uid}', '{row['version']}', '{row['accepted_at']}') on conflict do nothing")
        for grp in created:
            sql(f"delete from public.content_reports where target_kind = 'tc_expense' and target_id in "
                f"(select id::text from public.tc_expenses where group_id = '{grp}')")
            sql(f"delete from public.tc_expenses where group_id = '{grp}'")  # parts comprises (cascade)
            sql(f"delete from public.tc_groups where id = '{grp}'")


def token(s: Session) -> str:
    return s.headers['Authorization'].removeprefix('Bearer ')


def test_the_pot_asks_for_the_terms_and_an_expense_can_be_reported(pot):
    relay, a, b, c, created = pot
    with pytest.raises(accounts_mod.TermsRequired):
        relay.create(token(a), "Pot CGU (test)", "💸", "CHF", "Léa")
    assert a.rpc('accept_terms', p_version=a.rpc('my_terms').json()['version']).json()['accepted'] is True
    g = relay.create(token(a), "Pot CGU (test)", "💸", "CHF", "Léa")
    created.append(g["id"])
    me = g["members"][0]["id"]
    relay.join(token(b), g["link"].rsplit("/", 1)[1], "Tom", None)
    g = relay.save_expense(token(a), g["id"], {"title": "Courses (test)", "note": "pour le week-end", "amount_cents": 4000,
                                               "paid_by": me, "shares": [{"member_id": me}]})
    expense = next(e for e in g["expenses"] if e["title"] == "Courses (test)")

    # Plus de CGU (nouvelle version, par exemple) : une nouvelle dépense est refusée, rien d'écrit.
    sql(f"delete from public.terms_acceptances where user_id = '{a.uid}'")
    with pytest.raises(accounts_mod.TermsRequired):
        relay.save_expense(token(a), g["id"], {"title": "Pas écrit (test)", "amount_cents": 100, "paid_by": me,
                                               "shares": [{"member_id": me}]})
    assert sql(f"select count(*) n from public.tc_expenses where group_id = '{g['id']}' and title = 'Pas écrit (test)'")[0]['n'] == 0

    # Signaler : un membre oui, un inconnu non (il ne voit pas la dépense).
    r = c.rpc('report_content', p_kind='tc_expense', p_target=expense["id"], p_reason='spam')
    assert r.status_code >= 400 and 'not_found' in r.text
    r = b.rpc('report_content', p_kind='tc_expense', p_target=expense["id"], p_reason='harassment')
    assert r.status_code == 200, r.text
    snap = sql(f"select snapshot, target_user from public.content_reports where id = '{r.json()}'")[0]
    assert snap['target_user'] == a.uid
    assert snap['snapshot']['text'] == "Courses (test)\npour le week-end"
    assert snap['snapshot']['bucket'] == 'tc-receipts' and snap['snapshot']['place'] == 'Pot commun · Pot CGU (test)'

    # « Masquer » de la modération : titre, note et photo effacés, le montant reste.
    sql(f"select private.moderation_hide(r) from public.content_reports r where r.id = '{r.json()}'")
    row = sql(f"select title, note, receipt_path, amount_cents from public.tc_expenses where id = '{expense['id']}'")[0]
    assert row == {"title": "Dépense masquée par la modération", "note": None, "receipt_path": None, "amount_cents": 4000}


def test_the_profile_message_no_longer_asks_for_a_photo():
    rows = sql("select proname, pg_get_functiondef(oid) d from pg_proc where proname in "
               "('join_group_by_link', 'join_event_by_link', 'claim_app_invite')")
    assert len(rows) == 3
    for row in rows:
        assert 'surnom et photo' not in row['d'], row['proname']
