import MessageUI
import SwiftUI

/// Un SMS prérempli à envoyer (destinataire et texte) ; l'utilisateur relit et envoie lui-même, un à la fois
/// (pas d'envoi en masse : règle 5.1.1 de l'App Store).
struct MessageDraft: Identifiable, Equatable {
    let id = UUID()
    let recipient: String
    let body: String
    /// Contact invité (« Invité · il y a 2 j ») ; nil pour un simple message à un ami.
    var candidate: InviteCandidate?
}

/// Messages d'Apple (MFMessageComposeViewController) ; sent = true si le message est parti.
struct MessageComposer: UIViewControllerRepresentable {
    let draft: MessageDraft
    let done: (_ sent: Bool) -> Void

    static var available: Bool { MFMessageComposeViewController.canSendText() }

    func makeCoordinator() -> Coordinator { Coordinator(done: done) }

    func makeUIViewController(context: Context) -> MFMessageComposeViewController {
        let controller = MFMessageComposeViewController()
        controller.recipients = [draft.recipient]
        controller.body = draft.body
        controller.messageComposeDelegate = context.coordinator
        return controller
    }

    func updateUIViewController(_ controller: MFMessageComposeViewController, context: Context) {}

    final class Coordinator: NSObject, MFMessageComposeViewControllerDelegate {
        let done: (Bool) -> Void

        init(done: @escaping (Bool) -> Void) { self.done = done }

        func messageComposeViewController(_ controller: MFMessageComposeViewController, didFinishWith result: MessageComposeResult) {
            done(result == .sent)
        }
    }
}

/// Repli sans Messages (iPad sans SIM, simulateur) : la feuille de partage d'iOS avec le même texte.
struct ShareSheet: UIViewControllerRepresentable {
    let text: String
    let done: (_ shared: Bool) -> Void

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let controller = UIActivityViewController(activityItems: [text], applicationActivities: nil)
        controller.completionWithItemsHandler = { _, completed, _, _ in done(completed) }
        return controller
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
