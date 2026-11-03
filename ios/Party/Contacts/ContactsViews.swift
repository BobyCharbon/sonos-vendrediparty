import Contacts
import ContactsUI
import SwiftUI

/// « Nom du contact · pseudo » : le nom du répertoire (police de l'appelant), le pseudo Party en plus petit et gris.
/// Sans contact : le pseudo seul, comme avant.
struct PersonName: View {
    let id: String?
    let pseudo: String
    var pseudoFont: Font = .footnote
    @ObservedObject private var contacts = ContactNames.shared

    init(id: String?, pseudo: String, pseudoFont: Font = .footnote) {
        self.id = id
        self.pseudo = pseudo
        self.pseudoFont = pseudoFont
    }

    var body: some View {
        let label = contacts.label(for: id, pseudo: pseudo)
        HStack(alignment: .firstTextBaseline, spacing: 4) {
            Text(label.primary).lineLimit(1)
            if let nick = label.secondary {
                Text("· \(nick)").font(pseudoFont).foregroundStyle(.secondary).lineLimit(1).layoutPriority(-1)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(label.text)
    }
}

// MARK: Demande d'accès au bon moment

extension View {
    /// Première ouverture des Discussions : explication puis fenêtre d'iOS, une seule fois.
    func contactsPrompt() -> some View { modifier(ContactsPromptModifier()) }
}

private struct ContactsPromptModifier: ViewModifier {
    @ObservedObject private var contacts = ContactNames.shared
    @State private var shown = false

    func body(content: Content) -> some View {
        content
            .task {
                guard contacts.shouldPrompt else { return }
                try? await Task.sleep(nanoseconds: 700_000_000)
                if contacts.shouldPrompt { shown = true }
            }
            .sheet(isPresented: $shown, onDismiss: { contacts.promptShown() }) {
                ContactsExplainer { allow in
                    shown = false
                    if allow { Task { await contacts.requestAccess() } } else { contacts.promptShown() }
                }
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
    }
}

/// Écran d'explication, avant la fenêtre d'iOS : à quoi sert l'accès, ce qui part (des empreintes) et ce qui reste.
struct ContactsExplainer: View {
    let answer: (Bool) -> Void

    var body: some View {
        VStack(spacing: 18) {
            Image(systemName: "person.crop.circle.badge.checkmark")
                .font(.system(size: 54, weight: .semibold))
                .foregroundStyle(Palette.accent)
                .padding(.top, 28)
                .accessibilityHidden(true)
            Text("Reconnais tes amis").font(.title2.weight(.bold))
            VStack(alignment: .leading, spacing: 12) {
                point("text.badge.checkmark", "Les membres Party qui sont dans tes contacts s'affichent sous le nom que tu leur as donné, avec leur pseudo en plus petit.")
                point("lock.fill", "Tes contacts ne quittent pas ton iPhone : seule une empreinte chiffrée des numéros est comparée, jamais un nom.")
                point("eye.slash.fill", "Ces noms ne sont visibles que par toi.")
            }
            .padding(.horizontal, 4)
            Spacer(minLength: 0)
            Button { Haptics.tap(); answer(true) } label: {
                Text("Continuer").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .accessibilityIdentifier("contacts-allow")
            Button("Plus tard") { answer(false) }
                .foregroundStyle(.secondary)
                .accessibilityIdentifier("contacts-later")
        }
        .padding(.horizontal, 24)
        .padding(.bottom, 20)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppConfig.background.ignoresSafeArea())
        .tint(Palette.accent)
        .preferredColorScheme(.dark)
    }

    private func point(_ symbol: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: symbol).font(.body.weight(.semibold)).foregroundStyle(Palette.accent).frame(width: 26)
                .accessibilityHidden(true)
            Text(text).font(.subheadline).fixedSize(horizontal: false, vertical: true)
        }
    }
}

// MARK: Réglages › Confidentialité › Noms de mes contacts

struct ContactNamesSettingsView: View {
    @ObservedObject private var contacts = ContactNames.shared
    @State private var picking = false
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        List {
            Section {
                HStack(spacing: 12) {
                    Image(systemName: state.symbol)
                        .font(.system(size: 15, weight: .semibold)).foregroundStyle(.white)
                        .frame(width: 29, height: 29)
                        .background(state.tint, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                        .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(state.title)
                        Text(state.detail).font(.footnote).foregroundStyle(.secondary)
                    }
                }
                .accessibilityElement(children: .combine)
                .accessibilityIdentifier("contacts-state")
                actions
            } footer: {
                Text("Les membres Party qui sont dans tes contacts s'affichent sous le nom de ton répertoire (« Nom · pseudo ») dans les Discussions, les Événements et les fiches. Seule une empreinte chiffrée de chaque numéro est comparée, jamais un nom ; ces noms restent sur cet iPhone et ne sont visibles que par toi.")
            }
            if let error = contacts.error, contacts.access.canRead {
                Section { Label(error, systemImage: "exclamationmark.triangle.fill").foregroundStyle(.orange) }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Noms de mes contacts")
        .navigationBarTitleDisplayMode(.inline)
        .motion(Motion.smooth, value: contacts.access)
        .motion(Motion.smooth, value: contacts.recognized)
        .onChange(of: scenePhase) { phase in if phase == .active { contacts.appBecameActive() } }
        .modifier(LimitedPicker(isPresented: $picking))
    }

    @ViewBuilder private var actions: some View {
        switch contacts.access {
        case .notDetermined:
            Button("Autoriser l'accès aux contacts") { Task { await contacts.requestAccess() } }
                .accessibilityIdentifier("contacts-request")
        case .denied, .restricted:
            Button("Ouvrir les Réglages de l'iPhone") {
                if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
            }
        case .authorized, .limited:
            Button {
                Haptics.tap()
                Task { await contacts.refresh(force: true) }
            } label: {
                HStack {
                    Text("Actualiser maintenant")
                    Spacer()
                    if contacts.syncing { ProgressView() }
                }
            }
            .disabled(contacts.syncing)
            .accessibilityIdentifier("contacts-refresh")
            if contacts.access == .limited {
                Button("Choisir les contacts partagés") { picking = true }
            }
        }
    }

    private var state: (symbol: String, tint: Color, title: String, detail: String) {
        switch contacts.access {
        case .notDetermined:
            return ("person.crop.circle.badge.questionmark", .gray, "Pas encore autorisé", "Party affiche les pseudos.")
        case .denied:
            return ("person.crop.circle.badge.xmark", .red, "Accès refusé", "Autorise Contacts pour Party dans les Réglages de l'iPhone.")
        case .restricted:
            return ("person.crop.circle.badge.xmark", .red, "Accès bloqué", "Les restrictions de cet iPhone empêchent l'accès aux contacts.")
        case .authorized, .limited:
            let count = contacts.recognized
            let who = count == 0 ? "Aucun membre reconnu pour l'instant" : "\(count) membre\(count > 1 ? "s" : "") reconnu\(count > 1 ? "s" : "")"
            let when = contacts.snapshot.syncedAt.map { " · actualisé \($0.formatted(.relative(presentation: .named)))" } ?? ""
            return ("person.crop.circle.badge.checkmark", .green,
                    contacts.access == .limited ? "Accès limité aux contacts choisis" : "Activé", who + when)
        }
    }
}

/// iOS 18, accès limité : la liste d'Apple pour partager d'autres contacts avec Party.
private struct LimitedPicker: ViewModifier {
    @Binding var isPresented: Bool

