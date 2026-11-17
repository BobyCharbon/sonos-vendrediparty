-- Agenda : une soirée Party à laquelle on a répondu « Pas présent » ne rend plus occupé, même si on l'organise
-- (analyse du 17.11 : la « Fondue » de l'admin, répondue « Pas présent », bloquait toute sa soirée sur son lien de dispo).
-- Purement additive et rejouable : private.agenda_party_spans est ÉTENDUE par ancre.

do $$ declare def text;
begin
  def := pg_get_functiondef('private.agenda_party_spans(uuid,timestamptz,timestamptz)'::regprocedure);
  if position('n.status = ''no''' in def) = 0 then
    if position('and (ev.created_by = uid' in def) = 0 then raise exception 'agenda_party_spans : ancre created_by introuvable'; end if;
    execute replace(def, 'and (ev.created_by = uid',
      'and not exists (select 1 from public.rsvps n where n.event_id = ev.id and n.user_id = uid and n.status = ''no'')
    and (ev.created_by = uid');
  end if;
end $$;
revoke all on function private.agenda_party_spans(uuid, timestamptz, timestamptz) from public, anon, authenticated;
