import Foundation

/// Mesure de la vitesse des Discussions (demande de l'admin du 18.11 : « le plus rapide possible ») : chaque étape
/// (toucher, liste affichée, conversation affichée, bulle, message reçu) écrit « nom heure_ms » dans le fichier
/// PARTY_TIMING_FILE. Seulement dans les builds de recette (E2E_HOOKS) : l'app de l'App Store n'en contient rien.
enum ChatTiming {
    #if E2E_HOOKS
    private static let file: URL? = ProcessInfo.processInfo.environment["PARTY_TIMING_FILE"].map { URL(fileURLWithPath: $0) }
    private static let queue = DispatchQueue(label: "party.chat-timing")
    #endif

    @inline(__always)
    static func mark(_ name: @autoclosure () -> String) {
        #if E2E_HOOKS
        guard let file else { return }
        let line = "\(name()) \(Int64((Date().timeIntervalSince1970 * 1000).rounded()))\n"
        queue.async {
            guard let data = line.data(using: .utf8) else { return }
            if let handle = try? FileHandle(forWritingTo: file) {
                handle.seekToEndOfFile()
                handle.write(data)
                try? handle.close()
            } else {
                try? data.write(to: file)
            }
        }
        #endif
    }
}
