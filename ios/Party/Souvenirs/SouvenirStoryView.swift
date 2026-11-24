import SwiftUI
import UIKit

/// `PartyNative.souvenirs.story(eventId)` : la story du dévoilement (24 h), maquette v2 écran 6. Barres en haut ;
/// toucher à gauche / à droite ; maintenir = pause ; glisser vers le bas = fermer. Auteur et heure, « Visible encore X h »,
/// « ⭐ Garder » / « ⭐ Gardée » (can_keep), ⋯ Signaler (motif my_image en tête) et Bloquer. Les photos et leur auteur
/// sont dans ScreenshotProof (comme SecretCardsView) : une capture ou un enregistrement d'écran les rend noirs.
struct SouvenirStoryView: View {
    @ObservedObject var store: SouvenirsStore
    let eventID: String
    let close: () -> Void

    @State private var story: SouvenirStory?
    @State private var failure: String?
    @State private var index = 0
    @State private var progress: Double = 0
    @State private var holding = false
    @State private var drag: CGFloat = 0
    @State private var ended = false
    @State private var images: [String: UIImage] = [:]
    @State private var menuShown = false
    @State private var reporting: SouvenirPhoto?
    @State private var blocking: SouvenirAuthor?
    @State private var toast: String?
    @State private var keeping = false
    @State private var pressStart: Date?
    /// Doigt posé : remis à faux par SwiftUI même si le geste est annulé (barre d'accueil, appel…), sans onEnded.
    @GestureState private var touching = false

    static let perPhoto: Double = 5
    private static let tick: Double = 0.05

