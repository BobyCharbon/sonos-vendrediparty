-- Recette iPhone de l'Agenda (base de TEST seulement) : groupe « [QA] Qui est libre 2311 », ses 4 comptes de test qui
-- partagent leurs dispos, et des soirées prises connues (un jour sur quelques-uns, tous libres). À lancer AVANT
-- RecetteAgendaUITests / RecetteAgendaParcoursUITests : d'autres recettes (agenda_stop_sharing) effacent ces partages.
-- Testeur 1 = t1 (0790000001), Admin test = a.
--   python3 supabase/tools/sbq.py test rw < ios/PartyUITests/recette-agenda-qui-est-libre.sql
do $$
declare g uuid; a uuid := 'a7610087-3f63-43d0-8657-a3459f0fddcb'; t1 uuid := '407eb502-c0b8-45f3-8d3a-be471b72c4b5';
  t2 uuid := 'b539febf-3f90-42b0-ab6b-ed18f3a2380c'; v uuid := 'd83a1218-960d-4203-a08f-614211699b5d'; d int; day date;
  z timestamptz;
begin
  select id into g from public.member_groups where name = '[QA] Qui est libre 2311';
  if g is null then
    insert into public.member_groups(name, created_by, emoji, color) values ('[QA] Qui est libre 2311', a, '🍻', 'mint') returning id into g;
  end if;
  insert into public.member_group_members(group_id, user_id) select g, u from unnest(array[a,t1,t2,v]) u on conflict do nothing;
  insert into private.agenda_group_shares(user_id, group_id, consented_at) select u, g, now() from unnest(array[a,t1,t2,v]) u on conflict do nothing;
  delete from private.agenda_busy where user_id in (a,t1,t2,v);
  -- Liens « Jours de semaine HHmmss » des passages d'avant (RecetteAgendaParcoursUITests) : 10 liens au plus par personne.
  delete from private.agenda_links where user_id = t1 and name like 'Jours de semaine %';
  for d in 0..59 loop
    day := (now() at time zone 'Europe/Zurich')::date + d;
    z := (day::timestamp) at time zone 'Europe/Zurich';
    if d % 3 = 0 then insert into private.agenda_busy values (t1, 'web', z + interval '18 hours', z + interval '23 hours 30 minutes', '', true); end if;
    if d % 4 = 1 then insert into private.agenda_busy values (t2, 'web', z + interval '19 hours', z + interval '21 hours', '', true); end if;
    if d % 7 <> 5 then insert into private.agenda_busy values (v, 'web', z + interval '20 hours', z + interval '23 hours', '', true); end if;
    if d % 7 = 3 then insert into private.agenda_busy values (a, 'web', z + interval '18 hours', z + interval '20 hours', '', true); end if;
  end loop;
  raise notice '%', g;
end $$;
select id from public.member_groups where name = '[QA] Qui est libre 2311';
