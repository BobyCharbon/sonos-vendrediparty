import CoreImage.CIFilterBuiltins
import SwiftUI

/// QR code pour rejoindre la partie depuis un téléphone (ouvre Party sur la partie, comme le QR de l'hôte).
struct QRCodeView: View {
    let url: URL
    var size: CGFloat = 220

    var body: some View {
        if let image = Self.image(url.absoluteString) {
            Image(uiImage: image).interpolation(.none).resizable().scaledToFit()
                .frame(width: size, height: size)
                .padding(size * 0.06)
                .background(.white, in: RoundedRectangle(cornerRadius: size * 0.08))
                .accessibilityLabel("QR code pour rejoindre la partie")
        }
    }

    static func image(_ text: String) -> UIImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 12, y: 12)),
              let cg = CIContext().createCGImage(output, from: output.extent) else { return nil }
        return UIImage(cgImage: cg)
    }
}
