/** App iPhone (WKWebView) : la discussion d'un événement s'ouvre en écran natif (window.PartyNative.chat, 16.11.2026) ;
 * celle d'un groupe aussi, dans l'onglet Discussions (17.11) ; un message direct et « Nouveau message » aussi
 * (Discussions v2, 18.11 : openDirect / newMessage). Ailleurs (navigateur, ancienne app sans ce pont) : null,
 * la page web la montre. Version 2 (17.11) : l'app ouvre aussi les réglages de la discussion (cloche) en natif. */
type NativeChat = {
  openEvent: (id: string) => void;
  openEventSettings?: (id: string) => void;
  version?: number;
  openGroup?: (id: string) => void;
  /** Conversation directe NATIVE avec cette personne (créée au besoin, demande de message comprise). */
  openDirect?: (userId: string) => void;
  /** « Nouveau message » natif, avec la carte d'une soirée jointe. */
  newMessage?: (options: { event_id?: string }) => void;
};

/** Événement que l'app peut envoyer à la page quand l'écran natif de la discussion se ferme : la pastille des non-lus se relit. */
export const NATIVE_CHAT_CLOSED = 'party-native-chat:closed';

function bridge(): Partial<NativeChat> | null {
  return (globalThis as { PartyNative?: { chat?: Partial<NativeChat> } }).PartyNative?.chat ?? null;
}

export function nativeEventChat(): NativeChat | null {
  const native = bridge();
  return typeof native?.openEvent === 'function' ? (native as NativeChat) : null;
}

/** « Discussion » d'un événement : écran natif dans l'app iPhone, sinon la page de la discussion. */
export function openEventChat(id: string, push: (path: string) => void): void {
  const native = nativeEventChat();
  if (native) native.openEvent(id);
  else push(`/event/${id}/chat`);
}

/** « Discussion » d'un groupe (page du groupe) : Discussions natives de l'app iPhone, sinon la page web. */
export function openGroupChat(id: string, push: (path: string) => void): void {
  const native = nativeEventChat();
  if (typeof native?.openGroup === 'function') native.openGroup(id);
  else push(`/chats/${id}`);
}

/** Écrire à quelqu'un : dans l'app iPhone, la conversation native (true) ; sinon false, la page web s'en charge. */
export function openNativeDirect(userId: string): boolean {
  const native = bridge();
  if (typeof native?.openDirect !== 'function') return false;
  native.openDirect(userId);
  return true;
}

/** « Envoyer à un ami » (fiche d'un événement) : « Nouveau message » avec la carte de la soirée jointe ; natif dans
 * l'app iPhone, sinon la page web /chats/new?event=<id>. */
export function sendEventToFriend(eventId: string, push: (path: string) => void): void {
  const native = bridge();
  if (typeof native?.newMessage === 'function') native.newMessage({ event_id: eventId });
  else push(`/chats/new?event=${eventId}`);
}

/** Réglages natifs de la discussion (app de version 2 et plus) ; null ailleurs. */
export function nativeEventChatSettings(): ((id: string) => void) | null {
  const native = nativeEventChat();
  return native && (native.version ?? 1) >= 2 && typeof native.openEventSettings === 'function'
    ? (id) => native.openEventSettings!(id) : null;
}
