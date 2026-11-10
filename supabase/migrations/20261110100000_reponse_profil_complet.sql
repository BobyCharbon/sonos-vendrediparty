-- Répondre ou voter exige un profil complet (recette réelle du 10.11.2026, lien public « Partager ») :
-- un compte au profil vide pouvait, par l'API, poser un « Présent » ou un vote de date sur tout événement public
-- (l'organisateur voyait un invité sans nom). L'écran l'interdisait déjà (« Faisons connaissance » d'abord) ;
-- la base le garantit désormais, comme accept_invite (profile_required, migration 20261110090000).
-- Seulement à la CRÉATION, et seulement pour soi : l'organisateur qui note la présence de quelqu'un, les fonctions
-- internes sans session et un ancien invité qui change sa réponse existante ne sont pas touchés. Photo facultative.
-- Purement additif et rejouable.
create or replace function private.guard_answer_identity() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is not null and new.user_id = auth.uid() and not private.identity_complete(auth.uid()) then
    raise exception 'profile_required: complète ton profil (prénom, nom et surnom) pour répondre' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.guard_answer_identity() from public, anon, authenticated;

drop trigger if exists rsvps_identity on public.rsvps;
create trigger rsvps_identity before insert on public.rsvps
  for each row execute function private.guard_answer_identity();
drop trigger if exists date_votes_identity on public.date_votes;
create trigger date_votes_identity before insert on public.date_votes
  for each row execute function private.guard_answer_identity();
