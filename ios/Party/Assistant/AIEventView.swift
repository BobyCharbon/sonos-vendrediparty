import MapKit
import SwiftUI

/// « ✨ Avec l'IA » (Événements) : on décrit l'événement à voix haute (ou par écrit) ; l'IA le remplit, pose ses
/// questions s'il manque quelque chose ; la fiche s'affiche avec l'adresse trouvée, et « Créer » ne s'active
/// qu'après 5 secondes, le temps de tout relire.
struct AIEventView: View {
    @ObservedObject var store: AIEventStore
    /// Événement créé : l'app l'ouvre dans Événements.
    let open: (String) -> Void
    @StateObject private var dictation = Dictation()
    @Environment(\.dismiss) private var dismiss
    @State private var typed = ""
    @State private var countdown = AIEventView.reviewSeconds
    @State private var tick: Task<Void, Never>?
    @FocusState private var typing: Bool

    static let reviewSeconds = 5

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let created = store.created {
                        done(created)
                    } else {
                        if store.turns.isEmpty { tips }
                        if !store.turns.isEmpty { said }
                        if store.thinking { thinkingCard }
                        if let draft = store.draft, !store.thinking {
                            if !draft.ready { questions(draft) }
                            review(draft)
                        }
                        if let error = store.error ?? dictation.problem {
                            Label(error, systemImage: "exclamationmark.triangle.fill")
                                .font(.footnote).foregroundStyle(.orange)
                        }
                    }
                }
                .padding(16)
                .padding(.bottom, 140)
            }
            .scrollDismissesKeyboard(.interactively)
            .safeAreaInset(edge: .bottom) { if store.created == nil { inputBar } }
            .navigationTitle("Créer avec l'IA")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Fermer") { close() } }
                if !store.turns.isEmpty && store.created == nil {
                    ToolbarItem(placement: .primaryAction) {
                        Button("Recommencer") { dictation.finish(); store.reset(); typed = "" }
                    }
                }
            }
            .onChange(of: store.draft) { _ in restartCountdown() }
            .onChange(of: store.place) { _ in restartCountdown() }
            .onDisappear { dictation.finish(); tick?.cancel() }
        }
        .tint(Palette.accent)
    }

    // ── Avant de parler : ce qu'on peut dire ──
    private var tips: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Décris ton événement", systemImage: "sparkles").font(.title3.weight(.bold))
            Text("Touche le micro et parle naturellement. Dis ce que tu sais : l'IA te demandera ce qui manque.")
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 8) {
                tip("text.bubble", "Quoi", "raclette, bowling, anniversaire de Tom…")
                tip("calendar", "Quand", "« samedi à 19h », « le 14 novembre de 20h à minuit »")
                tip("mappin.and.ellipse", "Où", "une adresse ou un lieu : « au Fun Planet de Villeneuve »")
                tip("person.3", "Qui", "« pour le groupe Ski » ; sinon Vendredi Party")
                tip("plus.circle", "En plus", "prix, nombre de places, quoi amener, « avec un pot commun »")
            }
            .padding(14)
            .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            VStack(alignment: .leading, spacing: 6) {
                Text("Par exemple").font(.footnote.weight(.semibold)).foregroundStyle(.secondary)
                example("Raclette chez moi samedi à 19 heures, chemin des Vignes 4 à Lutry, chacun amène une salade.")
                example("Bowling au Fun Planet de Villeneuve vendredi 14 novembre à 20 heures, 25 francs, 12 places.")
                example("Soirée jeux pour le groupe Ski dimanche à 15 heures chez Léa, avec un pot commun.")
            }
        }
    }

    private func tip(_ symbol: String, _ title: String, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: symbol).foregroundStyle(Palette.accent).frame(width: 22)
            Text("**\(title)** · \(text)").font(.subheadline)
        }
    }

    private func example(_ text: String) -> some View {
        Text("« \(text) »").font(.subheadline).italic().foregroundStyle(.secondary)
    }

    // ── Ce que la personne a dit ──
    private var said: some View {
        VStack(alignment: .trailing, spacing: 6) {
            ForEach(Array(store.turns.enumerated()), id: \.offset) { _, t in
                Text(t).font(.subheadline)
                    .padding(.horizontal, 12).padding(.vertical, 8)
                    .background(Palette.accent.opacity(0.22), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
    }

    private var thinkingCard: some View {
        HStack(spacing: 12) {
            ProgressView()
            Text("L'IA prépare ton événement…").foregroundStyle(.secondary)
        }
        .padding(.vertical, 6)
    }

    // ── L'IA a besoin de précisions ──
    private func questions(_ d: AIEvent.Draft) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Il me manque quelques infos", systemImage: "questionmark.bubble.fill")
                .font(.headline).foregroundStyle(.orange)
            ForEach(d.questions, id: \.self) { q in Text("• \(q)").font(.subheadline) }
            Text("Réponds avec le micro ou par écrit, en bas.").font(.caption).foregroundStyle(.secondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.orange.opacity(0.12), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .accessibilityIdentifier("ai-questions")
    }

    // ── La fiche à relire ──
    private func review(_ d: AIEvent.Draft) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if !d.summary.isEmpty {
                Text(d.summary).font(.subheadline).foregroundStyle(.secondary)
            }
            Text(d.title.isEmpty ? "Titre à préciser" : d.title).font(.title2.weight(.bold))
            row("calendar", d.start.isEmpty ? "Date à préciser" : AIEvent.span(d.start, d.end))
            placeRow(d)
            row("person.3", d.audience)
            if d.price_chf > 0 { row("banknote", String(format: "%.2f CHF par personne", d.price_chf)) }
            if d.max_participants > 0 { row("person.crop.circle.badge.checkmark", "\(d.max_participants) places") }
            if !d.category.isEmpty { row("tag", d.category) }
            if d.pot { row("banknote.fill", "Pot commun pour les présents") }
            if !d.bring.isEmpty { row("bag", "À amener : " + d.bring.joined(separator: ", ")) }
            if !d.description.isEmpty { Text(d.description).font(.subheadline) }
            if d.ready { createButton }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .accessibilityIdentifier("ai-review")
    }

    private func row(_ symbol: String, _ text: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Image(systemName: symbol).foregroundStyle(Palette.accent).frame(width: 22)
            Text(text).font(.body)
        }
    }

    @ViewBuilder
    private func placeRow(_ d: AIEvent.Draft) -> some View {
        if store.searchingPlace {
            HStack(spacing: 10) { ProgressView(); Text("Recherche de l'adresse…").foregroundStyle(.secondary) }
        } else if let p = store.place {
            VStack(alignment: .leading, spacing: 8) {
                row("mappin.and.ellipse", p.name + (p.address.isEmpty || p.address == p.name ? "" : "\n" + p.address))
                Map(coordinateRegion: .constant(MKCoordinateRegion(
                    center: CLLocationCoordinate2D(latitude: p.latitude, longitude: p.longitude),
                    span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01))),
                    interactionModes: [],
                    annotationItems: [p]) { item in
                    MapMarker(coordinate: CLLocationCoordinate2D(latitude: item.latitude, longitude: item.longitude), tint: .pink)
                }
                .frame(height: 130)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                HStack {
                    if let url = URL(string: p.url) { Link("Voir dans Google Maps", destination: url).font(.footnote) }
                    Spacer()
                    Button("Pas ce lieu") { store.dropPlace() }.font(.footnote).foregroundStyle(.secondary)
                }
            }
        } else if !d.place_name.isEmpty || !d.place_query.isEmpty {
            row("mappin.and.ellipse", (d.place_name.isEmpty ? d.place_query : d.place_name) + "\nAdresse non trouvée : dis-la plus précisément si tu veux")
        }
    }

    private var createButton: some View {
        Button {
            Task { await store.create() }
        } label: {
            HStack {
                if store.creating { ProgressView().tint(.black) }
                Text(countdown > 0 ? "Relis bien… \(countdown)" : "Créer l'événement")
                    .font(.headline)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(countdown > 0 ? Color.white.opacity(0.12) : Palette.accent, in: Capsule())
            .foregroundStyle(countdown > 0 ? Color.secondary : Color.black)
        }
        .disabled(countdown > 0 || store.creating)
        .animation(.easeInOut, value: countdown)
        .accessibilityIdentifier("ai-create")
    }

    // ── C'est fait ──
    private func done(_ c: AIEvent.Created) -> some View {
        VStack(spacing: 14) {
            Image(systemName: "checkmark.circle.fill").font(.system(size: 56)).foregroundStyle(.green)
            Text(c.title).font(.title2.weight(.bold)).multilineTextAlignment(.center)
            Text(c.status == "published" ? "Événement publié : les invités sont prévenus."
                                         : "Événement proposé : il sera visible une fois validé par un admin.")
                .foregroundStyle(.secondary).multilineTextAlignment(.center)
            Button("Voir l'événement") { open(c.id); close() }
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 40)
    }

    // ── Micro et clavier ──
    private var inputBar: some View {
        VStack(spacing: 10) {
            if dictation.listening {
                Text(dictation.text.isEmpty ? "Je t'écoute…" : dictation.text)
                    .font(.subheadline).frame(maxWidth: .infinity, alignment: .leading)
                    .padding(12)
                    .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            HStack(spacing: 10) {
                TextField(store.draft?.ready == false ? "Ta réponse…" : store.draft == nil ? "Ou écris ici…" : "Une correction ?",
                          text: $typed, axis: .vertical)
                    .lineLimit(1...4)
                    .focused($typing)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .accessibilityIdentifier("ai-text")
                if !typed.trimmingCharacters(in: .whitespaces).isEmpty {
                    Button { submit(typed) } label: { Image(systemName: "arrow.up.circle.fill").font(.system(size: 34)) }
                        .accessibilityLabel("Envoyer")
                } else {
                    Button { toggleMic() } label: {
                        Image(systemName: dictation.listening ? "stop.circle.fill" : "mic.circle.fill")
                            .font(.system(size: 44))
                            .foregroundStyle(dictation.listening ? .red : Palette.accent)
                    }
                    .accessibilityLabel(dictation.listening ? "Arrêter et envoyer" : "Parler")
                    .accessibilityIdentifier("ai-mic")
                }
            }
            .disabled(store.thinking)
        }
        .padding(.horizontal, 16).padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    private func toggleMic() {
        if dictation.listening {
            dictation.finish()
            submit(dictation.text)
        } else {
            typing = false
            Task { await dictation.start() }
        }
    }

    private func submit(_ text: String) {
        typed = ""
        typing = false
        Task { await store.send(text) }
    }

    private func restartCountdown() {
        tick?.cancel()
        countdown = Self.reviewSeconds
        guard store.draft?.ready == true else { return }
        tick = Task { @MainActor in
            while countdown > 0 {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                if Task.isCancelled { return }
                countdown -= 1
            }
        }
    }

    private func close() {
        dictation.finish()
        if store.created != nil { store.reset() }
        dismiss()
    }
}

extension AIEvent.Place: Identifiable {
    var id: String { url }
}
