import AVFoundation
import SwiftUI
import UIKit

/// Capteur de l'appareil photo des Souvenirs (AVFoundation) : jamais la Photothèque, jamais d'aperçu de la photo prise.
/// Dans le simulateur (pas de caméra), la recette passe PARTY_E2E_SOUVENIR_CAMERA=1 : une image de test remplace le
/// capteur. Ce crochet n'existe que dans les builds DEBUG ou E2E_HOOKS (jamais dans la version de l'App Store).
@MainActor
final class SouvenirCameraSensor: NSObject, ObservableObject {
    enum State: Equatable { case starting, ready, denied, unavailable }

    @Published private(set) var state = State.starting
    @Published private(set) var front = false
    @Published var flash = false

    let session = AVCaptureSession()
    private let output = AVCapturePhotoOutput()
    private var input: AVCaptureDeviceInput?
    private var pending: CheckedContinuation<Data?, Never>?
    private let queue = DispatchQueue(label: "party.souvenirs.camera")

    /// Image de test au lieu du capteur (recette simulateur).
    var fake: Bool {
        #if DEBUG || E2E_HOOKS
        return ProcessInfo.processInfo.environment["PARTY_E2E_SOUVENIR_CAMERA"] == "1"
        #else
        return false
        #endif
    }

    func start() async {
        if fake { state = .ready; return }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: break
        case .notDetermined:
            guard await AVCaptureDevice.requestAccess(for: .video) else { state = .denied; return }
        default:
            state = .denied
            return
        }
        guard configure(front: false) else { state = .unavailable; return }
        let session = session
        await withCheckedContinuation { done in queue.async { session.startRunning(); done.resume() } }
        state = .ready
    }

    func stop() {
        let session = session
        queue.async { if session.isRunning { session.stopRunning() } }
    }

    func flip() {
        if fake { front.toggle(); return }
        if configure(front: !front) { Haptics.tap() }
    }

    @discardableResult
    private func configure(front wantFront: Bool) -> Bool {
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: wantFront ? .front : .back),
              let newInput = try? AVCaptureDeviceInput(device: device) else { return false }
        session.beginConfiguration()
        defer { session.commitConfiguration() }
        session.sessionPreset = .photo
        if let input { session.removeInput(input) }
        guard session.canAddInput(newInput) else {
            if let input { session.addInput(input) }
            return false
        }
        session.addInput(newInput)
        input = newInput
        if !session.outputs.contains(output), session.canAddOutput(output) { session.addOutput(output) }
        // Pleine résolution et qualité maximale : l'original est gardé 7 jours par le serveur (décision du 24.11).
        output.maxPhotoQualityPrioritization = .quality
        if #available(iOS 16.0, *), let largest = device.activeFormat.supportedMaxPhotoDimensions
            .max(by: { Int($0.width) * Int($0.height) < Int($1.width) * Int($1.height) }) {
            output.maxPhotoDimensions = largest
        }
        front = wantFront
        return true
    }

    /// Qualité JPEG du capteur (0,95) et taille au-delà de laquelle le serveur refuse (25 Mo, souvenirs.RAW_MAX).
    nonisolated static let quality: Float = 0.95
    nonisolated static let maxBytes = 24 * 1024 * 1024

    /// La photo du capteur, TELLE QUELLE : pleine résolution, JPEG 0,95, priorité à la qualité (jamais réduite ni
    /// redessinée ici). Le serveur retire GPS et numéros de série, garde l'original 7 jours et fait la version écran.
    func capture() async -> Data? {
        if fake { return Self.testImage(front: front) }
        guard state == .ready, pending == nil else { return nil }
        let settings = AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg,
                                                       AVVideoCompressionPropertiesKey: [AVVideoQualityKey: Self.quality]])
        settings.photoQualityPrioritization = .quality
        if #available(iOS 16.0, *) { settings.maxPhotoDimensions = output.maxPhotoDimensions }
        if output.supportedFlashModes.contains(.on) { settings.flashMode = flash ? .on : .off }
        let raw: Data? = await withCheckedContinuation { reply in
            pending = reply
            output.capturePhoto(with: settings, delegate: self)
        }
        return raw.flatMap(Self.sendable)
    }

    /// Le fichier du capteur tel quel ; seulement s'il dépasse la limite du serveur (rare : 48 Mpx très détaillée),
    /// réencodé à 0,9 (toujours pleine résolution, orientation gardée).
    nonisolated static func sendable(_ raw: Data) -> Data? {
        guard raw.count > maxBytes else { return raw }
        return UIImage(data: raw)?.jpegData(compressionQuality: 0.9).flatMap { $0.count <= maxBytes ? $0 : nil }
    }

    /// Image de la recette : un dégradé et l'heure, en 12 Mpx (3024 × 4032, comme un iPhone), jamais montrée à l'écran
    /// avant le dévoilement.
    nonisolated static func testImage(front: Bool) -> Data? {
        let size = CGSize(width: 3024, height: 4032)
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        let image = UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            let colors = [UIColor(red: 1, green: 0.31, blue: 0.6, alpha: 1).cgColor,
                          UIColor(red: 0.42, green: 0.36, blue: 0.96, alpha: 1).cgColor] as CFArray
            if let gradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                ctx.cgContext.drawLinearGradient(gradient, start: .zero, end: CGPoint(x: size.width, y: size.height), options: [])
            }
            let text = "📸 Recette Souvenirs\n\(front ? "selfie" : "dos") · \(Date().formatted(date: .omitted, time: .standard))" as NSString
            text.draw(in: CGRect(x: 200, y: 1640, width: 2620, height: 1000),
                      withAttributes: [.font: UIFont.systemFont(ofSize: 226, weight: .heavy), .foregroundColor: UIColor.white])
        }
        return image.jpegData(compressionQuality: CGFloat(quality))
    }
}

extension SouvenirCameraSensor: AVCapturePhotoCaptureDelegate {
    nonisolated func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        let data = error == nil ? photo.fileDataRepresentation() : nil
        Task { @MainActor in
            let reply = self.pending
            self.pending = nil
            reply?.resume(returning: data)
        }
    }
}

/// Le flux de la caméra (ou, en recette, un fond qui le remplace).
struct SouvenirCameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    final class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var preview: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.backgroundColor = .black
        view.preview.session = session
        view.preview.videoGravity = .resizeAspectFill
        return view
    }

    func updateUIView(_ view: PreviewView, context: Context) {}
}
