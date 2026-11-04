import SwiftUI
import WidgetKit

/// Widget Zicou : écran d'accueil (petit, moyen) et écran verrouillé (rond, rectangle, ligne). Le compagnon permanent
/// vit ici, jamais dans une Live Activity (CLAUDE.md, conformité). Toucher = ouvrir Zicou dans l'app.
struct ZicouWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: PetWidgetStore.widgetKind, provider: ZicouProvider()) { entry in
            ZicouWidgetView(entry: entry)
        }
        .configurationDisplayName("Zicou")
        .description("Ton Zicou Party : son humeur, ta série et le cadeau du jour.")
        .supportedFamilies([.systemSmall, .systemMedium, .accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}

struct ZicouEntry: TimelineEntry {
    let date: Date
    /// nil : pas encore de Zicou vu par l'app (pas connecté).
    let moment: PetMoment?
    let name: String
}

/// Chronologie calculée sur l'iPhone à partir du dernier état reçu (PetForecast) : aucun serveur ne réveille le widget.
/// L'app la recharge quand Zicou change (PetWidgetBridge).
struct ZicouProvider: TimelineProvider {
    /// Galerie et aperçus : Zicou seulement s'il a déjà été vu sur cet iPhone (Compagnon ouvert sur le site) ;
    /// sinon la vue neutre (le Compagnon est en bêta, éteint en production).
    func placeholder(in context: Context) -> ZicouEntry {
        PetWidgetStore.load().map { entry($0, at: Date()) } ?? Self.neutral(Date())
    }

    func getSnapshot(in context: Context, completion: @escaping (ZicouEntry) -> Void) {
        completion(placeholder(in: context))
    }

    static func neutral(_ date: Date) -> ZicouEntry {
        ZicouEntry(date: date, moment: nil, name: PetWidgetState.defaultName)
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<ZicouEntry>) -> Void) {
        let now = Date()
        guard let state = PetWidgetStore.load() else {
            completion(Timeline(entries: [Self.neutral(now)], policy: .never))
            return
        }
        let entries = PetForecast.moments(from: state, now: now).map { ZicouEntry(date: $0.date, moment: $0, name: state.name) }
        let next = entries.last?.date ?? now.addingTimeInterval(PetForecast.horizon)
        completion(Timeline(entries: entries, policy: .after(next)))
    }

    private func entry(_ state: PetWidgetState, at date: Date) -> ZicouEntry {
        ZicouEntry(date: date, moment: PetForecast.moment(of: state, at: date), name: state.name)
    }
}

struct ZicouWidgetView: View {
    let entry: ZicouEntry
    /// Captures hors WidgetKit (aperçus) : famille imposée ; sinon celle du système.
    var forcedFamily: WidgetFamily?
    @Environment(\.widgetFamily) private var systemFamily
    private var family: WidgetFamily { forcedFamily ?? systemFamily }
    @Environment(\.colorScheme) private var scheme

    var body: some View {
        content
            .widgetURL(entry.moment == nil ? PetLinks.base : PetLinks.zicou(src: "widget"))
            .zicouBackground(family: family, scheme: scheme)
    }

    @ViewBuilder
    private var content: some View {
        if let moment = entry.moment {
            switch family {
            case .accessoryCircular: circular(moment)
            case .accessoryRectangular: rectangular(moment)
            case .accessoryInline: inline(moment)
            case .systemMedium: medium(moment)
            default: small(moment)
            }
        } else {
            empty
        }
    }

    /// Rien de gardé (pas connecté, ou Compagnon fermé sur ce site : bêta, éteint en production) : vue neutre,
    /// sans Zicou.
    @ViewBuilder
    private var empty: some View {
        switch family {
        case .accessoryInline:
            Text("Party · bientôt")
        case .accessoryCircular:
            Image(systemName: "sparkles").font(.title2)
        default:
            VStack(spacing: 6) {
                Image(systemName: "sparkles").font(.title2)
                Text("Bientôt dans Party").font(.caption.weight(.semibold)).multilineTextAlignment(.center)
            }
        }
    }

    // MARK: Écran d'accueil

