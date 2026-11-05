import SwiftUI

/// Sous le coin musique : les Zicou des présents qui dansent sur le titre en cours (au plus 6 à la fois, les autres
/// prennent la relève toutes les 10 s). Quand quelqu'un gagne une manche ou la partie, son Zicou fait une figure
/// (saut vrillé) et reste à l'écran. En pause, ils s'arrêtent ; « Réduire les animations » : immobiles, le gagnant
/// marqué d'une étoile. Nom affiché : le surnom modéré par le serveur, ou rien.
struct ZicouFloorView: View {
    let zicous: [ZicouDancer]
    let music: JSON
    /// Partie affichée (jeu lancé dans une salle de jeux compris) : ses gagnants font une figure.
    let shown: JSON
    /// Places visibles (moins quand le classement de la partie occupe déjà la colonne).
    var limit = ZicouFloor.maxVisible

    @State private var winners: Set<String> = []
    @State private var figureAt: Date?

    static let figureSize: CGFloat = 104
    static let columns = 3
    /// Le gagnant reste en tête de la piste un moment après sa figure.
    static let pinnedSeconds: TimeInterval = 20

    private var playing: Bool { music["state"].string == "PLAYING" }
    private var bpm: Double { ZicouFloor.beatsPerMinute(music) }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("PISTE DE DANSE").font(.caption.bold()).foregroundStyle(TV.accent)
                Text("🪩 \(ZicouFloor.headline(zicous.count))").font(.system(size: 32, weight: .bold)).lineLimit(1)
                    .minimumScaleFactor(0.7)
                    .contentTransition(.numericText())
            }
            TimelineView(.periodic(from: .now, by: ZicouFloor.rotateEvery)) { context in
                let group = ZicouFloor.visible(zicous, turn: ZicouFloor.turn(at: context.date), limit: limit, pinned: pinned(context.date))
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: Self.columns), spacing: 14) {
                    ForEach(Array(group.enumerated()), id: \.element.key) { i, z in
                        DancerCell(dancer: z, index: i, bpm: bpm, playing: playing, star: winners.contains(z.key),
                                   figureAt: winners.contains(z.key) ? figureAt : nil)
                            .transition(.motion(.scale(scale: 0.6).combined(with: .opacity)))
                    }
                }
                .animation(Motion.update, value: group.map(\.key))
            }
        }
        .padding(26)
        .frame(width: MusicCorner.width, alignment: .leading)
        .glass()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(ZicouFloor.headline(zicous.count))
        .onChange(of: ZicouFloor.victoryKey(shown), initial: true) { _, key in celebrate(key) }
    }

    private func pinned(_ now: Date) -> Set<String> {
        guard let figureAt, now.timeIntervalSince(figureAt) < Self.pinnedSeconds else { return [] }
        return winners
    }

    private func celebrate(_ key: String?) {
        let found = key == nil ? [] : ZicouFloor.winners(shown, among: zicous)
        winners = found
        // La figure attend la fin de l'annonce plein écran du résultat (elle passerait sinon sous le voile).
        let flashing = !(Outcome.of(shown)?.isEmpty ?? true)
        figureAt = found.isEmpty ? nil : Date.now.addingTimeInterval(flashing ? OutcomeFlash.seconds : 0)
    }
}

/// Un Zicou et son nom : il danse sur le temps (chacun son pas), saute en vrille quand il gagne.
private struct DancerCell: View {
    let dancer: ZicouDancer
    let index: Int
    let bpm: Double
    let playing: Bool
    let star: Bool
    let figureAt: Date?

    private var size: CGFloat { ZicouFloorView.figureSize }

    var body: some View {
        VStack(spacing: 6) {
            TimelineView(.animation(minimumInterval: 1 / 30, paused: Motion.reduced || (!playing && figureAt == nil))) { context in
                let move = ZicouMove.at(context.date, dancer: dancer, index: index, bpm: bpm, playing: playing, figureAt: figureAt)
                ZicouFigure(dancer: dancer, size: size).equatable()
                    .scaleEffect(x: move.scale, y: move.scale * move.squash, anchor: .bottom)
                    .rotation3DEffect(.degrees(move.spin), axis: (x: 0, y: 1, z: 0))
                    .rotationEffect(.degrees(move.tilt), anchor: .bottom)
                    .offset(x: move.x, y: move.y)
            }
            .frame(width: size, height: size)
            .background(alignment: .bottom) {
                if star { Ellipse().fill(TV.coral.opacity(0.35)).frame(width: size * 0.9, height: 16).blur(radius: 6) }
            }
            Group {
                if let name = dancer.name {
                    Text(star ? "\(name) ⭐" : name)
                } else {
                    Text(star ? "⭐" : " ")
                }
            }
            .font(.system(size: 22, weight: .bold)).lineLimit(1).minimumScaleFactor(0.7)
            .foregroundStyle(dancer.stage == .egg ? TV.muted : .white)
        }
        .frame(maxWidth: .infinity)
    }
}

/// Le pas de danse à un instant : sur le temps (bpm), chacun son style ; la figure de victoire par-dessus.
struct ZicouMove: Equatable {
    var x: CGFloat = 0, y: CGFloat = 0, tilt: Double = 0, spin: Double = 0, scale: CGFloat = 1, squash: CGFloat = 1

    static let still = ZicouMove()

    static func at(_ date: Date, dancer: ZicouDancer, index: Int, bpm: Double, playing: Bool, figureAt: Date?) -> ZicouMove {
        guard !Motion.reduced else { return .still }
        let t = date.timeIntervalSinceReferenceDate
        if let figureAt, case let p = date.timeIntervalSince(figureAt) / ZicouFloor.figureSeconds, p >= 0, p < 1 {
            return figure(p, size: ZicouFloorView.figureSize)
        }
        guard playing else { return .still }
        return dance(beats: t * bpm / 60, style: style(of: dancer, index: index), dancer: dancer, size: ZicouFloorView.figureSize)
    }

    /// Saut vrillé : il monte, fait un tour complet sur lui-même et retombe en grossissant un peu.
    static func figure(_ p: Double, size: CGFloat) -> ZicouMove {
        ZicouMove(y: -CGFloat(sin(.pi * p)) * size * 0.3, spin: 360 * p, scale: 1 + CGFloat(sin(.pi * p)) * 0.15)
    }

    /// Un pas par temps : rebond (tous), balancé, pas chassé ou écrasé selon le style ; l'œuf se dandine, le Zicou qui
    /// dort se berce à peine.
    static func dance(beats: Double, style: Int, dancer: ZicouDancer, size: CGFloat) -> ZicouMove {
        let beat = sin(.pi * beats)          // change de signe à chaque temps
        let hop = CGFloat(abs(beat))
        if dancer.stage == .egg { return ZicouMove(tilt: 6 * beat) }
        if dancer.emotion == "sleep" { return ZicouMove(tilt: 2 * sin(.pi * beats / 4), squash: 1 - 0.02 * hop) }
        var move = ZicouMove(y: -hop * size * 0.08)
        switch style {
        case 0: move.tilt = 7 * beat
        case 1: move.x = CGFloat(sin(.pi * beats / 2)) * size * 0.08
        default: move.squash = 1 - 0.07 * (1 - hop)
        }
        return move
    }

    /// Style stable d'un Zicou : tiré de son identité (pas de sa place, qui change à chaque rotation).
    static func style(of dancer: ZicouDancer, index: Int) -> Int {
        Int(dancer.key.unicodeScalars.reduce(UInt32(7)) { ($0 &* 31) &+ $1.value } % 3)
    }
}
