-- PROD, retour arrière de 20261028180000 : remet la validation d'origine (jetons Expo seulement)
-- et retire les jetons iPhone natifs enregistrés.
begin;
create or replace function private.register_push_token(device_token text, device_platform text) returns void
language plpgsql security definer set search_path = '' as $$
declare member_id uuid := auth.uid(); active_session uuid;
begin
  if not public.is_active() or device_platform is null or device_platform not in ('ios', 'android')
    or device_token is null or device_token !~ '^(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{10,200}\]$' then
    raise exception 'Appareil non valide' using errcode = '42501';
  end if;
  select s.id into active_session from auth.sessions s
    where s.user_id = member_id and s.id::text = (auth.jwt() ->> 'session_id');
  if active_session is null then raise exception 'Session expirée' using errcode = '42501'; end if;
  insert into public.push_tokens(token, user_id, platform, session_id, updated_at)
  values(device_token, member_id, device_platform, active_session, now())
  on conflict(token) do update set user_id=excluded.user_id, platform=excluded.platform,
    session_id=excluded.session_id, updated_at=excluded.updated_at;
end;
$$;
delete from public.push_tokens where token like 'apns:%';
delete from supabase_migrations.schema_migrations where version = '20261028180000';
commit;
