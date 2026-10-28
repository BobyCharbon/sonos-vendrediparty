import PhotosUI
import SwiftUI

/// Réglages › Mon profil : photo, prénom et nom (privés), surnom (public). Mêmes règles que le module Événements :
/// tout est obligatoire, le surnom tient en 40 caractères.
struct ProfileView: View {
    @ObservedObject var store: SettingsStore

    @State private var first = ""
    @State private var last = ""
    @State private var nickname = ""
    @State private var picked: PhotosPickerItem?
    @State private var newPhoto: UIImage?
    @State private var newPhotoData: Data?
    @State private var photoError: String?
    @State private var filled = false
    @FocusState private var focused: Bool

    var body: some View {
        Form {
            photoSection
            Section {
                TextField("Prénom", text: $first).textContentType(.givenName)
                TextField("Nom", text: $last).textContentType(.familyName)
            } header: {
                Text("Identité")
            } footer: {
                Text("🔒 Ton prénom et ton nom ne sont visibles que par toi et les admins.")
            }
            Section {
                TextField("Surnom", text: $nickname)
                    .onChange(of: nickname) { new in
                        if new.count > ProfileRules.nicknameLength { nickname = String(new.prefix(ProfileRules.nicknameLength)) }
                    }
            } header: {
                Text("Surnom")
            } footer: {
                Text("👀 Ce que tout le monde voit : jeux, événements, discussions. \(nickname.count) / \(ProfileRules.nicknameLength)")
            }
            if let profile = store.profile {
                Section("Compte") {
                    LabeledContent("Statut", value: profile.roleLabel)
                    if let phone = profile.phone, !phone.isEmpty {
                        LabeledContent("Numéro de connexion", value: "+" + phone.trimmingCharacters(in: CharacterSet(charactersIn: "+")))
                    }
                }
            }
        }
        .focused($focused)
        .textInputAutocapitalization(.words)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Mon profil")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if store.savingProfile {
                    ProgressView()
                } else {
                    Button("Enregistrer") { save() }.bold().disabled(!canSave)
                }
            }
        }
        .overlay {
            if store.profile == nil {
                if let error = store.profileError {
                    VStack(spacing: 12) {
                        Text(error).multilineTextAlignment(.center).foregroundStyle(.secondary)
                        Button("Réessayer") { Task { await store.loadProfile() } }
                    }
                    .padding()
                } else {
                    ProgressView()
                }
            }
        }
        .overlay(alignment: .bottom) { SettingsNoticeBanner(store: store) }
        .task {
            await store.loadProfile()
            fill()
        }
        .onChange(of: picked) { item in Task { await load(item) } }
    }

    // MARK: Photo

    private var photoSection: some View {
        Section {
            VStack(spacing: 12) {
                photoPreview
                PhotosPicker(selection: $picked, matching: .images) {
                    Label(hasPhoto ? "Changer de photo" : "Choisir une photo", systemImage: "photo.on.rectangle")
                }
                .buttonStyle(.bordered)
                if let photoError { Text(photoError).font(.footnote).foregroundStyle(.red) }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 6)
        } footer: {
            Text("Obligatoire : pour que le groupe te reconnaisse, dans les jeux comme dans les événements. La photo est recadrée en carré.")
        }
    }

    @ViewBuilder
    private var photoPreview: some View {
        Group {
            if let newPhoto {
                Image(uiImage: newPhoto).resizable().scaledToFill()
            } else {
                AsyncImage(url: store.profile?.photo.flatMap(URL.init(string:))) { image in
                    image.resizable().scaledToFill()
                } placeholder: {
                    Image(systemName: "person.crop.circle.fill").resizable().foregroundStyle(.secondary)
                }
            }
        }
        .frame(width: 110, height: 110)
        .clipShape(Circle())
        .accessibilityLabel(newPhoto == nil ? "Ta photo de profil" : "Aperçu de ta nouvelle photo")
    }

    private func load(_ item: PhotosPickerItem?) async {
        guard let item else { return }
        photoError = nil
        guard let data = try? await item.loadTransferable(type: Data.self), let image = UIImage(data: data),
              let jpeg = ProfilePhoto.jpeg(from: image), let square = UIImage(data: jpeg) else {
            photoError = "Cette photo n'a pas pu être lue. Choisis-en une autre."
            return
        }
        newPhoto = square
        newPhotoData = jpeg
    }

    // MARK: Enregistrement

    private var hasPhoto: Bool { newPhotoData != nil || store.profile?.photo != nil }

    private var changed: Bool {
        guard let p = store.profile else { return false }
        return newPhotoData != nil || ProfileRules.clean(first) != p.firstName || ProfileRules.clean(last) != p.lastName
            || ProfileRules.clean(nickname) != p.displayName
    }

    private var canSave: Bool {
        changed && ProfileRules.isComplete(first: first, last: last, nickname: nickname, hasPhoto: hasPhoto)
    }

    private func fill() {
        guard !filled, let p = store.profile else { return }
        filled = true
        first = p.firstName
        last = p.lastName
        nickname = p.displayName
    }

    private func save() {
        focused = false
        Task {
            if await store.saveProfile(first: first, last: last, nickname: nickname, photo: newPhotoData) {
                newPhotoData = nil
                newPhoto = nil
                filled = false
                fill()
            }
        }
    }
}
