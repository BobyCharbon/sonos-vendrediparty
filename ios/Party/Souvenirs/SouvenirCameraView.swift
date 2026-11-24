import SwiftUI

/// `PartyNative.souvenirs.camera(eventId)` : l'appareil photo de la soirée, plein écran (maquette v2, écran 3).
/// « N poses » ; déclencher : flash, la photo part au labo, jamais d'aperçu ; « Annuler » pendant 5 s rend la pose.
/// Refus lisibles (full, closed, profile_required) ; terms_required : feuille des CGU puis nouvel essai.
struct SouvenirCameraView: View {
    @ObservedObject var store: SouvenirsStore
    let eventID: String
    let close: () -> Void

    @StateObject private var sensor = SouvenirCameraSensor()
    @State private var counter: SouvenirCounter?
    @State private var left = SouvenirText.maxPoses
    @State private var keep = true
    @State private var sent = 0
    @State private var sending = false
    @State private var flashOn = false
    /// Dernière photo partie au labo : « Annuler » jusqu'à `cancelEnd`.
    @State private var lastPhoto: String?
    @State private var cancelEnd: Date?
    @State private var problem: String?
    @State private var closedReason: String?
    /// Photo refusée faute de CGU : renvoyée une fois les CGU acceptées (jamais montrée).
    @State private var waitingTerms: Data?
    @State private var termsShown = false

