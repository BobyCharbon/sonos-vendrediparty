-- Avis ede29a5bb24e (22.11.2026) : une note privée sur le profil d'une personne (« où on l'a rencontrée… »).
-- Une note par (auteur, personne), lue et écrite par son AUTEUR seul (RLS : jamais par la personne notée, ni par un
-- admin à l'écran ; aucune fonction ne la montre à quelqu'un d'autre), 500 caractères au plus, effacée avec le compte
-- de l'auteur OU de la personne (cascade). Pas de filtre : personne d'autre ne la lit, et rien ne la partage.
-- Purement additive et rejouable.
create table if not exists public.member_notes (
  author_id  uuid not null references auth.users(id) on delete cascade,
  target_id  uuid not null references auth.users(id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 500),
  updated_at timestamptz not null default now(),
  primary key (author_id, target_id),
  check (author_id <> target_id)
);
create index if not exists member_notes_target_idx on public.member_notes (target_id);
alter table public.member_notes enable row level security;
revoke all on public.member_notes from public, anon;
grant select, insert, update, delete on public.member_notes to authenticated;

drop policy if exists member_notes_own on public.member_notes;
create policy member_notes_own on public.member_notes for all to authenticated
  using (author_id = (select auth.uid())) with check (author_id = (select auth.uid()));

-- Ma note sur cette personne (null s'il n'y en a pas). Invoker : la RLS décide.
create or replace function public.member_note_get(target uuid) returns jsonb
language sql stable security invoker set search_path = '' as $$
  select jsonb_build_object('body', n.body, 'updated_at', n.updated_at)
  from public.member_notes n where n.author_id = auth.uid() and n.target_id = target;
$$;

-- Écrire ma note ; un texte vide l'efface. Rend la note (ou null).
create or replace function public.member_note_set(target uuid, body text) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare me uuid := auth.uid(); t text := btrim(coalesce(body, ''));
begin
  if me is null then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if target is null or target = me then raise exception 'invalid: Personne invalide' using errcode = '22023'; end if;
  if char_length(t) > 500 then raise exception 'invalid: 500 caractères au plus' using errcode = '22023'; end if;
  if t = '' then
    delete from public.member_notes n where n.author_id = me and n.target_id = target;
    return null;
  end if;
  insert into public.member_notes as n (author_id, target_id, body, updated_at) values (me, target, t, now())
  on conflict (author_id, target_id) do update set body = excluded.body, updated_at = now();
  return public.member_note_get(target);
end $$;

revoke all on function public.member_note_get(uuid) from public, anon;
revoke all on function public.member_note_set(uuid, text) from public, anon;
grant execute on function public.member_note_get(uuid) to authenticated;
grant execute on function public.member_note_set(uuid, text) to authenticated;