    private var photos: [SouvenirPhoto] { story?.photos ?? [] }
    private var current: SouvenirPhoto? { photos.indices.contains(index) ? photos[index] : nil }
    private var paused: Bool { holding || menuShown || reporting != nil || blocking != nil || ended || drag > 0 }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if let story, !story.photos.isEmpty {
                player(story)
            } else if let failure {
                empty("📸", failure)
            } else if story != nil {
                empty("🧪", "Il n'y a plus de photo à voir dans cette story.")
            } else {
                ProgressView().tint(.white)
            }
        }
        .offset(y: drag)
        .opacity(1 - Double(min(drag, 300)) / 600)
        .preferredColorScheme(.dark)
        .task { await load() }
        .task(id: index) { await prefetch() }
        .task(id: "\(index)-\(paused)-\(images[current?.id ?? ""] != nil)") { await run() }
        .sheet(item: $reporting) { photo in
            SouvenirReportSheet(author: photo.author?.label ?? "Quelqu'un") { reason in
                try await store.report(photo.id, reason: reason)
                remove { $0.id == photo.id }
            }
            .presentationDetents([.medium, .large])
        }
        .confirmationDialog(blocking.map { "Bloquer \($0.label) ?" } ?? "", isPresented: Binding(get: { blocking != nil }, set: { if !$0 { blocking = nil } }),
                            titleVisibility: .visible, presenting: blocking) { author in
            Button("Bloquer", role: .destructive) { Task { await block(author) } }
            Button("Annuler", role: .cancel) {}
        } message: { author in
            Text("Tu ne verras plus les photos de \(author.label), et \(author.label) ne verra plus les tiennes. Tu pourras la débloquer dans Réglages › Personnes bloquées.")
        }
    }

    // MARK: Lecteur

    private func player(_ story: SouvenirStory) -> some View {
        ZStack {
            // Protégé des captures : la photo, l'auteur et l'heure (ce qu'on voudrait capturer).
            ScreenshotProof(content: protectedContent)
                .background(Color.black)
                .ignoresSafeArea()
                .accessibilityElement(children: .ignore)
                .accessibilityLabel(current.map { "Photo de \($0.author?.label ?? "quelqu'un"), \(SouvenirText.takenAt($0.takenAt))" } ?? "")
                .accessibilityIdentifier("souvenir-photo")
                .accessibilityAction(named: "Photo suivante") { next() }
                .accessibilityAction(named: "Photo précédente") { previous() }
            gestures
            controls(story)
            if ended { endCard(story) }
            if let toast {
                Text(toast).font(.subheadline.weight(.semibold)).multilineTextAlignment(.center)
                    .padding(14).background(.black.opacity(0.8), in: RoundedRectangle(cornerRadius: 14))
                    .padding(.horizontal, 30)
                    .accessibilityIdentifier("souvenir-toast")
                    .transition(.opacity)
            }
        }
    }

    private var protectedContent: some View {
        ZStack {
            Color.black
            if let current, let image = images[current.id] {
                Image(uiImage: image).resizable().scaledToFit()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if current != nil {
                ProgressView().tint(.white)
            }
        }
    }

    /// Toucher (gauche : précédente, droite : suivante), maintenir (pause), glisser vers le bas (fermer).
    private var gestures: some View {
        GeometryReader { g in
            Color.clear.contentShape(Rectangle())
                .gesture(DragGesture(minimumDistance: 0, coordinateSpace: .global)  // la story suit le doigt (offset) : repère de l'écran
                    .updating($touching) { _, state, _ in state = true }
                    .onChanged { value in
                        if pressStart == nil { pressStart = Date() }
                        if !holding, Date().timeIntervalSince(pressStart ?? Date()) > 0.18 { holding = true }
                        drag = max(0, value.translation.height)
                    }
                    .onEnded { value in
                        let quick = Date().timeIntervalSince(pressStart ?? Date()) < 0.3
                        pressStart = nil
                        holding = false
                        if value.translation.height > 120 { return finish() }
                        Motion.animate(Motion.snappy) { drag = 0 }
                        guard quick, abs(value.translation.width) < 12, abs(value.translation.height) < 12, !ended else { return }
                        if value.startLocation.x < g.size.width / 3 { previous() } else { next() }
                    })
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
        .onChange(of: touching) { down in
            guard !down else { return }
            // Geste annulé (pas d'onEnded) : la story reprend là où elle était. Fin normale : onEnded a déjà tout remis.
            Task {
                try? await Task.sleep(for: .milliseconds(150))
                guard pressStart != nil else { return }
                pressStart = nil
                holding = false
                Motion.animate(Motion.snappy) { drag = 0 }
            }
        }
    }

    private func controls(_ story: SouvenirStory) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            bars.allowsHitTesting(false)
            HStack(spacing: 10) {
                if let author = current?.author { avatar(author) }
                VStack(alignment: .leading, spacing: 1) {
                    Text(current?.mine == true ? "Toi" : current?.author?.label ?? "").font(.subheadline.weight(.bold))
                    Text(SouvenirText.takenAt(current?.takenAt)).font(.caption).foregroundStyle(.white.opacity(0.7))
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("souvenir-author")
                .allowsHitTesting(false)
                Spacer()
                if current?.mine != true {
                    Button { menuShown = true } label: {
                        Image(systemName: "ellipsis").font(.system(size: 18, weight: .bold)).frame(width: 44, height: 44)
                    }
                    .accessibilityLabel("Plus d'options")
                    .accessibilityIdentifier("souvenir-more")
                    .confirmationDialog("Cette photo", isPresented: $menuShown, titleVisibility: .hidden) {
                        if let photo = current {
                            Button("Signaler la photo", role: .destructive) { reporting = photo }
                            if let author = photo.author { Button("Bloquer \(author.label)", role: .destructive) { blocking = author } }
                        }
                        Button("Annuler", role: .cancel) {}
                    }
                }
                Button(action: finish) {
                    Image(systemName: "xmark").font(.system(size: 18, weight: .bold)).frame(width: 44, height: 44)
                }
                .accessibilityLabel("Fermer la story")
                .accessibilityIdentifier("souvenir-story-close")
            }
            .foregroundStyle(.white)
            .shadow(color: .black.opacity(0.5), radius: 4)
            Spacer()
            if let photo = current {
                if photo.canKeep == true {
                    keepButton(photo)
                } else if photo.mine == true, story.keep != false {
                    Label("Ta photo · dans tes souvenirs", systemImage: "camera.fill")
                        .font(.subheadline.weight(.semibold)).padding(.horizontal, 14).padding(.vertical, 10)
                        .background(.black.opacity(0.5), in: Capsule())
                        .allowsHitTesting(false)
                }
            }
            HStack {
                Text(story.title ?? "Souvenirs").font(.headline).lineLimit(1)
                Spacer()
                Text("\(index + 1) / \(photos.count)").font(.subheadline.monospacedDigit()).foregroundStyle(.white.opacity(0.8))
                    .accessibilityIdentifier("souvenir-position")
            }
            .allowsHitTesting(false)
            HStack(spacing: 6) {
                Text("⏳ \(SouvenirText.visibleFor(until: story.until) ?? "Visible 24 h") · 🚫 captures bloquées")
                    .font(.caption.weight(.semibold))
            }
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(.black.opacity(0.55), in: Capsule())
            .accessibilityIdentifier("souvenir-visible")
            .allowsHitTesting(false)
        }
        .foregroundStyle(.white)
        .padding(.horizontal, 14)
        .padding(.top, 8)
        .padding(.bottom, 12)
    }

    private var bars: some View {
        HStack(spacing: 3) {
            ForEach(Array(photos.enumerated()), id: \.element.id) { i, _ in
                GeometryReader { g in
                    Capsule().fill(.white.opacity(0.3))
                        .overlay(alignment: .leading) {
                            Capsule().fill(.white).frame(width: g.size.width * (i < index ? 1 : i == index ? progress : 0))
                        }
                }
                .frame(height: 3)
            }
        }
        .accessibilityHidden(true)
    }

    private func avatar(_ author: SouvenirAuthor) -> some View {
        ZStack {
            Circle().fill(ChatNeon.lavB)
            if let photo = author.photo, let url = URL(string: photo) {
                AsyncImage(url: url) { image in image.resizable().scaledToFill() } placeholder: { Text(author.initials).font(.caption.bold()) }
                    .clipShape(Circle())
            } else {
                Text(author.initials).font(.caption.bold())
            }
        }
        .frame(width: 36, height: 36)
        .overlay(Circle().stroke(.white.opacity(0.7), lineWidth: 1.5))
        .accessibilityHidden(true)
    }

    private func keepButton(_ photo: SouvenirPhoto) -> some View {
        let kept = photo.kept == true
        return Button {
            Task { await toggleKeep(photo) }
        } label: {
            Text(kept ? "⭐ Gardée" : "⭐ Garder")
                .font(.headline)
                .foregroundStyle(kept ? Color(red: 0.2, green: 0.12, blue: 0) : .white)
                .padding(.horizontal, 20).padding(.vertical, 12)
                .background(kept ? AnyShapeStyle(ChatNeon.coral) : AnyShapeStyle(.black.opacity(0.55)), in: Capsule())
                .overlay(Capsule().stroke(ChatNeon.coral, lineWidth: kept ? 0 : 1.5))
        }
        .disabled(keeping)
        .accessibilityLabel(kept ? "Gardée dans tes souvenirs" : "Garder dans mes souvenirs")
        .accessibilityIdentifier("souvenir-keep")
    }

    private func endCard(_ story: SouvenirStory) -> some View {
        VStack(spacing: 12) {
            Text("✨").font(.system(size: 54))
            Text("C'était toute la soirée").font(.title2.weight(.heavy))
            Text(story.keep == false
                 ? "\(SouvenirText.photos(photos.count)). Rien n'est gardé : les photos disparaissent à la fin de la story."
                 : "\(SouvenirText.photos(photos.count)). Tes photos et celles que tu as gardées t'attendent sur la fiche.")
                .font(.subheadline).multilineTextAlignment(.center).foregroundStyle(.white.opacity(0.8))
            Button("Fermer", action: finish)
                .font(.headline).foregroundStyle(ChatNeon.onPink)
                .frame(maxWidth: 260).padding(.vertical, 13)
                .background(ChatNeon.pink, in: Capsule())
                .accessibilityIdentifier("souvenir-end-close")
            Button("↺ Revoir") { Motion.animate { ended = false; index = 0; progress = 0 } }
                .font(.headline).foregroundStyle(.white)
                .accessibilityIdentifier("souvenir-replay")
        }
        .padding(28)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(.black.opacity(0.85))
        // Fin de la story : glisser vers le bas ferme aussi (la carte couvre le lecteur et ses gestes).
        .contentShape(Rectangle())
        .gesture(DragGesture(minimumDistance: 20, coordinateSpace: .global).onEnded { value in
            if value.translation.height > 120 { finish() }
        })
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("souvenir-end")
        .transition(.opacity)
    }

    private func empty(_ emoji: String, _ text: String) -> some View {
        VStack(spacing: 14) {
            Text(emoji).font(.system(size: 50))
            Text(text).font(.callout).multilineTextAlignment(.center).foregroundStyle(.white.opacity(0.85))
            Button("Fermer", action: finish).font(.headline).tint(ChatNeon.pink)
                .accessibilityIdentifier("souvenir-story-close")
        }
        .padding(32)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("souvenir-story-empty")
    }

    // MARK: Données et minuterie

    private func load() async {
        do {
            let s = try await store.story(eventID)
            story = s
            await store.markSeen(eventID)
        } catch {
            failure = SouvenirCameraView.text(error)
        }
    }

    /// La photo affichée et la suivante, chargées d'avance (liens signés de 10 min).
    private func prefetch() async {
        for photo in photos.dropFirst(index).prefix(2) where images[photo.id] == nil {
            guard let raw = photo.url, let url = URL(string: raw),
                  let (data, _) = try? await URLSession.shared.data(from: url), let image = UIImage(data: data) else { continue }
            images[photo.id] = image
        }
    }

    /// 5 s par photo ; en pause tant qu'on maintient, qu'une feuille est ouverte ou que la photo charge.
    private func run() async {
        guard let current, images[current.id] != nil else { return }
        while !Task.isCancelled && !paused {
            try? await Task.sleep(for: .seconds(Self.tick))
            guard !Task.isCancelled, !paused else { return }
            progress += Self.tick / Self.perPhoto
            if progress >= 1 { return next() }
        }
    }

    private func next() {
        Haptics.selection()
        if index + 1 < photos.count {
            index += 1
            progress = 0
        } else {
            progress = 1
            Motion.animate(Motion.smooth) { ended = true }
        }
    }

    private func previous() {
        Haptics.selection()
        progress = 0
        if index > 0 { index -= 1 }
    }

    private func toggleKeep(_ photo: SouvenirPhoto) async {
        keeping = true
        defer { keeping = false }
        do {
            let kept = try await store.setKept(photo.id, !(photo.kept == true))
            if kept { Haptics.success() } else { Haptics.tap() }
            if let i = story?.photos.firstIndex(where: { $0.id == photo.id }) {
                Motion.animate(Motion.bouncy) { story?.photos[i].kept = kept }
            }
        } catch {
            show(SouvenirCameraView.text(error))
        }
    }

    private func block(_ author: SouvenirAuthor) async {
        do {
            try await store.block(author.id)
            Haptics.success()
            remove { $0.author?.id == author.id }
            show("\(author.label) est bloqué·e : ses photos ne s'affichent plus.")
        } catch {
            show(SouvenirCameraView.text(error))
        }
    }

    /// Photo signalée ou auteur bloqué : la story continue sans.
    private func remove(_ match: (SouvenirPhoto) -> Bool) {
        guard var s = story else { return }
        let currentID = current?.id
        s.photos.removeAll(where: match)
        story = s
        if let currentID, let i = s.photos.firstIndex(where: { $0.id == currentID }) { index = i } else { index = min(index, max(0, s.photos.count - 1)) }
        progress = 0
    }

    private func show(_ text: String) {
        Motion.animate { toast = text }
        Task {
            try? await Task.sleep(for: .seconds(3))
            Motion.animate { toast = nil }
        }
    }

    private func finish() {
        close()
    }
}

/// « Signaler la photo » (maquette v2) : le motif, puis le message de remerciement. La photo est masquée aussitôt.
struct SouvenirReportSheet: View {
    let author: String
    let send: (SouvenirReportReason) async throws -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var sent = false
    @State private var busy = false
    @State private var problem: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if sent {
                VStack(spacing: 12) {
                    Text("🙏").font(.system(size: 46))
                    Text("Merci, c'est envoyé").font(.title3.weight(.bold))
                    Text("La photo est masquée pour tout le monde pendant que l'organisation et la modération de Party regardent. \(author) ne sait pas que c'est toi.")
                        .font(.subheadline).multilineTextAlignment(.center).foregroundStyle(.secondary)
                    Button("Fermer") { dismiss() }
                        .font(.headline).foregroundStyle(ChatNeon.t1).frame(maxWidth: .infinity).padding(.vertical, 13)
                        .background(ChatNeon.s1b, in: Capsule())
                        .accessibilityIdentifier("souvenir-report-done")
                }
                .frame(maxWidth: .infinity)
                .accessibilityElement(children: .contain)
                .accessibilityIdentifier("souvenir-report-thanks")
            } else {
                Text("Pourquoi signaler cette photo ?").font(.headline).padding(.bottom, 6)
                ForEach(SouvenirReportReason.allCases) { reason in
                    Button {
                        Task { await report(reason) }
                    } label: {
                        HStack(alignment: .top, spacing: 12) {
                            Text(reason.emoji)
                            Text(reason.label).multilineTextAlignment(.leading).frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .padding(.vertical, 12).padding(.horizontal, 10)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .disabled(busy)
                    .accessibilityIdentifier("souvenir-report-\(reason.rawValue)")
                }
                if let problem { Text(problem).font(.footnote).foregroundStyle(.red) }
                Button("Annuler") { dismiss() }
                    .font(.headline).foregroundStyle(ChatNeon.t1).frame(maxWidth: .infinity).padding(.vertical, 13)
                    .background(ChatNeon.s1b, in: Capsule())
                    .padding(.top, 6)
            }
        }
        .padding(20)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(ChatNeon.s1.ignoresSafeArea())
        .preferredColorScheme(.dark)
        .presentationDragIndicator(.visible)
    }

    private func report(_ reason: SouvenirReportReason) async {
        busy = true
        defer { busy = false }
        do {
            try await send(reason)
            Haptics.success()
            Motion.animate { sent = true }
        } catch {
            problem = SouvenirCameraView.text(error)
        }
    }
}
