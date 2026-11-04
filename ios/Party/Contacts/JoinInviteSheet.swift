import SwiftUI

/// Lien /events/join/<lien> ouvert dans l'app : « Ludo t'invite sur Party ». Connecté (profil complet), le lien est
/// réclamé aussitôt ; sinon il est gardé et réclamé après la connexion (SettingsView). Le lien ne donne aucun droit.
struct JoinInviteSheet: View {
    @ObservedObject var store: FriendsStore
    let invite: String
    let signedIn: Bool
    @State private var preview: AppInvitePreview?
    @State private var loaded = false
    @State private var outcome: String?
    @State private var failed = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 18) {
            Spacer(minLength: 12)
            if !loaded {
                ProgressView()
            } else if let preview {
                Text(preview.inviter.first.map(String.init) ?? "🎉")
                    .font(.system(size: 40, weight: .bold)).foregroundStyle(.white)
                    .frame(width: 96, height: 96)
                    .background(Palette.accent.gradient, in: Circle())
                    .accessibilityHidden(true)
                Text("\(preview.inviter.isEmpty ? "Un ami" : preview.inviter) t'invite sur Party")
                    .font(.title2.weight(.bold)).multilineTextAlignment(.center)
                Text(outcome ?? (signedIn ? "Un instant…" : "Connecte-toi avec ton numéro dans Réglages pour rejoindre tes amis."))
                    .font(.subheadline).foregroundStyle(failed ? AnyShapeStyle(.orange) : AnyShapeStyle(.secondary)).multilineTextAlignment(.center)
            } else {
                Text("Lien indisponible").font(.title2.weight(.bold))
                Text("Ce lien d'invitation n'est plus valable : demande le nouveau lien à la personne qui t'a invité.")
                    .font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            Spacer(minLength: 0)
            Button { dismiss() } label: {
                Text(signedIn || preview == nil ? "OK" : "Se connecter").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(AppConfig.background.ignoresSafeArea())
        .tint(Palette.accent)
        .task {
            preview = await store.preview(invite)
            loaded = true
            if preview == nil { store.forgetInvite(); return }
            guard signedIn else { return }
            switch await store.claim(invite) {
            case .success(let result):
                Haptics.success()
                outcome = result.new ? "Bienvenue sur Party ! Ton compte est prêt." : "Bienvenue sur Party !"
            case .failure(let error):
                failed = true
                outcome = (error as? LocalizedError)?.errorDescription ?? "L'invitation n'a pas pu être enregistrée."
            }
        }
    }
}
