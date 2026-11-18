import PhotosUI
import SwiftUI

// Pièces communes de la création et des réglages d'un groupe (et de « Nouveau groupe » à plusieurs) : 16 emojis et
// 6 couleurs (listes fermées, comme la base), photo facultative (galerie ou appareil photo, recadrée en carré).

/// 16 emojis en grille (cibles de 44 pt), celui choisi entouré de rose.
struct GroupEmojiGrid: View {
    @Binding var selection: String

    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 4), count: 8), spacing: 6) {
            ForEach(NewChatGroupView.emojis, id: \.self) { e in
                let on = e == selection
                Button { Haptics.selection(); selection = e } label: {
                    Text(e).font(.system(size: 28))
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(on ? PronoTheme.pink.opacity(0.12) : .clear, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(on ? PronoTheme.pink : .clear, lineWidth: 2))
                }
                .buttonStyle(PronoKitPressStyle())
                .accessibilityLabel(e)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }
}

/// 6 couleurs (pastilles de 44 pt et leur nom).
struct GroupColorRow: View {
    @Binding var selection: String

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            ForEach(NewChatGroupView.colors, id: \.key) { c in
                let on = c.key == selection
                let g = GroupLook.gradient(c.key)
                Button { Haptics.selection(); selection = c.key } label: {
                    VStack(spacing: 6) {
                        Circle().fill(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing))
                            .frame(width: 44, height: 44)
                            .overlay { if on { Image(systemName: "checkmark").font(.body.weight(.black)).foregroundStyle(PeopleNeon.pinkInk) } }
                            .padding(4)
                            .overlay(Circle().strokeBorder(on ? g.to : .clear, lineWidth: 3))
                        Text(c.name).font(.footnote).foregroundStyle(on ? PronoTheme.t1 : PronoTheme.t3)
                    }
                    .frame(maxWidth: .infinity, minHeight: 72)
                }
                .buttonStyle(PronoKitPressStyle())
                .accessibilityLabel(c.name)
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
    }
}

/// Photo du groupe (facultative) : « Choisir une photo » (galerie), « Prendre une photo », « Retirer la photo ».
/// La photo est recadrée en carré (centre) et compressée en JPEG avant l'envoi.
struct GroupPhotoField: View {
    let has: Bool
    var busy = false
    let picked: (Data) -> Void
    var remove: (() -> Void)? = nil

    @State private var item: PhotosPickerItem?
    @State private var camera = false
    @State private var confirmRemove = false
    @State private var problem: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            PeopleSectionLabel(text: "Photo du groupe (facultative)", systemImage: "photo")
            Text("Elle remplace l’emoji et devient la couverture du groupe. Seuls ses membres la voient, et ils peuvent la signaler.")
                .font(.footnote).foregroundStyle(PronoTheme.t2)
            HStack(spacing: 8) {
                PhotosPicker(selection: $item, matching: .images) {
                    Label(has ? "Changer la photo" : "Choisir une photo", systemImage: "photo.on.rectangle")
                        .font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(PronoTheme.s1b, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
                }
                .buttonStyle(.borderless)
                .accessibilityIdentifier("group-photo-pick")
                if UIImagePickerController.isSourceTypeAvailable(.camera) {
                    Button { camera = true } label: {
                        Label("Prendre une photo", systemImage: "camera")
                            .font(.subheadline.weight(.semibold)).foregroundStyle(PronoTheme.t1)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .background(PronoTheme.s1b, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(PronoTheme.line2, lineWidth: 1))
                    }
                    .buttonStyle(PronoKitPressStyle())
                }
            }
            .disabled(busy)
            if has, remove != nil {
                Button(role: .destructive) { confirmRemove = true } label: {
                    Text("Retirer la photo").font(.subheadline.weight(.semibold)).frame(minHeight: 44)
                }
                .buttonStyle(.borderless)
                .disabled(busy)
            }
            if let problem { Text(problem).font(.footnote).foregroundStyle(PronoTheme.pinkInk) }
        }
        .onChange(of: item) { value in
            guard let value else { return }
            Task {
                let data = try? await value.loadTransferable(type: Data.self)
                item = nil
                use(data.flatMap(UIImage.init(data:)))
            }
        }
        .fullScreenCover(isPresented: $camera) {
            GroupCameraPicker { image in camera = false; use(image) }.ignoresSafeArea()
        }
        .confirmationDialog("Retirer la photo du groupe ?", isPresented: $confirmRemove, titleVisibility: .visible) {
            Button("Retirer la photo", role: .destructive) { remove?() }
        }
    }

    private func use(_ image: UIImage?) {
        guard let image else { return }
        guard let jpeg = GroupPhotoCrop.squareJPEG(image) else {
            problem = "La photo n’a pas pu être lue. Choisis-la à nouveau."
            return
        }
        problem = nil
        picked(jpeg)
    }
}

enum GroupPhotoCrop {
    /// Carré du centre, 1024 pt au plus, JPEG (sous les 5 Mo du compartiment group-photos).
    static func squareJPEG(_ image: UIImage, side: CGFloat = 1024) -> Data? {
        let size = image.size
        guard size.width > 0, size.height > 0 else { return nil }
        let edge = min(size.width, size.height)
        let target = min(edge, side)
        let scale = target / edge
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        let out = UIGraphicsImageRenderer(size: CGSize(width: target, height: target), format: format).image { _ in
            image.draw(in: CGRect(x: -(size.width - edge) / 2 * scale, y: -(size.height - edge) / 2 * scale,
                                  width: size.width * scale, height: size.height * scale))
        }
        return out.jpegData(compressionQuality: 0.82)
    }
}

/// Appareil photo (UIImagePickerController) : rend la photo prise, ou nil si l'on annule.
struct GroupCameraPicker: UIViewControllerRepresentable {
    let done: (UIImage?) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ controller: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(done: done) }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let done: (UIImage?) -> Void
        init(done: @escaping (UIImage?) -> Void) { self.done = done }

        func imagePickerController(_ picker: UIImagePickerController, didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]) {
            done(info[.originalImage] as? UIImage)
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) { done(nil) }
    }
}
