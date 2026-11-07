-- PROD, campagne_bots_corrections (20261106200000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Public = jamais d'annonce ; créateur supprime un événement annulé ; surnom complet sur la carte d'invitation.
-- Prérequis : 20261105200000_invitations_v2 et 20261105131500 (déjà en prod). Rejouable. Tout ou rien.
begin;
-- 1. -----------------------------------------------------------------------------------------------------------------
create or replace function private.public_event_is_silent() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.public_link and new.status = 'published' then
    new.notify_on_publish := false;
  end if;
  return new;
end $$;
revoke all on function private.public_event_is_silent() from public, anon, authenticated;
-- Nommé après events_guard (qui fixe le statut) : PostgreSQL lance les déclencheurs BEFORE par ordre alphabétique.
drop trigger if exists events_public_silent on public.events;
create trigger events_public_silent before insert or update on public.events
  for each row execute function private.public_event_is_silent();

-- 2. -----------------------------------------------------------------------------------------------------------------
drop policy if exists "supprimer événement" on public.events;
create policy "supprimer événement" on public.events for delete
  using (public.is_admin() or (created_by = (select auth.uid()) and status in ('draft', 'pending', 'rejected', 'cancelled')));

-- 3. -----------------------------------------------------------------------------------------------------------------
do $$
declare
  def text := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  anchor text := '''inviter'', private.first_word(who)';
begin
  if position(anchor in def) > 0 then
    execute replace(def, anchor, '''inviter'', nullif(btrim(coalesce(who, '''')), '''')');
  end if;
end $$;

do $$
declare
  def text := pg_get_functiondef('public.nudge_invitees(uuid, uuid[])'::regprocedure);
  anchor text := 'coalesce(private.first_word(host), ''L''''organisateur'')';
begin
  if position(anchor in def) > 0 then
    execute replace(def, anchor, 'coalesce(nullif(btrim(coalesce(host, '''')), ''''), ''L''''organisateur'')');
  end if;
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261106200000', 'campagne_bots_corrections')
  on conflict (version) do nothing;
commit;

notify pgrst, 'reload schema';
