import UIKit

/// Photo de profil prête à envoyer : carrée, 1024 px au plus, JPEG (~200 Ko), comme le recadrage du module
/// Événements (web/events/src/lib/photos.ts). Le serveur refuse au-delà de 5 Mo.
enum ProfilePhoto {
    static let side: CGFloat = 1024
    static let quality: CGFloat = 0.8

    /// zoom ≥ 1 : recadrage plus serré ; offset : décalage du centre, en fraction de la marge disponible (-1…1).
    static func jpeg(from image: UIImage, zoom: CGFloat = 1, offset: CGPoint = .zero) -> Data? {
        let crop = square(of: image.size, zoom: zoom, offset: offset)
        let target = min(side, crop.width)
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let rendered = UIGraphicsImageRenderer(size: CGSize(width: target, height: target), format: format).image { _ in
            // L'image est dessinée entière, décalée et agrandie pour que le carré choisi remplisse la cible.
            let scale = target / crop.width
            image.draw(in: CGRect(x: -crop.minX * scale, y: -crop.minY * scale,
                                  width: image.size.width * scale, height: image.size.height * scale))
        }
        return rendered.jpegData(compressionQuality: quality)
    }

    /// Carré découpé dans l'image (coordonnées en points de l'image, orientation déjà appliquée).
    static func square(of size: CGSize, zoom: CGFloat = 1, offset: CGPoint = .zero) -> CGRect {
        let edge = min(size.width, size.height) / max(zoom, 1)
        let spareX = (size.width - edge) / 2
        let spareY = (size.height - edge) / 2
        let dx = max(-1, min(1, offset.x)) * spareX
        let dy = max(-1, min(1, offset.y)) * spareY
        return CGRect(x: spareX + dx, y: spareY + dy, width: edge, height: edge)
    }
}
