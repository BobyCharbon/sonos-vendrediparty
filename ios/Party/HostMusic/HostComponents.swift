import CoreImage.CIFilterBuiltins
import SwiftUI

/// Section repliable de « Gérer la soirée » : titre, compteur, chevron ; ouverte ou fermée, retenu d'une fois à l'autre.
struct HostSection<Content: View>: View {
    let title: String
    let symbol: String
    var badge: String?
    let key: String
    @AppStorage private var open: Bool
    @ViewBuilder let content: () -> Content

    init(_ title: String, symbol: String, badge: String? = nil, key: String, openByDefault: Bool = true,
         @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.symbol = symbol
        self.badge = badge
        self.key = key
        _open = AppStorage(wrappedValue: openByDefault, "hostSection." + key)
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Button {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.9)) { open.toggle() }
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: symbol).font(.body.weight(.semibold)).foregroundStyle(Palette.accent).frame(width: 24)
                    Text(title).font(.title3.weight(.bold)).lineLimit(1).minimumScaleFactor(0.8).layoutPriority(1)
                    if let badge {
                        Text(badge).font(.subheadline.weight(.semibold)).foregroundStyle(.secondary).lineLimit(1)
                    }
                    Spacer(minLength: 4)
                    Image(systemName: "chevron.down")
                        .font(.footnote.weight(.bold))
                        .foregroundStyle(.secondary)
                        .rotationEffect(.degrees(open ? 0 : -90))
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityAddTraits(.isHeader)
            .accessibilityValue(open ? "développé" : "réduit")
            if open {
                content().transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .padding(.top, 6)
        .id(key)
    }
}

/// QR code du lien invités (code inclus), dessiné sur l'iPhone.
struct QRCodeView: View {
    let text: String

    var body: some View {
        if let image = Self.image(text) {
            Image(uiImage: image)
                .interpolation(.none)
                .resizable()
                .scaledToFit()
                .padding(10)
                .background(.white, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .accessibilityLabel("QR code vers la page invités, code inclus")
        }
    }

    static func image(_ text: String) -> UIImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage,
              let cg = CIContext().createCGImage(output, from: output.extent) else { return nil }
        return UIImage(cgImage: cg)
    }
}

/// Bouton plein, couleur de la soirée, avec état « en cours ».
struct HostButton: View {
    let title: String
    var symbol: String?
    var role: ButtonRole?
    var busy = false
    let action: () -> Void

    var body: some View {
        Button(role: role, action: action) {
            HStack(spacing: 8) {
                if busy { ProgressView() } else if let symbol { Image(systemName: symbol) }
                Text(title).bold()
            }
            .frame(maxWidth: .infinity, minHeight: 30)
        }
        .buttonStyle(.borderedProminent)
        .tint(role == .destructive ? .red : Palette.accent)
        .disabled(busy)
    }
}

/// Démarrer la soirée : maison (file Sonos) ou extérieur (Spotify), pièce, mode, compte Spotify.
struct HostSetupView: View {
    @ObservedObject var store: HostMusicStore

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                sourceCard("sonos", "🏠 Party maison", "File Sonos de tes enceintes")
                sourceCard("spotify", "🏕️ Party extérieur", "Spotify sur ton téléphone → enceinte Bluetooth")
            }
            if store.chosenSource == "sonos" {
                VStack(alignment: .leading, spacing: 10) {
                    Text("1. Lance une playlist **depuis l'app Sonos** (pas via Spotify Connect / Jam) : la musique joue depuis la file Sonos.\n2. Choisis la même pièce ici et le mode, puis démarre la soirée. Les ajouts des invités entrent dans la file Sonos.")
                        .font(.subheadline).foregroundStyle(.secondary)
                    HStack {
                        Picker("Pièce Sonos", selection: $store.chosenRoom) {
                            if store.rooms.isEmpty { Text(store.roomsError ?? "Recherche des enceintes…").tag("") }
                            ForEach(store.rooms) { Text($0.name).tag($0.uid) }
                        }
                        .pickerStyle(.menu)
                        .tint(.primary)
                        Spacer()
                        Button { Task { await store.loadRooms() } } label: { Image(systemName: "arrow.clockwise") }
                            .accessibilityLabel("Actualiser les pièces")
                    }
                    .card()
                    modePicker
                }
            } else {
                Text("1. Connecte ton téléphone à l'enceinte Bluetooth.\n2. Lance une playlist dans l'app Spotify.\n3. Démarre la soirée : les invités ajoutent directement à ta file Spotify.")
                    .font(.subheadline).foregroundStyle(.secondary)
                SpotifyAccountCard(store: store)
            }
            HostButton(title: "Démarrer la soirée", symbol: "party.popper.fill", busy: store.busy.contains("start")) {
                Task { await store.startParty() }
            }
        }
        .task { if store.rooms.isEmpty { await store.loadRooms() } }
    }

    private var modePicker: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Mode d'insertion").font(.headline)
            Picker("Mode d'insertion", selection: $store.chosenMode) {
                ForEach(InsertMode.allCases) { Text($0.label).tag($0.rawValue) }
            }
            .pickerStyle(.segmented)
            Text(InsertMode(rawValue: store.chosenMode)?.help ?? "").font(.footnote).foregroundStyle(.secondary)
        }
    }

    private func sourceCard(_ source: String, _ title: String, _ hint: String) -> some View {
        let on = store.chosenSource == source
        return Button { withAnimation { store.chosenSource = source } } label: {
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.subheadline.weight(.bold))
                Text(hint).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.leading)
            }
            .frame(maxWidth: .infinity, minHeight: 64, alignment: .topLeading)
            .padding(12)
            .background(on ? Palette.mine : Palette.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(on ? Palette.accent : .clear, lineWidth: 2))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
    }
}

/// Compte Spotify de l'hôte : connecté (nom, Premium) ou bouton de connexion.
struct SpotifyAccountCard: View {
    @ObservedObject var store: HostMusicStore
    @State private var confirmLogout = false

    var body: some View {
        Group {
            if let account = store.state?.spotifyAccount {
                if account.connected {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("🟢 Connecté à Spotify").font(.subheadline.weight(.semibold))
                            Text(account.name ?? "").font(.footnote).foregroundStyle(.secondary)
                            if !account.premium { Text("⚠️ Premium requis").font(.caption.weight(.semibold)).foregroundStyle(.orange) }
                        }
                        Spacer()
                        Button("Déconnecter") { confirmLogout = true }.buttonStyle(.bordered)
                    }
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        Button { store.spotifyLogin() } label: {
                            Label("Se connecter à Spotify", systemImage: "music.note.list").frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent).tint(.green)
                        Text("Une seule fois : Spotify Premium est nécessaire pour piloter la lecture.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
            } else {
                Text("Spotify n'est pas configuré sur le serveur.").font(.subheadline).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .card()
        .confirmationDialog("Déconnecter ton compte Spotify ?", isPresented: $confirmLogout, titleVisibility: .visible) {
            Button("Déconnecter", role: .destructive) { Task { await store.spotifyLogout() } }
        }
    }
}
