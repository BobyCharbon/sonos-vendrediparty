-- PROD, retour arrière de tricount (20261031090000) : supprime le pot commun (ATTENTION : efface ses données).
-- À lancer après le retour arrière de pot_commun_events s'il a été appliqué.
begin;
drop policy if exists "tricount : envoyer un ticket" on storage.objects;
drop policy if exists "tricount : voir les tickets" on storage.objects;
drop function if exists public.tc_my_payment(), public.tc_list(), public.tc_state(uuid), private.tc_group_json(uuid),
  public.tc_set_payment(text, text, jsonb, text), public.tc_delete_expense(uuid), public.tc_save_expense(uuid, jsonb),
  public.tc_leave(uuid), public.tc_remove_member(uuid), public.tc_rename_member(uuid, text), public.tc_add_member(uuid, text),
  public.tc_join(uuid, text, uuid), public.tc_join_info(uuid), public.tc_renew_link(uuid),
  public.tc_update_group(uuid, text, text, text, boolean), public.tc_create(text, text, text, text), private.tc_need(uuid),
  private.tc_reads(uuid), private.tc_member_of(uuid, uuid);
drop table if exists public.tc_shares, public.tc_expenses, public.tc_payment, public.tc_members, public.tc_groups;
delete from supabase_migrations.schema_migrations where version = '20261031090000';
commit;
