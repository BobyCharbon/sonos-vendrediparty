-- Deux nouveaux rôles : invité (compte connecté, pas encore membre du groupe) et organisateur.
-- Fichier séparé : Postgres n'autorise l'usage d'une nouvelle valeur d'énumération qu'après sa validation.
alter type public.member_role add value if not exists 'guest' before 'member';
alter type public.member_role add value if not exists 'organizer' after 'member';
