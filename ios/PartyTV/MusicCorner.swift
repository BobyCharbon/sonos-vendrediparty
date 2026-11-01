import SwiftUI

/// Coin musique : titre en cours (pochette), puis les 4 prochains titres avec le prénom de qui les a demandés.
/// Un nouveau titre pousse l'ancien vers le haut ; la file remonte en glissant ; un petit égaliseur danse
/// tant que la musique joue (immobile en pause ou si les animations sont réduites).
struct MusicCorner: View {
    static let width: CGFloat = 430
    let music: JSON
    /// Prochains titres montrés (3 quand le classement de la partie est dessous).
    var next = 4

    private var playing: Bool { music["state"].string == "PLAYING" }

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            if music["active"] == .bool(false) {
                Label("La soirée n'a pas commencé", systemImage: "music.note").font(.headline)
                Text("Code de la soirée : \(music["pin"].string ?? "")").foregroundStyle(TV.muted)
            } else if let now = Optional(music["now"]), !now.isNull {
                HStack(spacing: 12) {
                    Equalizer(playing: playing)
                    Text(playing ? "EN CE MOMENT" : "EN PAUSE").font(.caption.bold()).foregroundStyle(TV.accent)
                        .contentTransition(.opacity)
                }
                ZStack(alignment: .leading) {
                    nowPlaying(now)
                        .id(Self.key(now))
                        .transition(.motion(.push(from: .bottom)))
                }
                .clipped()
                let next = Array(music["upcoming"].array.prefix(self.next))
                if !next.isEmpty {
                    Text("ENSUITE").font(.caption.bold()).foregroundStyle(TV.muted).padding(.top, 6)
                    ForEach(Array(Self.keyed(next).enumerated()), id: \.element.key) { i, item in
                        upcoming(i, item.track)
                            .transition(.motion(.move(edge: .bottom).combined(with: .opacity)))
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

    private func nowPlaying(_ now: JSON) -> some View {
        HStack(spacing: 18) {
            AsyncImage(url: now["art"].string.flatMap(URL.init(string:))) { phase in
                if let image = phase.image {
                    image.resizable().scaledToFill().transition(.opacity)
                } else {
                    Image(systemName: "music.note").font(.largeTitle).frame(maxWidth: .infinity, maxHeight: .infinity).background(TV.surface)
                }
            }
            .frame(width: 110, height: 110).clipShape(RoundedRectangle(cornerRadius: 16))
            VStack(alignment: .leading, spacing: 4) {
                Text(now["title"].string ?? "").font(.title3.bold()).lineLimit(2).minimumScaleFactor(0.8)
                Text(now["artist"].string ?? "").foregroundStyle(TV.muted).lineLimit(1)
                if let by = now["by"].string { Text("🙋 \(by)").font(.callout).foregroundStyle(TV.lavender) }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func upcoming(_ i: Int, _ t: JSON) -> some View {
        HStack(spacing: 14) {
            Text("\(i + 1)").font(.callout.monospacedDigit().bold()).foregroundStyle(TV.muted).frame(width: 28)
                .contentTransition(.numericText())
            VStack(alignment: .leading, spacing: 2) {
                Text(t["title"].string ?? "").font(.system(size: 28, weight: .bold)).lineLimit(1)
                Text([t["artist"].string, t["by"].string.map { "par \($0)" }].compactMap { $0 }.joined(separator: " · "))
                    .font(.system(size: 24, weight: .medium)).foregroundStyle(TV.muted).lineLimit(1)
            }
        }
    }

    /// Identité d'un titre : titre + artiste (un titre qui passe de la file à « en ce moment » est reconnu).
    static func key(_ track: JSON) -> String { "\(track["title"].string ?? "")|\(track["artist"].string ?? "")" }

    /// La file, chaque titre avec une identité stable (numérotée si le même titre est demandé deux fois).
    static func keyed(_ tracks: [JSON]) -> [(key: String, track: JSON)] {
        var seen: [String: Int] = [:]
        return tracks.map { t in
            let base = key(t)
            seen[base, default: 0] += 1
            let n = seen[base] ?? 1
            return (n == 1 ? base : "\(base)#\(n)", t)
        }
    }
}

/// Égaliseur de quatre barres : elles dansent tant que la musique joue, se posent en pause.
struct Equalizer: View {
    let playing: Bool
    static let bars = 4
    static let height: CGFloat = 22

    var body: some View {
        TimelineView(.animation(minimumInterval: 1 / 20, paused: !playing || Motion.reduced)) { timeline in
            let t = timeline.date.timeIntervalSinceReferenceDate
            HStack(alignment: .bottom, spacing: 3) {
                ForEach(0..<Self.bars, id: \.self) { i in
                    let level = playing && !Motion.reduced
                        ? 0.35 + 0.65 * abs(sin(t * (2.1 + Double(i) * 0.7) + Double(i) * 1.3))
                        : (playing ? 0.7 : 0.25)
                    Capsule().fill(TV.accent).frame(width: 5, height: Self.height * level)
                }
            }
            .frame(height: Self.height, alignment: .bottom)
        }
        .accessibilityHidden(true)
    }
}
