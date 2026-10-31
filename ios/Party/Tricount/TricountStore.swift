import SwiftUI

/// Tricount : mes groupes de dépenses, celui qui est ouvert, mon profil de paiement, et un lien à rejoindre
/// (lien universel /tricount/<lien> → « Rejoindre »). Le mode simplifié ou avancé est un choix de l'utilisateur.
@MainActor
final class TricountStore: ObservableObject {
    @Published private(set) var overview: TC.Overview?
    @Published private(set) var group: TC.Group?
    @Published private(set) var payment: TC.Payment?
    @Published private(set) var error: String?
    @Published private(set) var busy = false
    @Published var notice: String?
    /// Lien pour rejoindre reçu (lien universel) : l'écran de Réglages ouvre « Rejoindre ».
    @Published var pendingJoin: String?
    /// Simplifié (par défaut) : titre, montant, qui a payé, pour qui. Avancé : parts, montants, monnaie, date, ticket…
    @Published var advanced = UserDefaults.standard.bool(forKey: "tricountAdvanced") {
        didSet { UserDefaults.standard.set(advanced, forKey: "tricountAdvanced") }
    }

    private let api: PartyAPI
    private weak var web: WebStorage?

    init(api: PartyAPI, web: WebStorage?) {
        self.api = api
        self.web = web
    }

    var categories: [TC.Overview.Category] { overview?.categories ?? [] }
    var currencies: [String] { overview?.currencies ?? ["CHF", "EUR", "USD", "GBP"] }
    func category(_ id: String) -> TC.Overview.Category? { categories.first { $0.id == id } }

    func load() async { await run(loading: overview == nil) { token in overview = try await api.tricounts(token: token) } }

    func open(_ id: String) async {
        if group?.id != id { group = nil }
        await run(loading: group == nil) { token in group = try await api.tricount(token: token, id: id) }
    }

    @discardableResult
    func create(name: String, emoji: String, currency: String, myName: String) async -> TC.Group? {
        var made: TC.Group?
        await run { token in
            made = try await api.createTricount(token: token, name: name, emoji: emoji, currency: currency, myName: myName)
            group = made
            overview = try await api.tricounts(token: token)
        }
        return made
    }

    func update(name: String? = nil, emoji: String? = nil, currency: String? = nil, archived: Bool? = nil) async {
        guard let id = group?.id else { return }
        await apply { token in try await api.updateTricount(token: token, id: id, name: name, emoji: emoji, currency: currency, archived: archived) }
    }

    func renewLink() async {
        guard let id = group?.id else { return }
        await apply { token in try await api.renewTricountLink(token: token, id: id) }
        notice = "🔗 Nouveau lien : l'ancien ne marche plus"
    }

    func joinInfo(_ link: String) async -> TC.JoinInfo? {
        var info: TC.JoinInfo?
        await run { token in info = try await api.tricountJoinInfo(token: token, link: link) }
        return info
    }

    func join(_ link: String, myName: String, claim: String?) async -> TC.Group? {
        var joined: TC.Group?
        await run { token in
            joined = try await api.joinTricount(token: token, link: link, myName: myName, claim: claim)
            group = joined
            overview = try await api.tricounts(token: token)
        }
        return joined
    }

    func addMember(_ name: String) async {
        guard let id = group?.id else { return }
        await apply { token in try await api.tricountMember(token: token, id: id, member: nil, name: name) }
    }

    func renameMember(_ member: String, _ name: String) async {
        guard let id = group?.id else { return }
        await apply { token in try await api.tricountMember(token: token, id: id, member: member, name: name) }
    }

    func removeMember(_ member: String) async {
        guard let id = group?.id else { return }
        await apply { token in try await api.removeTricountMember(token: token, id: id, member: member) }
    }

    func leave() async -> Bool {
        guard let id = group?.id else { return false }
        var done = false
        await run { token in
            overview = try await api.leaveTricount(token: token, id: id)
            group = nil
            done = true
        }
        return done
    }

    /// Enregistre une dépense (nouvelle ou modifiée) ; la photo du ticket part d'abord, s'il y en a une.
    func save(_ draft: TricountDraft, receipt: Data?) async -> Bool {
        guard let g = group else { return false }
        if case .failure(let problem) = draft.payload(groupCurrency: g.currency, receiptPath: draft.receiptPath) {
            notice = problem.message
            return false
        }
        var done = false
        await run { token in
            var path = draft.receiptPath
            if let receipt { path = try await api.uploadTricountReceipt(token: token, id: g.id, jpeg: receipt) }
            guard case .success(let body) = draft.payload(groupCurrency: g.currency, receiptPath: path) else { return }
            group = try await api.saveTricountExpense(token: token, id: g.id, expense: body)
            done = true
        }
        if done { await refreshOverview() }
        return done
    }

    func delete(_ expense: String) async {
        guard let id = group?.id else { return }
        await apply { token in try await api.deleteTricountExpense(token: token, id: id, expense: expense) }
        await refreshOverview()
    }

    /// « C'est remboursé » : enregistre le virement proposé.
    func settle(_ t: TC.Settle) async {
        guard let id = group?.id else { return }
        await apply { token in try await api.settleTricount(token: token, id: id, from: t.from, to: t.to, cents: t.amount_cents) }
        notice = "✅ Remboursement enregistré"
        await refreshOverview()
    }

    func loadPayment() async { await run(loading: payment == nil) { token in payment = try await api.tricountPayment(token: token) } }

