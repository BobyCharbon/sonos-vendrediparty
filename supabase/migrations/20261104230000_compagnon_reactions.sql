-- Zicou, « Zicou réagit à ce que tu fais » (décision F de l'admin, 4 novembre 2026) : migration devenue NEUTRE.
--
-- Elle ajoutait à pet_load les réponses à un événement (« answers ») pour un petit bonus. Décision de l'admin du
-- 4 novembre 2026 : répondre à un événement ne rapporte plus rien, et la présence non plus (les pièces d'un événement
-- passent par le droit « zicou.event_coins », migration 20261105090000, qui redéfinit pet_load sans « answers »).
-- Gardée (vide) pour que l'historique des migrations reste le même partout ; rejouer le dossier sur une base vide donne
-- la même base : pet_load de 20261104210000, puis celui de 20261105090000.

select 1;
