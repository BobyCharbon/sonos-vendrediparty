import MapKit
import PhotosUI
import SwiftUI

/// « ✨ Avec l'IA » (Événements) : on décrit l'événement à voix haute (ou par écrit) ; l'IA le remplit, pose ses
/// questions s'il manque quelque chose ; la fiche s'affiche avec l'adresse trouvée, et « Créer » ne s'active
/// qu'après 5 secondes, le temps de tout relire.
struct AIEventView: View {
    @ObservedObject var store: AIEventStore
    /// Événement publié à modifier (« ✨ Modifier avec l'IA ») ; nil : créer un événement.
    var editing: String? = nil
    /// Événement créé : l'app l'ouvre dans Événements.
    let open: (String) -> Void
    @StateObject private var dictation = Dictation()
    @Environment(\.dismiss) private var dismiss
    @State private var typed = ""
    @State private var countdown = AIEventView.reviewSeconds
    @State private var tick: Task<Void, Never>?
    @FocusState private var typing: Bool
    @State private var picked: [PhotosPickerItem] = []

    static let reviewSeconds = 5

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let created = store.created {
                        done(created).motionTransition(.scale(scale: 0.9).combined(with: .opacity))
                    } else {
                        if store.turns.isEmpty {
                            if editing != nil { AIEditTips().transition(.opacity) } else { tips.transition(.opacity) }
                        }
                        if !store.turns.isEmpty { said }
                        if store.thinking { thinkingCard.motionTransition() }
                        if let draft = store.draft, !store.thinking {
                            if editing != nil && !store.turns.isEmpty {
                                AIChangesCard(changes: store.changes, announce: $store.announce).motionTransition()
                            }
                            if !draft.not_understood.isEmpty { notUnderstood(draft).motionTransition() }
                            if !draft.ready { questions(draft).motionTransition() }
                            review(draft).motionTransition()
                        }
                        if let error = store.error ?? dictation.problem {
                            Label(error, systemImage: "exclamationmark.triangle.fill")
                                .font(.footnote).foregroundStyle(.orange)
                                .motionTransition(.unfold)
                        }
                    }
                }
                // Chaque étape (phrase dite, l'IA réfléchit, fiche prête, questions, créé) arrive en douceur ;
                // le contenu de la fiche qui change (correction dictée) se fond au lieu de sauter.
                .motion(Motion.smooth, value: stage)
                .motion(Motion.smooth, value: store.draft)
                .motion(Motion.smooth, value: store.error ?? dictation.problem)
                .padding(16)
                .padding(.bottom, 140)
            }
            .scrollDismissesKeyboard(.interactively)
            .safeAreaInset(edge: .bottom) { if store.created == nil { inputBar } }
            .navigationTitle(editing == nil ? "Créer avec l'IA" : "Modifier avec l'IA")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Fermer") { close() } }
                if !store.turns.isEmpty && store.created == nil {
                    ToolbarItem(placement: .primaryAction) {
                        Button("Recommencer") { restart() }
                    }
                }
            }
            .task(id: editing) {
                if let editing, store.editingId != editing { await store.startEditing(editing) }
                else if editing == nil && store.editingId != nil { store.reset() }
            }
            .onChange(of: store.draft) { _ in restartCountdown() }
            .onChange(of: store.created != nil) { done in if done { Haptics.success() } }
            .onChange(of: store.error) { error in if error != nil { Haptics.error() } }
            .onChange(of: store.unsent) { text in
                guard let text else { return }
                typed = text
                store.unsent = nil
            }
            .onChange(of: store.place) { _ in restartCountdown() }
            .onDisappear { dictation.finish(); tick?.cancel() }
            .onChange(of: picked) { items in
                guard !items.isEmpty else { return }
                Task {
                    for item in items {
                        if let data = try? await item.loadTransferable(type: Data.self), let image = UIImage(data: data) {
                            store.attach(image)
                        }
                    }
                    picked = []
                }
            }
        }
        .tint(Palette.accent)
    }

    /// Étape affichée : sert de repère aux animations (pas le contenu, qui change à chaque correction).
    private var stage: String {
        if store.created != nil { return "created" }
        if store.thinking { return "thinking-\(store.turns.count)" }
        guard let draft = store.draft else { return "turns-\(store.turns.count)" }
        return "draft-\(draft.ready)-\(draft.questions.count)-\(draft.not_understood.count)-\(store.turns.count)"
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
                tip("link", "Déjà en ligne ?", "colle le lien de l'événement ou joins une capture d'écran : l'IA y lit tout")
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
                    .motionTransition(.asymmetric(insertion: .scale(scale: 0.85, anchor: .bottomTrailing).combined(with: .opacity),
                                                  removal: .opacity))
            }
        }
        .frame(maxWidth: .infinity, alignment: .trailing)
    }

    private var thinkingCard: some View {
        HStack(spacing: 12) {
            ThinkingSparkles()
            VStack(alignment: .leading, spacing: 2) {
                Text("L'IA prépare ton événement…").foregroundStyle(.secondary)
                Text("Elle réfléchit bien : ça prend souvent 20 à 40 secondes.").font(.caption).foregroundStyle(.secondary)
            }
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

    // ── Ce que l'IA n'a pas compris ──
    private func notUnderstood(_ d: AIEvent.Draft) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label("Pas bien compris", systemImage: "ear.trianglebadge.exclamationmark")
                .font(.headline).foregroundStyle(.secondary)
            ForEach(d.not_understood, id: \.self) { n in Text("• \(n)").font(.subheadline) }
            Text("Redis-le autrement si c'est important.").font(.caption).foregroundStyle(.secondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .accessibilityIdentifier("ai-not-understood")
    }

    // ── La fiche à relire ──
    private func review(_ d: AIEvent.Draft) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            if let cover = URL(string: d.cover_url), d.cover_url.hasPrefix("https://") {
                AsyncImage(url: cover) { image in
                    image.resizable().scaledToFill()
                } placeholder: {
                    Color.white.opacity(0.05)
                }
                .frame(maxWidth: .infinity).frame(height: 170)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .accessibilityLabel("Image de l'événement")
            }
            if !d.summary.isEmpty {
                Text(d.summary).font(.subheadline).foregroundStyle(.secondary)
            }
            Text(d.title.isEmpty ? "Titre à préciser" : d.title).font(.title2.weight(.bold))
                .id(d.title).transition(.opacity)
            if !d.description.isEmpty { Text(d.description).font(.subheadline) }

            part("Quand") { when(d) }
            part("Où") { placeRow(d) }
            part("Invités") {
                row("person.3", d.invitees.isEmpty ? d.audience
                    : d.audience == "Seulement les personnes invitées" ? d.invitees.joined(separator: ", ")
                    : d.audience + " + " + d.invitees.joined(separator: ", "))
                if !d.organizers.isEmpty { row("person.2.badge.gearshape", "Co-organisé avec " + d.organizers.joined(separator: ", ")) }
            }
            part("Réponses") {
                row("person.crop.circle.badge.checkmark", d.max_participants > 0
                    ? "\(d.max_participants) places" + (d.waitlist ? ", puis liste d'attente" : ", sans liste d'attente")
                    : "Places illimitées")
                row("person.badge.plus", d.plus_ones ? (d.max_plus_ones > 0 ? "Accompagnants : \(d.max_plus_ones) max par personne"
                                                                            : "Accompagnants permis") : "Sans accompagnants")
                row("questionmark.circle", d.allow_maybe ? "Réponse « Peut-être » permise" : "Pas de « Peut-être »")
                if !d.rsvp_deadline.isEmpty { row("clock.badge.exclamationmark", "Répondre avant " + AIEvent.when(d.rsvp_deadline)) }
                row("eye", d.show_participants ? "Liste des participants visible" : "Liste des participants cachée")
            }
            if d.price_chf > 0 || !d.payment_info.isEmpty {
                part("Prix") {
                    row("banknote", (d.price_chf > 0 ? String(format: "%.2f CHF par personne", d.price_chf) : "Prix non précisé")
                        + (d.payment_info.isEmpty ? "" : " · " + d.payment_info))
                }
            }
            if !d.polls.isEmpty {
                part("Sondages") {
                    ForEach(Array(d.polls.enumerated()), id: \.offset) { _, poll in
                        VStack(alignment: .leading, spacing: 4) {
                            row("chart.bar.doc.horizontal", poll.question)
                            ForEach(poll.options, id: \.self) { o in
                                Text("○ " + o).font(.subheadline).foregroundStyle(.secondary).padding(.leading, 32)
                            }
                            let flags = [poll.multiple ? "plusieurs choix" : nil, poll.anonymous ? "votes anonymes" : nil,
                                         poll.add_options ? "les invités peuvent ajouter des choix" : nil].compactMap { $0 }
                            if !flags.isEmpty {
                                Text(flags.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary).padding(.leading, 32)
                            }
                        }
                    }
                }
            }
            if !d.bring.isEmpty {
                part("Qui amène quoi") {
                    ForEach(d.bring, id: \.self) { item in row("bag", item) }
                    Text("Chaque invité choisira ce qu'il amène.").font(.caption).foregroundStyle(.secondary)
                }
            }
            part("En plus") {
                if !d.category.isEmpty || !d.tags.isEmpty {
                    row("tag", ([d.category] + d.tags.map { "#" + $0 }).filter { !$0.isEmpty }.joined(separator: " · "))
                }
                if d.pot { row("banknote.fill", "Pot commun pour les présents") }
                row("bubble.left.and.bubble.right", d.forum ? "Discussion ouverte" : "Sans discussion")
                row("bell", d.notify ? "Les invités sont prévenus à la publication" : "Pas de notification à la publication")
            }
            Text("Pour changer quoi que ce soit, dis-le simplement : « mets 15 places », « enlève le sondage »…")
                .font(.caption).foregroundStyle(.secondary)
            if store.canCreate { createButton }
            else if d.ready && !store.searchingPlace {
                Text("Confirme l'adresse sur la carte pour pouvoir créer l'événement.").font(.footnote).foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.white.opacity(0.07), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .accessibilityIdentifier("ai-review")
    }

    @ViewBuilder
    private func when(_ d: AIEvent.Draft) -> some View {
        if d.date_mode == "poll" {
            row("calendar.badge.clock", d.date_options.isEmpty ? "Dates à voter à préciser"
                : "Sondage de dates :\n" + d.date_options.map { "• " + AIEvent.when($0) }.joined(separator: "\n"))
            if !d.poll_deadline.isEmpty { row("hourglass", "Vote jusqu'au " + AIEvent.when(d.poll_deadline)) }
        } else {
            row("calendar", d.start.isEmpty ? "Date à préciser" : AIEvent.span(d.start, d.end))
        }
    }

    /// Une partie du récapitulatif, avec son petit titre.
    private func part<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased()).font(.caption.weight(.semibold)).foregroundStyle(.secondary)
            content()
        }
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
            HStack(spacing: 10) { ProgressView(); Text("Recherche du lieu…").foregroundStyle(.secondary) }
                .transition(.opacity)
        } else if let p = store.place {
            chosenPlace(p).motionTransition()
        } else if !store.candidates.isEmpty {
            placeChoices(d).motionTransition()
        } else if !d.place_query.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                row("mappin.and.ellipse", (d.place_name.isEmpty ? d.place_query : d.place_name)
                    + "\nIntrouvable sur la carte : garde l'adresse telle quelle, ou corrige-la (rue, numéro, NPA, localité)")
                keepAsSaidButton
            }
        } else {
            row("mappin.and.ellipse", (d.place_name.isEmpty ? "Lieu" : d.place_name) + " : adresse complète à préciser")
        }
    }

    /// Le lieu confirmé, avec sa carte et son lien.
    private func chosenPlace(_ p: AIEvent.Place) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            row("mappin.and.ellipse", p.name + (p.address.isEmpty || p.address == p.name ? "" : "\n" + p.address))
            if p.latitude != 0 || p.longitude != 0 { placeMap(p) }
            HStack {
                if let url = URL(string: p.url) { Link("Voir dans Google Maps", destination: url).font(.footnote) }
                Spacer()
                Button("Changer de lieu") { Haptics.tap(); Motion.animate(Motion.smooth) { store.choose(nil) } }
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
    }

    private func placeMap(_ p: AIEvent.Place) -> some View {
        Map(coordinateRegion: .constant(MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: p.latitude, longitude: p.longitude),
            span: MKCoordinateSpan(latitudeDelta: 0.008, longitudeDelta: 0.008))),
            interactionModes: [],
            annotationItems: [p]) { item in
            MapMarker(coordinate: CLLocationCoordinate2D(latitude: item.latitude, longitude: item.longitude), tint: .pink)
        }
        .frame(height: 130)
        .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
    }

    /// Aucune proposition ne convient : garder l'adresse dite (sans repasser par la recherche qui la rate).
    @ViewBuilder
    private var keepAsSaidButton: some View {
        if let mine = store.asSaid {
            Button { Haptics.selection(); Motion.animate(Motion.smooth) { store.choose(mine) } } label: {
                Label("Garder « \(mine.address) »", systemImage: "checkmark.circle")
                    .font(.footnote.weight(.semibold)).multilineTextAlignment(.leading)
            }
            .accessibilityIdentifier("ai-place-as-said")
        }
    }

    /// Plusieurs lieux possibles : la personne touche le bon (rien n'est choisi à sa place).
    private func placeChoices(_ d: AIEvent.Draft) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(d.place_kind == "home" ? "Quelle est la bonne adresse ?" : "Quel est le bon lieu ?",
                  systemImage: "mappin.and.ellipse")
                .font(.headline).foregroundStyle(.orange)
            Text("Trouvé dans \(store.placeSource) pour « \(d.place_query) ». Touche le bon.")
                .font(.caption).foregroundStyle(.secondary)
            ForEach(store.candidates) { p in
                HStack(alignment: .top, spacing: 10) {
                    Button { Haptics.selection(); Motion.animate(Motion.smooth) { store.choose(p) } } label: {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(p.name).font(.subheadline.weight(.semibold)).foregroundStyle(.primary)
                            if !p.address.isEmpty { Text(p.address).font(.caption).foregroundStyle(.secondary) }
                            if p.approximate {
                                Label("Approximatif : Google ne connaît pas le numéro ou la rue", systemImage: "exclamationmark.triangle")
                                    .font(.caption2).foregroundStyle(.orange)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    if let url = URL(string: p.url) {
                        Link(destination: url) { Image(systemName: "map").font(.footnote) }
                            .accessibilityLabel("Voir \(p.name) dans Google Maps")
                    }
                }
                .padding(10)
                .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .motionTransition()
            }
            keepAsSaidButton
            Button("Aucun : je corrige l'adresse") { typing = true }
                .font(.footnote)
        }
        .accessibilityIdentifier("ai-place-choices")
    }

    private var createButton: some View {
        Button {
            Haptics.press()
            Task { await store.create() }
        } label: {
            HStack {
                if store.creating { ProgressView().tint(.black).transition(.opacity.combined(with: .scale(scale: 0.6))) }
                // Compte à rebours : les chiffres défilent vers le bas, puis le libellé se fond en « Créer ».
                Text(countdown > 0 ? "Relis bien… \(countdown)" : editing == nil ? "Créer l'événement" : "Enregistrer les changements")
                    .font(.headline.monospacedDigit())
                    .contentTransition(.numericText(countsDown: true))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(countdown > 0 ? Color.white.opacity(0.12) : Palette.accent, in: Capsule())
            .foregroundStyle(countdown > 0 ? Color.secondary : Color.black)
        }
        .disabled(countdown > 0 || store.creating)
        .motion(Motion.smooth, value: countdown)
        .motion(Motion.snappy, value: store.creating)
        .onChange(of: countdown) { left in if left == 0 && store.canCreate { Haptics.tap() } }  // « Créer » devient actif
        .accessibilityIdentifier("ai-create")
    }

    // ── C'est fait ──
    private func done(_ c: AIEvent.Created) -> some View {
        VStack(spacing: 14) {
            SuccessCheck()
            Text(c.title).font(.title2.weight(.bold)).multilineTextAlignment(.center)
            Text(c.status == "updated" ? (store.announce ? "Changements enregistrés : un message les résume aux invités."
                                                         : "Changements enregistrés.")
                 : c.status == "published" ? "Événement publié : les invités sont prévenus."
                 : "Événement proposé : il sera visible une fois validé par un admin.")
                .foregroundStyle(.secondary).multilineTextAlignment(.center)
            if !c.problems.isEmpty {
                Label("Pas ajouté : " + c.problems.joined(separator: ", ") + ". Ouvre l'événement pour le compléter.",
                      systemImage: "exclamationmark.triangle.fill")
                    .font(.footnote).foregroundStyle(.orange).multilineTextAlignment(.leading)
            }
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
                    .motionTransition(.opacity.combined(with: .move(edge: .bottom)))
            }
            if !store.images.isEmpty { shots }
            HStack(spacing: 10) {
                PhotosPicker(selection: $picked, maxSelectionCount: AIEvent.maxShots - store.images.count, matching: .images) {
                    Image(systemName: "photo.badge.plus").font(.system(size: 24))
                }
                .disabled(store.images.count >= AIEvent.maxShots)
                .accessibilityLabel("Joindre une capture d'écran de l'événement")
                .accessibilityIdentifier("ai-photo")
                TextField(store.draft?.ready == false ? "Ta réponse…" : store.draft == nil ? "Écris, ou colle un lien…" : "Une correction ?",
                          text: $typed, axis: .vertical)
                    .lineLimit(1...4)
                    .focused($typing)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Color.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                    .accessibilityIdentifier("ai-text")
                if !typed.trimmingCharacters(in: .whitespaces).isEmpty || (!store.images.isEmpty && store.turns.isEmpty) {
                    Button { Haptics.tap(); submit(typed) } label: { Image(systemName: "arrow.up.circle.fill").font(.system(size: 34)) }
                        .accessibilityLabel("Envoyer")
                        .motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                } else {
                    Button { toggleMic() } label: {
                        Image(systemName: dictation.listening ? "stop.circle.fill" : "mic.circle.fill")
                            .font(.system(size: 44))
                            .foregroundStyle(dictation.listening ? .red : Palette.accent)
                            .background { if dictation.listening { ListeningHalo() } }
                    }
                    .accessibilityLabel(dictation.listening ? "Arrêter et envoyer" : "Parler")
                    .accessibilityIdentifier("ai-mic")
                    .motionTransition(.scale(scale: 0.5).combined(with: .opacity))
                }
            }
            .disabled(store.thinking)
        }
        .motion(Motion.snappy, value: dictation.listening)
        .motion(Motion.snappy, value: typed.trimmingCharacters(in: .whitespaces).isEmpty)
        .padding(.horizontal, 16).padding(.vertical, 10)
        .background(.ultraThinMaterial)
    }

    /// Captures jointes : miniatures, chacune avec sa croix pour la retirer.
    private var shots: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(store.images) { shot in
                    Image(uiImage: shot.thumbnail).resizable().scaledToFill()
                        .frame(width: 64, height: 64)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        .overlay(alignment: .topTrailing) {
                            Button { Haptics.tap(); store.detach(shot) } label: {
                                Image(systemName: "xmark.circle.fill").font(.system(size: 20)).symbolRenderingMode(.palette)
                                    .foregroundStyle(.white, .black.opacity(0.6))
                            }
                            .accessibilityLabel("Retirer cette capture")
                            .offset(x: 6, y: -6)
                        }
                }
            }
            .padding(.top, 6)
        }
        .frame(height: 76)
    }

    private func toggleMic() {
        Haptics.press()
        if dictation.listening {
            Task { submit(await dictation.stopAndCollect()) }
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
        guard store.canCreate else { return }
        tick = Task { @MainActor in
            while countdown > 0 {
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                if Task.isCancelled { return }
                countdown -= 1
            }
        }
    }

    /// Repartir de zéro : la fiche vide (création) ou l'événement tel qu'il est en base (modification).
    private func restart() {
        dictation.finish()
        typed = ""
        if let editing { Task { await store.startEditing(editing) } } else { store.reset() }
    }

    private func close() {
        dictation.finish()
        if store.created != nil { store.reset() }
        dismiss()
    }
}

