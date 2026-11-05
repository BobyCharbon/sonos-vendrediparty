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
