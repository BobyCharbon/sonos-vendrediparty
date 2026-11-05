import SwiftUI

/// Onglet « À inviter » : contacts du répertoire sans compte Party (d'après leur numéro), mobiles d'abord. Calculé sur
/// l'iPhone : aucun numéro n'est envoyé. « Inviter » ouvre Messages avec un SMS prérempli et mon lien (raccourci) ;
/// l'icône de partage ouvre la feuille d'iOS (WhatsApp, Instagram, Snapchat, Mail…). Un à la fois, jamais en masse.
struct InviteList: View {
    @ObservedObject var store: FriendsStore
    let query: String
    let link: URL?
    let compose: (MessageDraft) -> Void
    let share: (InviteCandidate, String) -> Void

    var body: some View {
        let shown = store.toInvite.filter { FriendsLogic.matches($0.name, query: query) || $0.phone.contains(query) }
        if !store.loaded {
            Section { HStack { Spacer(); ProgressView(); Spacer() } }.listRowBackground(Color.clear)
        } else if store.toInvite.isEmpty {
            Section {
                EmptyState(symbol: "checkmark.circle", title: "Tout le monde est là",
                           text: "Tous tes contacts avec un numéro sont déjà sur Party, ou ton répertoire est vide.")
            }
        } else if shown.isEmpty {
            Section { Text("Aucun résultat pour « \(query) »").foregroundStyle(.secondary) }
        } else {
            Section {
                ForEach(shown) { candidate in
                    InviteRow(candidate: candidate, invitedAt: store.invited[candidate.id], enabled: link != nil, invite: {
                        guard let link else { return }
                        Haptics.tap()
                        compose(MessageDraft(recipient: candidate.phone, body: FriendsLogic.smsBody(firstName: first(candidate), link: link),
                                             candidate: candidate))
                    }, share: {
                        guard let link else { return }
                        Haptics.tap()
                        share(candidate, FriendsLogic.smsBody(firstName: first(candidate), link: link))
                    })
                }
            } header: {
                Text("Pas encore sur Party")
            } footer: {
                Text("Pas encore sur Party, d'après leur numéro. Le message part de ton iPhone, avec ton lien personnel ; tu le relis avant d'envoyer. L'icône de partage l'envoie aussi par WhatsApp, Instagram, Snapchat…")
            }
        }
    }

    private func first(_ candidate: InviteCandidate) -> String {
        candidate.name.split(separator: " ").first.map(String.init) ?? ""
    }
}

private struct InviteRow: View {
    let candidate: InviteCandidate
    let invitedAt: Date?
    let enabled: Bool
    let invite: () -> Void
    let share: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            Text(initials)
                .font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                .frame(width: 42, height: 42)
                .background(Color.gray.opacity(0.55), in: Circle())
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(candidate.name).lineLimit(1)
                Text(invitedAt.map { FriendsLogic.invitedText($0) } ?? (candidate.mobile ? "Mobile" : "Téléphone"))
                    .font(.footnote).foregroundStyle(invitedAt == nil ? AnyShapeStyle(.secondary) : AnyShapeStyle(Palette.accent))
            }
            Spacer(minLength: 8)
            Button(action: share) { Image(systemName: "square.and.arrow.up") }
                .buttonStyle(.borderless)
                .disabled(!enabled)
                .accessibilityLabel("Partager une invitation pour \(candidate.name)")
            Button(invitedAt == nil ? "Inviter" : "Relancer", action: invite)
                .buttonStyle(.bordered)
                .buttonBorderShape(.capsule)
                .controlSize(.small)
                .disabled(!enabled)
                .accessibilityLabel("Inviter \(candidate.name)")
        }
        .padding(.vertical, 2)
    }

    private var initials: String {
        candidate.name.split(separator: " ").prefix(2).compactMap { $0.first.map(String.init) }.joined().uppercased()
    }
}
