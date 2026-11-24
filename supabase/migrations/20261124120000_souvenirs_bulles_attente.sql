-- Souvenirs (24.11) : bulles des Discussions de l'app iPhone (contrat pont-ios.md). Avant : seulement les stories ouvertes.
-- Maintenant aussi l'attente : appareil photo fermé, dévoilement à venir (phase « waiting ») → bulle grise à cadenas et
-- compte à rebours jusqu'à `reveal_at`. Pendant l'attente, le NOMBRE de photos seulement (comme souvenir_counter),
-- jamais qui ni quoi ; une soirée sans photo n'a pas de bulle. Chaque ligne dit sa phase (« waiting » ou « story »).
-- Purement additive et rejouable.
create or replace function public.souvenir_stories() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('event_id', ev.id, 'title', ev.title, 'phase', x.ph,
      'reveal_at', private.souvenir_reveal_at(ev),
      'until', private.souvenir_reveal_at(ev) + interval '24 hours', 'count', x.n,
      'seen', exists (select 1 from public.souvenir_seen s where s.event_id = ev.id and s.user_id = auth.uid()))
    order by (x.ph = 'story') desc, private.souvenir_reveal_at(ev) desc), '[]'::jsonb)
  from public.events ev
  cross join lateral (select private.souvenir_phase(ev) ph) p
  cross join lateral (select p.ph, case when p.ph = 'story'
        then (select count(*) from public.souvenir_photos f where f.event_id = ev.id and private.souvenir_visible(f, auth.uid()))
        else (select count(*) from public.souvenir_photos f where f.event_id = ev.id and f.hidden_at is null
              and not private.blocked_either(auth.uid(), f.author_id)) end n) x
  where ev.souvenirs_enabled and x.ph in ('story', 'waiting') and x.n > 0
    and (private.souvenir_circle(ev.id, auth.uid()) or private.souvenir_staff(ev.id, auth.uid()));
$$;
revoke all on function public.souvenir_stories() from public, anon;
grant execute on function public.souvenir_stories() to authenticated;
