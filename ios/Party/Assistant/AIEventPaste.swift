import CoreTransferable
import SwiftUI
import UIKit
import UniformTypeIdentifiers

/// Images collées ou glissées dans « Créer avec l'IA » (retour du 03.11 : « je ne peux que prendre une photo de ma
/// galerie ») : une capture, une affiche copiée dans Safari ou Messages arrive en pièce jointe, comme une photo.
extension AIEvent {
    /// Les images d'un presse-papiers (une par élément copié : plusieurs images copiées d'un coup = plusieurs pièces).
    static func pastedImages(from pasteboard: UIPasteboard) -> [UIImage] {
        guard pasteboard.hasImages else { return [] }
        let found = pastedImages(fromItems: pasteboard.items)
        return found.isEmpty ? (pasteboard.images ?? []) : found
    }

    /// Chaque élément du presse-papiers ([type: valeur]) donne au plus une image : UIImage telle quelle, ou données
    /// d'image (PNG, JPEG, HEIC…) décodées. Le texte qui l'accompagne (adresse de l'image) est ignoré.
    static func pastedImages(fromItems items: [[String: Any]]) -> [UIImage] {
        items.compactMap { item in
            item.keys.sorted().lazy
                .filter { UTType($0)?.conforms(to: .image) == true }
                .compactMap { key -> UIImage? in
                    if let image = item[key] as? UIImage { return image }
                    if let data = item[key] as? Data { return UIImage(data: data) }
                    return nil
                }
                .first
        }
    }

    /// Trop d'images d'un coup : on garde les premières et on le dit.
    static func overflowNotice(dropped: Int) -> String {
        dropped == 1 ? "\(maxShots) images au plus : 1 image n'a pas été ajoutée."
                     : "\(maxShots) images au plus : \(dropped) images n'ont pas été ajoutées."
    }

    static let fullNotice = "\(maxShots) images au plus : retires-en une pour en ajouter une autre."
    static let unreadableNotice = "Cette image n'a pas pu être lue : essaie une capture d'écran."
    static let editingNotice = "Les images servent à créer un événement : pour le modifier, dis ou écris ce qui change."
}

/// Image reçue par le bouton « Coller » ou un glisser-déposer : n'importe quel format d'image que UIKit sait lire.
struct PastedImage: Transferable {
    let image: UIImage

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(importedContentType: .image) { data in
            guard let image = UIImage(data: data) else { throw CocoaError(.fileReadCorruptFile) }
            return PastedImage(image: image)
        }
    }
}

/// Champ de saisie de l'assistant : texte sur 1 à 4 lignes, et « Coller » (appui long, ⌘V sur iPad) d'une image
/// l'ajoute en pièce jointe au lieu de ne rien faire (un TextField SwiftUI ne sait coller que du texte).
struct AIPromptField: UIViewRepresentable {
    @Binding var text: String
    @Binding var focused: Bool
    let placeholder: String
    let onImages: ([UIImage]) -> Void

    static let maxLines: CGFloat = 4

    func makeUIView(context: Context) -> PasteImageTextView {
        let view = PasteImageTextView()
        view.delegate = context.coordinator
        view.font = .preferredFont(forTextStyle: .body)
        view.adjustsFontForContentSizeCategory = true
        view.backgroundColor = .clear
        view.textColor = .label
        view.tintColor = AppConfig.uiAccent
        view.textContainerInset = .zero
        view.textContainer.lineFragmentPadding = 0
        view.isScrollEnabled = false
        view.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        view.accessibilityIdentifier = "ai-text"
        return view
    }

    func updateUIView(_ view: PasteImageTextView, context: Context) {
        context.coordinator.parent = self
        view.onImages = onImages
        view.placeholder = placeholder
        if view.text != text { view.text = text; view.refreshPlaceholder() }
        if focused && !view.isFirstResponder {
            DispatchQueue.main.async { view.becomeFirstResponder() }
        } else if !focused && view.isFirstResponder {
            DispatchQueue.main.async { view.resignFirstResponder() }
        }
    }

    func sizeThatFits(_ proposal: ProposedViewSize, uiView view: PasteImageTextView, context: Context) -> CGSize? {
        let width = proposal.width ?? 240
        let lineHeight = view.font?.lineHeight ?? 22
        let fitting = view.sizeThatFits(CGSize(width: width, height: .greatestFiniteMagnitude)).height
        let tallest = ceil(lineHeight * Self.maxLines)
        let scrolls = fitting > tallest
        if view.isScrollEnabled != scrolls { DispatchQueue.main.async { view.isScrollEnabled = scrolls } }
        return CGSize(width: width, height: max(ceil(lineHeight), min(fitting, tallest)))
    }

    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }

    final class Coordinator: NSObject, UITextViewDelegate {
        var parent: AIPromptField

        init(parent: AIPromptField) { self.parent = parent }

        func textViewDidChange(_ view: UITextView) {
            parent.text = view.text
            (view as? PasteImageTextView)?.refreshPlaceholder()
        }

        func textViewDidBeginEditing(_ view: UITextView) { if !parent.focused { parent.focused = true } }
        func textViewDidEndEditing(_ view: UITextView) { if parent.focused { parent.focused = false } }
    }
}

/// UITextView qui accepte « Coller » quand le presse-papiers contient une image, et la remet à l'assistant.
final class PasteImageTextView: UITextView {
    var onImages: (([UIImage]) -> Void)?
    /// Presse-papiers lu par « Coller » (un presse-papiers privé dans les tests).
    var pasteboard: UIPasteboard = .general
    private let placeholderLabel = UILabel()

    var placeholder = "" {
        didSet { placeholderLabel.text = placeholder }
    }

    override init(frame: CGRect, textContainer: NSTextContainer?) {
        super.init(frame: frame, textContainer: textContainer)
        placeholderLabel.font = .preferredFont(forTextStyle: .body)
        placeholderLabel.adjustsFontForContentSizeCategory = true
        placeholderLabel.textColor = .placeholderText
        placeholderLabel.translatesAutoresizingMaskIntoConstraints = false
        placeholderLabel.isAccessibilityElement = false
        addSubview(placeholderLabel)
        NSLayoutConstraint.activate([
            placeholderLabel.leadingAnchor.constraint(equalTo: leadingAnchor),
            placeholderLabel.topAnchor.constraint(equalTo: topAnchor),
            placeholderLabel.widthAnchor.constraint(lessThanOrEqualTo: widthAnchor),
        ])
    }

    required init?(coder: NSCoder) { fatalError("init(coder:) n'est pas utilisé") }

    func refreshPlaceholder() {
        placeholderLabel.isHidden = !text.isEmpty
        accessibilityLabel = text.isEmpty ? placeholder : nil
    }

    override var text: String! {
        didSet { refreshPlaceholder() }
    }

    override func canPerformAction(_ action: Selector, withSender sender: Any?) -> Bool {
        if action == #selector(paste(_:)) && pasteboard.hasImages && onImages != nil { return true }
        return super.canPerformAction(action, withSender: sender)
    }

    override func paste(_ sender: Any?) {
        let images = AIEvent.pastedImages(from: pasteboard)
        guard !images.isEmpty, let onImages else { return super.paste(sender) }
        onImages(images)
    }
}
