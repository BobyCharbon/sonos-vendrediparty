import SwiftUI

/// Code et QR des invités, invités connectés (avec leurs actions), nouveau code, événement lié.
struct HostAccessSection: View {
    @ObservedObject var store: HostMusicStore
    let state: AdminState
    @State private var customPin = ""
    @State private var confirmRandom = false
    @State private var confirmCustom = false
    @FocusState private var pinFocused: Bool

    var body: some View {
        HostSection("Code et QR des invités", symbol: "qrcode", badge: badge, key: "access", openByDefault: false) {
            VStack(spacing: 14) {
                Text(state.guestPin.isEmpty ? "····" : state.guestPin)
                    .font(.system(size: 54, weight: .heavy, design: .rounded).monospacedDigit())
                    .tracking(8)
                    .accessibilityLabel("Code \(state.guestPin.map(String.init).joined(separator: " "))")
                QRCodeView(text: "\(state.guestURL)?pin=\(state.guestPin)").frame(width: 190, height: 190)
                Text("\(state.guestURL)?pin=\(state.guestPin)").font(.footnote).foregroundStyle(.secondary).textSelection(.enabled)
                Button { confirmRandom = true } label: {
                    Label("Nouveau code au hasard", systemImage: "dice").frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                HStack(spacing: 10) {
                    TextField("Choisir un code (4 chiffres)", text: $customPin)
                        .keyboardType(.numberPad).multilineTextAlignment(.center).focused($pinFocused)
                        .padding(9)
                        .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                        .onChange(of: customPin) { new in customPin = String(new.filter(\.isNumber).prefix(4)) }
                    Button("Utiliser") { confirmCustom = true }.buttonStyle(.bordered).disabled(!GuestPin.isValid(customPin))
                }
                Text("Un nouveau code déconnecte tous les invités : ils devront saisir le nouveau ou rescanner le QR.")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                eventPicker
                guestsList
            }
            .card()
        }
        .confirmationDialog("Changer le code au hasard ?", isPresented: $confirmRandom, titleVisibility: .visible) {
            Button("Nouveau code") { Task { await store.newPin() } }
        } message: { Text("Tous les invités devront saisir le nouveau ou rescanner le QR.") }
        .confirmationDialog("Utiliser le code \(customPin) ?", isPresented: $confirmCustom, titleVisibility: .visible) {
            Button("Utiliser ce code") {
                pinFocused = false
                Task { await store.newPin(customPin); customPin = "" }
            }
        } message: { Text("Tous les invités devront le saisir (ou rescanner le QR).") }
    }

    private var badge: String {
        let online = state.onlineGuests.count
        return state.guestPin + (online > 0 ? " · 👥 \(online)" : "")
    }

    private var eventPicker: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("🎉 Événement de la soirée").font(.subheadline.weight(.semibold))
            Menu {
                Button("Aucun : le code seulement") { Task { await store.linkEvent(nil) } }
                ForEach(store.eventOptions) { option in
                    Button("\(option.title) · \(Self.day(option.startsAt))") { Task { await store.linkEvent(option) } }
                }
            } label: {
                HStack {
                    Text(state.event?.title ?? "Aucun : le code seulement").lineLimit(1)
                    Spacer()
                    Image(systemName: "chevron.up.chevron.down").font(.footnote)
                }
                .padding(10).background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
            }
            .tint(.primary)
            Text(state.event.map { "Les personnes notées « Présent » à « \($0.title) » entrent sans code. Les autres utilisent le code." }
                 ?? "Lie l'événement de ce soir : ses invités notés « Présent » entreront sans code.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .task { await store.loadEventOptions() }
    }

    @ViewBuilder
    private var guestsList: some View {
        let online = state.onlineGuests
        VStack(alignment: .leading, spacing: 8) {
            Text(online.isEmpty ? "Aucun invité connecté pour l'instant" : "\(online.count) connecté\(online.count > 1 ? "s" : "")")
                .font(.subheadline.weight(.semibold))
            ForEach(online) { guest in GuestRow(store: store, guest: guest, usesSpotify: state.usesSpotify) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    static func day(_ iso: String) -> String {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = parser.date(from: iso) ?? ISO8601DateFormatter().date(from: iso)
        return date?.formatted(.dateTime.weekday(.abbreviated).day().month(.abbreviated)) ?? ""
    }
}

/// Un invité et ce que l'hôte peut faire : renommer, déconnecter, bloquer 10 min, bannir, retirer ses titres.
struct GuestRow: View {
    @ObservedObject var store: HostMusicStore
    let guest: AdminState.Guest
    let usesSpotify: Bool
    @State private var renaming = false
    @State private var newName = ""
    @State private var confirmBan = false

    var body: some View {
        HStack(spacing: 10) {
            Circle().fill(guest.isOnline() ? .green : .gray).frame(width: 8, height: 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(guest.name + (guest.via.contains("music") ? " 🎵" : "") + (guest.via.contains("games") ? " 🎮" : ""))
                    .font(.subheadline.weight(.semibold))
                Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
            }
            Spacer()
            if store.busy.contains("g.\(guest.id)") { ProgressView() }
            Menu {
                if guest.ban != nil {
                    Button { act("unban") } label: { Label("Débloquer", systemImage: "lock.open") }
                } else {
                    Button { newName = guest.name; renaming = true } label: { Label("Renommer", systemImage: "pencil") }
                    Button { act("kick") } label: { Label("Déconnecter (redemande le code)", systemImage: "eject") }
                    Button { act("ban", minutes: 10) } label: { Label("Bloquer 10 minutes", systemImage: "pause.circle") }
                    Button(role: .destructive) { confirmBan = true } label: { Label("Bannir", systemImage: "nosign") }
                }
                if guest.queued > 0 && !usesSpotify {
                    Button(role: .destructive) { act("purge") } label: { Label("Retirer ses titres en attente", systemImage: "trash") }
                }
            } label: {
                Image(systemName: "ellipsis.circle").font(.title3).frame(width: 36, height: 36)
            }
            .accessibilityLabel("Actions pour \(guest.name)")
        }
        .padding(10)
        .background(Color.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 12))
        .alert("Renommer \(guest.name)", isPresented: $renaming) {
            TextField("Nouveau prénom", text: $newName)
            Button("Annuler", role: .cancel) {}
            Button("Renommer") {
                let name = newName.trimmingCharacters(in: .whitespaces)
                if !name.isEmpty && name != guest.name { act("rename", name: name) }
            }
        }
        .confirmationDialog("Bannir \(guest.name) ?", isPresented: $confirmBan, titleVisibility: .visible) {
            Button("Bannir", role: .destructive) { act("ban") }
        } message: { Text("Il ne pourra plus ajouter de titres ni rejoindre les jeux.") }
    }

    private var detail: String {
        let joined = Date(timeIntervalSince1970: guest.joinedAt).formatted(date: .omitted, time: .shortened)
        var parts = ["arrivé à \(joined)"]
        if guest.via.contains("music") {
            parts.append("\(guest.total) titre\(guest.total > 1 ? "s" : "")")
            parts.append("\(guest.queued) " + (usesSpotify ? "envoi(s) Spotify" : "en attente"))
        }
        if let ban = guest.ban {
            parts.append(ban.until == 0 ? "⛔ banni" : "⏸ bloqué jusqu'à \(Date(timeIntervalSince1970: ban.until).formatted(date: .omitted, time: .shortened))")
        }
        return parts.joined(separator: " · ")
    }

    private func act(_ action: String, name: String? = nil, minutes: Int? = nil) {
        Task { await store.guestAction(guest, action, name: name, minutes: minutes) }
    }
}

/// Ajouter un titre : recherche (ou lien collé), puis « Jouer ensuite » ou « À la suite des demandes ».
struct HostAddSection: View {
    @ObservedObject var store: HostMusicStore
    let state: AdminState
    @FocusState private var searching: Bool

    var body: some View {
        HostSection("Ajouter un titre", symbol: "plus.magnifyingglass", key: "add") {
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "magnifyingglass").foregroundStyle(.secondary)
                    TextField("Titre, artiste… ou colle un lien", text: $store.query)
                        .focused($searching).submitLabel(.search).autocorrectionDisabled()
                    if store.searching { ProgressView() }
                    if !store.query.isEmpty {
                        Button { store.query = "" } label: { Image(systemName: "xmark.circle.fill").foregroundStyle(.secondary) }
                            .accessibilityLabel("Effacer")
                    }
                }
                .card()
                ForEach(store.results) { track in result(track) }
                if !store.searching && store.query.count >= 2 && store.results.isEmpty {
                    Text("Aucun résultat").font(.subheadline).foregroundStyle(.secondary)
                }
            }
        }
        .confirmationDialog(store.duplicate?.message ?? "", isPresented: Binding(get: { store.duplicate != nil },
                                                                              set: { if !$0 { store.duplicate = nil } }),
                            titleVisibility: .visible) {
            Button("Ajouter quand même") {
                if let dup = store.duplicate { Task { await store.add(dup.track, place: dup.place, force: true) } }
                store.duplicate = nil
            }
        }
    }

