/** App iPhone (WKWebView) : la discussion d'un événement s'ouvre en écran natif (window.PartyNative.chat, 16.11.2026).
 * Ailleurs (navigateur, ancienne app sans ce pont) : null, la page web la montre.
 * Version 2 (17.11) : l'app ouvre aussi les réglages de la discussion (cloche) en natif. */
type NativeChat = { openEvent: (id: string) => void; openEventSettings?: (id: string) => void; version?: number };

/** Événement que l'app peut envoyer à la page quand l'écran natif de la discussion se ferme : la pastille des non-lus se relit. */
export const NATIVE_CHAT_CLOSED = 'party-native-chat:closed';

export function nativeEventChat(): NativeChat | null {
  const native = (globalThis as { PartyNative?: { chat?: Partial<NativeChat> } }).PartyNative?.chat;
  return typeof native?.openEvent === 'function' ? (native as NativeChat) : null;
}

/** « Discussion » d'un événement : écran natif dans l'app iPhone, sinon la page de la discussion. */
export function openEventChat(id: string, push: (path: string) => void): void {
  const native = nativeEventChat();
  if (native) native.openEvent(id);
  else push(`/event/${id}/chat`);
}

/** Réglages natifs de la discussion (app de version 2 et plus) ; null ailleurs. */
export function nativeEventChatSettings(): ((id: string) => void) | null {
  const native = nativeEventChat();
  return native && (native.version ?? 1) >= 2 && typeof native.openEventSettings === 'function'
    ? (id) => native.openEventSettings!(id) : null;
}
