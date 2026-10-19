// Ce module est exclusivement web : les notifications de musique restent gérées par Party.
export type PushRegistration = 'web';
export async function registerPushToken(_userId: string, _requestPermission = false): Promise<PushRegistration> { return 'web'; }
export async function unregisterPushToken(): Promise<void> {}
