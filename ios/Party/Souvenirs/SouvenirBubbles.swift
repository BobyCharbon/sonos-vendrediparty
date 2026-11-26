import SwiftUI
import WebKit

/// Bulles des Souvenirs en haut de l'onglet Discussions (maquette v2, écrans 4 et 5) : anneau néon pendant la story
/// (un toucher l'ouvre), anneau gris à cadenas et compte à rebours pendant l'attente (un toucher dit quand).
struct SouvenirBubblesRow: View {
    @ObservedObject var store: SouvenirsStore
    @State private var waitingInfo: SouvenirBubble?

    var body: some View {
        if !store.bubbles.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 14) {
                        ForEach(store.bubbles) { bubble in
                            Button {
                                Haptics.selection()
                                if bubble.waiting {
                                    Motion.animate(Motion.snappy) { waitingInfo = waitingInfo?.id == bubble.id ? nil : bubble }
                                } else {
                                    waitingInfo = nil
                                    store.openStory(bubble.eventId)
                                }
                            } label: {
                                SouvenirBubbleView(bubble: bubble)
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("souvenir-bubble-\(bubble.eventId)")
                        }
                    }
                    .padding(.horizontal, 16)
                }
                if let info = waitingInfo { waitingCard(info) }
            }
            .padding(.vertical, 6)
        } else {
            // Ligne vide de la liste (ChatsView : defaultMinListRowHeight à 0) : aucune place prise.
            Color.clear.frame(height: 0).accessibilityHidden(true)
        }
    }

    private func waitingCard(_ bubble: SouvenirBubble) -> some View {
        let when = SouvenirDates.parse(bubble.revealAt).map { date -> String in
            let f = DateFormatter()
            f.locale = Locale(identifier: "fr_CH")
            f.timeZone = TimeZone(identifier: "Europe/Zurich")
            f.dateFormat = "EEE dd.MM 'à' H 'h' mm"
            return f.string(from: date).replacingOccurrences(of: " 00", with: "")
        } ?? "bientôt"
        return HStack(alignment: .top, spacing: 10) {
            Text("🧪")
            Text("Les photos de \(bubble.title ?? "la soirée") sont au labo. Dévoilement \(when), pour tout le monde en même temps.")
                .font(.subheadline).foregroundStyle(ChatNeon.t1)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(12)
        .background(ChatNeon.glass, in: RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(ChatNeon.glassLine, lineWidth: 1))
        .padding(.horizontal, 16)
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("souvenir-waiting-info")
        .transition(.opacity.combined(with: .move(edge: .top)))
    }
}

struct SouvenirBubbleView: View {
    let bubble: SouvenirBubble

    private static let neon = AngularGradient(colors: [ChatNeon.pinkA, ChatNeon.coral, ChatNeon.lavA, ChatNeon.pinkA], center: .center)

