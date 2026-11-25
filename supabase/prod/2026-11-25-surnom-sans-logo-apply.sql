-- PROD, revue Apple (5.2.5, 5.6.2) du 25.11.2026 : le surnom de l'organisateur de la démo et des événements publics
-- contenait U+F8FF (affiché comme le logo Apple sur un iPhone) et le drapeau suisse. Il devient « Boby ».
-- Valeur d'avant lue en prod le 25.11 (lecture seule, hex 426f627920efa3bff09f87a8f09f87ad) ;
-- retour arrière : 2026-11-25-surnom-sans-logo-rollback.sql. Aucune notification ne part (simple colonne du profil).
-- Les titres et textes des notifications DÉJÀ envoyées gardaient l'ancien surnom (27 lignes lues le 25.11, dont une dans
-- l'Activité d'Apple-test) : « Boby <U+F8FF>🇨🇭 » y devient aussi « Boby ». Les déclencheurs de notifications ne
-- réagissent qu'à l'insertion (notifications_blocked, notifications_kick_push) : aucun push ne repart.
begin;
update public.profiles set display_name = 'Boby'
 where id = '298ff6e0-07b2-4127-bb69-d254dd63a3d5'
   and display_name = convert_from('\x426f627920efa3bff09f87a8f09f87ad'::bytea, 'UTF8');
update public.notifications
   set title = replace(replace(title, convert_from('\x426f627920efa3bff09f87a8f09f87ad'::bytea, 'UTF8'), 'Boby'), chr(63743), ''),
       body = replace(replace(body, convert_from('\x426f627920efa3bff09f87a8f09f87ad'::bytea, 'UTF8'), 'Boby'), chr(63743), '')
 where title like '%' || chr(63743) || '%' or body like '%' || chr(63743) || '%';
do $$
begin
  if exists (select 1 from public.profiles where display_name like '%' || chr(63743) || '%')
     or exists (select 1 from public.notifications
                 where title like '%' || chr(63743) || '%' or body like '%' || chr(63743) || '%') then
    raise exception 'Il reste un surnom ou une notification avec U+F8FF (logo Apple).';
  end if;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261125090100', 'surnom_sans_logo')
  on conflict do nothing;
commit;
