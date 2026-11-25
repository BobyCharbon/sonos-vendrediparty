-- Retour arrière de 2026-11-25-surnom-sans-logo-apply.sql : remet l'ancien surnom (valeur lue en prod le 25.11.2026).
begin;
update public.profiles set display_name = convert_from('\x426f627920efa3bff09f87a8f09f87ad'::bytea, 'UTF8')
 where id = '298ff6e0-07b2-4127-bb69-d254dd63a3d5' and display_name = 'Boby';
-- Pot commun : les 3 noms de membres d'avant (même valeur que le surnom). Les notifications ne sont PAS remises : leur
-- texte (extraits de messages privés) ne doit jamais entrer dans le dépôt, et remettre le logo n'y sert à rien.
update public.tc_members set name = convert_from('\x426f627920efa3bff09f87a8f09f87ad'::bytea, 'UTF8')
 where id in ('5bfac184-d11b-47f4-8cfc-c2aa66ecbaea', '7a0756a8-0c6f-4460-932d-9bbb49b493a5',
              'b59bbc9c-97bd-449e-80d3-7b4fc2cd7c74') and name = 'Boby';
delete from supabase_migrations.schema_migrations where version = '20261125090100';
commit;
