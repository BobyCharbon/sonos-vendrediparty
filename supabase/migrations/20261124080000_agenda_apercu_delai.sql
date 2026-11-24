-- Agenda : l'aperçu d'un lien (« Voici ce que verra la personne ») tient compte du délai minimum (recette iPhone du 24.11).
-- Avec les demandes de rendez-vous allumées, l'aperçu ne recevait pas min_notice_min (null) : aucun créneau, « Aucun moment
-- libre dans ces heures » juste au-dessus de « Dès le … ». Délai lu dans le brouillon (par 15 min, 14 jours au plus),
-- 12 h sinon, comme un nouveau lien. Purement additive et rejouable.
create or replace function public.agenda_link_preview(link jsonb) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare l private.agenda_links; n int;
begin
  if not private.is_account_active(auth.uid()) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.agenda_rules_ok(link->'rules') then raise exception 'forbidden: Choisis au moins un jour et des heures.' using errcode = '22023'; end if;
  l.id := gen_random_uuid(); l.user_id := auth.uid(); l.rules := link->'rules';
  l.horizon_days := least(greatest(coalesce((link->>'horizon_days')::int, 28), 7), 60);
  l.duration_min := coalesce((link->>'duration_min')::int, 60);
  if l.duration_min not between 30 and 240 or l.duration_min % 30 <> 0 then l.duration_min := 60; end if;
  l.booking_enabled := coalesce((link->>'booking_enabled')::boolean, false);
  l.calendars := private.agenda_link_cals(link->'calendars');
  l.buffer_before_min := coalesce(private.agenda_buffer(link->'buffer_before_min'), 0);
  l.buffer_after_min := coalesce(private.agenda_buffer(link->'buffer_after_min'), 0);
  n := case when jsonb_typeof(link->'min_notice_min') = 'number' then (link->>'min_notice_min')::numeric::int end;
  l.min_notice_min := case when n between 0 and 20160 and n % 15 = 0 then n else 720 end;
  return jsonb_build_object('slots', private.agenda_link_free(l), 'tz', 'Europe/Zurich');
end $$;
revoke all on function public.agenda_link_preview(jsonb) from public, anon;
grant execute on function public.agenda_link_preview(jsonb) to authenticated;
