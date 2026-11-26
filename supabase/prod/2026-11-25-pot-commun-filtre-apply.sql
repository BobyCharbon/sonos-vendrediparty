-- PROD, Pot commun filtré (20261125110000, revue Apple 1.2 du 25.11.2026) : noms, titres et notes du Pot commun passent
-- le filtre commun. Appliqué et testé sur la base de TEST le 25.11. Rejouable, tout ou rien.
-- Retour arrière : 2026-11-25-pot-commun-filtre-rollback.sql.
begin;
create or replace function private.moderate_tc_text() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then return new; end if;
  if tg_table_name in ('tc_groups', 'tc_members') then
    if tg_op = 'INSERT' or new.name is distinct from old.name then
      new.name := private.item_text_verdict(new.name, 'Nom');
    end if;
  elsif tg_table_name = 'tc_expenses' then
    if tg_op = 'INSERT' or new.title is distinct from old.title then
      new.title := private.item_text_verdict(new.title, 'Dépense');
    end if;
    if coalesce(new.note, '') <> '' and (tg_op = 'INSERT' or new.note is distinct from old.note) then
      new.note := private.item_text_verdict(new.note, 'Note');
    end if;
  end if;
  return new;
end $$;
revoke all on function private.moderate_tc_text() from public, anon, authenticated;

drop trigger if exists tc_groups_moderation on public.tc_groups;
create trigger tc_groups_moderation before insert or update of name on public.tc_groups
  for each row execute function private.moderate_tc_text();
drop trigger if exists tc_members_moderation on public.tc_members;
create trigger tc_members_moderation before insert or update of name on public.tc_members
  for each row execute function private.moderate_tc_text();
drop trigger if exists tc_expenses_moderation on public.tc_expenses;
create trigger tc_expenses_moderation before insert or update of title, note on public.tc_expenses
  for each row execute function private.moderate_tc_text();
insert into supabase_migrations.schema_migrations (version, name) values ('20261125110000', 'pot_commun_filtre') on conflict do nothing;
commit;
