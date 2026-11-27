import AVFoundation
import SwiftUI

/// Appels à AVAudioSession hors du fil principal (ils peuvent bloquer plusieurs centaines de ms : « Hang Risk »).
/// File série : activer, puis rendre la session se font toujours dans l'ordre des gestes.
enum AudioSessionQueue {
    private static let queue = DispatchQueue(label: "party.audio-session", qos: .userInitiated)

    static func run(_ work: @escaping @Sendable () -> Void) { queue.async(execute: work) }

    static func perform<T: Sendable>(_ work: @escaping @Sendable () -> T) async -> T {
        await withCheckedContinuation { done in queue.async { done.resume(returning: work()) } }
    }

    /// Comme perform, mais rendu au plus tard après `seconds` : nil si la file est encore prise (micro bloqué : recette
    /// de nuit du 28.11, prepareToRecord resté plus de 3 min). Un résultat arrivé après le délai passe à `late`, sur la
    /// file, pour être nettoyé dans l'ordre des gestes.
    static func perform<T: Sendable>(within seconds: Double, _ work: @escaping @Sendable () -> T,
                                     late: @escaping @Sendable (T) -> Void = { _ in }) async -> T? {
        let once = Once()
        return await withCheckedContinuation { (done: CheckedContinuation<T?, Never>) in
            queue.async {
                let value = work()
                if once.claim() { done.resume(returning: value) } else { late(value) }
            }
            DispatchQueue.global(qos: .userInitiated).asyncAfter(deadline: .now() + seconds) {
                if once.claim() { done.resume(returning: nil) }
            }
        }
    }

    /// Reprise unique : le travail ou le délai, le premier des deux.
    private final class Once: @unchecked Sendable {
        private let lock = NSLock()
        private var claimed = false
        func claim() -> Bool {
            lock.lock()
            defer { lock.unlock() }
            if claimed { return false }
            claimed = true
            return true
        }
    }
}

/// L'enregistreur passe de la file audio au fil principal (AVAudioRecorder n'est pas Sendable : un seul fil s'en sert à
/// la fois, la file pour l'ouvrir, puis le fil principal).
final class RecorderBox: @unchecked Sendable {
    let recorder: AVAudioRecorder?
    init(_ recorder: AVAudioRecorder?) { self.recorder = recorder }
}

/// Messages vocaux des Discussions : appui long sur le micro pour enregistrer, relâcher pour envoyer, glisser vers la
/// gauche pour annuler. L'enregistrement passe TOUJOURS par le micro du téléphone, jamais par un appareil Bluetooth
/// (AirPods, voiture) : c'est le plus rapide à démarrer et le son le plus net (demande de l'admin, 30.10).
@MainActor
final class VoiceRecorder: ObservableObject {
    /// En dessous, un appui trop court : rien n'est envoyé (évite les vocaux vides par erreur).
    static let minimumSeconds: TimeInterval = 0.6
    nonisolated static let maximumSeconds: TimeInterval = 600
    /// Au-delà, le micro est déclaré en panne : message à l'écran, la session est rendue dès que la file se libère.
    nonisolated static let startTimeout: Double = 4

    @Published private(set) var recording = false
    @Published private(set) var elapsed: TimeInterval = 0
    @Published var problem: String?

    private var recorder: AVAudioRecorder?
    private var timer: Task<Void, Never>?
    private var started = Date()
    /// Faux dès qu'on demande l'arrêt : un démarrage encore en cours (micro lent à s'ouvrir) s'annule au lieu de
    /// lancer un enregistrement que plus personne n'attend (avis ea8cc508a706 : un second vocal partait tout seul).
    private var wanted = false
    /// Change à chaque appui et à chaque arrêt : un démarrage resté en attente (session audio ouverte hors du fil
    /// principal) qui reprend après un nouvel appui s'efface au lieu de lancer un second enregistrement.
    private var generation = 0

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

    // Jamais de session audio à l'ouverture d'une conversation (ancien « warmUp ») : l'activer coupait la musique
    // en cours (Spotify…) sans qu'on lise ni n'enregistre rien (avis c54e83dc5130). Elle s'ouvre au toucher du micro.

