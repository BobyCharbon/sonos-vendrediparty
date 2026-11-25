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
-- Pot commun : le nom d'un membre est une copie (il ne suit pas le profil). 3 lignes lues le 25.11 (dont le pot
-- « Cobalt Project Paintball » où se trouve Apple-test) : « Boby <U+F8FF>🇨🇭 » y devient aussi « Boby ».
update public.tc_members set name = 'Boby'
 where id in ('5bfac184-d11b-47f4-8cfc-c2aa66ecbaea', '7a0756a8-0c6f-4460-932d-9bbb49b493a5',
              'b59bbc9c-97bd-449e-80d3-7b4fc2cd7c74')
   and name = convert_from('\x426f627920efa3bff09f87a8f09f87ad'::bytea, 'UTF8');
do $$
begin
  if exists (select 1 from public.profiles where display_name like '%' || chr(63743) || '%')
     or exists (select 1 from public.notifications
                 where title like '%' || chr(63743) || '%' or body like '%' || chr(63743) || '%')
     or exists (select 1 from public.tc_members where name like '%' || chr(63743) || '%') then
    raise exception 'Il reste un surnom, une notification ou un membre de Pot commun avec U+F8FF (logo Apple).';
  end if;
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261125090100', 'surnom_sans_logo')
  on conflict do nothing;
commit;
