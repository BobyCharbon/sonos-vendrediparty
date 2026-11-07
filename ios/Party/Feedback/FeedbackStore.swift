import Combine
import Foundation

/// Onglet « Ton avis » natif : envoyer une idée ou un bug, suivre ses retours et les réponses de l'hôte.
/// Mêmes règles et mêmes appels que la page web (index.html, section data-view="feedback").
@MainActor
final class FeedbackStore: ObservableObject {
    struct Notice: Equatable {
        let text: String
        let isError: Bool
    }

    @Published private(set) var items: [FeedbackItem] = []
    @Published private(set) var loaded = false
    @Published private(set) var sending = false
    @Published var kind: FeedbackKind = .idea
    @Published var text = ""
    @Published var notice: Notice?
    /// Hôte : son avis est classé dès l'envoi (statut, priorité, zone…) et 5 caractères suffisent.
    @Published var asAdmin = false
    @Published var draft = FeedbackDraft()
    /// Retours terminés depuis la dernière visite : mis en avant pendant cette visite, puis marqués « vus ».
    @Published private(set) var highlighted: Set<String> = []
    /// IA pour écrire l'avis (FeedbackAI.swift) : état, feuille d'accord, étape « C'est bien ça ? ».
    @Published private(set) var ai: FeedbackAI.Status?
    @Published private(set) var aiStep: FeedbackAI.Step = .none
    @Published private(set) var aiDraft: FeedbackAI.Draft?
    @Published var askingConsent = false
    @Published var aiExtra = ""
    /// Ce que la personne a dit : la description, puis ses réponses et corrections (gardé comme texte d'origine).
    private(set) var aiTurns: [String] = []
    private var consentAnswer: CheckedContinuation<Bool, Never>?

    private let api: PartyAPI
    private weak var web: WebStorage?
    /// Onglet d'où vient l'idée (Musique, Jeux…) : l'hôte sait de quoi on parle.
    private let fromTab: () -> String?

    init(api: PartyAPI, web: WebStorage, fromTab: @escaping () -> String?) {
        self.api = api
        self.web = web
        self.fromTab = fromTab
    }

    var trimmedText: String { text.trimmingCharacters(in: .whitespacesAndNewlines) }

    var minimumLength: Int { asAdmin ? FeedbackRules.adminMinimumLength : FeedbackRules.minimumLength }

    var canSend: Bool {
        !sending && (minimumLength...FeedbackRules.maximumLength).contains(trimmedText.count)
    }

    /// Minimum de caractères avant « Envoyer » : une phrase courte suffit quand l'IA reformule.
    private var effectiveMinimum: Int { aiReady ? FeedbackAI.minimumLength : minimumLength }
    /// L'IA peut reformuler (admin compris, retour du 07.11 : dictée + IA aussi pour l'hôte).
    var aiReady: Bool { ai?.usable == true }
    var canSubmit: Bool {
        !sending && aiStep == .none && (effectiveMinimum...FeedbackRules.maximumLength).contains(trimmedText.count)
    }
    var counterMinimum: Int { effectiveMinimum }

    /// Avis de l'hôte : créé déjà classé (POST /api/admin/feedback/new), puis « Mes retours » relus.
    func sendAsAdmin(_ admin: FeedbackAdminStore) async {
        guard canSend else { return }
        sending = true
        defer { sending = false }
        if await admin.create(kind: kind.rawValue, text: trimmedText, draft: draft, tab: fromTab()) {
            text = ""
            draft = FeedbackDraft()
            notice = Notice(text: "Merci ! Ton message est bien arrivé 🙏", isError: false)
            await appear()
        }
    }

    /// L'onglet s'affiche : ses retours, et les terminés passent « vus » (la pastille s'éteint aussi sur la page).
    func appear() async {
        guard let me = await web?.guestIdentity() else { return }
        do {
            items = try await api.feedback(guestID: me.id)
            loaded = true
            let unseen = Set(items.filter(\.unseen).map(\.id))
            guard !unseen.isEmpty else { return }
            highlighted.formUnion(unseen)
            try await api.markFeedbackSeen(guestID: me.id)
            web?.refreshFeedbackBadge()
        } catch {
            loaded = true  // le formulaire reste utilisable, comme sur la page
        }
    }

    // MARK: IA

    private var context: [String: String] {
        var out = FeedbackAI.deviceContext()
        if let tab = fromTab() { out["tab"] = tab }
        return out
    }

    func refreshAI() async {
        guard let me = await web?.guestIdentity() else { return }
        ai = try? await api.feedbackAIStatus(guestID: me.id, token: await web?.accountToken())
    }

