-- Qui amène quoi : tout participant peut ajouter ce qu'il ramène (added_by = lui).
-- Les objets demandés par l'organisateur gardent added_by null (affichés « Demandé par l'organisateur »).
-- Purement additif : la base est partagée entre le site de test et la production, et le code de production
-- (qui n'utilise pas encore added_by) continue de fonctionner une fois cette migration appliquée.

alter table public.bring_items add column if not exists added_by uuid references public.profiles (id) on delete set null;

drop policy if exists "ajouter ce que j'amène" on public.bring_items;
create policy "ajouter ce que j'amène" on public.bring_items for insert with check (
  public.can_participate(event_id) and added_by = auth.uid() and claimed_by = auth.uid()
  and length(label) between 1 and 100);

drop policy if exists "retirer ce que j'ai ajouté" on public.bring_items;
create policy "retirer ce que j'ai ajouté" on public.bring_items for delete using (
  added_by = auth.uid() and public.can_participate(event_id));

-- La politique « prendre un objet » autorise la mise à jour de la ligne entière : sans garde, un participant
-- pourrait renommer l'objet d'un autre, ou s'en déclarer l'auteur (added_by) pour ensuite le supprimer.
-- Hors admin et organisateur, seul « qui l'amène » (claimed_by) peut changer ; le reste est remis tel quel.
create or replace function public.guard_bring_item() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is not null and not (public.is_admin() or public.is_organizer(old.event_id)) then
    new.event_id := old.event_id;
    new.label := old.label;
    new.sort := old.sort;
    new.added_by := old.added_by;
  end if;
  return new;
end $$;

drop trigger if exists bring_items_guard on public.bring_items;
create trigger bring_items_guard before update on public.bring_items
  for each row execute function public.guard_bring_item();
