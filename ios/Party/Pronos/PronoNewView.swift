import SwiftUI

/// « Nouveau prono » (maquette du 17.11, écran 2) : la question, le type de réponse, qui joue (un de mes groupes, des
/// personnes croisées dans Party, un lien), la fin, le dévoilement et les points (1 à 10). Ouvert depuis un groupe ou un
/// événement : il est déjà choisi. Pour l'honneur : aucun champ d'enjeu (revue de conformité).
struct PronoNewView: View {
    @ObservedObject var store: PronosStore
    let group: String?
    let event: String?
    let created: (String) -> Void

    struct MyGroup: Decodable, Identifiable, Hashable {
        let id: String
        let name: String
        let emoji: String
        let color: String?
        let system: Bool
        let member: Bool
    }

    @State private var question = ""
    @State private var kind = "choice"
    @State private var options = ["", ""]
    @State private var points = 3
    @State private var end = Calendar.current.date(bySettingHour: 20, minute: 0, second: 0, of: Date().addingTimeInterval(86_400)) ?? Date().addingTimeInterval(86_400)
    @State private var reveal = "close"
    @State private var chosenGroup: String?
    @State private var people: Set<String> = []
    @State private var link = false
    @State private var groups: [MyGroup] = []
    @State private var suggestions: [PronoFace] = []
    @State private var busy = false
    @State private var error: String?
    @State private var askTerms = false
    enum Field: Hashable { case question, option(Int) }
    @FocusState private var focused: Field?