/// L'IA réfléchit : une étincelle qui respire doucement (immobile avec Réduire les animations).
private struct ThinkingSparkles: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var lit = false

    var body: some View {
        Image(systemName: "sparkles").font(.title2).foregroundStyle(Palette.accent)
            .scaleEffect(lit ? 1.12 : 0.92)
            .opacity(lit ? 1 : 0.55)
            .frame(width: 28, height: 28)
            .onAppear {
                guard !reduceMotion else { lit = true; return }
                withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { lit = true }
            }
            .accessibilityHidden(true)
    }
}

/// Micro ouvert : un halo qui s'élargit et s'efface en boucle, comme Siri (rien avec Réduire les animations).
private struct ListeningHalo: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var wide = false

    var body: some View {
        Circle().fill(Color.red.opacity(0.35))
            .scaleEffect(wide ? 1.5 : 0.9)
            .opacity(reduceMotion ? 0 : wide ? 0 : 1)
            .onAppear {
                guard !reduceMotion else { return }
                withAnimation(.easeOut(duration: 1.2).repeatForever(autoreverses: false)) { wide = true }
            }
            .allowsHitTesting(false)
    }
}

/// Événement créé : la coche arrive avec un petit rebond (simple fondu avec Réduire les animations).
private struct SuccessCheck: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown = false

    var body: some View {
        Image(systemName: "checkmark.circle.fill").font(.system(size: 56)).foregroundStyle(.green)
            .scaleEffect(shown || reduceMotion ? 1 : 0.4)
            .opacity(shown ? 1 : 0)
            .onAppear { withAnimation(Motion.pick(Motion.bouncy, reduced: reduceMotion).delay(0.1)) { shown = true } }
            .accessibilityHidden(true)
    }
}

extension AIEvent.Place: Identifiable {

    var id: String { "\(name)|\(address)|\(latitude)" }
}
