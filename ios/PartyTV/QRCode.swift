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

/// Carte à jouer (« QD », « 10H », « TS ») ; « ?? » = carte cachée, montrée de dos.
struct PlayingCard: View {
    let code: String
    var width: CGFloat = 86

    private var hidden: Bool { code.isEmpty || code.contains("?") }
    private var suit: Character { code.last ?? "?" }
    private var rank: String {
        let r = String(code.dropLast())
        return r == "T" ? "10" : r
    }
    private var sign: String { ["S": "♠", "H": "♥", "D": "♦", "C": "♣"][String(suit)] ?? "" }
    private var red: Bool { suit == "H" || suit == "D" }

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: width * 0.12)
                .fill(hidden ? AnyShapeStyle(LinearGradient(colors: [TV.accent, TV.lavender], startPoint: .topLeading, endPoint: .bottomTrailing))
                             : AnyShapeStyle(Color.white))
            if hidden {
                Text("🎉").font(.system(size: width * 0.4))
            } else {
                VStack(spacing: 0) {
                    Text(rank).font(.system(size: width * 0.38, weight: .heavy))
                    Text(sign).font(.system(size: width * 0.34))
                }
                .foregroundStyle(red ? Color(red: 0.85, green: 0.1, blue: 0.2) : .black)
            }
        }
        .frame(width: width, height: width * 1.4)
        .shadow(color: .black.opacity(0.35), radius: 6, y: 4)
        .accessibilityLabel(hidden ? "Carte cachée" : "\(rank) \(sign)")
    }
}

struct CardRow: View {
    let cards: [JSON]
    var width: CGFloat = 86
    var body: some View {
        HStack(spacing: -width * 0.25) {
            ForEach(Array(cards.enumerated()), id: \.offset) { _, c in PlayingCard(code: c.string ?? "??", width: width) }
        }
    }
}
