import SwiftUI

/// Aucune discussion encore (maquette 5-vide) : deux bulles qui se répondent, trois personnes croisées avec « Écrire »,
/// « Nouveau message » et « Groupe ».
struct ChatsEmptyView: View {
    let crossed: [ChatPerson]
    let write: (ChatPerson) -> Void
    let newMessage: (() -> Void)?
    let newGroup: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var shown = false

    /// « Croisés à Raclette chez Léa » quand les trois viennent de la même soirée, sinon « Croisés récemment ».
    private var crossedTitle: String {
        let subs = Set(crossed.prefix(3).compactMap(\.sub))
        if subs.count == 1, let sub = subs.first, !sub.isEmpty { return "Croisés à « \(sub) »" }
        return "Croisés récemment"
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 22) {
                bubbles
                    .padding(.top, 8)
                VStack(spacing: 10) {
                    Text("Ta première discussion commence ici")
                        .font(.system(.title, design: .rounded).weight(.heavy))
                        .foregroundStyle(ChatNeon.t1)
                        .multilineTextAlignment(.center)
                    Text("Écris à quelqu'un croisé à une soirée, ou réunis ta bande dans un groupe.")
                        .font(.body).foregroundStyle(ChatNeon.t2)
                        .multilineTextAlignment(.center)
                }
                .padding(.horizontal, 12)

                if !crossed.isEmpty {
                    VStack(alignment: .leading, spacing: 14) {
                        Label(crossedTitle, systemImage: "sparkle")
                            .font(ChatNeon.label).kerning(0.9).textCase(.uppercase)
                            .foregroundStyle(ChatNeon.t3)
                            .lineLimit(1)
                        HStack(alignment: .top, spacing: 8) {
                            ForEach(crossed.prefix(3)) { person in
                                VStack(spacing: 8) {
                                    NeonAvatar(id: person.id, name: person.name, photo: person.photo, size: 44)
                                    Text(person.firstName).font(.body.weight(.medium)).foregroundStyle(ChatNeon.t1).lineLimit(1)
                                    Button { write(person) } label: {
                                        Label("Écrire", systemImage: "bubble.left")
                                            .font(.subheadline.weight(.semibold))
                                            .foregroundStyle(ChatNeon.lav)
                                            .padding(.horizontal, 14).frame(minHeight: 40)
                                            .background(ChatNeon.lav.opacity(0.12), in: Capsule())
                                            .overlay(Capsule().strokeBorder(ChatNeon.lav.opacity(0.35), lineWidth: 1))
                                            .frame(minHeight: 44)
                                    }
                                    .buttonStyle(.plain)
                                    .accessibilityLabel("Écrire à \(person.name)")
                                }
                                .frame(maxWidth: .infinity)
                            }
                        }
                    }
                    .padding(18)
                    .background(ChatNeon.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(ChatNeon.line, lineWidth: 1))
                }

                HStack(spacing: 10) {
                    if let newMessage {
                        Button(action: newMessage) {
                            Label("Nouveau message", systemImage: "square.and.pencil")
                                .font(.body.weight(.bold)).foregroundStyle(ChatNeon.onPink)
                                .frame(maxWidth: .infinity, minHeight: 54)
                                .background(ChatNeon.pinkGradient, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                                .shadow(color: ChatNeon.pink.opacity(0.5), radius: 14, y: 6)
                        }
                        .accessibilityIdentifier("chats-empty-new-message")
                    }
                    Button(action: newGroup) {
                        Label("Groupe", systemImage: "person.2")
                            .font(.body.weight(.semibold)).foregroundStyle(ChatNeon.t1)
                            .padding(.horizontal, 20)
                            .frame(maxWidth: newMessage == nil ? .infinity : nil, minHeight: 54)
                            .background(ChatNeon.glass, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(ChatNeon.glassLine, lineWidth: 1))
                    }
                    .accessibilityIdentifier("chats-empty-new-group")
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .onAppear { withAnimation(Motion.pick(Motion.smooth, reduced: reduceMotion)) { shown = true } }
    }

    /// « Ça te dit vendredi ? » / « Grave ! 🎉 » : les bulles des Discussions, posées de biais, quelques confettis.
    private var bubbles: some View {
        ZStack {
            ForEach(Array(Self.confetti.enumerated()), id: \.offset) { _, c in
                RoundedRectangle(cornerRadius: 3).fill(c.color)
                    .frame(width: c.w, height: c.h).rotationEffect(.degrees(c.angle))
                    .offset(x: c.x, y: c.y)
            }
            Text("Ça te dit vendredi ?")
                .font(.title3.weight(.semibold)).foregroundStyle(ChatNeon.t1)
                .padding(.horizontal, 20).padding(.vertical, 14)
                .background(ChatNeon.theirs, in: Capsule())
                .overlay(Capsule().strokeBorder(ChatNeon.lavA.opacity(0.35), lineWidth: 1.5))
                .shadow(color: ChatNeon.lavB.opacity(0.35), radius: 16)
                .rotationEffect(.degrees(-5))
                .offset(x: -40, y: shown ? -34 : -20)
            Text("Grave ! 🎉")
                .font(.title3.weight(.bold)).foregroundStyle(.white)
                .padding(.horizontal, 22).padding(.vertical, 14)
                .background(LinearGradient(colors: [ChatNeon.mineA, ChatNeon.mineB], startPoint: .topLeading, endPoint: .bottomTrailing), in: Capsule())
                .overlay(Capsule().strokeBorder(ChatNeon.pink.opacity(0.7), lineWidth: 1.5))
                .shadow(color: ChatNeon.pink.opacity(0.35), radius: 16)
                .rotationEffect(.degrees(4))
                .offset(x: 70, y: shown ? 42 : 56)
                .opacity(shown ? 1 : 0)
        }
        .frame(height: 190)
        .frame(maxWidth: .infinity)
        .accessibilityHidden(true)
    }

    private struct Confetto { let x, y, w, h, angle: CGFloat; let color: Color }
    private static let confetti: [Confetto] = [
        .init(x: -130, y: -60, w: 14, h: 6, angle: 0, color: ChatNeon.pink),
        .init(x: -10, y: -88, w: 14, h: 6, angle: -25, color: Color(hex: 0xFFB347)),
        .init(x: 75, y: -92, w: 7, h: 7, angle: 45, color: ChatNeon.pink.opacity(0.8)),
        .init(x: 120, y: -50, w: 10, h: 10, angle: 45, color: Color(hex: 0xFFE27A)),
        .init(x: 150, y: 5, w: 14, h: 6, angle: 30, color: Color(hex: 0x5BE3A6)),
        .init(x: -150, y: 50, w: 10, h: 10, angle: 45, color: Color(hex: 0x6CC7FF)),
        .init(x: -95, y: 80, w: 7, h: 7, angle: 0, color: ChatNeon.lavA),
    ]
}