    private func small(_ m: PetMoment) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            ZicouFigure(emotion: m.emotion, stage: m.stage).frame(maxWidth: .infinity)
            Text(headline(m)).font(.caption.weight(.bold)).lineLimit(1).minimumScaleFactor(0.8)
            footer(m).font(.caption2).foregroundStyle(.secondary)
        }
    }

    private func medium(_ m: PetMoment) -> some View {
        HStack(spacing: 12) {
            ZicouFigure(emotion: m.emotion, stage: m.stage)
            VStack(alignment: .leading, spacing: 6) {
                Text(entry.name).font(.headline).lineLimit(1)
                Text(PetWidgetState.moodLine(m.emotion, name: entry.name)).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                if m.stage == "egg" {
                    hatchCountdown(m).font(.caption.weight(.semibold))
                } else if m.stage != "dead" {
                    GaugeRow(symbol: "fork.knife", value: m.gauges.food, color: Z.gold, label: "Ventre")
                    GaugeRow(symbol: "heart.fill", value: m.gauges.joy, color: Z.pink, label: "Humeur")
                    GaugeRow(symbol: "bolt.fill", value: m.gauges.energy, color: Z.cyan, label: "Énergie")
                    GaugeRow(symbol: "sparkles", value: m.gauges.care, color: Z.green, label: "Forme")
                }
                Spacer(minLength: 0)
                footer(m).font(.caption2).foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder
    private func hatchCountdown(_ m: PetMoment) -> some View {
        if let hatch = m.hatchAt, hatch > entry.date {
            HStack(spacing: 4) {
                Text("Éclosion dans")
                Text(hatch, style: .timer).monospacedDigit()
            }
        } else {
            Text("L'œuf va éclore !")
        }
    }

    private func headline(_ m: PetMoment) -> String {
        m.stage == "egg" ? "Un œuf !" : "\(entry.name) \(PetWidgetState.moodWord(m.emotion))"
    }

    /// Série 🔥 et cadeau du jour (symboles : ils restent lisibles en rendu teinté).
    private func footer(_ m: PetMoment) -> some View {
        HStack(spacing: 8) {
            if m.streak > 0 { Label("\(m.streak)", systemImage: "flame.fill") }
            if m.chestReady { Label(family == .systemMedium ? "Cadeau du jour prêt" : "Prêt", systemImage: "gift.fill") }
        }
        .labelStyle(TightLabel())
        .lineLimit(1)
        .minimumScaleFactor(0.8)
    }

    // MARK: Écran verrouillé

    private func circular(_ m: PetMoment) -> some View {
        Gauge(value: m.stage == "egg" ? 1 : m.gauges.lowest, in: 0...PetRates.full) {
            Text("Zicou")
        } currentValueLabel: {
            if m.streak > 0 {
                VStack(spacing: -2) {
                    Image(systemName: "flame.fill").font(.caption2)
                    Text("\(m.streak)").font(.system(.body, design: .rounded).weight(.bold))
                }
            } else {
                ZicouFigure(emotion: m.emotion, stage: m.stage).padding(2)
            }
        }
        .gaugeStyle(.accessoryCircular)
        .widgetAccentable()
    }

    private func rectangular(_ m: PetMoment) -> some View {
        HStack(spacing: 6) {
            ZicouFigure(emotion: m.emotion, stage: m.stage).frame(width: 44, height: 44)
            VStack(alignment: .leading, spacing: 0) {
                Text(entry.name).font(.headline).widgetAccentable().lineLimit(1)
                Text(m.stage == "egg" ? "va éclore" : PetWidgetState.moodWord(m.emotion)).font(.caption).lineLimit(1)
                if m.chestReady {
                    Text("\(Image(systemName: "gift.fill")) Cadeau prêt").font(.caption).lineLimit(1)
                } else if m.streak > 0 {
                    Text("\(Image(systemName: "flame.fill")) \(m.streak) jours").font(.caption).lineLimit(1)
                }
            }
            Spacer(minLength: 0)
        }
    }

    private func inline(_ m: PetMoment) -> some View {
        let mood = m.stage == "egg" ? "va éclore" : PetWidgetState.moodWord(m.emotion)
        return ViewThatFits {
            if m.streak > 0 {
                Text("\(entry.name) \(mood) · \(Image(systemName: "flame.fill")) \(m.streak)")
            }
            Text("\(entry.name) \(mood)")
        }
    }
}

/// Symbole collé au texte (pied des widgets).
private struct TightLabel: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 3) {
            configuration.icon
            configuration.title
        }
    }
}

/// Une jauge : symbole + barre.
private struct GaugeRow: View {
    let symbol: String
    let value: Double
    let color: Color
    let label: String
    @Environment(\.widgetRenderingMode) private var mode

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: symbol).font(.system(size: 9, weight: .bold)).frame(width: 12)
                .foregroundStyle(mode == .fullColor ? color : .primary)
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule().fill(.primary.opacity(0.15))
                    Capsule().fill(mode == .fullColor ? color : .primary)
                        .frame(width: max(4, proxy.size.width * value / PetRates.full))
                        .widgetAccentable()
                }
            }
            .frame(height: 5)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label) \(Int(value.rounded())) sur 100")
    }
}

extension View {
    /// Fond : nuit de Zicou (sombre) ou lavande (clair) ; iOS l'enlève en rendu teinté et sur l'écran verrouillé.
    @ViewBuilder
    func zicouBackground(family: WidgetFamily, scheme: ColorScheme) -> some View {
        let colors = scheme == .dark ? Z.night : Z.day
        let isAccessory = [.accessoryCircular, .accessoryRectangular, .accessoryInline].contains(family)
        if #available(iOSApplicationExtension 17.0, *) {
            containerBackground(for: .widget) {
                if isAccessory {
                    if family == .accessoryCircular { AccessoryWidgetBackground() } else { Color.clear }
                } else {
                    LinearGradient(colors: colors, startPoint: .top, endPoint: .bottom)
                }
            }
        } else if isAccessory {
            self
        } else {
            padding().background(LinearGradient(colors: colors, startPoint: .top, endPoint: .bottom))
        }
    }
}
