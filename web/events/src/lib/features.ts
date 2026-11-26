/**
 * Fonctions en bêta. Compagnon (Zicou) : éteint hors site de test — Party sert alors la page avec
 * <html data-compagnon="off"> (app/features.py) : ni réglages, ni cadeaux Zicou, ni mesure dans l'admin.
 */
export const compagnonOn = typeof document === 'undefined' || document.documentElement.dataset.compagnon !== 'off';

/**
 * Discussions (groupes et messages directs) : absentes hors site de test — Party sert alors la page avec
 * <html data-discussions="off"> (app/features.py) : ni onglet, ni « Écrire » sur les fiches, ni page /chats.
 */
export const discussionsOn = typeof document === 'undefined' || document.documentElement.dataset.discussions !== 'off';

/**
 * Invitations v2 (carte « Invités », feuille « Inviter », réponse sans app) : en bêta, absentes hors site de test —
 * Party sert alors la page avec <html data-invites="off"> (app/features.py) : ancienne carte « Lien d'invitation ».
 */
export const invitesV2On = typeof document === 'undefined' || document.documentElement.dataset.invites !== 'off';

/**
 * Bar de la soirée (articles, stock, commandes, QR unique, barmans) : en construction, absent hors site de test — Party
 * sert alors la page avec <html data-bar="off"> (app/features.py) : ni bouton, ni carte, ni scanner du bar.
 */
export const barOn = typeof document === 'undefined' || document.documentElement.dataset.bar !== 'off';

/**
 * Agenda et Pronos : gardés en test (décision du 19.11) — Party sert la page avec <html data-agenda="off"> /
 * data-pronos="off" hors site de test (app/features.py) : ni entrée (Réglages, en-tête, groupe, fiche), ni page.
 */
/**
 * App VendrediParty de l'App Store (refus Apple 1.4.3, 25.11) : Party sert la page avec <html data-store="1">
 * (app/store_app.py) : aucun emoji de boisson à l'écran (emojis 🍻 🍷 des groupes montrés en 🎉, absents du choix).
 */
export const storeApp = typeof document !== 'undefined' && document.documentElement.dataset.store === '1';

export const agendaOn = typeof document === 'undefined' || document.documentElement.dataset.agenda !== 'off';
export const pronosOn = typeof document === 'undefined' || document.documentElement.dataset.pronos !== 'off';

/**
 * Souvenirs et Couverture d'événement (contrôle Apple du 26.11) : pas en prod — Party sert la page avec
 * <html data-souvenirs="off"> / <html data-covers="off"> (app/features.py), et jamais dans l'app App Store (storeApp).
 * Éteints : ni réglage, ni carte, ni bandeau, ni bouton, et le formulaire ne lit ni n'écrit leurs colonnes (absentes en prod).
 */
export const souvenirsOn = !storeApp && (typeof document === 'undefined' || document.documentElement.dataset.souvenirs !== 'off');
export const coversOn = !storeApp && (typeof document === 'undefined' || document.documentElement.dataset.covers !== 'off');
