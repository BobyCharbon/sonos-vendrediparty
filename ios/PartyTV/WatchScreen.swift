import SwiftUI

/// La partie en grand, et la musique dans le coin en haut à droite (verre semi-transparent) :
/// titre en cours, prochains titres et qui les a demandés. Bouton Menu de la télécommande : changer de partie.
struct WatchScreen: View {
    @ObservedObject var store: TVStore
    /// Annonce plein écran du dernier résultat (quelques secondes).
    @State private var flash: Outcome?
    @State private var flashTask: Task<Void, Never>?
    static let flashSeconds: UInt64 = 6

    private var shown: JSON { GameView.shown(store.game) }
    private var outcome: Outcome? { Outcome.of(shown) }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            header
            HStack(alignment: .top, spacing: 36) {
                // La scène : toute la place restante, le jeu y est centré verticalement.
                FitToStage { GameView(game: store.game, join: store.joinURL) }
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
                    .animation(.spring(response: 0.5, dampingFraction: 0.8), value: shown["phase"].string)
                // Colonne de droite : la musique (verre), puis le classement de la partie s'il y en a un.
                VStack(alignment: .leading, spacing: 22) {
                    MusicCorner(music: store.music, next: SideBoard.shows(store.game) ? 2 : 4)
                    SideBoard(game: store.game)
                }
                .frame(width: MusicCorner.width)
                .frame(maxHeight: .infinity, alignment: .top)
            }
        }
        .padding(.horizontal, 10)
        .overlay {
            if let flash {
                ZStack {
                    Color.black.opacity(0.55).ignoresSafeArea()
                    OutcomeFlash(outcome: flash)
                }
                .transition(.opacity)
            }
        }
        .overlay(alignment: .bottom) {
            if let problem = store.problem {
                Text(problem).font(.title3).padding(.horizontal, 30).padding(.vertical, 14).glass(cornerRadius: 30).padding(30)
            }
        }
        .onChange(of: outcome?.key) { _, key in announce(key) }
        .onExitCommand { store.leave() }
        .task { await store.appear() }
    }

    /// Nouveau résultat : annonce en grand, puis le tableau reste dans la scène.
    private func announce(_ key: String?) {
        flashTask?.cancel()
        guard key != nil, let outcome, !outcome.isEmpty else {
            withAnimation { flash = nil }
            return
        }
        withAnimation(.easeOut(duration: 0.3)) { flash = outcome }
        flashTask = Task {
            try? await Task.sleep(nanoseconds: Self.flashSeconds * 1_000_000_000)
            guard !Task.isCancelled else { return }
            withAnimation(.easeIn(duration: 0.4)) { flash = nil }
        }
    }

    private var watchedCode: String {
        if case .watching(let code) = store.screen { return code }
        return store.game["code"].string ?? ""
    }

    /// Salle d'attente affichée (la partie, ou le jeu de la salle de jeux, pas encore lancé ; ou la salle vide).
    private var inLobby: Bool {
        let g = store.game
        if g["type"].string == "room" { return g["current"].isNull || g["current"]["phase"].string == "lobby" }
        return g["phase"].string == "lobby"
    }

    /// Barre du haut, compacte : le jeu, sa phase et son avancée à gauche ; le code et le QR pour rejoindre à droite.
    private var header: some View {
        HStack(alignment: .center, spacing: 24) {
            if shown != store.game { Text("🎲").font(.system(size: 50)) }
            Text(shown["name"].string ?? "Partie").font(.system(size: 54, weight: .heavy)).lineLimit(1).fixedSize()
            if let mode = shown["mode"].string { Text(mode).font(.system(size: 34, weight: .semibold)).foregroundStyle(TV.lavender).lineLimit(1) }
            if !inLobby && !shown.isNull {
                PhaseTag(text: Phase.label(shown)).transition(.scale.combined(with: .opacity)).id(Phase.label(shown))
                if let info = Phase.progress(shown) { Text(info).font(.system(size: 32, weight: .semibold)).foregroundStyle(TV.muted).lineLimit(1) }
            }
            Spacer(minLength: 20)
            // Pendant la partie : petit QR code et code pour rejoindre (en salle d'attente, le grand QR est au centre).
            Text("Code \(watchedCode)").font(.system(size: 36, weight: .bold).monospacedDigit()).foregroundStyle(TV.muted)
            if !inLobby, let join = store.joinURL { QRCodeView(url: join, size: 96) }
        }
        .frame(height: 100)
        .animation(.spring(response: 0.4, dampingFraction: 0.8), value: Phase.label(shown))
    }
}

/// Coin musique : titre en cours (pochette), puis les 4 prochains titres avec le prénom de qui les a demandés.
struct MusicCorner: View {
    static let width: CGFloat = 430
    let music: JSON
    /// Prochains titres montrés (3 quand le classement de la partie est dessous).
    var next = 4

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if music["active"] == .bool(false) {
                Label("La soirée n'a pas commencé", systemImage: "music.note").font(.headline)
                Text("Code de la soirée : \(music["pin"].string ?? "")").foregroundStyle(TV.muted)
            } else if let now = Optional(music["now"]), !now.isNull {
                Text(music["state"].string == "PLAYING" ? "EN CE MOMENT" : "EN PAUSE").font(.caption.bold()).foregroundStyle(TV.accent)
                HStack(spacing: 18) {
                    AsyncImage(url: now["art"].string.flatMap(URL.init(string:))) { $0.resizable().scaledToFill() } placeholder: {
                        Image(systemName: "music.note").font(.largeTitle).frame(maxWidth: .infinity, maxHeight: .infinity).background(TV.surface)
                    }
                    .frame(width: 110, height: 110).clipShape(RoundedRectangle(cornerRadius: 16))
                    VStack(alignment: .leading, spacing: 4) {
                        Text(now["title"].string ?? "").font(.title3.bold()).lineLimit(2).minimumScaleFactor(0.8)
                        Text(now["artist"].string ?? "").foregroundStyle(TV.muted).lineLimit(1)
                        if let by = now["by"].string { Text("🙋 \(by)").font(.callout).foregroundStyle(TV.lavender) }
                    }
                }
                let next = Array(music["upcoming"].array.prefix(self.next))
                if !next.isEmpty {
                    Text("ENSUITE").font(.caption.bold()).foregroundStyle(TV.muted).padding(.top, 6)
                    ForEach(Array(next.enumerated()), id: \.offset) { i, t in
                        HStack(spacing: 14) {
                            Text("\(i + 1)").font(.callout.monospacedDigit().bold()).foregroundStyle(TV.muted).frame(width: 28)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(t["title"].string ?? "").font(.system(size: 28, weight: .bold)).lineLimit(1)
                                Text([t["artist"].string, t["by"].string.map { "par \($0)" }].compactMap { $0 }.joined(separator: " · "))
                                    .font(.system(size: 24, weight: .medium)).foregroundStyle(TV.muted).lineLimit(1)
                            }
                        }
                    }
                }
            } else {
                Label(music["error"].string ?? "Rien ne joue pour l'instant", systemImage: "music.note").font(.headline)
            }
        }
        .padding(30)
        .frame(width: Self.width, alignment: .leading)
        .glass()
        .accessibilityElement(children: .combine)
    }
}
