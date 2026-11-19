-- Notification « … a répondu par ton lien d'invitation » (retour de l'admin, 19.11.2026) : on ne savait pas CE QU'il avait
-- répondu. Elle dit désormais la réponse, avec les mots des autres notifications (private.rsvp_phrase) : « Apple-test vient ·
-- par ton lien d'invitation », « … viendra peut-être · … », « … ne vient pas · … » ; sondage de dates : « … a voté les dates · … ».
-- Modifie accept_invite par repère (texte en place relu, jamais réécrit en entier). Rejouable.
do $$
declare src text := pg_get_functiondef('public.accept_invite(uuid, text, text)'::regprocedure);
  old_text text := E'coalesce(nullif(btrim(who), ''''), ''Quelqu''''un'') || '' a répondu par ton lien d''''invitation''';
  new_text text := E'case when answer = ''poll'' then coalesce(nullif(btrim(who), ''''), ''Quelqu''''un'') || '' a voté les dates'' else private.rsvp_phrase(who, answer::public.rsvp_status) end || '' · par ton lien d''''invitation''';
begin
  if position('a voté les dates'' else private.rsvp_phrase' in src) > 0 then return; end if;  -- déjà fait
  if position(old_text in src) = 0 then raise exception 'accept_invite : repère introuvable, rien changé'; end if;
  execute replace(src, old_text, new_text);
end $$;
