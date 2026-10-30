import SwiftUI

/// Premier lancement : le code admin de la soirée (gardé ensuite dans le trousseau de l'Apple TV).
struct PinScreen: View {
    @ObservedObject var store: TVStore
    @State private var pin = ""

    var body: some View {
        VStack(spacing: 40) {
            Text("🎉 Party TV").font(.system(size: 90, weight: .heavy))
            Text("Code admin de la soirée").font(.title2).foregroundStyle(TV.muted)
            SecureField("Code admin", text: $pin)
                .keyboardType(.numberPad)
                .frame(width: 600)
                .onSubmit { Task { await store.submitPin(pin) } }
            Button(store.busy ? "Connexion…" : "Continuer") { Task { await store.submitPin(pin) } }
                .disabled(pin.isEmpty || store.busy)
            if let problem = store.problem { Text(problem).foregroundStyle(TV.red).font(.title3) }
            Text("Demandé une seule fois : l'Apple TV devient l'écran de l'hôte.").foregroundStyle(TV.muted)
        }
        .padding(80)
    }
}

/// Code de la partie à suivre (4 chiffres, affiché sur les téléphones) ; raccourcis vers les parties en cours.
struct CodeScreen: View {
    @ObservedObject var store: TVStore
    @State private var code = ""

    var body: some View {
        HStack(alignment: .top, spacing: 80) {
            VStack(alignment: .leading, spacing: 34) {
                Text("Quelle partie afficher ?").font(.system(size: 70, weight: .heavy))
                Text("Tape le code à 4 chiffres affiché sur les téléphones des joueurs.").font(.title3).foregroundStyle(TV.muted)
                TextField("Code de la partie", text: $code)
                    .keyboardType(.numberPad)
                    .frame(width: 520)
                    .onSubmit { Task { await store.watch(code) } }
                Button(store.busy ? "Ouverture…" : "Afficher la partie") { Task { await store.watch(code) } }
                    .disabled(code.filter(\.isNumber).count != 4 || store.busy)
                if let problem = store.problem { Text(problem).foregroundStyle(TV.red).font(.title3) }
                Spacer()
                Button("Changer de code admin", role: .destructive) { store.forgetPin() }.font(.callout)
            }
            if !store.games.isEmpty {
                VStack(alignment: .leading, spacing: 20) {
                    Text("Parties en cours").font(.title2.bold())
                    ForEach(Array(store.games.enumerated()), id: \.offset) { _, g in
                        Button {
                            Task { await store.watch(g["code"].string ?? "") }
                        } label: {
                            HStack {
                                Text(g["name"].string ?? "Partie").font(.title3.bold())
                                Spacer()
                                Text("\(g["players"].int ?? 0) joueurs · \(g["code"].string ?? "")").foregroundStyle(TV.muted)
                            }
                            .frame(width: 640)
                        }
                    }
                }
            }
        }
        .padding(80)
        .task { await store.appear() }
    }
}
