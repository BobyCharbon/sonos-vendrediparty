"""Mes amis dans Party et invitations dans l'app (avis 84fab3987f68), sur la VRAIE base de TEST (jamais la prod) :
liste des amis sans numéro, lien personnel (aperçu avant connexion, renouvellement limité), parrainage noté une seule
fois par un compte de moins de 24 h, jamais soi-même, notification referral_join et son interrupteur ; « Invité par »
(lien Party, liens de groupe unique et réutilisable, lien d'événement) lisible seulement avec members.view_referrals.
Lancement : SUPABASE_LIVE_TESTS=1 python -m pytest tests/supabase_live/test_friends_invites_live.py -q"""
import uuid

import httpx
import pytest

from tests.supabase_live.test_audiences_live import create_event
from tests.supabase_live.test_invite_links_live import NEW, anon_rpc
from tests.supabase_live.test_member_admin_live import ADMIN_PHONE, GUESTS, TEST_URL, Session, pytestmark  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql


def reset(*uids: str):
    ids = ", ".join(f"'{u}'" for u in uids)
    sql(f"delete from private.app_referrals where invitee in ({ids}) or inviter in ({ids}); "
        f"delete from private.app_invites where user_id in ({ids}); "
        f"delete from private.invite_joins where user_id in ({ids}) or invited_by in ({ids}); "
        f"delete from public.notifications where kind = 'referral_join' and user_id in ({ids});")


@pytest.fixture(scope="module")
def pair():
    inviter, invitee = Session(GUESTS[0]), Session(GUESTS[1])
    inviter.set_nickname("Testeur 1")  # d'autres tests les renomment (« Guest A »…)
    invitee.set_nickname("Testeur 2")
    born = sql(f"select created_at::text c from public.profiles where id = '{invitee.uid}'")[0]["c"]
    reset(inviter.uid, invitee.uid)
    yield inviter, invitee
    reset(inviter.uid, invitee.uid)
    sql(f"update public.profiles set created_at = '{born}' where id = '{invitee.uid}'")
    sql(f"update public.notification_prefs set referral_joins = true where user_id = '{inviter.uid}'")


def test_every_role_may_invite_and_the_right_is_listed():
    roles = {r["key"] for r in sql("select key from public.roles")}
    granted = {r["role"] for r in sql("select role from public.role_permissions where perm = 'members.invite'")}
    assert roles and roles <= granted
    assert sql("select label from public.permissions where key = 'members.invite'") == [{"label": "Inviter dans Party"}]


def test_friends_list_returns_only_active_accounts_and_never_a_number(pair):
    inviter, invitee = pair
    r = inviter.rpc("contacts_friends", ids=[invitee.uid, inviter.uid, str(uuid.uuid4())])
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["id"] for row in rows] == [invitee.uid]  # pas moi, pas l'inconnu
    assert set(rows[0]) == {"id", "display_name", "avatar_url", "joined_at", "common_groups"}
    assert GUESTS[1] not in r.text and "role" not in r.text
    assert inviter.rpc("contacts_friends", ids=[str(uuid.uuid4())] * 2001).status_code >= 400
    assert anon_rpc("contacts_friends", ids=[invitee.uid]).status_code in (401, 403)


def test_personal_link_preview_before_sign_in_and_renewal(pair):
    inviter, _ = pair
    first = inviter.rpc("my_app_invite").json()
    assert inviter.rpc("my_app_invite").json()["token"] == first["token"]  # même lien tant qu'on ne le change pas
    assert anon_rpc("app_invite_preview", token=first["token"]).json() == {"inviter": "Testeur 1", "avatar_url": first_avatar(inviter)}
    assert anon_rpc("app_invite_preview", token=str(uuid.uuid4())).json() is None
    renewed = inviter.rpc("my_app_invite", renew=True).json()
    assert renewed["token"] != first["token"]
    assert anon_rpc("app_invite_preview", token=first["token"]).json() is None  # l'ancien ne marche plus
    for _ in range(4):
        assert inviter.rpc("my_app_invite", renew=True).status_code == 200
    limited = inviter.rpc("my_app_invite", renew=True)
    assert limited.status_code >= 400 and "5 fois" in limited.text
    sql(f"update private.app_invites set renewals = 0 where user_id = '{inviter.uid}'")


def first_avatar(s: Session) -> str | None:
    return s.get(f"profiles?select=avatar_url&id=eq.{s.uid}").json()[0]["avatar_url"]


