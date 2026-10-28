-- PROD, jetons iPhone natifs pour les notifications des événements (20261028180000_native_apns_tokens).
-- À appliquer SEULEMENT après l'accord explicite de l'admin (« Ok prod ») pour cette migration.
-- Tout-ou-rien ; rejouable. Retour arrière : 2026-10-28-apns-tokens-rollback.sql.
begin;
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text primary key, statements text[], name text);

-- Notifications des événements vers l'app iOS native (Swift) : l'iPhone s'enregistre avec son jeton APNs brut,
-- noté « apns:<hex> » (même format que le serveur Party, app/push.py). La fonction send-push l'envoie alors
-- directement à Apple (secrets APNS_* de la fonction) ; les jetons Expo restent envoyés par Expo.
-- Seule la validation du jeton change ; le reste de la fonction est identique à 20261019075941.
-- Rejouable (create or replace).

create or replace function private.register_push_token(device_token text, device_platform text) returns void
language plpgsql security definer set search_path = '' as $$
declare member_id uuid := auth.uid(); active_session uuid;
begin
  if not public.is_active() or device_platform is null or device_platform not in ('ios', 'android')
    or device_token is null
    or not (device_token ~ '^(ExponentPushToken|ExpoPushToken)\[[A-Za-z0-9_-]{10,200}\]$'
            or (device_platform = 'ios' and device_token ~ '^apns:[0-9a-f]{64,200}$')) then
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
revoke all on function private.register_push_token(text,text) from public, anon;
grant execute on function private.register_push_token(text,text) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261028180000', 'native_apns_tokens')
  on conflict (version) do nothing;
commit;
