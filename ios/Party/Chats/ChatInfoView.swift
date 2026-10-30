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
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Initials(name: m.name, photo: m.photo)
                VStack(alignment: .leading, spacing: 2) {
                    Text(m.name)
                    if let call = m.call, let phone = m.phone {
                        // Numéro montré dans ce groupe : un toucher appelle, comme dans WhatsApp.
                        Link(destination: call) { Label(phone, systemImage: "phone.fill").font(.subheadline) }
                            .accessibilityLabel("Appeler \(m.name) au \(phone)")
                    }
                }
                Spacer()
                if m.creator { Text("Créateur").foregroundStyle(.secondary) } else if m.admin { Text("Admin").foregroundStyle(.secondary) }
            }
            if canName && !m.creator {
                Toggle("Admin du groupe", isOn: Binding(get: { m.admin }, set: { on in Task { await store.setAdmin(m, on) } }))
                    .font(.subheadline)
                    .accessibilityLabel("\(m.name), admin du groupe")
            }
        }
    }
}
