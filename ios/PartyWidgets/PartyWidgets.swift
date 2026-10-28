import ActivityKit
import SwiftUI
import WidgetKit

@main
struct PartyWidgets: WidgetBundle {
    var body: some Widget {
        TrackLiveActivity()
    }
}

/// « Ton titre arrive » : décompte et barre jusqu'au passage ; une fois l'heure atteinte (ou le titre lancé),
/// « Ton titre joue actuellement » en vert. Couleurs de la soirée, texte toujours blanc (l'écran verrouillé peut être clair).
/// Le décompte a une largeur fixe : un décompte iOS prend sinon toute la place et coupe le titre.
struct TrackLiveActivity: Widget {
    private static let accent = Color(red: 1, green: 79 / 255, blue: 154 / 255)
    private static let gold = Color(red: 1, green: 181 / 255, blue: 71 / 255)
    private static let background = Color(red: 0.16, green: 0.06, blue: 0.24)
    private static let green = Color(red: 48 / 255, green: 209 / 255, blue: 88 / 255)

    /// Le titre passe, ou l'heure estimée est atteinte (décompte à 0, l'app fermée ne voit pas le départ).
    private static func playing(_ context: ActivityViewContext<TrackActivityAttributes>) -> Bool {
        !context.state.paused && (context.state.playing || context.isStale || context.state.arrival <= Date())
    }

    private static func counting(_ context: ActivityViewContext<TrackActivityAttributes>) -> Bool {
        !context.state.paused && !playing(context)
    }

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TrackActivityAttributes.self) { context in
            lockScreen(context)
                .activityBackgroundTint(Self.background)
                .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    badge(Self.playing(context)).padding(.leading, 4)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    if context.state.paused {
                        Image(systemName: "pause.fill").font(.title3).foregroundStyle(Self.gold)
                    } else if Self.counting(context) {
                        countdown(context.state.arrival).font(.title3.monospacedDigit().weight(.bold))
                            .foregroundStyle(Self.gold).frame(width: 62, alignment: .trailing)
                    }
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(spacing: 2) {
                        Text(headline(context)).font(.caption.weight(.bold)).foregroundStyle(headlineColor(context))
                        Text(context.attributes.title).font(.headline).foregroundStyle(.white).lineLimit(1)
                        Text(context.attributes.artist).font(.caption).foregroundStyle(.white.opacity(0.7)).lineLimit(1)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    if context.state.paused {
                        Text(queueText(context.state.ahead)).font(.caption).foregroundStyle(.white.opacity(0.7))
                    } else if Self.counting(context) {
                        progress(context).padding(.horizontal, 8)
                    }
                }
            } compactLeading: {
                Image(systemName: Self.playing(context) ? "music.note" : "hourglass")
                    .foregroundStyle(Self.playing(context) ? Self.green : Self.accent)
            } compactTrailing: {
                if context.state.paused {
                    Image(systemName: "pause.fill").foregroundStyle(Self.gold)
                } else if Self.playing(context) {
                    Image(systemName: "play.fill").foregroundStyle(Self.green)
                } else {
                    countdown(context.state.arrival).monospacedDigit().foregroundStyle(Self.gold).frame(width: 44)
                }
            } minimal: {
                Image(systemName: "music.note").foregroundStyle(Self.accent)
            }
            .keylineTint(Self.accent)
        }
    }

    private func lockScreen(_ context: ActivityViewContext<TrackActivityAttributes>) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                badge(Self.playing(context))
                VStack(alignment: .leading, spacing: 2) {
                    Text(headline(context)).font(.caption.weight(.heavy)).foregroundStyle(headlineColor(context))
                    Text(context.attributes.title).font(.headline).foregroundStyle(.white).lineLimit(1)
                    Text(context.attributes.artist).font(.subheadline).foregroundStyle(.white.opacity(0.7)).lineLimit(1)
                }
                Spacer(minLength: 0)
                if context.state.paused {
                    Image(systemName: "pause.fill").font(.title).foregroundStyle(Self.gold)
                } else if Self.counting(context) {
                    countdown(context.state.arrival).font(.title2.monospacedDigit().weight(.heavy))
                        .foregroundStyle(Self.gold).multilineTextAlignment(.trailing).frame(width: 76, alignment: .trailing)
                }
            }
            if context.state.paused {
                Text(queueText(context.state.ahead)).font(.subheadline).foregroundStyle(.white.opacity(0.75))
            } else if Self.counting(context) {
                progress(context)
                Text(queueText(context.state.ahead)).font(.caption).foregroundStyle(.white.opacity(0.7))
            }
        }
        .padding(16)
    }

    private func headline(_ context: ActivityViewContext<TrackActivityAttributes>) -> String {
        if context.state.paused { return "LECTURE EN PAUSE ⏸" }
        return Self.playing(context) ? "TON TITRE JOUE ACTUELLEMENT 🎶" : "TON TITRE ARRIVE"
    }

    private func headlineColor(_ context: ActivityViewContext<TrackActivityAttributes>) -> Color {
        Self.playing(context) ? Self.green : Self.accent
    }

    private func badge(_ playing: Bool) -> some View {
        Image(systemName: playing ? "play.fill" : "hourglass")
            .font(.title3.weight(.bold)).foregroundStyle(.white)
            .frame(width: 44, height: 44)
            .background((playing ? Self.green : Self.accent).gradient, in: Circle())
    }

    /// Place dans la file, toujours juste (même en pause, même après un déplacement).
    private func queueText(_ ahead: Int) -> String {
        switch ahead {
        case 0: return "Ton titre est le prochain"
        case 1: return "1 titre avant le tien"
        default: return "\(ahead) titres avant le tien"
        }
    }

    /// Barre de l'ajout au passage (avance seule, sans l'app).
    private func progress(_ context: ActivityViewContext<TrackActivityAttributes>) -> some View {
        let start = min(context.attributes.addedAt, context.state.arrival)
        return ProgressView(timerInterval: start...context.state.arrival, countsDown: false) {
            EmptyView()
        } currentValueLabel: {
            EmptyView()
        }
        .tint(Self.accent)
    }

    /// Décompte jusqu'au passage (avance seul, sans l'app).
    private func countdown(_ arrival: Date) -> Text {
        let now = Date()
        return Text(timerInterval: now...max(now, arrival), countsDown: true)
    }
}