    func savePayment(_ p: TC.Payment) async -> Bool {
        var done = false
        await run { token in
            payment = try await api.saveTricountPayment(token: token, payment: p)
            done = true
        }
        if done { notice = "💾 Profil de paiement enregistré" }
        return done
    }

    private func refreshOverview() async {
        guard let token = await web?.accountToken() else { return }
        overview = (try? await api.tricounts(token: token)) ?? overview
    }

    private func apply(_ work: (String) async throws -> TC.Group) async {
        await run { token in group = try await work(token) }
    }

    private func run(loading: Bool = false, _ work: (String) async throws -> Void) async {
        guard let token = await web?.accountToken() else {
            error = "Connecte-toi pour utiliser le pot commun"
            return
        }
        busy = true
        defer { busy = false }
        do {
            try await work(token)
            if loading { error = nil }
        } catch PartyAPIError.needsCode {
            error = "Ta connexion a expiré : reconnecte-toi dans Réglages"
        } catch is CancellationError {
            return
        } catch {
            if loading { self.error = error.localizedDescription } else { notice = error.localizedDescription }
        }
    }
}

/// Une dépense en cours de saisie : le mode simplifié remplit titre, montant, payeur et « pour qui » (parts égales) ;
/// le mode avancé ajoute le partage par parts ou par montants, la monnaie, la date, la catégorie, la note et le ticket.
struct TricountDraft: Equatable {
    enum Split: String, CaseIterable, Identifiable {
        case equal, shares, amounts
        var id: String { rawValue }
        var label: String { ["equal": "Égal", "shares": "Parts", "amounts": "Montants"][rawValue] ?? rawValue }
    }
    struct Problem: Error, Equatable { let message: String }

    var id: String?
    var transfer = false
    var title = ""
    var amount = ""
    var payer = ""
    var forWhom: Set<String> = []
    var split = Split.equal
    var weights: [String: Double] = [:]
    var amounts: [String: String] = [:]
    var category = ""
    var date = Date()
    var currency = ""
    var rate = "1"
    var note = ""
    var receiptPath: String?

    /// Nouvelle dépense : payée par moi, pour tous les membres actifs.
    init(group: TC.Group) {
        payer = group.me ?? group.active.first?.id ?? ""
        forWhom = Set(group.active.map(\.id))
        currency = group.currency
    }

    /// Modifier une dépense existante.
    init(expense e: TC.Expense, group: TC.Group) {
        id = e.id
        transfer = e.isTransfer
        title = e.title
        amount = Money.typed(e.amount_cents)
        payer = e.paid_by
        forWhom = Set(e.shares.map(\.member_id))
        split = Split(rawValue: e.split_mode) ?? .equal
        weights = Dictionary(uniqueKeysWithValues: e.shares.map { ($0.member_id, $0.weight ?? 1) })
        amounts = Dictionary(uniqueKeysWithValues: e.shares.compactMap { s in s.amount_cents.map { (s.member_id, Money.typed($0)) } })
        category = e.category
        currency = e.currency
        rate = e.rate.map { String($0) } ?? "1"
        note = e.note ?? ""
        receiptPath = e.receipt_path
        if let day = e.spent_on, let parsed = Self.day.date(from: day) { date = parsed }
    }

    static let day: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    /// Corps envoyé au serveur, ou le problème à afficher (montant, personnes, total des montants…).
    func payload(groupCurrency: String, receiptPath: String?) -> Result<[String: Any], Problem> {
        let name = title.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty || transfer else { return .failure(Problem(message: "Écris un titre (ex. : Courses)")) }
        guard let total = Money.cents(amount) else { return .failure(Problem(message: "Montant invalide")) }
        guard !payer.isEmpty else { return .failure(Problem(message: "Qui a payé ?")) }
        let people = forWhom.sorted()
        guard !people.isEmpty else { return .failure(Problem(message: "Pour qui ? Choisis au moins une personne")) }
        var shares: [[String: Any]] = []
        switch split {
        case .equal:
            shares = people.map { ["member_id": $0] }
        case .shares:
            shares = people.compactMap { m in (weights[m] ?? 1) > 0 ? ["member_id": m, "weight": weights[m] ?? 1] : nil }
            if shares.isEmpty { return .failure(Problem(message: "Donne au moins une part")) }
        case .amounts:
            var sum = 0
            for m in people {
                guard let c = Money.cents(amounts[m] ?? "") else { continue }
                shares.append(["member_id": m, "amount_cents": c])
                sum += c
            }
            if sum != total {
                return .failure(Problem(message: "Les montants font \(Money.text(sum, currency)) au lieu de \(Money.text(total, currency))"))
            }
        }
        let fx = Double(rate.replacingOccurrences(of: ",", with: ".")) ?? 1
        var body: [String: Any] = ["kind": transfer ? "transfer" : "expense", "title": transfer && name.isEmpty ? "Remboursement" : name,
                                   "amount_cents": total, "paid_by": payer, "split_mode": split.rawValue, "shares": shares,
                                   "currency": currency.isEmpty ? groupCurrency : currency, "rate": currency == groupCurrency ? 1 : fx,
                                   "spent_on": Self.day.string(from: date), "note": note]
        if let id { body["id"] = id }
        if !category.isEmpty { body["category"] = category }
        if let receiptPath { body["receipt_path"] = receiptPath }
        return .success(body)
    }
}
