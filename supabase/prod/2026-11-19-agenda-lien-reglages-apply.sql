-- PROD, agenda dans les Réglages (20261119160000) : migration supabase/migrations/20261119160000_agenda_lien_reglages.sql telle quelle (19.11).
-- Additive et rejouable. Tout ou rien.
begin;
-- Réglages › Agenda Vendredi Party (avis du 19.11.2026) : sous Android, « Ajouter à mon agenda » partait d'office dans
-- Google Agenda, et « Dans ton agenda » s'affichait dès qu'un agenda avait lu le lien, même si le téléphone ne l'avait pas
-- gardé. La personne peut désormais rajouter son calendrier « Vendredi Party » depuis les Réglages, sans événement.
-- Rend le lien de la personne (le crée au besoin) et s'il a été lu ces 10 derniers jours. Purement additif et rejouable.
create or replace function public.calendar_feed_link() returns jsonb
language plpgsql security definer set search_path = '' as $$
declare f public.calendar_feeds;
begin
  if auth.uid() is null then
    raise exception 'forbidden: connexion requise' using errcode = '42501';
  end if;
  insert into public.calendar_feeds (user_id) values (auth.uid())
  on conflict (user_id) do update set user_id = excluded.user_id
  returning * into f;
  return jsonb_build_object('token', f.token, 'subscribed', coalesce(f.read_at > now() - interval '10 days', false));
end $$;
revoke all on function public.calendar_feed_link() from public, anon;
grant execute on function public.calendar_feed_link() to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261119160000', 'agenda_lien_reglages') on conflict do nothing;
commit;
