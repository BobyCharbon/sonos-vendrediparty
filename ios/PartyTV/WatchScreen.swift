import SwiftUI

/// La partie en grand, et la musique dans le coin en haut à droite (verre semi-transparent) :
/// titre en cours, prochains titres et qui les a demandés. Bouton Menu de la télécommande : changer de partie.
struct WatchScreen: View {
    @ObservedObject var store: TVStore

    var body: some View {
        HStack(alignment: .top, spacing: 44) {
            VStack(alignment: .leading, spacing: 28) {
                header
                GameView(game: store.game, join: store.joinURL)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            }
            // Colonne de droite : la musique (verre), puis le classement de la partie s'il y en a un.
            VStack(alignment: .leading, spacing: 26) {
                MusicCorner(music: store.music, next: SideBoard.shows(store.game) ? 3 : 4)
                SideBoard(game: store.game)
            }
            .frame(width: MusicCorner.width)
            .frame(maxHeight: .infinity, alignment: .top)
        }
        .padding(60)
        .overlay(alignment: .bottom) {
            if let problem = store.problem {
                Text(problem).font(.title3).padding(.horizontal, 30).padding(.vertical, 14).glass(cornerRadius: 30).padding(30)
            }
        }
        .onExitCommand { store.leave() }
        .task { await store.appear() }
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

    private var header: some View {
        HStack(alignment: .firstTextBaseline, spacing: 24) {
            let shown = store.game["type"].string == "room" && !store.game["current"].isNull ? store.game["current"] : store.game
            VStack(alignment: .leading, spacing: 4) {
                if shown != store.game { Text("🎲 Salle de jeux").font(.headline).foregroundStyle(TV.muted) }
                Text(shown["name"].string ?? "Partie").font(.system(size: 60, weight: .heavy)).lineLimit(1)
            }
            if let mode = shown["mode"].string { Text(mode).font(.title2).foregroundStyle(TV.lavender) }
            Spacer()
            // Pendant la partie : petit QR code et code pour rejoindre (en salle d'attente, le grand QR est au centre).
            if !inLobby, let join = store.joinURL {
                VStack(alignment: .trailing, spacing: 6) {
                    QRCodeView(url: join, size: 110)
                    Text("Code \(watchedCode)").font(.headline.monospacedDigit()).foregroundStyle(TV.muted)
                }
            } else {
                Text("Code \(watchedCode)").font(.title2.monospacedDigit()).foregroundStyle(TV.muted)
            }
        }
    }
}

/// Coin musique : titre en cours (pochette), puis les 4 prochains titres avec le prénom de qui les a demandés.
struct MusicCorner: View {
    static let width: CGFloat = 480
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
                                Text(t["title"].string ?? "").font(.callout.bold()).lineLimit(1)
                                Text([t["artist"].string, t["by"].string.map { "par \($0)" }].compactMap { $0 }.joined(separator: " · "))
                                    .font(.caption).foregroundStyle(TV.muted).lineLimit(1)
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
