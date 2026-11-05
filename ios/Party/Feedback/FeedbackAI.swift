import Foundation
import UIKit

/// « Ton avis » écrit avec l'IA (app/ai_feedback.py ; page web : app/static/feedback-ai.js). Ouvert à tous ceux qui
/// écrivent un avis, après l'accord de la feuille (Apple 5.1.2(i)) ; sans accord ou sans IA, l'avis s'écrit comme avant.
enum FeedbackAI {
    /// POST /api/feedback/ai/status et /consent.
    struct Status: Decodable, Equatable {
        var configured: Bool
        /// "" (jamais demandé) · "accepted" · "declined"
        var consent: String
        var remaining: Int
        var maxTurns: Int

        enum CodingKeys: String, CodingKey { case configured, consent, remaining, maxTurns = "max_turns" }

        init(configured: Bool, consent: String, remaining: Int, maxTurns: Int = 4) {
            (self.configured, self.consent, self.remaining, self.maxTurns) = (configured, consent, remaining, maxTurns)
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            configured = (try? c.decode(Bool.self, forKey: .configured)) ?? false
            consent = (try? c.decode(String.self, forKey: .consent)) ?? ""
            remaining = (try? c.decode(Int.self, forKey: .remaining)) ?? 0
            maxTurns = (try? c.decode(Int.self, forKey: .maxTurns)) ?? 4
        }

        var accepted: Bool { consent == "accepted" }
        /// L'IA peut aider : configurée, pas refusée, des reformulations restantes aujourd'hui.
        var usable: Bool { configured && consent != "declined" && remaining > 0 }
    }

    /// Avis reformulé (clean_draft du serveur) ; renvoyé tel quel à l'envoi, où le serveur le revalide.
    struct Draft: Codable, Equatable {
        var kind: String
        var area: String
        var game: String
        var title: String
        var description: String
        var steps: [String]
        var expected: String
        var actual: String
        var need: String
        var proposal: String
        var device: String?

        /// Corps JSON pour POST /api/feedback (« ai »).
        var json: [String: Any] {
            guard let data = try? JSONEncoder().encode(self),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
            return object
        }

        /// Lignes affichées sous le titre (« C'est bien ça ? »), dans l'ordre de la page web.
        var rows: [(label: String, text: String)] {
            var out: [(String, String)] = []
            if !steps.isEmpty { out.append(("Étapes", steps.enumerated().map { "\($0.offset + 1). \($0.element)" }.joined(separator: "\n"))) }
            for (label, text) in [("Attendu", expected), ("Ce qui se passe", actual), ("Le besoin", need),
                                  ("La proposition", proposal), ("Appareil", device ?? "")] where !text.isEmpty {
                out.append((label, text))
            }
            return out
        }
    }

    /// POST /api/feedback/ai/rewrite : avis prêt, question de précision, ou IA indisponible (on écrit sans elle).
    struct Rewrite: Decodable, Equatable {
        let status: String
        let question: String
        let draft: Draft?
        let message: String

        enum CodingKeys: String, CodingKey { case status, question, draft, message }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            status = try c.decode(String.self, forKey: .status)
            question = (try? c.decode(String.self, forKey: .question)) ?? ""
            draft = try? c.decode(Draft.self, forKey: .draft)
            message = (try? c.decode(String.self, forKey: .message)) ?? ""
        }

        var unavailable: Bool { status == "unavailable" || draft == nil }
        var needsInfo: Bool { status == "needs_info" && !question.isEmpty }
    }

    /// Étape de l'écran : rien, reformulation en cours, question, « C'est bien ça ? », correction.
    enum Step: Equatable { case none, loading, question(String), ready, correcting }

    static let minimumLength = 8  // FEEDBACK_AI_MIN_LENGTH (app/main.py)
    /// Accord unique pour toute l'IA de Party, version 2 (CONSENT_VERSION de app/ai_feedback.py, feuille #fbAiConsent
    /// de index.html) : un accord d'une version plus ancienne revient « à demander » et la feuille se rouvre.
    static let consentVersion = 2
    static let consentTitle = "✨ Utiliser l'IA de Party ?"
    static let consentText = "Quand tu utilises l'IA, Party envoie ce que tu lui confies à Anthropic (Claude) : le texte de ton avis (et la transcription de ta voix) ; avec l'assistant des événements, ta description, tes captures d'écran, tes photos et les liens que tu donnes ; pour un ticket du pot commun, sa photo."
    static let consentFootnote = "Jamais ton numéro. Un seul accord pour toute l'IA de Party, que tu peux retirer à tout moment dans Réglages › Ton avis. Sans accord, tout marche sans l'IA."

    static let kinds = ["idea": "💡 Idée", "bug": "🐞 Bug", "other": "💬 Autre"]
    static let areas = ["music": "🎵 Musique", "games": "🎲 Jeux", "pet": "🐾 Zicou", "events": "📅 Événements",
                        "calendar": "🗓️ Calendrier", "chats": "💬 Discussions", "account": "⚙️ Réglages",
                        "admin": "🛠️ Retours", "tv": "📺 Apple TV", "general": "🌐 Général"]

    /// Appareil rempli par l'app (jamais par l'IA) : « iPhone · iOS 26.1 · app 2.4 (51) » côté serveur.
    static func deviceContext(info: [String: Any]? = Bundle.main.infoDictionary,
                              system: String = UIDevice.current.systemVersion,
                              idiom: UIUserInterfaceIdiom = UIDevice.current.userInterfaceIdiom) -> [String: String] {
        let version = info?["CFBundleShortVersionString"] as? String ?? ""
        let build = info?["CFBundleVersion"] as? String ?? ""
        var out = ["platform": idiom == .pad ? "ipad" : "iphone", "os": "iOS \(system)"]
        if !version.isEmpty { out["app"] = build.isEmpty ? version : "\(version) (\(build))" }
        return out
    }
}

extension PartyAPI {
    private func aiBody(_ guestID: String, _ token: String?, _ extra: [String: Any] = [:]) -> [String: Any] {
        ["guest_id": guestID, "token": token ?? ""].merging(extra) { _, new in new }
    }

    func feedbackAIStatus(guestID: String, token: String?) async throws -> FeedbackAI.Status {
        try await postDecoding("/api/feedback/ai/status", body: aiBody(guestID, token))
    }

    func feedbackAIConsent(guestID: String, token: String?, accept: Bool) async throws -> FeedbackAI.Status {
        try await postDecoding("/api/feedback/ai/consent", body: aiBody(guestID, token, ["accept": accept]))
    }

    /// Le nom sert seulement au journal de l'admin : il n'entre jamais dans le prompt (app/ai_feedback.py).
    func feedbackAIRewrite(guestID: String, token: String?, name: String, turns: [String], context: [String: String]) async throws -> FeedbackAI.Rewrite {
        try await postDecoding("/api/feedback/ai/rewrite",
                               body: aiBody(guestID, token, ["name": name, "turns": turns, "context": context]), timeout: 45)
    }

    /// Avis envoyé avec sa version structurée (ou tel quel si draft est nil) et l'appareil.
    func sendFeedback(guestID: String, name: String, kind: String, text: String, context: [String: String],
                      draft: FeedbackAI.Draft?, token: String?) async throws -> [FeedbackItem] {
        var body: [String: Any] = ["guest_id": guestID, "name": name, "kind": kind, "text": text, "token": token ?? "",
                                   "context": context]
        if let draft { body["ai"] = draft.json }
        let list: FeedbackList = try await postDecoding("/api/feedback", body: body)
        return list.mine
    }
}
