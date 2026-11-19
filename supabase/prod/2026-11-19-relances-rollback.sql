-- PROD, retour arrière de relances (20261119140000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;
CREATE OR REPLACE FUNCTION private.has_app(u uuid)
 RETURNS boolean
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  select exists (select 1 from public.push_tokens t where t.user_id = u and t.session_id is not null);
$function$;

CREATE OR REPLACE FUNCTION public.nudge_invitees(e uuid, people uuid[])
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare ev public.events; u uuid; host text; notified int := 0; skipped int := 0; share uuid[] := '{}';
begin
  if not private.manages_event(e) then
    raise exception 'forbidden: réservé aux organisateurs de l''événement' using errcode = '42501';
  end if;
  if coalesce(array_length(people, 1), 0) > 300 then raise exception 'Trop de personnes d''un coup'; end if;
  select * into ev from public.events where id = e;
  if ev.status <> 'published' then raise exception 'Cet événement n''est pas ouvert aux réponses'; end if;
  select display_name into host from public.profiles where id = auth.uid();
  foreach u in array coalesce(people, '{}') loop
    if u = auth.uid() or exists (select 1 from public.rsvps r where r.event_id = e and r.user_id = u) then continue; end if;
    -- Seulement les invités (groupe, Vendredi Party, un par un, lien).
    if not (exists (select 1 from public.event_invites i where i.event_id = e and i.user_id = u)
            or (ev.visibility = 'all' and not ev.public_link and private.is_member(u))) then continue; end if;
    if private.nudged_today(e, u, null) is not null then skipped := skipped + 1; continue; end if;
    if private.has_app(u) then
      perform public.queue_notification(u, 'private_invite', e, '📬 ' || ev.title,
        coalesce(nullif(btrim(coalesce(host, '')), ''), 'L''organisateur') || ' attend ta réponse : tu viens ?',
        'invite_nudge:' || e || ':' || u || ':' || to_char(now() at time zone 'Europe/Zurich', 'YYYY-MM-DD'));
      insert into private.invite_nudges (event_id, user_id, by, channel) values (e, u, auth.uid(), 'push');
      notified := notified + 1;
    else
      insert into private.invite_nudges (event_id, user_id, by, channel) values (e, u, auth.uid(), 'share');
      share := share || u;
    end if;
  end loop;
  return jsonb_build_object('notified', notified, 'skipped', skipped, 'share', to_jsonb(share));
end $function$;

delete from supabase_migrations.schema_migrations where version = '20261119140000';
commit;
