import SwiftUI

/// Réglages des Discussions (`public.chat_prefs`, soi seulement ; Discussions v2, 18.11) : qui peut m'envoyer une demande
/// de message, confirmations de lecture réciproques. Par le relais `POST /api/account/chats/rpc` (chat_prefs_get / _set).
struct ChatPrefs: Decodable, Equatable {
    /// "all" : tout membre ; "none" : personne.
    var messageRequests: String
    var readReceipts: Bool

    enum CodingKeys: String, CodingKey {
        case messageRequests = "message_requests", readReceipts = "read_receipts"
    }
}

@MainActor
final class ChatPrefsStore: ObservableObject {
    /// nil : pas encore lu, Discussions fermées sur ce site ou serveur d'avant les Discussions v2 (section cachée).
    @Published private(set) var prefs: ChatPrefs?
    @Published private(set) var saving = false
    @Published var error: String?

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    private struct Reply: Decodable { let result: ChatPrefs }

    func load() async {
        // Drapeau éteint (/api/account/chats* en 404) ou ancien serveur : pas de section, sans message d'erreur.
        guard let token = await web?.accountToken(),
              let reply: Reply = try? await api.postDecoding("/api/account/chats/rpc",
                                                              body: ["token": token, "fn": "chat_prefs_get", "args": [String: Any]()])
        else { return }
        prefs = reply.result
    }

    func set(messageRequests: String? = nil, readReceipts: Bool? = nil) async {
        guard let before = prefs, !saving else { return }
        var next = before
        var args: [String: Any] = [:]
        if let messageRequests { args["message_requests"] = messageRequests; next.messageRequests = messageRequests }
        if let readReceipts { args["read_receipts"] = readReceipts; next.readReceipts = readReceipts }
        saving = true
        defer { saving = false }
        prefs = next
        do {
            guard let token = await web?.accountToken() else { throw PartyAPIError.offline }
            try await api.post("/api/account/chats/rpc", body: ["token": token, "fn": "chat_prefs_set", "args": args])
            error = nil
        } catch {
            prefs = before
            self.error = "Ton réglage des Discussions n'a pas été enregistré. Vérifie ta connexion et réessaie."
        }
    }
}

/// Réglages › Confidentialité › Discussions : « Demandes de message » (Tout membre / Personne), « Confirmations de lecture ».
struct ChatPrefsSection: View {
    @ObservedObject var store: ChatPrefsStore

    var body: some View {
        if let prefs = store.prefs {
            Section {
                Picker(selection: Binding(get: { prefs.messageRequests },
                                          set: { v in Task { await store.set(messageRequests: v) } })) {
                    Text("Tout membre").tag("all")
                    Text("Personne").tag("none")
                } label: {
                    SettingsRow(symbol: "envelope.badge.fill", tint: .orange, title: "Demandes de message",
                                hint: prefs.messageRequests == "all"
                                    ? "Tout membre peut t'envoyer une demande (un seul message texte, à accepter ou non)"
                                    : "Plus aucune demande : seules les personnes avec un vrai lien t'écrivent")
                }
                .pickerStyle(.menu)
                .disabled(store.saving)
                .accessibilityIdentifier("privacy-message-requests")
                Toggle(isOn: Binding(get: { prefs.readReceipts },
                                     set: { v in Task { await store.set(readReceipts: v) } })) {
                    SettingsRow(symbol: "checkmark.message.fill", tint: .green, title: "Confirmations de lecture",
                                hint: "Dans un message direct, l'autre voit « Vu » quand tu as lu")
                }
                .disabled(store.saving)
                .accessibilityIdentifier("privacy-read-receipts")
                if let error = store.error { Text(error).foregroundStyle(.red).font(.footnote) }
            } header: {
                Text("Discussions")
            } footer: {
                Text("Les personnes avec qui tu as un groupe, un événement privé en commun ou dont tu as rejoint l'événement t'écrivent toujours directement. Si tu coupes les confirmations de lecture, tu ne vois plus celles des autres.")
            }
        }
    }
}