def test_a_new_account_claims_once_and_the_inviter_is_notified(pair):
    inviter, invitee = pair
    token = inviter.rpc("my_app_invite").json()["token"]
    # Compte ancien : refusé (le lien sert aux nouveaux venus).
    old = invitee.rpc("claim_app_invite", token=token)
    assert old.status_code >= 400 and "déjà sur Party" in old.text
    # Soi-même : refusé.
    assert "propre lien" in inviter.rpc("claim_app_invite", token=token).text
    # Profil incomplet : refusé avant tout.
    assert "profile_incomplete" in Session(NEW).rpc("claim_app_invite", token=token).text
    sql(f"update public.profiles set created_at = now() - interval '1 hour' where id = '{invitee.uid}'")
    role_before = invitee.get(f"profiles?select=role&id=eq.{invitee.uid}").json()
    claimed = invitee.rpc("claim_app_invite", token=token)
    assert claimed.status_code == 200, claimed.text
    assert claimed.json() == {"new": True}  # l'invité ne reçoit pas le nom de l'inviteur (réservé aux admins)
    assert invitee.rpc("claim_app_invite", token=token).json() == {"new": False}  # une fois
    assert invitee.get(f"profiles?select=role&id=eq.{invitee.uid}").json() == role_before  # aucun droit donné
    notes = inviter.get("notifications?select=body,kind&kind=eq.referral_join").json()
    assert notes == [{"body": "Testeur 2 a rejoint Party grâce à toi", "kind": "referral_join"}]
    assert inviter.rpc("my_app_invite").json()["joined"] == 1  # le nombre seulement, pas la liste
    assert inviter.rpc("my_referrals").status_code == 404


def test_referral_join_respects_its_switch_on_every_channel(pair):
    inviter, _ = pair
    allowed = ("select private.web_push_allowed(n) a from public.notifications n "
               f"where n.user_id = '{inviter.uid}' and n.kind = 'referral_join'")
    sql(f"insert into public.notification_prefs (user_id) values ('{inviter.uid}') on conflict do nothing; "
        f"update public.notification_prefs set push_enabled = true, referral_joins = true where user_id = '{inviter.uid}'")
    assert sql(allowed) == [{"a": True}]  # Guest compris (may_receive_push)
    sql(f"update public.notification_prefs set referral_joins = false where user_id = '{inviter.uid}'")
    assert sql(allowed) == [{"a": False}]


def test_invited_by_is_recorded_for_every_link_and_shown_to_admins_only(pair):
    inviter, invitee = pair
    admin, third = Session(ADMIN_PHONE), Session(GUESTS[2])
    sql(f"delete from private.invite_joins where user_id in ('{invitee.uid}', '{third.uid}', '{admin.uid}')")
    # Rejoindre par lien exige un profil complet : d'autres tests peuvent avoir vidé celui du 3e compte de test.
    sql(f"update public.profiles set display_name = coalesce(nullif(display_name, ''), 'Testeur 3'), "
        f"first_name = coalesce(nullif(first_name, ''), 'Test'), last_name = coalesce(nullif(last_name, ''), 'Trois'), "
        f"avatar_url = coalesce(avatar_url, (select avatar_url from public.profiles where avatar_url is not null limit 1)) "
        f"where id = '{third.uid}'")
    assert sql("select role from public.role_permissions where perm = 'members.view_referrals'") == [{"role": "admin"}]
    r = httpx.post(f"{TEST_URL}/rest/v1/member_groups", timeout=30, headers={**inviter.headers, "Prefer": "return=representation"},
                   json={"name": "Test invité par", "created_by": inviter.uid})
    assert r.status_code == 201, r.text
    group = r.json()[0]["id"]
    event = create_event(admin, "Test invité par", visibility="invited")
    try:
        single = inviter.rpc("create_invite_link", k="group", target=group).json()
        assert invitee.rpc("join_group_by_link", token=single).json() == group
        reusable = inviter.rpc("group_invite_link", grp=group).json()
        assert third.rpc("join_group_by_link", token=reusable).json() == group
        link = admin.rpc("create_invite_link", k="event", target=event).json()
        assert invitee.rpc("join_event_by_link", token=link).json() == event

        seen = admin.rpc("member_invited_by", target=invitee.uid).json()
        assert {(x["via"], x["inviter"], x["target_name"]) for x in seen} >= {
            ("group", "Testeur 1", "Test invité par"), ("event", "Admin test", "Test invité par")}
        assert all(x["at"] for x in seen)
        by_reusable = admin.rpc("member_invited_by", target=third.uid).json()
        assert [(x["via"], x["inviter"]) for x in by_reusable] == [("group", "Testeur 1")]
        # Ni l'invité, ni l'inviteur, ni un autre membre : rien (droit members.view_referrals).
        for who in (invitee, inviter, third):
            assert who.rpc("member_invited_by", target=invitee.uid).json() is None
        assert anon_rpc("member_invited_by", target=invitee.uid).status_code in (401, 403)
    finally:
        httpx.delete(f"{TEST_URL}/rest/v1/member_groups?id=eq.{group}", headers=inviter.headers, timeout=30)
        httpx.delete(f"{TEST_URL}/rest/v1/events?id=eq.{event}", headers=admin.headers, timeout=30)
        sql(f"delete from private.invite_joins where user_id in ('{invitee.uid}', '{third.uid}')")
