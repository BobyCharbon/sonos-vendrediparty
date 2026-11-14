-- PROD, heure_des_votes (20261114100000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée modifiée : une colonne date_votes.voted_at (vide pour les votes d'avant) et un
-- déclencheur qui y met l'heure du serveur à chaque vote.
begin;
-- Heure de chaque vote de date (avis 2f5abe63e8ff de l'admin, 13.11.2026) : sous chaque réponse, on voit en petit
-- quand la personne a voté ou répondu. Les réponses (rsvps) gardaient déjà leur heure (updated_at) ; les votes de
-- dates n'en avaient pas. Les votes d'avant restent sans heure (rien n'est inventé). Purement additive et rejouable.

alter table public.date_votes add column if not exists voted_at timestamptz;
alter table public.date_votes alter column voted_at set default now();

create or replace function private.date_vote_time() returns trigger
language plpgsql set search_path = '' as $$
begin
  if tg_op = 'INSERT' or new.vote is distinct from old.vote then
    new.voted_at := now();  -- jamais l'heure envoyée par l'app : celle du serveur
  else
    new.voted_at := old.voted_at;
  end if;
  return new;
end;
$$;
revoke all on function private.date_vote_time() from public, anon, authenticated;

drop trigger if exists date_votes_time on public.date_votes;
create trigger date_votes_time before insert or update on public.date_votes
  for each row execute function private.date_vote_time();

insert into supabase_migrations.schema_migrations (version, name) values ('20261114100000', 'heure_des_votes') on conflict do nothing;
commit;
