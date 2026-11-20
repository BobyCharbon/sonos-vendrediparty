import SwiftUI

/// Photo de profil en grand (avis 163be6ce5df6, 20.11) : toucher la photo d'un profil l'ouvre en plein écran, dans sa
/// qualité réelle (le fichier enregistré, 1024 px, jamais une miniature). Pincer ou toucher deux fois pour zoomer,
/// glisser vers le bas ou ✕ pour fermer.
struct ProfilePhotoViewer: View {
    let url: URL
    let name: String
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var scale: CGFloat = 1
    @State private var lastScale: CGFloat = 1
    @State private var pan: CGSize = .zero
    @State private var lastPan: CGSize = .zero
    @State private var drag: CGSize = .zero

    var body: some View {
        ZStack {
            Color.black.opacity(1 - min(0.6, abs(drag.height) / 600)).ignoresSafeArea()
            AsyncImage(url: url, transaction: Transaction(animation: .easeOut(duration: 0.2))) { phase in
                switch phase {
                case .success(let image): image.resizable().scaledToFit()
                case .failure: Label("La photo n'a pas pu s'afficher.", systemImage: "photo").foregroundStyle(.white.opacity(0.8))
                default: ProgressView().tint(.white)
                }
            }
            .scaleEffect(scale)
            .offset(scale > 1 ? pan : drag)
            .gesture(MagnificationGesture()
                .onChanged { scale = max(1, min(5, lastScale * $0)) }
                .onEnded { _ in
                    lastScale = scale
                    Motion.animate { drag = .zero }
                    if scale <= 1 { Motion.animate(Motion.snappy) { pan = .zero; lastPan = .zero } }
                })
            .simultaneousGesture(DragGesture()
                .onChanged { value in
                    if scale > 1 {
                        drag = .zero  // un pincement commence à 1 : jamais de reste du glissé (✕ caché, photo décalée)
                        pan = CGSize(width: lastPan.width + value.translation.width, height: lastPan.height + value.translation.height)
                    } else {
                        drag = value.translation
                    }
                }
                .onEnded { value in
                    if scale > 1 { lastPan = pan; drag = .zero; return }
                    if abs(value.translation.height) > 120 { dismiss() } else { Motion.animate { drag = .zero } }
                })
            .onTapGesture(count: 2) {
                Motion.animate(Motion.snappy) {
                    scale = scale > 1 ? 1 : 2.5
                    lastScale = scale
                    pan = .zero
                    lastPan = .zero
                }
            }
            .accessibilityLabel("Photo de profil de \(name)")
            .accessibilityAddTraits(.isImage)
            .accessibilityIdentifier("profile-photo-full")
        }
        .overlay(alignment: .topLeading) {
            Button { dismiss() } label: {
                Image(systemName: "xmark").font(.headline).frame(width: 44, height: 44).background(.ultraThinMaterial, in: Circle())
            }
            .foregroundStyle(.white)
            .padding(.horizontal, 16).padding(.top, 8)
            .opacity(drag == .zero ? 1 : 0)
            .accessibilityLabel("Fermer")
            .accessibilityIdentifier("profile-photo-close")
        }
        .animation(reduceMotion ? nil : Motion.snappy, value: drag == .zero)
        .preferredColorScheme(.dark)
    }
}

extension View {
    /// La photo devient un bouton qui l'ouvre en grand ; sans photo, rien ne change.
    func opensProfilePhoto(_ photo: String?, name: String) -> some View {
        modifier(OpensProfilePhoto(url: photo.flatMap(URL.init(string:)), name: name))
    }
}

private struct OpensProfilePhoto: ViewModifier {
    let url: URL?
    let name: String
    @State private var showing = false

    func body(content: Content) -> some View {
        if let url {
            Button {
                Haptics.tap()
                showing = true
            } label: { content }
            .buttonStyle(.plain)
            .accessibilityLabel("Voir la photo de \(name) en grand")
            .accessibilityIdentifier("profile-photo-open")
            .fullScreenCover(isPresented: $showing) { ProfilePhotoViewer(url: url, name: name) }
        } else {
            content
        }
    }
}