    func body(content: Content) -> some View {
        if #available(iOS 18, *) {
            content.contactAccessPicker(isPresented: $isPresented) { _ in
                Task { await ContactNames.shared.refresh(force: true) }
            }
        } else {
            content
        }
    }
}

// MARK: Ajouter aux contacts / Voir le contact (fiche d'un membre)

/// Fiche Contacts d'Apple : nouveau contact prérempli (le nom s'ajuste avant d'enregistrer), ou contact existant.
struct ContactCardSheet: UIViewControllerRepresentable {
    enum Mode {
        case new(CNMutableContact)
        case existing(CNContact)
    }

    let mode: Mode
    let done: () -> Void

    static func newContact(phone: String, firstName: String?, lastName: String?, pseudo: String) -> CNMutableContact {
        let contact = CNMutableContact()
        let first = firstName?.trimmingCharacters(in: .whitespaces) ?? ""
        let last = lastName?.trimmingCharacters(in: .whitespaces) ?? ""
        if first.isEmpty && last.isEmpty {
            contact.givenName = pseudo
        } else {
            contact.givenName = first
            contact.familyName = last
            if !pseudo.isEmpty { contact.nickname = pseudo }
        }
        contact.phoneNumbers = [CNLabeledValue(label: CNLabelPhoneNumberMobile, value: CNPhoneNumber(stringValue: phone))]
        return contact
    }

    /// Le contact du répertoire relié à ce membre (accès aux contacts accordé).
    static func existing(_ identifier: String) -> CNContact? {
        try? CNContactStore().unifiedContact(withIdentifier: identifier, keysToFetch: [CNContactViewController.descriptorForRequiredKeys()])
    }

    /// Depuis la page (pont natif) : la fiche par-dessus l'écran du moment ; rend la main à sa fermeture.
    @MainActor
    static func present(_ mode: Mode) async {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        guard var top = scenes.flatMap(\.windows).first(where: \.isKeyWindow)?.rootViewController else { return }
        while let next = top.presentedViewController { top = next }
        await withCheckedContinuation { (done: CheckedContinuation<Void, Never>) in
            var finished = false
            var sheet: UIViewController?
            let finish = {
                guard !finished else { return }
                finished = true
                sheet?.dismiss(animated: true)
                done.resume()
            }
            let host = UIHostingController(rootView: ContactCardSheet(mode: mode, done: finish).ignoresSafeArea())
            host.isModalInPresentation = true  // « Annuler » ou « OK » de la fiche referment ; pas de glissement perdu
            sheet = host
            top.present(host, animated: true)
        }
    }

    func makeCoordinator() -> Coordinator { Coordinator(done: done) }

    func makeUIViewController(context: Context) -> UINavigationController {
        let controller: CNContactViewController
        switch mode {
        case .new(let contact):
            controller = CNContactViewController(forNewContact: contact)
            controller.contactStore = CNContactStore()
        case .existing(let contact):
            controller = CNContactViewController(for: contact)
            controller.allowsEditing = true
            controller.contactStore = CNContactStore()
            controller.navigationItem.leftBarButtonItem = UIBarButtonItem(systemItem: .close, primaryAction: UIAction { _ in done() })
        }
        controller.delegate = context.coordinator
        return UINavigationController(rootViewController: controller)
    }

    func updateUIViewController(_ controller: UINavigationController, context: Context) {}

    final class Coordinator: NSObject, CNContactViewControllerDelegate {
        let done: () -> Void

        init(done: @escaping () -> Void) { self.done = done }

        func contactViewController(_ viewController: CNContactViewController, didCompleteWith contact: CNContact?) {
            done()
            guard contact != nil else { return }
            // Enregistré : nom reconnu aussitôt (demande l'accès d'abord s'il n'a jamais été donné).
            Task { @MainActor in
                let names = ContactNames.shared
                if names.access == .notDetermined { await names.requestAccess() } else { await names.refresh(force: true) }
            }
        }
    }
}