    var body: some View {
        VStack(spacing: 5) {
            ZStack {
                if bubble.waiting {
                    Circle().stroke(ChatNeon.t3.opacity(0.6), lineWidth: 2.5)
                } else if bubble.seen == true {
                    Circle().stroke(ChatNeon.line2, lineWidth: 2)
                } else {
                    Circle().stroke(Self.neon, lineWidth: 3).shadow(color: ChatNeon.pinkA.opacity(0.6), radius: 6)
                }
                Circle().fill(ChatNeon.s1b).padding(5)
                Text(bubble.waiting ? "🧪" : "📸").font(.system(size: 26))
                    .saturation(bubble.waiting ? 0.2 : 1)
                if bubble.waiting {
                    Image(systemName: "lock.fill").font(.system(size: 11, weight: .bold)).foregroundStyle(.white)
                        .frame(width: 22, height: 22).background(ChatNeon.muted, in: Circle())
                        .overlay(Circle().stroke(ChatNeon.bg, lineWidth: 2))
                        .offset(x: 22, y: 22)
                }
            }
            .frame(width: 64, height: 64)
            Text(bubble.title ?? "Souvenirs").font(.caption2.weight(.semibold)).lineLimit(1)
                .foregroundStyle(ChatNeon.t1).frame(width: 74)
            if bubble.waiting {
                TimelineView(.periodic(from: .now, by: 1)) { context in
                    Text(SouvenirText.countdown(to: bubble.revealAt, now: context.date))
                        .font(.caption2.monospacedDigit()).foregroundStyle(ChatNeon.t2)
                }
            } else {
                Text(bubble.seen == true ? "vue" : "Nouveau").font(.caption2.weight(bubble.seen == true ? .regular : .bold))
                    .foregroundStyle(bubble.seen == true ? ChatNeon.t3 : ChatNeon.pinkInk)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(bubble.waiting
            ? "Souvenirs de \(bubble.title ?? "la soirée"), au labo, dévoilement dans \(SouvenirText.countdown(to: bubble.revealAt))"
            : "Story des souvenirs de \(bubble.title ?? "la soirée"), \(SouvenirText.photos(bubble.count))\(bubble.seen == true ? ", vue" : ", nouvelle")")
        .accessibilityAddTraits(.isButton)
    }
}

/// « 📸 Les souvenirs sont arrivés » en haut de la discussion d'un événement (maquette v2, écran 5 bis), pendant les 24 h
/// de la story seulement (souvenir_counter : le nombre, jamais qui ni quoi). Un toucher ouvre la story native.
struct SouvenirChatBanner: View {
    let eventID: String
    @Environment(\.souvenirs) private var store
    @State private var counter: SouvenirCounter?

    private var shown: Bool {
        guard let c = counter, c.enabled, c.phase == "story", c.member == true || c.staff == true else { return false }
        return (c.count ?? 0) > 0
    }

    var body: some View {
        // VStack, pas Group : un Group vide (bandeau caché au départ) ne porte pas le .task, qui ne partait jamais.
        VStack(spacing: 0) {
            if shown, let c = counter, let store {
                let count = c.count ?? 0
                let until = SouvenirText.visibleFor(until: c.storyUntil)
                Button {
                    Haptics.selection()
                    store.openStory(eventID)
                } label: {
                    HStack(spacing: 12) {
                        Text("📸").font(.system(size: 22))
                            .frame(width: 44, height: 44)
                            .background(ChatNeon.s1b, in: Circle())
                            .overlay(Circle().stroke(c.seen == true ? AnyShapeStyle(ChatNeon.line2) : AnyShapeStyle(ChatNeon.pinkA), lineWidth: 2))
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Les souvenirs sont arrivés").font(.subheadline.weight(.bold)).foregroundStyle(ChatNeon.t1)
                            Text([SouvenirText.photos(count), until].compactMap { $0 }.joined(separator: " · "))
                                .font(.caption).foregroundStyle(ChatNeon.t2)
                        }
                        .lineLimit(1)
                        Spacer(minLength: 4)
                        Text(c.seen == true ? "▶︎ Revoir" : "▶︎ Voir").font(.subheadline.weight(.bold)).foregroundStyle(ChatNeon.onPink)
                            .padding(.horizontal, 14).frame(minHeight: 44)
                            .background(ChatNeon.pinkGradient, in: Capsule())
                    }
                    .padding(.horizontal, 12).padding(.vertical, 10)
                    .background(ChatNeon.pink.opacity(0.14), in: RoundedRectangle(cornerRadius: 18))
                    .overlay(RoundedRectangle(cornerRadius: 18).stroke(ChatNeon.pink.opacity(0.55), lineWidth: 1))
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .padding(.horizontal, 12).padding(.top, 8)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Les souvenirs sont arrivés : \(SouvenirText.photos(count))\(until.map { ", \($0)" } ?? "")")
                .accessibilityHint("Ouvre la story")
                .accessibilityAddTraits(.isButton)
                .accessibilityIdentifier("souvenir-chat-banner")
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .task(id: eventID) {
            // Relu chaque minute : le dévoilement (ou la fin de la story) arrive pendant que la discussion est ouverte.
            // Échec (page pas encore prête au lancement par une notification, jeton absent, réseau) : nouvel essai dans 5 s,
            // sinon le bandeau manquait une minute entière.
            while !Task.isCancelled {
                var ok = false
                if let store, let fresh = try? await store.counter(eventID) {
                    ok = true
                    if fresh != counter { Motion.animate(Motion.smooth) { counter = fresh } }
                }
                try? await Task.sleep(for: .seconds(ok ? 60 : 5))
            }
        }
    }
}

/// Le store des Souvenirs pour l'onglet Discussions (bulles) ; nil avant que l'app soit prête.
private struct SouvenirsStoreKey: EnvironmentKey {
    static let defaultValue: SouvenirsStore? = nil
}

extension EnvironmentValues {
    var souvenirs: SouvenirsStore? {
        get { self[SouvenirsStoreKey.self] }
        set { self[SouvenirsStoreKey.self] = newValue }
    }
}

/// Pont `partySouvenirs` (module Événements, cadre compris) : appareil photo, story, enregistrement dans Photos.
/// Promesses : camera / story → true ; save → { saved: true }, rejetée avec la phrase à montrer.
final class SouvenirsBridge: NSObject, WKScriptMessageHandlerWithReply {
    static let handler = "partySouvenirs"
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    static let script = """
    {
          camera: function (id) { var p = window.webkit.messageHandlers.\(handler).postMessage({ action: "camera", eventId: String(id) }); p.catch(function () {}); return p; },
          story: function (id) { var p = window.webkit.messageHandlers.\(handler).postMessage({ action: "story", eventId: String(id) }); p.catch(function () {}); return p; },
          save: function (url) { return window.webkit.messageHandlers.\(handler).postMessage({ action: "save", url: String(url) }); }
        }
    """

    @MainActor
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) async -> (Any?, String?) {
        guard AppConfig.mayUseBridge(message.frameInfo.securityOrigin.url) else { return (nil, "Origine refusée") }
        guard let request = SouvenirBridgeRequest.parse(message.body), let model else { return (nil, "Demande inconnue") }
        switch request {
        case .open(let route):
            model.openSouvenirs(route)
            return (true, nil)
        case .save(let url):
            guard let store = model.souvenirs else { return (nil, "Party n'est pas encore prête.") }
            if let problem = await store.save(url) {
                Haptics.warning()
                return (nil, problem)
            }
            Haptics.success()
            return (["saved": true], nil)
        }
    }
}
