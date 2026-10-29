import SwiftUI

/// Infos du groupe : mes notifications (par défaut : mentions seulement), membres et admins du groupe.
struct ChatInfoView: View {
    @ObservedObject var store: ChatsStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                if let chat = store.conversation {
                    if chat.member {
                        Section {
                            Picker("Notifications", selection: Binding(get: { chat.notify }, set: { level in
                                Task { await store.setNotify(level) }
                            })) {
                                ForEach(ChatNotify.allCases) { Text($0.label).tag($0) }
                            }
                            .pickerStyle(.segmented)
                        } header: {
                            Text("Notifications")
                        } footer: {
                            Text(chat.notify.hint)
                        }
                    }
                    Section {
                        ForEach(chat.members) { m in member(m, canName: chat.canNameAdmins) }
                    } header: {
                        Text("\(chat.members.count) membre\(chat.members.count > 1 ? "s" : "")")
                    } footer: {
                        Text("Les admins du groupe épinglent et suppriment les messages et peuvent écrire @tout. "
                             + (chat.canNameAdmins ? "Tu les nommes ici." : "Le créateur du groupe les nomme."))
                    }
                }
            }
            .scrollContentBackground(.hidden)
            .background(AppConfig.background.ignoresSafeArea())
            .navigationTitle(store.conversation?.name ?? "Groupe")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("OK") { dismiss() } } }
        }
        .preferredColorScheme(.dark)
    }

    @ViewBuilder private func member(_ m: Conversation.Member, canName: Bool) -> some View {
        if canName && !m.creator {
            Toggle(isOn: Binding(get: { m.admin }, set: { on in Task { await store.setAdmin(m, on) } })) {
                HStack { Initials(name: m.name, photo: m.photo); Text(m.name) }
            }
            .accessibilityLabel("\(m.name), admin du groupe")
        } else {
            HStack {
                Initials(name: m.name, photo: m.photo)
                Text(m.name)
                Spacer()
                if m.creator { Text("Créateur").foregroundStyle(.secondary) } else if m.admin { Text("Admin").foregroundStyle(.secondary) }
            }
        }
    }
}
