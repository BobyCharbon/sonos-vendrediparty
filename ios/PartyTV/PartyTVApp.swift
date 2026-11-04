import SwiftUI

@main
struct PartyTVApp: App {
    @StateObject private var store: TVStore = {
        #if DEBUG
        // Simulateur : PARTY_TV_DEMO=<fichier JSON {"game":…,"music":…}> affiche une partie figée, sans serveur.
        if let path = ProcessInfo.processInfo.environment["PARTY_TV_DEMO"], let data = FileManager.default.contents(atPath: path),
           let demo = try? JSONDecoder().decode(JSON.self, from: data) {
            // {"steps": [{"game":…, "music":…}, …], "every": 4} : plusieurs états à la suite (annonces, cartes, podium…).
            if !demo["steps"].array.isEmpty {
                return TVStore(steps: demo["steps"].array, every: demo["every"].double ?? 4)
            }
            return TVStore(demo: (demo["game"], demo["music"]), before: demo["before"], zicou: demo["zicou"])
        }
        // Simulateur : PARTY_TV_BASE=http://127.0.0.1:<port> branche l'app sur un serveur local (essai de bout en bout).
        if let raw = ProcessInfo.processInfo.environment["PARTY_TV_BASE"], let base = URL(string: raw) {
            return TVStore(client: TVClient(base: base))
        }
        #endif
        return TVStore()
    }()

    var body: some Scene {
        WindowGroup {
            ZStack {
                TV.backdrop
                switch store.screen {
                case .pin: PinScreen(store: store)
                case .code: CodeScreen(store: store)
                case .watching: WatchScreen(store: store)
                }
            }
            .preferredColorScheme(.dark)
            #if DEBUG
            // Essai de bout en bout sur le simulateur : PARTY_TV_PIN puis PARTY_TV_CODE, comme si on les tapait.
            .task {
                let env = ProcessInfo.processInfo.environment
                if let pin = env["PARTY_TV_PIN"], store.screen == .pin { await store.submitPin(pin) }
                if let code = env["PARTY_TV_CODE"], store.screen == .code { await store.watch(code) }
            }
            #endif
        }
    }
}
