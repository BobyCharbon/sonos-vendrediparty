/** App iPhone (WKWebView) : la discussion d'un événement s'ouvre en écran natif (window.PartyNative.chat, 16.11.2026) ;
 * celle d'un groupe aussi, dans l'onglet Discussions (17.11). Ailleurs (navigateur, ancienne app sans ce pont) : null,
 * la page web la montre. */
type NativeChat = { openEvent: (id: string) => void; openGroup?: (id: string) => void };

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

/** « Discussion » d'un groupe (page du groupe) : Discussions natives de l'app iPhone, sinon la page web. */
export function openGroupChat(id: string, push: (path: string) => void): void {
  const native = nativeEventChat();
  if (typeof native?.openGroup === 'function') native.openGroup(id);
  else push(`/chats/${id}`);
}
