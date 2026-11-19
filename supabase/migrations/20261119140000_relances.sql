-- Relances des invités sans réponse (demande de l'admin, 19.11.2026) : depuis la fiche, l'organisateur (et ses
-- co-organisateurs) relance d'un geste ceux qui n'ont pas répondu. Vérification de bout en bout du 19.11 :
--  1. private.has_app ne regardait que les iPhone (push_tokens) : un invité qui n'utilise que la webapp, abonné aux
--     notifications Web Push, passait pour « sans l'app » et ne recevait jamais la relance (feuille de partage à la place).
--     Désormais : un appareil qui reçoit les notifications (iPhone OU navigateur, session encore ouverte), notifications
--     allumées, interrupteur « Invitations » (notification_prefs.invites) allumé, compte qui peut les recevoir.
--     Sinon la relance passe par le partage (WhatsApp, Messages…) : jamais compté « prévenu » pour rien.
--  2. Une personne bloquée (dans un sens ou dans l'autre) était comptée « prévenue » alors que la base jetait la
--     notification (drop_blocked_notification) : elle n'est plus relancée du tout, ni par Party ni par le partage.
--  3. Événement terminé (private.event_is_over) ou date limite de réponse passée : plus de relance (elle ne pourrait plus
--     répondre). Événement mis en sourdine par la personne : pas de notification, le partage seulement.
--  4. Texte sans culpabilisation : « Invitation de Ludo · Tu viens ? Réponds en un geste. » (sondage : « Quelles dates te
--     vont ? Vote en un geste. »), à la place de « Ludo attend ta réponse : tu viens ? ».
-- Rien d'autre ne change : une relance par jour et par personne, organisateurs seulement, invités seulement, toucher →
-- la fiche sur Événements (kind private_invite, send-push / send-web-push inchangés).
-- Fonction partagée nudge_invitees étendue par ancres (jamais réécrite) ; rejouable.

create or replace function private.has_app(u uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select (exists (select 1 from public.push_tokens t where t.user_id = u and t.session_id is not null)
          or exists (select 1 from private.web_push_subscriptions s
                     join auth.sessions a on a.id = s.session_id and (a.not_after is null or a.not_after > now())
                     where s.user_id = u))
     and coalesce((select p.push_enabled and coalesce(p.invites, true) from public.notification_prefs p where p.user_id = u), false)
     and private.may_receive_push(u, 'private_invite');
$$;
revoke all on function private.has_app(uuid) from public, anon;

do $$
declare
  def text := pg_get_functiondef('public.nudge_invitees(uuid, uuid[])'::regprocedure);
  -- 3. Terminé ou date limite passée.
  a_open text := 'if ev.status <> ''published'' then raise exception ''Cet événement n''''est pas ouvert aux réponses''; end if;';
  n_open text := a_open || '
  if private.event_is_over(ev) then raise exception ''Cet événement est terminé : plus de relance.'' using errcode = ''P0001''; end if;
  if ev.rsvp_deadline is not null and now() > ev.rsvp_deadline then
    raise exception ''La date limite de réponse est passée : plus de relance.'' using errcode = ''P0001'';
  end if;';
  -- 2. Bloqué : ni notification ni partage.
  a_block text := 'if private.nudged_today(e, u, null) is not null then skipped := skipped + 1; continue; end if;';
  n_block text := 'if private.blocked_either(auth.uid(), u) then continue; end if;
    ' || a_block;
  -- 1 et 3. Joignable par Party (iPhone ou navigateur), sauf événement en sourdine.
  a_app text := 'if private.has_app(u) then';
  n_app text := 'if private.has_app(u) and not exists (select 1 from public.event_mutes m where m.event_id = e and m.user_id = u) then';
  -- 4. Texte.
  a_text text := 'coalesce(nullif(btrim(coalesce(host, '''')), ''''), ''L''''organisateur'') || '' attend ta réponse : tu viens ?''';
  n_text text := '''Invitation de '' || coalesce(nullif(btrim(coalesce(host, '''')), ''''), ''l''''organisateur'') || case when ev.date_mode = ''poll'' then '' · Quelles dates te vont ? Vote en un geste.'' else '' · Tu viens ? Réponds en un geste.'' end';
begin
  if position('private.event_is_over(ev)' in def) = 0 then
    if position(a_open in def) = 0 then raise exception 'nudge_invitees : ancre « published » introuvable'; end if;
    def := replace(def, a_open, n_open);
  end if;
  if position('private.blocked_either(auth.uid(), u)' in def) = 0 then
    if position(a_block in def) = 0 then raise exception 'nudge_invitees : ancre « nudged_today » introuvable'; end if;
    def := replace(def, a_block, n_block);
  end if;
  if position('public.event_mutes m' in def) = 0 then
    if position(a_app in def) = 0 then raise exception 'nudge_invitees : ancre « has_app » introuvable'; end if;
    def := replace(def, a_app, n_app);
  end if;
  if position('Réponds en un geste' in def) = 0 then
    if position(a_text in def) = 0 then raise exception 'nudge_invitees : ancre du texte introuvable'; end if;
    def := replace(def, a_text, n_text);
  end if;
  execute def;
end $$;

notify pgrst, 'reload schema';
