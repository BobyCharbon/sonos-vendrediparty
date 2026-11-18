import SwiftUI

/// Infos de la discussion d'un événement : mes notifications (le même réglage que la fiche : « notifications coupées
/// pour cet événement »), les citations de l'organisation, et les personnes de la discussion par réponse.
/// Les invités sans réponse n'apparaissent que pour l'organisation (règle du 11.11 : un invité ne voit pas les noms).
struct EventChatInfoView: View {
    @ObservedObject var store: ChatsStore
    @Environment(\.dismiss) private var dismiss
    @Environment(\.conversationRoutes) private var routes
    /// Un toucher sur une personne : son mini-profil (Discussions v2).
    @State private var person: PersonRef?

    private struct Bucket: Identifiable {
        let id: String
        let title: String
        let people: [Conversation.Member]
    }

    private func buckets(_ chat: Conversation) -> [Bucket] {
        let organizers = chat.members.filter { $0.organizer == true }
        let rest = chat.members.filter { $0.organizer != true }
        return [
            Bucket(id: "orga", title: "Organisation", people: organizers),
            Bucket(id: "yes", title: "Présents", people: rest.filter { $0.rsvp == "yes" }),
            Bucket(id: "maybe", title: "Peut-être", people: rest.filter { $0.rsvp == "maybe" }),
            Bucket(id: "no", title: "Pas présents", people: rest.filter { $0.rsvp == "no" }),
            Bucket(id: "invited", title: "Invités sans réponse", people: rest.filter { $0.rsvp == nil && $0.invited == true }),
            Bucket(id: "other", title: "Autres personnes de la discussion", people: rest.filter { $0.rsvp == nil && $0.invited != true }),
        ].filter { !$0.people.isEmpty }
    }

    var body: some View {
        NavigationStack {
            Form {
                if let chat = store.conversation {
                    Section {
                        Toggle("Notifications de cet événement", isOn: Binding(get: { chat.notify != .none }, set: { on in
                            Haptics.selection()
                            Task { await store.setNotify(on ? .all : .none) }
                        }))
                        .tint(ConvNeon.lavDeep)
                        .accessibilityIdentifier("event-chat-notify")
                    } footer: {
                        Text(chat.notify == .none
                             ? "Coupées : aucune notification de cet événement, même quand on te cite. Le même réglage que sur sa fiche."
                             : "Selon Réglages › Notifications : chaque message, ou seulement quand on te cite (@surnom, @toutlemonde, @present, annonce) ou te répond.")
                    }
                    .listRowBackground(ConvNeon.surface)
                    if chat.isStaff {
                        Section {
                            Label("@toutlemonde : prévient tous les invités et participants", systemImage: "person.3.fill")
                            Label("@present : prévient les présents et les peut-être", systemImage: "checkmark.circle.fill")
                            Label("Bouton annonce ou @annonce : épinglée en haut, envoyée à tous", systemImage: "megaphone.fill")
                        } header: {
                            Text("Réservé à l'organisation")
                        } footer: {
                            Text("Tu organises cet événement (ou tu es admin) : tu peux aussi épingler un message ou retirer celui d'un autre, d'un appui long.")
                        }
                        .font(.subheadline)
                        .foregroundStyle(ConvNeon.t1)
                        .listRowBackground(ConvNeon.surface)
                    }
                    ForEach(buckets(chat)) { bucket in
                        Section {
                            ForEach(bucket.people) { member in
                                Button {
                                    Haptics.tap()
                                    person = PersonRef(id: member.id)
                                } label: {
                                    HStack(spacing: 12) {
                                        ConvFace(id: member.id, name: member.name, photo: member.photo, size: 36)
                                        PersonName(id: member.id, pseudo: member.name).foregroundStyle(ConvNeon.t1)
                                        Spacer()
                                        if member.id == chat.me { Text("Toi").font(.caption).foregroundStyle(ConvNeon.t2) }
                                    }
                                    .frame(minHeight: 44)
                                    .contentShape(Rectangle())
                                }
                                .buttonStyle(.plain)
                                .disabled(member.id == chat.me)
                                .accessibilityElement(children: .combine)
                                .accessibilityHint(member.id == chat.me ? "" : "Ouvre son profil")
                            }
                        } header: {
                            Text("\(bucket.title) · \(bucket.people.count)")
                        }
                        .listRowBackground(ConvNeon.surface)
                    }
                } else {
                    ProgressView().tint(ConvNeon.lav)
                }
            }
            .convNeonForm()
            .personSheet($person, store: store, routes: routes)
            .navigationTitle(store.conversation?.name ?? "Discussion")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } }
            }
        }
        .presentationDragIndicator(.visible)
        .preferredColorScheme(.dark)
    }
}
