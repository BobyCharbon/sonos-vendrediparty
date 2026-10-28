import ActivityKit
import SwiftUI
import WidgetKit

@main
struct PartyWidgets: WidgetBundle {
    var body: some Widget {
        TrackLiveActivity()
    }
}

/// « Ton titre arrive » : compte à rebours jusqu'au passage, puis « C'est ton titre ! ».
struct TrackLiveActivity: Widget {
    private static let accent = Color(red: 1, green: 79 / 255, blue: 154 / 255)
    private static let background = Color(red: 14 / 255, green: 11 / 255, blue: 22 / 255)

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TrackActivityAttributes.self) { context in
            HStack(spacing: 14) {
                Image(systemName: context.state.playing ? "music.note" : "hourglass")
                    .font(.title2.weight(.semibold)).foregroundStyle(Self.accent)
                VStack(alignment: .leading, spacing: 2) {
                    Text(context.state.playing ? "C'est ton titre ! 🎶" : "Ton titre arrive")
                        .font(.caption.weight(.bold)).foregroundStyle(Self.accent)
                    Text(context.attributes.title).font(.headline).lineLimit(1)
                    Text(context.attributes.artist).font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
                }
                Spacer(minLength: 0)
                if !context.state.playing { countdown(context.state.arrival).font(.title2.monospacedDigit().weight(.bold)) }
            }
            .padding(16)
            .activityBackgroundTint(Self.background)
            .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Image(systemName: context.state.playing ? "music.note" : "hourglass").foregroundStyle(Self.accent)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    if !context.state.playing { countdown(context.state.arrival).monospacedDigit() }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 2) {
                        Text(context.state.playing ? "C'est ton titre ! 🎶" : "Ton titre arrive").font(.caption.weight(.bold))
                            .foregroundStyle(Self.accent)
                        Text("\(context.attributes.title) · \(context.attributes.artist)").lineLimit(1)
                    }
                }
            } compactLeading: {
                Image(systemName: context.state.playing ? "music.note" : "hourglass").foregroundStyle(Self.accent)
            } compactTrailing: {
                if context.state.playing { Text("🎶") } else { countdown(context.state.arrival).monospacedDigit().frame(maxWidth: 44) }
            } minimal: {
                Image(systemName: "music.note").foregroundStyle(Self.accent)
            }
            .keylineTint(Self.accent)
        }
    }

    /// Décompte jusqu'au passage ; « 0:00 » s'il est dépassé (le titre va démarrer).
    private func countdown(_ arrival: Date) -> Text {
        let now = Date()
        return Text(timerInterval: now...max(now, arrival), countsDown: true)
    }
}
