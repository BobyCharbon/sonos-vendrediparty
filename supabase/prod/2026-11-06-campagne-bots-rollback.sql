-- PROD, retour arrière de campagne_bots_corrections (20261106200000) : un événement public annonce de nouveau sa
-- publication (selon notify_on_publish), le créateur ne supprime plus un événement annulé, la carte d'invitation et la
-- relance reprennent le premier mot du surnom. Tout ou rien.
begin;
drop trigger if exists events_public_silent on public.events;
drop function if exists private.public_event_is_silent();
drop policy if exists "supprimer événement" on public.events;
create policy "supprimer événement" on public.events for delete
  using (public.is_admin() or (created_by = auth.uid() and status in ('draft', 'pending', 'rejected')));
do $$
declare def text := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
begin
  execute replace(def, '''inviter'', nullif(btrim(coalesce(who, '''')), '''')', '''inviter'', private.first_word(who)');
end $$;
do $$
declare def text := pg_get_functiondef('public.nudge_invitees(uuid, uuid[])'::regprocedure);
begin
  execute replace(def, 'coalesce(nullif(btrim(coalesce(host, '''')), ''''), ''L''''organisateur'')',
                  'coalesce(private.first_word(host), ''L''''organisateur'')');
end $$;
delete from supabase_migrations.schema_migrations where version = '20261106200000';
commit;

notify pgrst, 'reload schema';