    static let cancelSeconds: Double = 5

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            viewfinder.ignoresSafeArea()
            if flashOn { Color.white.ignoresSafeArea().transition(.opacity) }
            VStack(spacing: 12) {
                topBar
                if let lastPhoto, let cancelEnd { laboCard(lastPhoto, until: cancelEnd) }
                if let problem { problemCard(problem) }
                Spacer()
                if let closedReason {
                    finished(closedReason)
                } else if counter != nil {
                    Text(SouvenirText.cameraPromise(keep: keep))
                        .font(.footnote).multilineTextAlignment(.center)
                        .foregroundStyle(.white.opacity(0.88))
                        .padding(.horizontal, 28)
                        .shadow(color: .black.opacity(0.6), radius: 6)
                        .accessibilityIdentifier("souvenir-camera-promise")
                }
                bottomBar
            }
            .padding(.horizontal, 14)
            .padding(.bottom, 8)
        }
        .preferredColorScheme(.dark)
        .statusBarHidden(false)
        .task { await prepare() }
        .onDisappear { sensor.stop() }
        .sheet(isPresented: $termsShown) {
            TermsAcceptSheet(store: store.moderation) { accepted in
                let photo = waitingTerms
                waitingTerms = nil
                if accepted, let photo { Task { await send(photo) } }
            }
        }
    }

    // MARK: Viseur

    @ViewBuilder private var viewfinder: some View {
        switch sensor.state {
        case .ready where sensor.fake:
            LinearGradient(colors: [Color(red: 0.36, green: 0.13, blue: 0.4), Color(red: 0.1, green: 0.07, blue: 0.2)],
                           startPoint: .top, endPoint: .bottom)
                .overlay(Text("🥳🎂🙌").font(.system(size: 64)))
                .overlay(grid)
        case .ready:
            SouvenirCameraPreview(session: sensor.session).overlay(grid)
        case .starting:
            if closedReason == nil && counter == nil { ProgressView().tint(.white) }
        case .denied:
            message("📷", "Autorise l'appareil photo pour Party dans Réglages › Party › Appareil photo.")
        case .unavailable:
            message("📷", "Pas d'appareil photo disponible sur cet appareil.")
        }
    }

    private var grid: some View {
        GeometryReader { g in
            Path { p in
                for i in 1...2 {
                    let x = g.size.width * CGFloat(i) / 3, y = g.size.height * CGFloat(i) / 3
                    p.move(to: CGPoint(x: x, y: 0)); p.addLine(to: CGPoint(x: x, y: g.size.height))
                    p.move(to: CGPoint(x: 0, y: y)); p.addLine(to: CGPoint(x: g.size.width, y: y))
                }
            }
            .stroke(.white.opacity(0.14), lineWidth: 0.6)
        }
        .allowsHitTesting(false)
    }

    private func message(_ emoji: String, _ text: String) -> some View {
        VStack(spacing: 10) {
            Text(emoji).font(.system(size: 48))
            Text(text).font(.callout).multilineTextAlignment(.center).foregroundStyle(.white.opacity(0.85))
        }
        .padding(32)
    }

    // MARK: Barres

    private var topBar: some View {
        HStack {
            roundButton("xmark", label: "Fermer", id: "souvenir-camera-close") { finish() }
            Spacer()
            HStack(spacing: 8) {
                Text("🎞️")
                Text("\(left)").font(.title3.weight(.heavy)).foregroundStyle(ChatNeon.coral).contentTransition(.numericText())
                Text(left > 1 ? "poses" : "pose").font(.subheadline.weight(.semibold))
            }
            .padding(.horizontal, 16).padding(.vertical, 9)
            .background(.black.opacity(0.55), in: Capsule())
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(SouvenirText.poses(left))
            .accessibilityIdentifier("souvenir-poses")
            Spacer()
            roundButton("arrow.triangle.2.circlepath.camera", label: "Changer de caméra", id: "souvenir-camera-flip") { sensor.flip() }
                .disabled(sensor.state != .ready)
        }
        .padding(.top, 6)
    }

    private var bottomBar: some View {
        HStack {
            VStack(spacing: 4) {
                ZStack {
                    ForEach(0..<min(sent, 3), id: \.self) { i in
                        RoundedRectangle(cornerRadius: 5).fill(Color(red: 0.93, green: 0.9, blue: 0.82))
                            .frame(width: 34, height: 40).rotationEffect(.degrees(Double(i) * 8 - 6))
                    }
                    if sent == 0 { RoundedRectangle(cornerRadius: 5).stroke(.white.opacity(0.35), style: StrokeStyle(lineWidth: 1, dash: [3])).frame(width: 34, height: 40) }
                }
                Text("Au labo").font(.caption2.weight(.semibold)).foregroundStyle(.white.opacity(0.8))
            }
            .frame(width: 72)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(sent) au labo")
            Spacer()
            Button(action: shoot) {
                ZStack {
                    Circle().stroke(.white, lineWidth: 5).frame(width: 82, height: 82)
                    Circle().fill(.white).frame(width: 66, height: 66).scaleEffect(sending ? 0.86 : 1)
                    if sending { ProgressView().tint(.black) }
                }
            }
            .buttonStyle(.plain)
            .disabled(!canShoot)
            .opacity(canShoot ? 1 : 0.4)
            .accessibilityLabel("Prendre la photo")
            .accessibilityIdentifier("souvenir-shutter")
            Spacer()
            roundButton(sensor.flash ? "bolt.fill" : "bolt.slash", label: sensor.flash ? "Flash allumé" : "Flash éteint", id: "souvenir-flash") {
                sensor.flash.toggle()
                Haptics.selection()
            }
            .frame(width: 72)
            .disabled(sensor.front)
        }
        .padding(.bottom, 10)
    }

    private func roundButton(_ symbol: String, label: String, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol).font(.system(size: 17, weight: .semibold)).foregroundStyle(.white)
                .frame(width: 44, height: 44).background(.black.opacity(0.55), in: Circle())
        }
        .accessibilityLabel(label)
        .accessibilityIdentifier(id)
    }

    // MARK: Cartes

    private func laboCard(_ photo: String, until: Date) -> some View {
        TimelineView(.periodic(from: .now, by: 0.2)) { context in
            let remaining = max(0, until.timeIntervalSince(context.date))
            VStack(alignment: .leading, spacing: 0) {
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("🧪 Partie au labo").font(.subheadline.weight(.bold))
                        Text("\(left > 0 ? "Encore \(SouvenirText.poses(left))" : "Pellicule terminée") · tu ne la reverras qu'au dévoilement.")
                            .font(.caption).foregroundStyle(.white.opacity(0.75))
                    }
                    Spacer(minLength: 6)
                    if remaining > 0 {
                        Button { Task { await cancel(photo) } } label: {
                            Text("Annuler \(Int(remaining.rounded(.up)))").font(.subheadline.weight(.bold))
                                .foregroundStyle(ChatNeon.coral)
                                .padding(.horizontal, 14).padding(.vertical, 10)
                                .background(ChatNeon.lavB.opacity(0.35), in: Capsule())
                        }
                        .accessibilityIdentifier("souvenir-cancel")
                    }
                }
                .padding(12)
                GeometryReader { g in
                    Capsule().fill(ChatNeon.coral).frame(width: g.size.width * remaining / Self.cancelSeconds, height: 3)
                }
                .frame(height: 3)
            }
            .background(Color(red: 0.12, green: 0.09, blue: 0.2).opacity(0.94), in: RoundedRectangle(cornerRadius: 16))
            .overlay(RoundedRectangle(cornerRadius: 16).stroke(ChatNeon.coral.opacity(0.55), lineWidth: 1))
            .task(id: remaining <= 0) { if remaining <= 0 { Motion.animate(Motion.smooth) { self.cancelEnd = nil; self.lastPhoto = nil } } }
        }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("souvenir-labo")
        .transition(.move(edge: .top).combined(with: .opacity))
    }

    private func problemCard(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "exclamationmark.circle.fill").foregroundStyle(ChatNeon.coral)
            Text(text).font(.subheadline).foregroundStyle(.white).frame(maxWidth: .infinity, alignment: .leading)
            Button { Motion.animate { problem = nil } } label: { Image(systemName: "xmark").font(.caption.weight(.bold)) }
                .tint(.white).accessibilityLabel("Masquer")
        }
        .padding(12)
        .background(.black.opacity(0.75), in: RoundedRectangle(cornerRadius: 14))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("souvenir-problem")
        .transition(.opacity)
    }

    private func finished(_ reason: String) -> some View {
        VStack(spacing: 10) {
            Text(left == 0 ? "🎞️" : "📷").font(.system(size: 48))
            Text(left == 0 ? "Pellicule terminée" : "Appareil fermé").font(.title3.weight(.heavy))
            Text(reason).font(.subheadline).multilineTextAlignment(.center).foregroundStyle(.white.opacity(0.8))
            Button("Fermer") { finish() }
                .font(.headline).foregroundStyle(ChatNeon.onPink)
                .padding(.horizontal, 36).padding(.vertical, 12)
                .background(ChatNeon.pink, in: Capsule())
                .accessibilityIdentifier("souvenir-camera-done")
        }
        .padding(22)
        .frame(maxWidth: .infinity)
        .background(.black.opacity(0.72), in: RoundedRectangle(cornerRadius: 22))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("souvenir-finished")
        .transition(.scale(scale: 0.92).combined(with: .opacity))
    }

    // MARK: Actions

    private var canShoot: Bool {
        sensor.state == .ready && counter?.canTake == true && left > 0 && !sending && closedReason == nil
    }

    private func prepare() async {
        do {
            let c = try await store.counter(eventID)
            counter = c
            keep = c.keep ?? true
            left = c.left ?? 0
            sent = c.taken ?? 0  // déjà au labo (appareil rouvert)
            if !c.enabled {
                closedReason = "Les Souvenirs ne sont pas actifs sur cet événement."
            } else if c.canTake != true {
                closedReason = SouvenirText.closedCamera(c)
            }
        } catch {
            closedReason = Self.text(error)
        }
        if closedReason == nil { await sensor.start() }
    }

    private func shoot() {
        guard canShoot else { return }
        Haptics.press()
        Motion.animate(Motion.fade) { flashOn = true }
        sending = true
        Task {
            try? await Task.sleep(for: .milliseconds(120))
            Motion.animate(Motion.fade) { flashOn = false }
            guard let jpeg = await sensor.capture() else {
                sending = false
                Motion.animate { problem = "La photo n'a pas pu être prise. Réessaie." }
                return
            }
            await send(jpeg)
        }
    }

    private func send(_ jpeg: Data) async {
        sending = true
        defer { sending = false }
        do {
            let taken = try await store.upload(jpeg, event: eventID)
            Haptics.success()
            Motion.animate(Motion.smooth) {
                problem = nil
                sent += 1
                left = taken.left ?? max(0, left - 1)
                lastPhoto = taken.id
                cancelEnd = Date().addingTimeInterval(Self.cancelSeconds)
            }
            if left == 0 {
                try? await Task.sleep(for: .seconds(Self.cancelSeconds + 0.3))
                if left == 0 {
                    Motion.animate(Motion.smooth) { closedReason = "Tes 3 photos sont au labo. Profite de la soirée, on s'occupe du reste ✨" }
                }
            }
        } catch let refusal as SouvenirRefusal where refusal.code == "terms_required" {
            waitingTerms = jpeg
            termsShown = true
        } catch let refusal as SouvenirRefusal where refusal.code == "full" {
            Haptics.warning()
            Motion.animate(Motion.smooth) { left = 0; closedReason = refusal.message }
        } catch let refusal as SouvenirRefusal where refusal.code == "closed" {
            Haptics.warning()
            Motion.animate(Motion.smooth) { closedReason = refusal.message }
        } catch {
            Haptics.warning()
            Motion.animate { problem = Self.text(error) }
        }
    }

    private func cancel(_ photo: String) async {
        do {
            let rest = try await store.cancel(photo)
            Haptics.success()
            Motion.animate(Motion.smooth) {
                sent = max(0, sent - 1)
                left = rest ?? min(SouvenirText.maxPoses, left + 1)
                lastPhoto = nil
                cancelEnd = nil
                closedReason = nil
                problem = "Photo annulée : la pose t'est rendue."
            }
        } catch {
            Haptics.warning()
            Motion.animate { lastPhoto = nil; cancelEnd = nil; problem = Self.text(error) }
        }
    }

    private func finish() {
        sensor.stop()
        close()
    }

    static func text(_ error: Error) -> String {
        if let refusal = error as? SouvenirRefusal { return refusal.message }
        return (error as? LocalizedError)?.errorDescription ?? "Ça n'a pas marché. Réessaie dans un instant."
    }
}
