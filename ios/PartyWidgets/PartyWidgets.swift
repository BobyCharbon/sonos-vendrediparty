import ActivityKit
import SwiftUI
import WidgetKit

@main
struct PartyWidgets: WidgetBundle {
    var body: some Widget {
        TrackLiveActivity()
    }
}

/// « Ton titre arrive » : décompte et barre jusqu'au passage, « D'un instant à l'autre » une fois l'heure dépassée,
/// puis « C'est ton titre ! ». Couleurs de la soirée, texte toujours blanc (l'écran verrouillé peut être clair).
struct TrackLiveActivity: Widget {
    private static let accent = Color(red: 1, green: 79 / 255, blue: 154 / 255)
    private static let gold = Color(red: 1, green: 181 / 255, blue: 71 / 255)
    private static let background = Color(red: 0.16, green: 0.06, blue: 0.24)

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TrackActivityAttributes.self) { context in
            lockScreen(context)
                .activityBackgroundTint(Self.background)
                .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    badge(context.state.playing).padding(.leading, 4)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    if !context.state.playing && !context.isStale {
                        countdown(context.state.arrival).font(.title3.monospacedDigit().weight(.bold))
                            .foregroundStyle(Self.gold).frame(maxWidth: 80)
                    }
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(spacing: 2) {
                        Text(headline(context)).font(.caption.weight(.bold)).foregroundStyle(Self.accent)
                        Text(context.attributes.title).font(.headline).foregroundStyle(.white).lineLimit(1)
                        Text(context.attributes.artist).font(.caption).foregroundStyle(.white.opacity(0.7)).lineLimit(1)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    if !context.state.playing && !context.isStale { progress(context).padding(.horizontal, 8) }
                }
            } compactLeading: {
                Image(systemName: context.state.playing ? "music.note" : "hourglass").foregroundStyle(Self.accent)
            } compactTrailing: {
                if context.state.playing || context.isStale {
                    Text("🎶")
                } else {
                    countdown(context.state.arrival).monospacedDigit().foregroundStyle(Self.gold).frame(maxWidth: 46)
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
                badge(context.state.playing)
                VStack(alignment: .leading, spacing: 2) {
                    Text(headline(context)).font(.caption.weight(.heavy)).foregroundStyle(Self.accent)
                    Text(context.attributes.title).font(.headline).foregroundStyle(.white).lineLimit(1)
                    Text(context.attributes.artist).font(.subheadline).foregroundStyle(.white.opacity(0.7)).lineLimit(1)
                }
                Spacer(minLength: 0)
                if !context.state.playing && !context.isStale {
                    countdown(context.state.arrival).font(.title.monospacedDigit().weight(.heavy))
                        .foregroundStyle(Self.gold).multilineTextAlignment(.trailing).frame(maxWidth: 110, alignment: .trailing)
                }
            }
            if !context.state.playing && !context.isStale { progress(context) }
        }
        .padding(16)
    }

    private func headline(_ context: ActivityViewContext<TrackActivityAttributes>) -> String {
        if context.state.playing { return "C'EST TON TITRE ! 🎶" }
        return context.isStale ? "D'UN INSTANT À L'AUTRE…" : "TON TITRE ARRIVE"
    }

    private func badge(_ playing: Bool) -> some View {
        Image(systemName: playing ? "music.note" : "hourglass")
            .font(.title3.weight(.bold)).foregroundStyle(.white)
            .frame(width: 44, height: 44)
            .background(Self.accent.gradient, in: Circle())
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
