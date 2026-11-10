-- PROD, LECTURE SEULE (python3 supabase/tools/sbq.py prod < ce fichier) : retrouver les invités du sondage du paintball
-- (avis 39f148377a8f). Un compte « invité léger » effacé par la purge part avec ses votes (cascade), mais il reste des
-- traces : le compteur `uses` des liens, et la notification « X a répondu par ton lien d'invitation » reçue par
-- l'organisateur (kind = link_join, dans `notifications`, purgée après quelques jours).
with ev as (
  select id, title, visibility, public_link, date_mode, created_by, created_at from public.events
  where title ilike '%paint%' or title ilike '%global project%' order by created_at desc limit 5
)
select jsonb_pretty(jsonb_build_object(
  'evenements', (select jsonb_agg(to_jsonb(ev)) from ev),
  -- Liens : arrivées encore présentes vs compteur d'utilisations (un écart = des comptes effacés).
  'liens', (select jsonb_agg(jsonb_build_object('label', l.label, 'uses', l.uses, 'max_uses', l.max_uses,
              'arrivees_restantes', (select count(*) from private.invite_link_arrivals a where a.token = l.token)))
            from private.invite_links l where l.kind = 'event' and l.target in (select id from ev)),
  -- Qui a répondu par un lien (noms gardés dans les notifications de l'organisateur, même si le compte n'existe plus).
  'reponses_par_lien', (select jsonb_agg(jsonb_build_object('quand', n.created_at, 'texte', n.body) order by n.created_at)
            from public.notifications n where n.kind = 'link_join' and n.event_id in (select id from ev)),
  -- Votes encore là, par personne.
  'votants', (select jsonb_agg(jsonb_build_object('nom', p.display_name, 'votes', x.n)) from (
              select dv.user_id, count(*) n from public.date_votes dv join public.date_options o on o.id = dv.option_id
              where o.event_id in (select id from ev) group by dv.user_id) x join public.profiles p on p.id = x.user_id),
  -- Ont dit « Présent » sur la page publique, sans voter de date (invisibles dans le sondage avant le 10.11).
  'presents_sans_date', (select jsonb_agg(jsonb_build_object('nom', p.display_name, 'reponse', r.status))
            from public.rsvps r join public.profiles p on p.id = r.user_id
            where r.event_id in (select id from ev) and r.status in ('yes', 'maybe')
              and not exists (select 1 from public.date_votes dv join public.date_options o on o.id = dv.option_id
                              where o.event_id = r.event_id and dv.user_id = r.user_id)),
  -- Comptes « légers » encore là, et ceux que la purge de cette nuit prendrait (ancienne règle).
  'invites_legers_restants', (select count(*) from private.light_invitees li where li.event_id in (select id from ev)),
  'a_purger_cette_nuit', (select count(*) from private.light_invitees_to_purge())
)) diagnostic;