    private let kinds = [("choice", "Choix"), ("person", "Personne"), ("number", "Nombre"), ("text", "Libre")]
    private var filled: [String] { options.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty } }
    private var ready: Bool {
        question.trimmingCharacters(in: .whitespaces).count >= 3 && (chosenGroup != nil || event != nil || !people.isEmpty || link)
            && (kind != "choice" || filled.count >= 2) && !busy
    }

    var body: some View {
        Form {
            Section {
                TextField("Qui marque le premier but samedi ?", text: $question, axis: .vertical)
                    .font(.title3.weight(.semibold)).focused($focused, equals: .question)
                    .accessibilityIdentifier("prono-question")
                Picker("Type de réponse", selection: $kind) { ForEach(kinds, id: \.0) { Text($0.1).tag($0.0) } }
                    .pickerStyle(.segmented)
            } footer: {
                Text(kind == "choice" ? "De 2 à 8 réponses possibles." : kind == "person" ? "On choisit quelqu'un du prono."
                     : kind == "number" ? "Le plus proche gagne." : "Les réponses se dévoilent à la fin, puis tu coches les bonnes.")
            }
            if kind == "choice" {
                Section("Réponses possibles") {
                    ForEach(options.indices, id: \.self) { i in
                        TextField("Choix \(i + 1)", text: Binding(get: { options[i] }, set: { options[i] = String($0.prefix(60)) }))
                            .focused($focused, equals: .option(i))
                            .submitLabel(.next)
                            .onSubmit { focused = i + 1 < options.count ? .option(i + 1) : nil }
                            .accessibilityIdentifier("prono-option-\(i)")
                    }
                    .onDelete { idx in if options.count > 2 { options.remove(atOffsets: idx) } }
                    if options.count < 8 {
                        Button { Motion.animate { options.append("") } } label: { Label("Ajouter un choix", systemImage: "plus") }
                    }
                }
            }
            Section {
                if event != nil {
                    Label("Les participants de l'événement", systemImage: "calendar")
                } else {
                    if !groups.isEmpty {
                        Picker("Groupe", selection: $chosenGroup) {
                            Text("Aucun").tag(String?.none)
                            ForEach(groups) { g in Text("\(g.emoji) \(g.name)").tag(String?.some(g.id)) }
                        }
                        .accessibilityIdentifier("prono-group-picker")
                    }
                    NavigationLink {
                        PronoPeoplePicker(suggestions: suggestions, selected: $people)
                    } label: {
                        HStack { Text("Des personnes"); Spacer(); Text(people.isEmpty ? "Aucune" : "\(people.count)").foregroundStyle(.secondary) }
                    }
                    Toggle("Un lien à partager", isOn: $link)
                }
            } header: { Text("Qui joue") } footer: {
                Text(event != nil ? "Présent ou Peut-être, et l'organisation." : "Tout le groupe est prévenu ; qui ouvre le lien se connecte à Party, puis joue.")
            }
            Section {
                DatePicker("Fin des pronos", selection: $end, in: Date().addingTimeInterval(600)..., displayedComponents: [.date, .hourAndMinute])
                if kind != "text" {
                    Picker("Dévoiler les réponses", selection: $reveal) {
                        Text("À la fin").tag("close")
                        Text("Avec le résultat").tag("result")
                    }
                }
                Stepper(value: $points, in: 1...10) {
                    HStack { Text("Points pour une bonne réponse"); Spacer(); Text("\(points)").bold().foregroundStyle(PronoLook.lemon) }
                }
            } header: { Text("Réglages") } footer: {
                Text("Avant le dévoilement, chacun voit seulement qui a joué, jamais quoi (toi compris).")
            }
            Section {
                PronoHonour(points: points).listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            }
            if let error { Section { Text(error).foregroundStyle(.red) } }
        }
        .scrollContentBackground(.hidden)
        .scrollDismissesKeyboard(.interactively)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Nouveau prono")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                Button("Publier") { create() }.bold().disabled(!ready).accessibilityIdentifier("prono-publish")
            }
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("OK") { hideKeyboard() }.bold().accessibilityIdentifier("prono-keyboard-done")
            }
        }
        .task {
            chosenGroup = group
            await loadChoices()
            if question.isEmpty { focused = .question }
        }
        .sheet(isPresented: $askTerms) {
            TermsAcceptSheet(store: store.moderation) { accepted in if accepted { create() } }
        }
    }

    private func loadChoices() async {
        // Mes groupes (jamais Membres Vendredi Party : la base le refuse aussi) et les personnes croisées.
        if let list: [MyGroup] = try? await store.call("my_groups_overview") { groups = list.filter { !$0.system && $0.member } }
        if let list: [PronoFace] = try? await store.call("prono_suggestions") { suggestions = list }
    }

    private func hideKeyboard() {
        focused = nil
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }

    private func create() {
        busy = true
        error = nil
        var body: [String: Any] = [
            "question": question.trimmingCharacters(in: .whitespacesAndNewlines), "kind": kind, "points": points,
            "closes_at": ISO8601DateFormatter().string(from: end), "reveal": kind == "text" ? "close" : reveal,
            "people": Array(people), "link": link,
        ]
        if kind == "choice" { body["options"] = filled }
        if let chosenGroup { body["group_id"] = chosenGroup }
        if let event { body["event_id"] = event }
        Task {
            defer { busy = false }
            do {
                let p: Prono = try await store.call("prono_create", ["body": body])
                Haptics.success()
                await store.refreshBadge()
                created(p.id)
            } catch PartyAPIError.termsRequired {
                askTerms = true
            } catch {
                Haptics.error()
                self.error = PronosStore.message(error)
            }
        }
    }
}

/// Choisir des personnes croisées dans Party (événements, groupes) ; jamais tout le site.
struct PronoPeoplePicker: View {
    let suggestions: [PronoFace]
    @Binding var selected: Set<String>
    @State private var search = ""

    var body: some View {
        List {
            if suggestions.isEmpty {
                Text("Personne pour l'instant : les personnes croisées à un événement ou dans tes groupes apparaîtront ici.")
                    .foregroundStyle(.secondary)
            }
            ForEach(suggestions.filter { search.isEmpty || $0.name.localizedCaseInsensitiveContains(search) }) { f in
                Button {
                    Haptics.selection()
                    if selected.contains(f.id) { selected.remove(f.id) } else { selected.insert(f.id) }
                } label: {
                    HStack(spacing: 12) {
                        Initials(name: f.name, photo: f.photo, size: 34)
                        Text(f.name).foregroundStyle(.primary)
                        Spacer()
                        Image(systemName: selected.contains(f.id) ? "checkmark.circle.fill" : "circle")
                            .foregroundStyle(selected.contains(f.id) ? PronoLook.accent : .secondary)
                    }
                }
                .accessibilityAddTraits(selected.contains(f.id) ? .isSelected : [])
            }
        }
        .searchable(text: $search, prompt: "Chercher")
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle("Des personnes")
    }
}
