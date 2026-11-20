-- Retour de l'admin (20.11.2026) : l'organisateur n'est prévenu d'une réponse que si la personne vient ou viendra
-- peut-être. « Ne vient pas » ne notifie plus personne (réponses regroupées et lien d'invitation) ; la réponse reste
-- visible dans la liste des invités. Modifie les fonctions par repère (texte en place relu). Rejouable.
do $$
declare src text := pg_get_functiondef('private.flush_rsvp_digests()'::regprocedure);
  old_text text := 'd.user_id <> recipient and d.updated_at <= started;';
  new_text text := 'd.user_id <> recipient and d.updated_at <= started and d.status in (''yes'', ''maybe'');';
begin
  if position(new_text in src) > 0 then return; end if;  -- déjà fait
  if position(old_text in src) = 0 then raise exception 'flush_rsvp_digests : repère introuvable, rien changé'; end if;
  execute replace(src, old_text, new_text);
end $$;

do $$
declare src text := pg_get_functiondef('public.accept_invite(uuid, text, text)'::regprocedure);
  old_text text := E'where event_id = ev.id) o loop\n      perform public.queue_notification(u, ''link_join''';
  new_text text := E'where event_id = ev.id) o where answer <> ''no'' loop\n      perform public.queue_notification(u, ''link_join''';
begin
  if position(new_text in src) > 0 then return; end if;  -- déjà fait
  if position(old_text in src) = 0 then raise exception 'accept_invite : repère introuvable, rien changé'; end if;
  execute replace(src, old_text, new_text);
end $$;
