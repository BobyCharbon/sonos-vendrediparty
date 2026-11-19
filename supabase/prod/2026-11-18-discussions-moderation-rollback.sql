-- PROD, retour arrière de discussions_moderation (20261118121000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;
CREATE OR REPLACE FUNCTION public.invite_to_group(grp uuid, member uuid DEFAULT NULL::uuid, phone text DEFAULT NULL::text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare g public.member_groups; target uuid := member; number text := private.digits(phone); me text;
begin
  if not private.manages_group(grp) then
    raise exception 'forbidden: réservé au créateur du groupe' using errcode = '42501';
  end if;
  select * into g from public.member_groups where id = grp;
  if target is null and number is not null then
    select id into target from public.profiles p where private.digits(p.phone) = number limit 1;
  end if;
  if target is null and number is null then raise exception 'Choisis une personne ou un numéro'; end if;
  if target is not null and exists (select 1 from public.member_group_members where group_id = grp and user_id = target) then
    raise exception 'Déjà dans le groupe';
  end if;
  if target is not null then
    insert into private.group_invitations (group_id, user_id, invited_by) values (grp, target, auth.uid()) on conflict do nothing;
    select display_name into me from public.profiles where id = auth.uid();
    perform public.queue_notification(target, 'group_invite', null, g.name,
      coalesce(nullif(btrim(me), ''), 'Quelqu''un') || ' t''invite dans le groupe « ' || g.name || ' »',
      'group_invite:' || grp || ':' || target);
    return jsonb_build_object('invited', 'member');
  end if;
  insert into private.group_invitations (group_id, phone, invited_by) values (grp, number, auth.uid()) on conflict do nothing;
  return jsonb_build_object('invited', 'phone');
end $function$;

CREATE OR REPLACE FUNCTION public.report_content(p_kind text, p_target text, p_reason text, p_comment text DEFAULT NULL::text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare me uuid := auth.uid(); snap jsonb; owner uuid; rid uuid; v_comment text := nullif(btrim(left(p_comment, 500)), '');
begin
  if me is null or not private.is_account_active(me) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if p_reason is null or p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'other') then
    raise exception 'reason: choisis une raison' using errcode = '22023';
  end if;
  if (select count(*) from public.content_reports where reporter_id = me and created_at > now() - interval '1 hour') >= 10
     or (select count(*) from public.content_reports where reporter_id = me and created_at > now() - interval '1 day') >= 30 then
    raise exception 'rate_limited: tu as fait beaucoup de signalements, réessaie plus tard' using errcode = '54000';
  end if;
  snap := private.report_snapshot(p_kind, p_target, me);
  if snap is null then raise exception 'not_found: ce contenu n''existe plus ou ne t''est pas visible' using errcode = 'PT404'; end if;
  owner := nullif(snap ->> 'owner', '')::uuid;
  if owner = me then raise exception 'self: tu ne peux pas signaler ton propre contenu' using errcode = '22023'; end if;
  select id into rid from public.content_reports
    where reporter_id = me and target_kind = p_kind and target_id = p_target and status = 'open';
  if rid is not null then
    update public.content_reports set reason = p_reason, comment = v_comment where id = rid;
    return rid;
  end if;
  insert into public.content_reports (reporter_id, target_kind, target_id, target_user, reason, comment, snapshot)
  values (me, p_kind, p_target, owner, p_reason, v_comment, snap - 'owner')
  returning id into rid;
  return rid;
end $function$;

drop trigger if exists chat_files_of_account on auth.users;

drop trigger if exists moderation_evidence_gone on public.content_reports;

delete from supabase_migrations.schema_migrations where version = '20261118121000';
commit;
