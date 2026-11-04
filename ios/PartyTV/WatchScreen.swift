import SwiftUI

/// La partie en grand, et la musique dans le coin en haut à droite (verre semi-transparent) :
/// titre en cours, prochains titres et qui les a demandés. Bouton Menu de la télécommande : changer de partie.
struct WatchScreen: View {
    @ObservedObject var store: TVStore
    /// Annonce plein écran du dernier résultat (quelques secondes).
    @State private var flash: Outcome?
    @State private var flashTask: Task<Void, Never>?
    /// Salle de jeux : le jeu qui vient d'être lancé, annoncé en grand quelques instants.
    @State private var intro: String?
    @State private var introTask: Task<Void, Never>?

    private var shown: JSON { GameView.shown(store.game) }
    private var outcome: Outcome? { Outcome.of(shown) }

    var body: some View {
        VStack(alignment: .leading, spacing: 22) {
            header
            HStack(alignment: .top, spacing: 36) {
                // La scène : toute la place restante, le jeu y est centré verticalement.
                // D'un jeu à l'autre (Salle de jeux) : l'ancien glisse vers la gauche, le nouveau arrive de la droite.
                FitToStage { GameView(game: store.game, join: store.joinURL) }
                    .id(GameScene.key(shown))
                    .transition(.motion(.asymmetric(insertion: .move(edge: .trailing).combined(with: .opacity),
                                                    removal: .move(edge: .leading).combined(with: .opacity))))
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
                    .environment(\.outcomeFlashing, flash != nil)
                    .animation(Motion.update, value: shown["phase"].string)
                // Colonne de droite : la musique (verre), puis le classement de la partie s'il y en a un.
                FitToStage {
                    VStack(alignment: .leading, spacing: 22) {
                        MusicCorner(music: store.music, next: SideBoard.shows(store.game) ? 2 : 4)
                        // Les Zicou des présents dansent sous la musique (une seule rangée si le classement suit).
                        if !store.zicous.isEmpty {
                            ZicouFloorView(zicous: store.zicous, music: store.music, shown: shown,
                                           limit: SideBoard.shows(store.game) ? ZicouFloorView.columns : ZicouFloor.maxVisible)
                                .transition(.motion(.move(edge: .bottom).combined(with: .opacity)))
                        }
                        SideBoard(game: store.game)
                    }
                }
                .frame(width: MusicCorner.width)
                .frame(maxHeight: .infinity, alignment: .top)
            }
        }
        .padding(.horizontal, 10)
        .overlay {
            // Pause de l'animateur : un voile sur toute la télé.
            if let by = shown["paused"]["by"].string { PauseVeil(by: by).transition(.opacity) }
        }
        .overlay {
            if let intro, flash == nil { GameIntro(name: intro).transition(.motion(.scale(scale: 1.3).combined(with: .opacity))) }
        }
        .animation(.easeInOut(duration: 0.4), value: shown["paused"].isNull)
        .overlay {
            if let flash {
                ZStack {
                    Color.black.opacity(0.55).ignoresSafeArea()
                    // Un résultat chasse l'autre : chaque annonce rejoue son entrée.
                    OutcomeFlash(outcome: flash)
                        .id(flash.key)
                        .transition(.motion(.asymmetric(insertion: .opacity.animation(.easeOut(duration: 0.3).delay(0.22)),
                                                        removal: .scale(scale: 0.85).combined(with: .opacity).animation(.easeIn(duration: 0.22)))))
                }
                .transition(.opacity)
            }
        }
        .overlay {
            // 🌟 Zicou en vedette : 30 s au milieu de l'écran, sauf pendant l'annonce d'un résultat.
            if let star = store.star, flash == nil {
                ZicouStarView(star: star).id(star.dancer.key)
                    .transition(.motion(.scale(scale: 0.6).combined(with: .opacity)))
            }
        }
        .animation(Motion.update, value: store.star?.dancer.key)
        .overlay(alignment: .bottomLeading) {
            // Décor du Salon de Party débloqué par la caisse commune du groupe.
            if !store.salon.isEmpty {
                HStack(spacing: 10) { ForEach(store.salon) { Text($0.emoji).accessibilityLabel($0.label) } }
                    .font(.system(size: 44)).padding(.horizontal, 18).padding(.vertical, 8).glass(cornerRadius: 26).padding(24)
            }
        }
        .overlay(alignment: .bottom) {
            if let problem = store.problem {
                Text(problem).font(.title3).padding(.horizontal, 30).padding(.vertical, 14).glass(cornerRadius: 30).padding(30)
            }
        }
        // Aussi à l'ouverture : une télé allumée sur un résultat tout frais l'annonce.
        .onChange(of: outcome?.key, initial: true) { _, key in announce(key) }
        .onChange(of: GameScene.key(shown)) { _, _ in introduce() }
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
            try? await Task.sleep(for: .seconds(OutcomeFlash.seconds))
            guard !Task.isCancelled else { return }
            withAnimation(.easeIn(duration: 0.4)) { flash = nil }
        }
    }

    /// Un jeu vient d'être lancé dans la Salle de jeux : « C'est parti : Quiz ! » en grand, puis le jeu.
    private func introduce() {
        introTask?.cancel()
        guard store.game["type"].string == "room", !store.game["current"].isNull, let name = shown["name"].string else {
            return withAnimation(Motion.update) { intro = nil }
        }
        withAnimation(Motion.pop) { intro = name }
        introTask = Task {
            try? await Task.sleep(for: .seconds(GameIntro.seconds))
            guard !Task.isCancelled else { return }
            withAnimation(Motion.update) { intro = nil }
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
                .id(shown["name"].string ?? "").transition(.motion(.push(from: .bottom)))
            if let mode = shown["mode"].string { Text(mode).font(.system(size: 34, weight: .semibold)).foregroundStyle(TV.lavender).lineLimit(1) }
            if !inLobby && !shown.isNull {
                PhaseTag(text: Phase.label(shown)).transition(.popIn).id(Phase.label(shown))
                if let info = Phase.progress(shown) {
                    Text(info).font(.system(size: 32, weight: .semibold)).foregroundStyle(TV.muted).lineLimit(1)
                        .contentTransition(.numericText())
                }
            }
            Spacer(minLength: 20)
            // Pendant la partie : petit QR code et code pour rejoindre (en salle d'attente, le grand QR est au centre).
            Text("Code \(watchedCode)").font(.system(size: 36, weight: .bold).monospacedDigit()).foregroundStyle(TV.muted)
            // Le grand QR de la salle d'attente laisse la place à ce petit QR dès que la partie commence.
            if !inLobby, let join = store.joinURL { QRCodeView(url: join, size: 96).transition(.popIn) }
        }
        .frame(height: 100)
        .animation(Motion.animation(.spring(response: 0.4, dampingFraction: 0.8)), value: Phase.label(shown))
        .animation(Motion.update, value: inLobby)
    }
}


/// 🌟 Le Zicou en vedette : grand, au milieu, qui danse avec sa tenue ; seulement le surnom modéré (ou rien).
struct ZicouStarView: View {
    let star: ZicouStar
    @State private var bounce = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 18) {
            Text("🌟 En vedette").font(.system(size: 38, weight: .heavy)).foregroundStyle(.yellow)
            ZicouFigure(dancer: star.dancer, size: 420)
                .rotationEffect(.degrees(reduceMotion ? 0 : (bounce ? 6 : -6)))
                .offset(y: reduceMotion ? 0 : (bounce ? -18 : 0))
            if let name = star.dancer.name {
                Text("Le Zicou de \(name)").font(.system(size: 44, weight: .bold))
            }
            if star.waiting > 0 {
                Text(star.waiting > 1 ? "\(star.waiting) Zicou attendent leur tour" : "1 Zicou attend son tour")
                    .font(.title3).foregroundStyle(.secondary)
            }
        }
        .padding(48)
        .glass(cornerRadius: 48)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(star.dancer.name.map { "Le Zicou de \($0) est en vedette" } ?? "Un Zicou est en vedette")
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 0.26).repeatForever(autoreverses: true)) { bounce = true }
        }
    }
}
