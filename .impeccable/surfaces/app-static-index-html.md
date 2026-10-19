---
version: 1
slug: "app-static-index-html"
primary_target: "app/static/index.html"
related_targets: ["web/events/src/app/(tabs)/index.tsx", "app/static/admin.html", "web/events/src/app/settings/notifications.tsx", "web/events/src/app/admin/announcements.tsx"]
---

# Onglet Événements de Party

## Direction contract

**THESIS** — Les sorties du groupe rejoignent Musique et Jeux dans la même webapp Party. La connexion SMS est obligatoire pour les événements ; musique et jeux gardent leurs accès actuels.

**OWN-WORLD** — Conserver le violet sombre de Party, les accents rose et orange, la largeur mobile de 640 px, Bricolage Grotesque pour les titres et les contrôles arrondis existants. Le contenu événementiel hérite de cette identité.

**STORY** — Ouvrir Événements, se connecter au compte existant, retrouver les sorties, voter, discuter ou proposer. Les comptes et données Supabase/Twilio sont conservés.

**FIRST VIEWPORT** — Le troisième onglet rejoint la barre inférieure. Il ouvre un module hébergé sur le même site, avec connexion SMS ou liste des sorties. Les liens Activité, Profil et Admin sont secondaires dans ce module.

**FORM** — Extension précise de la navigation existante, sans nouvelle identité ni sélection de concepts. Réutilisation des écrans fonctionnels, adaptée à une présentation web intégrée.

**NOTIFICATIONS** — Choisir les alertes facultatives et les abonnements catégorie/tag ; activation propre à chaque navigateur et heures silencieuses. Les annonces admin sont obligatoires dans l’interface, restent accessibles après lecture et ne suivent pas les filtres. Le système d’exploitation reste maître de son autorisation push. La page admin musique intègre aussi Événements, avec les droits du compte SMS.

**FINISH** — unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
