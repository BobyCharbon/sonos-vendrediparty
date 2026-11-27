import SwiftUI

/// Demandes de message : quelqu'un qu'on ne connaît pas encore (Membres Vendredi Party, soirée publique, recherche)
/// veut t'écrire. Chaque demande : qui c'est, son message, Accepter / Supprimer, Bloquer · Signaler.
/// L'autre ne sait pas si tu l'as lue ; supprimer ne le prévient pas.
struct ChatRequestsView: View {
    @ObservedObject var store: ChatsStore
    @State private var reporting: ReportTarget?
    @State private var blocking: ChatSummary?

    private var requests: [ChatSummary] { ChatListLogic.requests(store.chats ?? []) }

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 14) {
                if requests.isEmpty {
                    VStack(spacing: 10) {
                        Image(systemName: "tray").font(.largeTitle).foregroundStyle(ChatNeon.lav)
                        Text("Aucune demande").font(.title3.weight(.bold)).foregroundStyle(ChatNeon.t1)
                        Text("Quand quelqu'un que tu n'as encore jamais croisé veut t'écrire, sa demande arrive ici. Tu choisis de répondre ou non.")
                            .font(.subheadline).foregroundStyle(ChatNeon.t2).multilineTextAlignment(.center)
                    }
                    .padding(.top, 80).padding(.horizontal, 32)
                    .transition(.opacity)
                } else {
                    Text("La personne ne sait pas si tu as lu sa demande. Si tu la supprimes, elle n'est pas prévenue.")
                        .font(.footnote).foregroundStyle(ChatNeon.t3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ForEach(requests) { chat in
                        ChatRequestCard(chat: chat, store: store,
                                        report: { reporting = $0 }, block: { blocking = chat })
                            .motionTransition()
                    }
                }
            }
            .padding(16)
            .motion(Motion.smooth, value: requests.map(\.id))
        }
        .background(NeonGlow())
        .navigationTitle("Demandes")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.loadList() }
        .refreshable { await store.loadList() }
        .sheet(item: $reporting) { ReportSheet(store: store.moderation, target: $0) }
        .confirmationDialog(blocking.map { "Bloquer \($0.name) ?" } ?? "", isPresented: Binding(get: { blocking != nil }, set: { if !$0 { blocking = nil } }),
                            titleVisibility: .visible, presenting: blocking) { chat in
            Button("Bloquer", role: .destructive) { Task { await store.blockRequest(chat) } }
        } message: { _ in
            Text("La demande disparaît. Cette personne ne pourra plus t'écrire, ni te citer, t'inviter ou voir ta fiche ; elle n'en est pas prévenue.")
        }
    }
}

private struct ChatRequestCard: View {
    let chat: ChatSummary
    @ObservedObject var store: ChatsStore
    let report: (ReportTarget) -> Void
    let block: () -> Void
    @State private var who: ChatRequester?
    @State private var busy = false

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                NeonAvatar(id: chat.userID ?? chat.id, name: who?.name ?? chat.name, photo: who?.photo ?? chat.photo, size: 54)
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text(who?.name ?? chat.name).font(.headline).foregroundStyle(ChatNeon.t1).lineLimit(1)
                        if let nick = who?.nickname, !nick.isEmpty {
                            Text("@" + nick).font(.subheadline).foregroundStyle(ChatNeon.t3).lineLimit(1)
                        }
                    }
                    Text((who?.facts ?? ["Veut t'écrire"]).joined(separator: " · "))
                        .font(.footnote).foregroundStyle(ChatNeon.t2).fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
            VStack(alignment: .leading, spacing: 6) {
                Text(chat.lastMessage?.text ?? chat.last ?? "")
                    .font(.body).foregroundStyle(ChatNeon.t1)
                    .textSelection(.enabled)
                Text(ChatListText.time(chat.lastAt)).font(.caption).foregroundStyle(ChatNeon.t3)
            }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ChatNeon.theirs, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(ChatNeon.lavA.opacity(0.10), lineWidth: 1))

            HStack(spacing: 10) {
                Button {
                    busy = true
                    Haptics.tap()
                    Task { _ = await store.accept(chat); busy = false }
                } label: {
                    Label("Accepter", systemImage: "checkmark")
                        .font(.body.weight(.bold)).foregroundStyle(ChatNeon.onPink)
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .background(ChatNeon.pinkGradient, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                }
                .accessibilityIdentifier("chat-request-accept")
                ConfirmedButton(question: "Supprimer cette demande ?", message: "La personne n'est pas prévenue.") {
                    busy = true
                    Task { await store.decline(chat); busy = false }
                } label: {
                    Text("Supprimer")
                        .font(.body.weight(.semibold)).foregroundStyle(ChatNeon.t1)
                        .frame(maxWidth: .infinity, minHeight: 48)
                        .background(ChatNeon.glass, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(ChatNeon.glassLine, lineWidth: 1))
                }
                .accessibilityIdentifier("chat-request-decline")
            }
            .buttonStyle(.plain)
            .disabled(busy)

            HStack(spacing: 4) {
                Button("Bloquer", action: block)
                    .frame(minHeight: 44).padding(.horizontal, 8)
                Text("·").foregroundStyle(ChatNeon.t3).accessibilityHidden(true)
                Button("Signaler") {
                    if let id = chat.lastMessage?.id {
                        report(ReportTarget(kind: .directMessage, id: id, label: "le message de \(who?.name ?? chat.name)"))
                    } else if let user = chat.userID {
                        report(ReportTarget(kind: .profile, id: user, label: who?.name ?? chat.name))
                    }
                }
                .frame(minHeight: 44).padding(.horizontal, 8)
            }
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(ChatNeon.t2)
            .buttonStyle(.plain)
            .frame(maxWidth: .infinity)
        }
        .padding(16)
        .background(ChatNeon.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(ChatNeon.line, lineWidth: 1))
        .task(id: chat.userID) {
            guard let user = chat.userID else { return }
            who = await store.requester(user)
        }
    }
}

/// Archivées : mêmes lignes et mêmes gestes (glisser à gauche = Désarchiver).
struct ChatArchivedView: View {
    @ObservedObject var store: ChatsStore
    let open: (ChatSummary) -> Void
    let askMute: (ChatSummary) -> Void
    let askBlock: (ChatSummary) -> Void
    let showProfile: ((String) -> Void)?

    private var archived: [ChatSummary] { ChatListLogic.archived(store.chats ?? []) }

    var body: some View {
        List {
            if archived.isEmpty {
                Text("Aucune discussion archivée. Glisse une discussion vers la gauche dans la liste pour la ranger ici.")
                    .font(.subheadline).foregroundStyle(ChatNeon.t2)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            } else {
                Section {
                    ForEach(archived) { chat in
                        Button { open(chat) } label: { ChatListRow(chat: chat).padding(.horizontal, 16) }
                            .buttonStyle(ChatRowPressStyle())
                            .chatRowActions(chat, store: store, askMute: askMute, askBlock: askBlock, showProfile: showProfile)
                            .listRowInsets(EdgeInsets())
                            .listRowBackground(Color.clear)
                            .listRowSeparatorTint(ChatNeon.line)
                            .alignmentGuide(.listRowSeparatorLeading) { _ in 82 }
                    }
                } footer: {
                    Text("Une discussion archivée garde ses messages et ses réglages. Glisse-la vers la gauche pour la ressortir.")
                        .font(.footnote).foregroundStyle(ChatNeon.t3)
                }
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(NeonGlow())
        .motion(Motion.snappy, value: archived.map(\.id))
        .navigationTitle("Archivées")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.loadList() }
        .refreshable { await store.loadList() }
    }
}
