-- Pot commun (revue Apple 1.2 du 25.11.2026) : nom du pot, noms des membres, titres et notes des dépenses passent le
-- filtre commun (private.item_text_verdict, comme sondages, choix et « qui amène quoi »). Un texte refusé n'est pas
-- enregistré (content_refused : la phrase de la base va à l'écran). Les écritures du serveur (service, sans session)
-- ne sont pas filtrées. Seul un texte NOUVEAU ou CHANGÉ est contrôlé : rien d'existant ne casse. Additive, rejouable.
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
