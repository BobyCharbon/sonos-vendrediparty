import AVFoundation
import SwiftUI

/// Messages vocaux des Discussions : appui long sur le micro pour enregistrer, relâcher pour envoyer, glisser vers la
/// gauche pour annuler. L'enregistrement passe TOUJOURS par le micro du téléphone, jamais par un appareil Bluetooth
/// (AirPods, voiture) : c'est le plus rapide à démarrer et le son le plus net (demande de l'admin, 30.10).
@MainActor
final class VoiceRecorder: ObservableObject {
    /// En dessous, un appui trop court : rien n'est envoyé (évite les vocaux vides par erreur).
    static let minimumSeconds: TimeInterval = 0.6
    static let maximumSeconds: TimeInterval = 600

    @Published private(set) var recording = false
    @Published private(set) var elapsed: TimeInterval = 0
    @Published var problem: String?

    private var recorder: AVAudioRecorder?
    private var timer: Task<Void, Never>?
    private var started = Date()

    /// AAC mono 44,1 kHz, qualité moyenne (débit choisi par l'encodeur : imposer un débit fait échouer la préparation
    /// sur certains appareils) : léger, lu partout (iPhone, Android, navigateurs).
    nonisolated static let settings: [String: Any] = [
        AVFormatIDKey: kAudioFormatMPEG4AAC, AVSampleRateKey: 44_100, AVNumberOfChannelsKey: 1,
        AVEncoderAudioQualityKey: AVAudioQuality.medium.rawValue,
    ]

    /// Micro du téléphone seulement : catégorie sans option Bluetooth, entrée « micro intégré » imposée.
    nonisolated static func useBuiltInMicrophone(_ session: AVAudioSession = .sharedInstance()) throws {
        // Sans .allowBluetooth ni .allowBluetoothA2DP : un casque ou des AirPods ne sont jamais pris comme micro.
        try session.setCategory(.playAndRecord, mode: .default, options: [.defaultToSpeaker])
        try session.setActive(true)
        // Micro intégré imposé quand le téléphone en a un (toujours sur iPhone ; le simulateur n'en a pas).
        if let mic = session.availableInputs?.first(where: { $0.portType == .builtInMic }) {
            try? session.setPreferredInput(mic)
        }
    }

    /// Prépare le micro dès l'ouverture d'une conversation (autorisation déjà donnée) : l'appui démarre sans délai.
    func warmUp() {
        guard AVAudioSession.sharedInstance().recordPermission == .granted else { return }
        try? Self.useBuiltInMicrophone()
    }

    func start() async {
        guard !recording else { return }
        problem = nil
        let session = AVAudioSession.sharedInstance()
        if session.recordPermission != .granted {
            let allowed = await withCheckedContinuation { done in session.requestRecordPermission { done.resume(returning: $0) } }
            guard allowed else {
                problem = "Autorise le micro pour Party dans Réglages › Party."
                return
            }
            return  // première autorisation : l'utilisateur relâche le bouton pendant la question ; il réappuie
        }
        do {
            let file = FileManager.default.temporaryDirectory.appendingPathComponent("vocal-\(UUID().uuidString).m4a")
            var recorder: AVAudioRecorder?
            // Deux essais : la session audio peut être encore prise (lecture d'un vocal, autre app) au premier.
            for attempt in 0..<2 where recorder == nil {
                if attempt > 0 { try? await Task.sleep(for: .milliseconds(150)) }
                try? Self.useBuiltInMicrophone(session)
                if let r = try? AVAudioRecorder(url: file, settings: Self.settings), r.prepareToRecord(),
                   r.record(forDuration: Self.maximumSeconds) { recorder = r }
            }
            guard let recorder else { throw CocoaError(.fileWriteUnknown) }
            self.recorder = recorder
            started = Date()
            elapsed = 0
            recording = true
            UIImpactFeedbackGenerator(style: .medium).impactOccurred()
            timer = Task { [weak self] in
                while !Task.isCancelled {
                    try? await Task.sleep(for: .milliseconds(100))
                    guard let self else { return }
                    self.elapsed = Date().timeIntervalSince(self.started)
                }
            }
        } catch {
            problem = "Le micro n'a pas pu démarrer. Réessaie."
        }
    }

    /// send : le fichier et sa durée ; sinon (annulé, trop court) rien et le fichier est effacé.
    func stop(send: Bool) -> (URL, TimeInterval)? {
        timer?.cancel()
        timer = nil
        guard recording, let recorder else { return nil }
        let seconds = Date().timeIntervalSince(started)
        recorder.stop()
        self.recorder = nil
        recording = false
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        guard send, seconds >= Self.minimumSeconds else {
            try? FileManager.default.removeItem(at: recorder.url)
            return nil
        }
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        return (recorder.url, seconds)
    }

    nonisolated static func clock(_ seconds: TimeInterval) -> String {
        let s = max(0, Int(seconds.rounded()))
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

/// Lecture des vocaux : un seul à la fois ; la sortie suit le choix de l'utilisateur (haut-parleur, AirPods…).
@MainActor
final class VoicePlayer: ObservableObject {
    @Published private(set) var playing: String?
    @Published private(set) var progress: Double = 0

    private var player: AVPlayer?
    private var observer: Any?
    private var ended: NSObjectProtocol?

    func toggle(id: String, url: URL) {
        if playing == id { return stop() }
        stop()
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio)
        try? AVAudioSession.sharedInstance().setActive(true)
        let player = AVPlayer(url: url)
        self.player = player
        playing = id
        progress = 0
        observer = player.addPeriodicTimeObserver(forInterval: CMTime(value: 1, timescale: 10), queue: .main) { [weak self] time in
            guard let duration = player.currentItem?.duration.seconds, duration.isFinite, duration > 0 else { return }
            MainActor.assumeIsolated { self?.progress = time.seconds / duration }
        }
        ended = NotificationCenter.default.addObserver(forName: .AVPlayerItemDidPlayToEndTime, object: player.currentItem, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { self?.stop() }
        }
        player.play()
    }

    func stop() {
        if let observer { player?.removeTimeObserver(observer) }
        if let ended { NotificationCenter.default.removeObserver(ended) }
        observer = nil
        ended = nil
        player?.pause()
        player = nil
        playing = nil
        progress = 0
    }
}

/// Bulle d'un vocal : lecture / pause, barre d'avancement, durée.
struct VoiceBubble: View {
    @ObservedObject var player: VoicePlayer
    let id: String
    let url: URL?
    let seconds: Double
    let mine: Bool

    var body: some View {
        let active = player.playing == id
        HStack(spacing: 10) {
            Button {
                if let url { player.toggle(id: id, url: url) }
            } label: {
                Image(systemName: active ? "pause.circle.fill" : "play.circle.fill").font(.system(size: 34))
            }
            .buttonStyle(.plain)
            .disabled(url == nil)
            .accessibilityLabel(active ? "Pause" : "Écouter le message vocal")
            VStack(alignment: .leading, spacing: 4) {
                ProgressView(value: active ? player.progress : 0)
                    .tint(mine ? .black : .white)
                    .frame(width: 140)
                Text(VoiceRecorder.clock(seconds)).font(.caption.monospacedDigit())
            }
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Message vocal, \(VoiceRecorder.clock(seconds))")
    }
}
