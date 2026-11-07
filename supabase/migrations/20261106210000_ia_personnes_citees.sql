-- « Créer avec l'IA » (retour de l'admin, 06.11.2026) : les personnes citées à l'IA sont retenues avec le BROUILLON,
-- sans être invitées, pour être cochées d'avance quand l'étape 2 « Qui est invité » est rouverte depuis la fiche
-- (« Inviter et publier »). Écrites par le serveur juste après la création du brouillon (session de l'organisateur),
-- vidées à la publication par l'étape 2. Seuls les identifiants des personnes, jamais une invitation.
-- Purement additive et rejouable.
alter table public.events add column if not exists ai_suggested uuid[] not null default '{}';
comment on column public.events.ai_suggested is
  'Assistant IA : personnes citées (cochées d''avance à l''étape 2), jamais invitées ; vidé à la publication.';

notify pgrst, 'reload schema';
