-- Qui amène quoi : tout participant peut ajouter ce qu'il ramène (added_by = lui).
-- Les objets demandés par l'organisateur gardent added_by null (affichés « Demandé par l'organisateur »).

alter table public.bring_items add column added_by uuid references public.profiles (id) on delete set null;

create policy "ajouter ce que j'amène" on public.bring_items for insert with check (
  public.can_participate(event_id) and added_by = auth.uid() and claimed_by = auth.uid()
  and length(label) between 1 and 100);

create policy "retirer ce que j'ai ajouté" on public.bring_items for delete using (
  added_by = auth.uid() and public.can_participate(event_id));
