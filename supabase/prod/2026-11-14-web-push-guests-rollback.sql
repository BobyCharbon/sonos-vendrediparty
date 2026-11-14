-- PROD, retour arrière de web_push_guests (20261114200000) : Web Push de nouveau réservé aux Membres VIP et plus,
-- plus de notification d'essai pour les Guests. Les abonnements web déjà enregistrés par des Guests sont retirés.
begin;
do $$ declare f text; def text;
begin
  foreach f in array array['private.web_push_public_key()', 'private.register_web_push(jsonb,text)',
                           'private.web_push_device_status(text)'] loop
    def := pg_get_functiondef(f::regprocedure);
    if position('private.is_account_active(auth.uid())' in def) > 0 then
      execute replace(def, 'private.is_account_active(auth.uid())', 'public.is_active()');
    end if;
  end loop;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''web_push_test''' in def) > 0 then
    execute replace(def, '''link_join'', ''web_push_test'', ''push_test'',', '''link_join'',');
  end if;
end $$;
delete from private.web_push_subscriptions s where not private.is_member(s.user_id);
delete from supabase_migrations.schema_migrations where version = '20261114200000';
commit;