    private func result(_ track: HostSearchTrack) -> some View {
        HStack(spacing: 10) {
            HostArtwork(path: track.image, load: store.artwork)
            VStack(alignment: .leading, spacing: 2) {
                Text(track.title).font(.subheadline.weight(.semibold)).lineLimit(1)
                Text(track.artist + (track.explicit ? " · 🅴" : "") + (track.via.map { " · 🔗 \($0)" } ?? ""))
                    .font(.caption).foregroundStyle(.secondary).lineLimit(1)
            }
            Spacer()
            if store.busy.contains("add.\(track.id)") {
                ProgressView()
            } else {
                if !state.usesSpotify {
                    Button { add(track, "next") } label: { Image(systemName: "text.line.first.and.arrowtriangle.forward") }
                        .buttonStyle(.bordered).accessibilityLabel("Jouer ensuite")
                }
                Button { add(track, "end") } label: { Image(systemName: "plus") }
                    .buttonStyle(.borderedProminent).tint(Palette.accent)
                    .accessibilityLabel(state.usesSpotify ? "Ajouter à Spotify" : "À la suite des demandes")
            }
        }
        .card()
    }

    private func add(_ track: HostSearchTrack, _ place: String) {
        searching = false
        Task { await store.add(track, place: place) }
    }
}

/// Mode d'insertion des demandes (soirée maison seulement).
struct HostModeSection: View {
    @ObservedObject var store: HostMusicStore
    let state: AdminState

    var body: some View {
        HostSection("Mode d'insertion", symbol: "arrow.triangle.branch", badge: InsertMode(rawValue: state.mode)?.label,
                    key: "mode", openByDefault: false) {
            VStack(alignment: .leading, spacing: 8) {
                Picker("Mode d'insertion", selection: Binding(get: { state.mode }, set: { new in
                    if let mode = InsertMode(rawValue: new) { Task { await store.setMode(mode) } }
                })) {
                    ForEach(InsertMode.allCases) { Text($0.label).tag($0.rawValue) }
                }
                .pickerStyle(.segmented)
                .disabled(store.busy.contains("mode"))
                Text(InsertMode(rawValue: state.mode)?.help ?? "").font(.footnote).foregroundStyle(.secondary)
            }
            .card()
        }
    }
}
