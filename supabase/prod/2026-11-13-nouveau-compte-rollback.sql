-- PROD, retour arrière de nouveau_compte (20261113100000) : plus de notification « Nouveau compte ».
begin;
drop trigger if exists profiles_member_signup on public.profiles;
drop function if exists private.notify_member_signup();
do $$ declare def text;
begin
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''member_signup''' in def) > 0 then
    execute replace(def, $a$
    when 'member_signup' then coalesce(prefs.member_signups, true)$a$, '');
  end if;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''member_signup''' in def) > 0 then
    execute replace(def, '''link_join'', ''member_signup'',', '''link_join'',');
  end if;
end $$;
alter table public.notification_prefs drop column if exists member_signups;
delete from supabase_migrations.schema_migrations where version = '20261113100000';
commit;
