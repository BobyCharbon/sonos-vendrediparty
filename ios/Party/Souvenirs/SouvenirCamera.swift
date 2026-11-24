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
        front = wantFront
        return true
    }

    /// La photo en JPEG (1600 px au plus, sans métadonnées : redessinée) ; nil si la prise a échoué.
    func capture() async -> Data? {
        if fake { return Self.testImage(front: front) }
        guard state == .ready, pending == nil else { return nil }
        let settings = AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg])
        if output.supportedFlashModes.contains(.on) { settings.flashMode = flash ? .on : .off }
        let raw: Data? = await withCheckedContinuation { reply in
            pending = reply
            output.capturePhoto(with: settings, delegate: self)
        }
        guard let raw, let image = UIImage(data: raw) else { return nil }
        return Self.jpeg(image)
    }

    /// Redessinée (EXIF, GPS et orientation appliqués puis oubliés), 1600 px au plus, JPEG 0,85.
    nonisolated static func jpeg(_ image: UIImage, maxSide: CGFloat = 1600) -> Data? {
        let size = image.size
        guard size.width > 0, size.height > 0 else { return nil }
        let scale = min(1, maxSide / max(size.width, size.height))
        let target = CGSize(width: (size.width * scale).rounded(), height: (size.height * scale).rounded())
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        format.opaque = true
        let drawn = UIGraphicsImageRenderer(size: target, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: target))
        }
        return drawn.jpegData(compressionQuality: 0.85)
    }

    /// Image de la recette : un dégradé et l'heure, jamais montrée à l'écran avant le dévoilement.
    nonisolated static func testImage(front: Bool) -> Data? {
        let size = CGSize(width: 1200, height: 1600)
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        let image = UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            let colors = [UIColor(red: 1, green: 0.31, blue: 0.6, alpha: 1).cgColor,
                          UIColor(red: 0.42, green: 0.36, blue: 0.96, alpha: 1).cgColor] as CFArray
            if let gradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                ctx.cgContext.drawLinearGradient(gradient, start: .zero, end: CGPoint(x: size.width, y: size.height), options: [])
            }
            let text = "📸 Recette Souvenirs\n\(front ? "selfie" : "dos") · \(Date().formatted(date: .omitted, time: .standard))" as NSString
            text.draw(in: CGRect(x: 80, y: 650, width: 1040, height: 400),
                      withAttributes: [.font: UIFont.systemFont(ofSize: 90, weight: .heavy), .foregroundColor: UIColor.white])
        }
        return image.jpegData(compressionQuality: 0.85)
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
