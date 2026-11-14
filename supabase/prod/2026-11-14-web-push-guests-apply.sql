-- PROD, web_push_guests (20261114200000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée modifiée : trois fonctions Web Push acceptent tout compte actif (Guest compris)
-- au lieu des seuls Membres VIP et plus, et la notification d'essai passe le filtre private.may_receive_push.
begin;
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

insert into supabase_migrations.schema_migrations (version, name) values ('20261114200000', 'web_push_guests') on conflict do nothing;
commit;