    /// « Envoyer » (ou fin de la dictée) : l'IA reformule si elle peut aider (après l'accord), sinon envoi comme avant.
    func submit() async {
        guard canSubmit else { return }
        if !aiReady { return await sendPlain() }
        if ai?.accepted != true {
            guard await askConsent() else { return await sendPlain() }
        }
        aiTurns = [trimmedText]
        aiDraft = nil
        await rewrite()
    }

    /// Sans l'IA : les règles d'avant (30 caractères), dites si le texte est trop court.
    private func sendPlain() async {
        guard canSend else {
            notice = Notice(text: "Écris au moins \(minimumLength) caractères pour bien expliquer ton idée", isError: true)
            return
        }
        await send()
    }

    private func askConsent() async -> Bool {
        askingConsent = true
        return await withCheckedContinuation { consentAnswer = $0 }
    }

    /// Feuille d'accord : « J'accepte » ou « Écrire sans l'IA » (enregistré par compte, ou par invité).
    func answerConsent(_ accept: Bool) async {
        let answer = consentAnswer
        consentAnswer = nil  // la fermeture de la feuille (consentDismissed) ne répond plus à sa place
        askingConsent = false
        await setConsent(accept)
        answer?.resume(returning: accept && ai?.accepted == true)
    }

    /// Feuille fermée d'un geste : comme « Écrire sans l'IA » pour cet avis, sans rien enregistrer.
    func consentDismissed() {
        guard let answer = consentAnswer else { return }
        consentAnswer = nil
        answer.resume(returning: false)
    }

    func setConsent(_ accept: Bool) async {
        guard let me = await web?.guestIdentity() else { return }
        do {
            ai = try await api.feedbackAIConsent(guestID: me.id, token: await web?.accountToken(), accept: accept)
            if !accept, aiStep == .none { notice = Notice(text: "Accord retiré : plus rien n'est envoyé à l'IA.", isError: false) }
        } catch {
            notice = Notice(text: error.localizedDescription, isError: true)
        }
    }

    private func rewrite() async {
        guard let me = await web?.guestIdentity() else { return }
        aiStep = .loading
        do {
            let r = try await api.feedbackAIRewrite(guestID: me.id, token: await web?.accountToken(), name: me.name,
                                                    turns: aiTurns, context: context)
            guard !r.unavailable, let draft = r.draft else {
                notice = Notice(text: r.message.isEmpty ? "L'IA n'est pas disponible : écris ton avis comme d'habitude." : r.message, isError: true)
                aiStep = .none
                return
            }
            aiDraft = draft
            aiStep = r.needsInfo ? .question(r.question) : .ready
        } catch {
            notice = Notice(text: error.localizedDescription, isError: true)
            aiStep = .none
            await refreshAI()
        }
    }

    /// Réponse à la question, ou correction : l'IA reformule l'avis complet.
    func sendExtra(_ said: String? = nil) async {
        let extra = (said ?? aiExtra).trimmingCharacters(in: .whitespacesAndNewlines)
        guard !extra.isEmpty, aiTurns.count < (ai?.maxTurns ?? 4) else { return }
        aiTurns.append(extra)
        aiExtra = ""
        await rewrite()
    }

    func startCorrection() { aiExtra = ""; aiStep = .correcting }

    func cancelAI() { aiStep = .none; aiDraft = nil; aiTurns = [] }

    /// « Oui, envoyer » (version structurée) ou « Envoyer mon texte tel quel ».
    func sendAI(useDraft: Bool) async {
        guard let me = await web?.guestIdentity(), !aiTurns.isEmpty else { return }
        sending = true
        defer { sending = false }
        let draft = useDraft ? aiDraft : nil
        do {
            items = try await api.sendFeedback(guestID: me.id, name: me.name, kind: draft?.kind ?? kind.rawValue,
                                               text: aiTurns.joined(separator: " · "), context: context, draft: draft,
                                               token: await web?.accountToken())
            text = ""
            cancelAI()
            notice = Notice(text: "Merci ! Ton message est bien arrivé 🙏", isError: false)
            web?.refreshFeedbackBadge()
        } catch {
            notice = Notice(text: error.localizedDescription, isError: true)
        }
    }

    func send() async {
        guard canSend, let me = await web?.guestIdentity() else { return }
        sending = true
        defer { sending = false }
        do {
            items = try await api.sendFeedback(guestID: me.id, name: me.name, kind: kind.rawValue,
                                               text: trimmedText, fromTab: fromTab(), token: await web?.accountToken())
            text = ""
            notice = Notice(text: "Merci ! Ton message est bien arrivé 🙏", isError: false)
            web?.refreshFeedbackBadge()
        } catch {
            notice = Notice(text: error.localizedDescription, isError: true)
        }
    }
}