    func start() async {
        guard !recording else { return }
        wanted = true
        generation += 1
        let mine = generation
        problem = nil
        // Avec délai : derrière un micro bloqué, la file ne répond plus (le nouvel appui ne doit pas geler non plus).
        guard let granted = await AudioSessionQueue.perform(within: Self.startTimeout, {
            AVAudioSession.sharedInstance().recordPermission == .granted
        }) else {
            if !recording { problem = "Le micro n'a pas pu démarrer. Réessaie." }
            return
        }
        if !granted {
            let allowed = await withCheckedContinuation { done in
                AVAudioSession.sharedInstance().requestRecordPermission { done.resume(returning: $0) }
            }
            guard allowed else {
                problem = "Autorise le micro pour Party dans Réglages › Party."
                return
            }
            return  // première autorisation : l'utilisateur relâche le bouton pendant la question ; il réappuie
        }
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("vocal-\(UUID().uuidString).m4a")
        // Session, création, préparation et démarrage de l'enregistreur hors du fil principal, dans la file de la session
        // (ordre des gestes gardé) : prepareToRecord a gelé l'app plus de 3 min sur le fil principal (recette du 28.11).
        let opened = await AudioSessionQueue.perform(within: Self.startTimeout, {
            var made: AVAudioRecorder?
            // Deux essais : la session audio peut être encore prise (lecture d'un vocal, autre app) au premier.
            for attempt in 0..<2 where made == nil {
                if attempt > 0 { Thread.sleep(forTimeInterval: 0.15) }
                try? VoiceRecorder.useBuiltInMicrophone()
                if let r = try? AVAudioRecorder(url: file, settings: VoiceRecorder.settings), r.prepareToRecord(),
                   r.record(forDuration: VoiceRecorder.maximumSeconds) { made = r }
            }
            if made == nil {  // micro pas démarré : la session est rendue (la musique reprend)
                try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
            }
            return RecorderBox(made)
        }, late: { box in
            // Prêt après le délai : plus personne ne l'attend (message déjà affiché) ; rien ne s'enregistre.
            box.recorder?.stop()
            try? FileManager.default.removeItem(at: file)
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        })
        guard let opened, let recorder = opened.recorder else {
            if !recording { problem = "Le micro n'a pas pu démarrer. Réessaie." }
            return
        }
        guard wanted, generation == mine, !recording else {  // arrêt (ou nouvel appui) pendant l'ouverture du micro
            // Session rendue seulement si plus personne ne veut le micro (un nouvel appui garde la sienne).
            let release = !wanted && !recording
            let box = opened
            AudioSessionQueue.run {
                box.recorder?.stop()
                try? FileManager.default.removeItem(at: file)
                if release { try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) }
            }
            return
        }
        self.recorder = recorder
        started = Date()
        elapsed = 0
        recording = true
        problem = nil  // un appui précédent en panne ne laisse pas son message sous un enregistrement en cours
        Haptics.press()
        timer = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(100))
                guard let self else { return }
                self.elapsed = Date().timeIntervalSince(self.started)
            }
        }
    }

    /// send : le fichier et sa durée ; sinon (annulé, trop court) rien et le fichier est effacé.
    func stop(send: Bool) -> (URL, TimeInterval)? {
        wanted = false
        generation += 1
        timer?.cancel()
        timer = nil
        guard recording, let recorder else { return nil }
        let seconds = Date().timeIntervalSince(started)
        recorder.stop()
        self.recorder = nil
        recording = false
        AudioSessionQueue.run { try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) }
        guard send, seconds >= Self.minimumSeconds else {
            try? FileManager.default.removeItem(at: recorder.url)
            Haptics.warning()  // vocal annulé (glissé à gauche) ou trop court : il n'est pas envoyé
            return nil
        }
        Haptics.tap()

        return (recorder.url, seconds)
    }

    nonisolated static func clock(_ seconds: TimeInterval) -> String {
        let s = max(0, Int(seconds.rounded()))
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

/// Lecture des vocaux : un seul à la fois ; la sortie suit le choix de l'utilisateur (haut-parleur, AirPods…).
/// Vitesse 1× / 1,5× / 2× / 3×, gardée pour les vocaux suivants (comme WhatsApp).
@MainActor
final class VoicePlayer: ObservableObject {
    static let speeds: [Float] = [1, 1.5, 2, 3]
    static let speedKey = "chatVoiceSpeed"

    @Published private(set) var playing: String?
    @Published private(set) var progress: Double = 0
    @Published private(set) var speed: Float = {
        let saved = UserDefaults.standard.float(forKey: VoicePlayer.speedKey)
        return VoicePlayer.speeds.contains(saved) ? saved : 1
    }()

    /// Vitesse suivante (1× → 1,5× → 2× → 3× → 1×), appliquée aussitôt au vocal en cours.
    func nextSpeed() {
        speed = Self.next(after: speed)
        UserDefaults.standard.set(speed, forKey: Self.speedKey)
        if playing != nil { player?.rate = speed }
    }

    nonisolated static func next(after speed: Float) -> Float {
        let index = speeds.firstIndex(of: speed) ?? 0
        return speeds[(index + 1) % speeds.count]
    }

    nonisolated static func label(_ speed: Float) -> String {
        speed == 1.5 ? "1,5×" : "\(Int(speed))×"
    }

    private var player: AVPlayer?
    private var observer: Any?
    private var ended: NSObjectProtocol?

    func toggle(id: String, url: URL) {
        if playing == id { return stop() }
        stop(release: false)  // d'un vocal au suivant : la session reste prise (la musique ne repart pas entre les deux)
        let player = AVPlayer(url: url)
        // Voix accélérée sans effet « chipmunk » : la hauteur est gardée.
        player.currentItem?.audioTimePitchAlgorithm = .timeDomain
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
        // Session ouverte hors du fil principal, puis la lecture démarre ; arrêté entre-temps : rien ne démarre
        // (la session est rendue par stop(), dans la même file, après cette ouverture).
        let started = ObjectIdentifier(player)
        AudioSessionQueue.run { [weak self] in
            try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio)
            try? AVAudioSession.sharedInstance().setActive(true)
            Task { @MainActor [weak self] in
                guard let self, let current = self.player, ObjectIdentifier(current) == started else { return }
                current.playImmediately(atRate: self.speed)
            }
        }
    }

    func stop(release: Bool = true) {
        let wasPlaying = player != nil
        if let observer { player?.removeTimeObserver(observer) }
        if let ended { NotificationCenter.default.removeObserver(ended) }
        observer = nil
        ended = nil
        player?.pause()
        player = nil
        playing = nil
        progress = 0
        // Vocal fini ou arrêté : la session audio est rendue, la musique coupée (Spotify…) reprend.
        if wasPlaying && release { AudioSessionQueue.run { try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) } }
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
                // Néon : disque lavande (le mien : blanc), triangle sombre.
                Image(systemName: active ? "pause.fill" : "play.fill").font(.system(size: 16, weight: .bold))
                    .foregroundStyle(PronoTheme.fixed(0x120B26))
                    .frame(width: 44, height: 44)
                    .background(mine ? AnyShapeStyle(Color.white) : AnyShapeStyle(PronoTheme.lavender), in: Circle())
            }
            .buttonStyle(.plain)
            .disabled(url == nil)
            .accessibilityLabel(active ? "Pause" : "Écouter le message vocal")
            VStack(alignment: .leading, spacing: 4) {
                ProgressView(value: active ? player.progress : 0)
                    .tint(mine ? .white : PronoTheme.lavA)
                    .frame(width: 120)
                Text(VoiceRecorder.clock(seconds)).font(.caption.monospacedDigit())
                    .foregroundStyle(mine ? Color.white.opacity(0.9) : PronoTheme.t2)
            }
            Button { player.nextSpeed() } label: {
                Text(VoicePlayer.label(player.speed)).font(.caption.weight(.bold).monospacedDigit())
                    .padding(.horizontal, 8).padding(.vertical, 4)
                    .background((mine ? Color.white : PronoTheme.lavA).opacity(0.18), in: Capsule())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Vitesse de lecture \(VoicePlayer.label(player.speed))")
            .accessibilityHint("Touche pour passer à \(VoicePlayer.label(VoicePlayer.next(after: player.speed)))")
            .accessibilityIdentifier("voice-speed")
        }
        .padding(.vertical, 2)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Message vocal, \(VoiceRecorder.clock(seconds))")
    }
}
