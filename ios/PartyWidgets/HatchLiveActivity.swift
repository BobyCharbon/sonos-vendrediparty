import ActivityKit
import SwiftUI
import WidgetKit

/// « Éclosion » : décompte de 3 min jusqu'à la naissance du Zicou (écran verrouillé, Dynamic Island), puis
/// « … est né ! Viens le voir » et l'activité s'en va. Périmée à l'heure (staleDate) : elle dit « est né » même
/// app fermée. Texte toujours blanc sur fond nuit (l'écran verrouillé peut être clair).
struct HatchLiveActivity: Widget {
    private static let background = Color(hex: 0x1A1040)

    static func hatched(_ context: ActivityViewContext<HatchActivityAttributes>) -> Bool {
        context.state.hatched || context.isStale || context.state.hatchAt <= Date()
    }

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: HatchActivityAttributes.self) { context in
            lockScreen(context)
                .activityBackgroundTint(Self.background)
                .activitySystemActionForegroundColor(.white)
                .widgetURL(PetLinks.zicou(src: "link"))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    figure(context).frame(width: 52, height: 52)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    if !Self.hatched(context) {
                        countdown(context.state.hatchAt).font(.title2.monospacedDigit().weight(.bold))
                            .foregroundStyle(Z.pink).frame(width: 70, alignment: .trailing)
                    }
                }
                DynamicIslandExpandedRegion(.center) {
                    VStack(spacing: 2) {
                        Text("ÉCLOSION").font(.caption.weight(.heavy)).foregroundStyle(Z.pink)
                        Text(title(context)).font(.headline).foregroundStyle(.white).lineLimit(1)
                    }
                }
                DynamicIslandExpandedRegion(.bottom) {
                    if !Self.hatched(context) { progress(context).padding(.horizontal, 8) }
                }
            } compactLeading: {
                figure(context).frame(width: 22, height: 22)
            } compactTrailing: {
                if Self.hatched(context) {
                    Image(systemName: "sparkles").foregroundStyle(Z.gold)
                } else {
                    countdown(context.state.hatchAt).monospacedDigit().foregroundStyle(Z.pink).frame(width: 44)
                }
            } minimal: {
                figure(context).frame(width: 22, height: 22)
            }
            .widgetURL(PetLinks.zicou(src: "link"))
            .keylineTint(Z.pink)
        }
    }

    private func lockScreen(_ context: ActivityViewContext<HatchActivityAttributes>) -> some View {
        HStack(spacing: 14) {
            figure(context).frame(width: 56, height: 56)
            VStack(alignment: .leading, spacing: 4) {
                Text("PARTY · ÉCLOSION").font(.caption.weight(.heavy)).foregroundStyle(Z.pink)
                Text(title(context)).font(.headline).foregroundStyle(.white).lineLimit(1)
                if Self.hatched(context) {
                    Text("Viens le voir 🎉").font(.subheadline).foregroundStyle(.white.opacity(0.75))
                } else {
                    progress(context)
                }
            }
            Spacer(minLength: 0)
            if !Self.hatched(context) {
                countdown(context.state.hatchAt).font(.title.monospacedDigit().weight(.heavy)).foregroundStyle(.white)
                    .multilineTextAlignment(.trailing).frame(width: 84, alignment: .trailing)
            }
        }
        .padding(16)
    }

    private func figure(_ context: ActivityViewContext<HatchActivityAttributes>) -> some View {
        Self.hatched(context) ? ZicouFigure(emotion: "party", stage: "baby") : ZicouFigure(emotion: "egg", stage: "egg")
    }

    private func title(_ context: ActivityViewContext<HatchActivityAttributes>) -> String {
        Self.hatched(context) ? "\(context.attributes.name) est né !" : "\(context.attributes.name) arrive !"
    }

    private func progress(_ context: ActivityViewContext<HatchActivityAttributes>) -> some View {
        ProgressView(timerInterval: min(context.attributes.laidAt, context.state.hatchAt)...context.state.hatchAt,
                     countsDown: false) {
            EmptyView()
        } currentValueLabel: {
            EmptyView()
        }
        .tint(Z.pink)
    }

    private func countdown(_ hatchAt: Date) -> Text {
        let now = Date()
        return Text(timerInterval: now...max(now, hatchAt), countsDown: true)
    }
}
