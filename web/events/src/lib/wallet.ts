import { supabase } from './supabase';

/**
 * Billets dans Cartes Apple (Wallet) : après un changement (arrivée, paiement, nouveau QR, événement modifié), le
 * serveur Party prévient les iPhone qui ont ajouté le billet ; ils redemandent alors le pass à jour.
 * member : un participant ; absent : tous les billets de l'événement. La base vérifie les droits.
 * Ne bloque jamais l'écran : sans Wallet configuré ou hors ligne, rien ne se passe.
 */
export function notifyWallet(eventId: string, member?: string | null): void {
  void (async () => {
    try {
      const { data } = await supabase.auth.getSession();
      const token = data.session?.access_token;
      if (!token || typeof fetch !== 'function') return;
      await fetch('/api/wallet/notify', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, event_id: eventId, member: member ?? null }),
      });
    } catch {
      // Mise à jour du pass manquée : Cartes la récupère au prochain rafraîchissement du billet.
    }
  })();
}
