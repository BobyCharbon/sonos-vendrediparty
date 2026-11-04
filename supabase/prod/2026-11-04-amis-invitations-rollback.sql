-- PROD, retour arrière de friends_and_app_invites (20261104090000) : « Mes amis dans Party », le lien personnel
-- d'invitation et « Invité par » (historique effacé) disparaissent (l'app affiche « indisponible ») ; les parrainages notés sont effacés. Les notifications
-- referral_join déjà envoyées restent dans l'historique. Tout ou rien.
begin;

drop function if exists public.contacts_friends(uuid[]);
drop function if exists public.my_app_invite(boolean);
drop function if exists public.app_invite_preview(uuid);
drop function if exists public.claim_app_invite(uuid);
drop function if exists public.member_invited_by(uuid);
drop table if exists private.app_referrals;
drop table if exists private.app_invites;

delete from public.role_permissions where perm in ('members.invite', 'members.view_referrals');
delete from public.permissions where key in ('members.invite', 'members.view_referrals');
delete from private.one_time_changes where name in ('members_invite_2026_11_04', 'members_view_referrals_2026_11_04');

-- « Invité par » : déclencheurs, historique, auteur du lien réutilisable ; join_group_by_link revient à 20261029170000.
drop trigger if exists invite_link_used on private.invite_links;
drop function if exists private.invite_link_used();
drop trigger if exists group_token_author on public.member_groups;
drop function if exists private.group_token_author();
create or replace function public.join_group_by_link(token uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if not private.identity_complete(auth.uid()) then
    raise exception 'profile_incomplete: complète ton profil (nom, prénom, surnom et photo) avant de rejoindre';
  end if;
  select id into grp from public.member_groups where token is not null and invite_token = token and system_key is null;
  if grp is null then
    select id into grp from public.member_groups where id = private.claim_invite_link(token, 'group') and system_key is null;
  end if;
  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  perform private.join_group(grp, auth.uid());
  return grp;
end $$;
drop function if exists private.note_invite_join(uuid, uuid, text, uuid);
drop table if exists private.invite_joins;
alter table public.member_groups drop column if exists invite_token_by;

-- referral_join retiré des types reçus par les Guests, et de web_push_allowed (le reste de la fonction ne change pas).
create or replace function private.may_receive_push(uid uuid, kind text) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.is_member(uid)
    or (kind in ('group_message', 'group_invite', 'group_join', 'link_join') and private.is_account_active(uid));
$$;
revoke all on function private.may_receive_push(uuid, text) from public, anon;
do $$
declare def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
begin
  if position('''referral_join''' in def) > 0 then
    execute replace(def, E'\n    when ''referral_join'' then coalesce(prefs.referral_joins, true)', '');
  end if;
end $$;

alter table public.notification_prefs drop column if exists referral_joins;
alter table public.notification_prefs drop column if exists contact_joins;

delete from supabase_migrations.schema_migrations where version = '20261104090000';
commit;

notify pgrst, 'reload schema';
