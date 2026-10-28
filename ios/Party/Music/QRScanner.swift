import SwiftUI
import VisionKit

/// Scanner de QR code d'Apple (VisionKit, comme l'app Appareil photo) : rend le premier QR code lu.
struct QRScanner: UIViewControllerRepresentable {
    let found: (String) -> Void

    /// Caméra présente et autorisée (faux sur le simulateur et sur les appareils trop anciens).
    @MainActor static var isAvailable: Bool {
        DataScannerViewController.isSupported && DataScannerViewController.isAvailable
    }

    func makeCoordinator() -> Coordinator { Coordinator(found: found) }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(recognizedDataTypes: [.barcode(symbologies: [.qr])],
                                                qualityLevel: .balanced, isHighlightingEnabled: true)
        scanner.delegate = context.coordinator
        try? scanner.startScanning()
        return scanner
    }

    func updateUIViewController(_ scanner: DataScannerViewController, context: Context) {}

    static func dismantleUIViewController(_ scanner: DataScannerViewController, coordinator: Coordinator) {
        scanner.stopScanning()
    }

    @MainActor
    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        private let found: (String) -> Void
        private var done = false

        init(found: @escaping (String) -> Void) {
            self.found = found
        }

        func dataScanner(_ scanner: DataScannerViewController, didAdd items: [RecognizedItem], allItems: [RecognizedItem]) {
            guard !done else { return }
            for case .barcode(let code) in items {
                guard let text = code.payloadStringValue else { continue }
                done = true
                UINotificationFeedbackGenerator().notificationOccurred(.success)
                found(text)
                return
            }
        }
    }
}

/// Feuille « Scanner le QR de l'hôte ».
struct QRScannerSheet: View {
    let found: (String) -> Void
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if QRScanner.isAvailable {
                    QRScanner { text in
                        dismiss()
                        found(text)
                    }
                    .ignoresSafeArea()
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "camera.fill").font(.largeTitle).foregroundStyle(.secondary)
                        Text("Caméra indisponible : autorise-la pour Party ! dans Réglages, ou entre le code à la main.")
                            .multilineTextAlignment(.center).foregroundStyle(.secondary)
                    }
                    .padding(32)
                }
            }
            .navigationTitle("QR de l'hôte")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Fermer") { dismiss() } } }
        }
        .preferredColorScheme(.dark)
    }
}
