-- Notifications web pour les Guests (campagne de tests du 14.11.2026, zone Web Push).
-- Un Guest reçoit déjà sur l'iPhone ses invitations, rappels, changements d'heure… (private.may_receive_push), et la fiche
-- web lui propose « Activer les notifications » (bandeau « Ne rate rien de cet événement »). Mais l'inscription d'un
-- navigateur exigeait public.is_active() (droit events.view, Membre VIP et plus) : le bouton répondait « Connexion
-- requise ». Désormais : tout compte actif (profiles.status = 'active'), comme pour l'iPhone. Les types reçus ne
-- changent pas (may_receive_push et les interrupteurs restent la règle) ; on ajoute seulement la notification d'essai
-- (« Envoyer une notification d'essai », Réglages › Notifications), jamais envoyée à un Guest jusqu'ici.
-- Fonctions COMPLÉTÉES en place (jamais recopiées). Purement additive et rejouable.
do $$ declare f text; def text;
begin
  foreach f in array array['private.web_push_public_key()', 'private.register_web_push(jsonb,text)',
                           'private.web_push_device_status(text)'] loop
    def := pg_get_functiondef(f::regprocedure);
    if position('public.is_active()' in def) > 0 then
      execute replace(def, 'public.is_active()', 'private.is_account_active(auth.uid())');
    end if;
  end loop;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''web_push_test''' in def) = 0 then
    if position('''link_join'',' in def) = 0 then raise exception 'may_receive_push : ancre link_join introuvable'; end if;
    execute replace(def, '''link_join'',', '''link_join'', ''web_push_test'', ''push_test'',');
  end if;
end $$;
