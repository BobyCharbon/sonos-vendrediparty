"""Corrections de la campagne des bots et décision de l'admin du 06.11.2026 (migration 20261106200000), sur la VRAIE
base de TEST (jamais la prod). Tout se passe dans des transactions ANNULÉES, avec la session d'un compte de test
(règles de la base) : aucune ligne ne reste, aucune notification ne part vers de vrais membres.
- un événement PUBLIC ne prévient personne à sa publication (notify_on_publish forcé à false), même demandé ; un
  événement de groupe passé public après coup non plus ; un brouillon public passé à un groupe avant publication
  garde son annonce ;
- le créateur d'un événement ANNULÉ peut le supprimer ;
- la carte d'invitation (sans compte) donne le surnom complet de qui invite."""
import json

from tests.supabase_live.test_audiences_live import ADMIN, GUEST_A
from tests.supabase_live.test_groups_members_only_live import sql_test
from tests.supabase_live.test_member_admin_live import Session, pytestmark  # noqa: F401


def as_user(uid: str, body: str, grants: tuple[str, ...] = ('events.view', 'events.create', 'events.publish_direct')) -> str:
    """Corps exécuté avec la session de `uid` (droits donnés au rôle guest le temps de la transaction), puis annulé.
    Le corps lève une exception « résultat: … » : c'est la réponse (la transaction est de toute façon annulée)."""
    claims = json.dumps({"sub": uid, "role": "authenticated"})
    inserts = "\n".join(f"insert into public.role_permissions (role, perm) values ('guest', '{g}') on conflict do nothing;" for g in grants)
    rows = sql_test(f"""
    begin;
    {inserts}
    set local role authenticated;
    set local request.jwt.claims = '{claims}';
    do $$ declare e uuid; n int; r jsonb; begin
      {body}
    end $$;
    rollback;""")
    return json.dumps(rows, ensure_ascii=False)


def test_a_public_event_announces_nothing_when_it_is_published():
    guest = Session(GUEST_A).uid
    out = as_user(guest, """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test public muet', 'published', 'all', true, true, now() + interval '30 days') returning id into e;
      r := jsonb_build_object('notify', (select notify_on_publish from public.events where id = e));
      execute 'reset role';  -- compter TOUTES les notifications de l'événement (la session n'en lit que les siennes)
      select count(*) into n from public.notifications where event_id = e;
      raise exception 'résultat: notify=% notifications=%', r->>'notify', n;""")
    assert 'résultat: notify=false notifications=0' in out, out


def test_a_group_event_made_public_later_stays_silent():
    guest = Session(GUEST_A).uid
    out = as_user(guest, """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test groupe puis public', 'draft', 'invited', false, true, now() + interval '30 days') returning id into e;
      update public.events set visibility = 'all', public_link = true where id = e;
      update public.events set status = 'published' where id = e;
      r := jsonb_build_object('notify', (select notify_on_publish from public.events where id = e));
      execute 'reset role';  -- compter TOUTES les notifications de l'événement (la session n'en lit que les siennes)
      select count(*) into n from public.notifications where event_id = e;
      raise exception 'résultat: notify=% notifications=%', r->>'notify', n;""")
    assert 'résultat: notify=false notifications=0' in out, out


def test_a_public_draft_switched_to_a_group_before_publishing_keeps_its_announcement():
    guest = Session(GUEST_A).uid
    out = as_user(guest, """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test public puis groupe', 'draft', 'all', true, true, now() + interval '30 days') returning id into e;
      update public.events set visibility = 'invited', public_link = false where id = e;
      raise exception 'résultat: notify=%', (select notify_on_publish from public.events where id = e);""")
    assert 'résultat: notify=t' in out, out


def test_the_creator_deletes_a_cancelled_event():
    guest = Session(GUEST_A).uid
    out = as_user(guest, """
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test annulé à supprimer', 'published', 'invited', false, false, now() + interval '30 days') returning id into e;
      update public.events set status = 'cancelled' where id = e;
      delete from public.events where id = e;
      get diagnostics n = row_count;
      raise exception 'résultat: supprimés=%', n;""")
    assert 'résultat: supprimés=1' in out, out


def test_the_invite_card_names_the_inviter_with_the_whole_nickname():
    admin = Session(ADMIN).uid  # organisateur avec events.manage_all (créer un lien), transaction annulée
    out = as_user(admin, """
      update public.profiles set display_name = 'Bot Olga Test' where id = auth.uid();
      insert into public.events (title, status, visibility, public_link, notify_on_publish, starts_at)
        values ('Test carte', 'published', 'invited', false, false, now() + interval '30 days') returning id into e;
      r := public.create_event_invite(e, 1, null, null);
      raise exception 'résultat: %', public.invite_preview((r->>'token')::uuid, false)->>'inviter';""",
                 grants=('events.create', 'events.publish_direct'))
    assert 'résultat: Bot Olga Test' in out, out
