import SwiftUI
import CoreImage.CIFilterBuiltins

/// « Nouveau prono » v2 (maquettes 2-1 à 2-4 du 18.11, direction C « Néon club ») : 1 « Qu'est-ce qu'on prédit ? »
/// (modèles de la base, prono_templates, par famille ; « Partir de zéro » avec les 9 types), 2 « La question » avec
/// l'aperçu en direct de la carte, 3 « Réglages » (qui joue d'abord : il décide si les patates sont possibles ; fin,
/// patates, points, dévoilement), 4 « C'est lancé ! » (lien, partage, QR, « Jouer maintenant »).
/// Conformité : jamais d'argent ni de boisson ; les patates n'ont aucune valeur (rappel toujours visible quand elles
/// sont allumées) ; pas de patates sans groupe ni soirée, ni pour un trophée ou une réponse libre ; pas de confettis ici.
struct PronoNewView: View {
    @ObservedObject var store: PronosStore
    let group: String?
    let event: String?
    let created: (String) -> Void
    /// Modèle déjà choisi (états vides de la liste) : l'étape 1 est sautée.
    private let initialTemplate: PronoTemplate?

    init(store: PronosStore, group: String?, event: String?, created: @escaping (String) -> Void) {
        self.init(store: store, group: group, event: event, template: nil, created: created)
    }

    init(store: PronosStore, group: String?, event: String?, template: PronoTemplate?, created: @escaping (String) -> Void) {
        _store = ObservedObject(wrappedValue: store)
        self.group = group
        self.event = event
        self.created = created
        initialTemplate = template
        if let template {
            let question: String? = template.question
            let emoji: String? = template.emoji
            let basic = NPTemplate(id: template.id, kind: template.kind, emoji: emoji, title: template.title,
                                   question: question, hint: template.hint)
            _template = State(initialValue: basic)
            _kind = State(initialValue: NPKind.of(template.kind).id)
            _question = State(initialValue: String((question ?? template.title).prefix(120)))
            _step = State(initialValue: .question)
        }
    }

    struct MyGroup: Decodable, Identifiable, Hashable {
        let id: String
        let name: String
        let emoji: String
        let color: String?
        let system: Bool
        let member: Bool
        var members: Int?
    }

    enum Step: Int { case template = 1, question, settings, launched }
    enum Field: Hashable { case question, option(Int), rules, unit }

    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var typeSize
    @ScaledMetric(relativeTo: .largeTitle) private var lineDigits: CGFloat = 64
    @ScaledMetric(relativeTo: .title) private var pointsDigits: CGFloat = 40
    @ScaledMetric(relativeTo: .title2) private var endDigits: CGFloat = 28

    @State private var step: Step = .template
    @State private var forward = true
    @State private var family = "all"
    @State private var templates: [NPTemplate] = []
    @State private var loadingTemplates = true
    @State private var template: NPTemplate?

    @State private var question = ""
    @State private var kind = "choice"
    @State private var options = ["", ""]
    @State private var line = 7.5
    @State private var unit = "buts"
    @State private var customUnit = ""
    @State private var notOver = false
    @State private var rules = ""
    @State private var award: String?

    @State private var chosenGroup: String?
    @State private var people: Set<String> = []
    @State private var link = false
    @State private var groups: [MyGroup] = []
    @State private var suggestions: [PronoFace] = []
    @State private var loaded = false
    @State private var points = 3
    @State private var end = NPDates.at(days: 1, hour: 20)
    @State private var endChoice = "tomorrow"
    @State private var reveal = "close"
    @State private var patates = true
    @State private var bagOn = false

    @State private var busy = false
    @State private var error: String?
    @State private var askTerms = false
    @State private var pickingEnd = false
    @State private var createdID: String?
    @State private var createdURL: URL?
    @State private var showQR = false
    @State private var copied = false
    @State private var pulse = false
    @State private var sealIn = false
    @State private var ripple = false
    @State private var textIn = false
    @State private var cardIn = false
    @State private var shareIn = false
    @State private var rays = false
    @FocusState private var focused: Field?

    // MARK: - État calculé

    private var filled: [String] { options.map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty } }
    private var hasOptions: Bool { kind == "choice" || kind == "majority" }
    private var trimmedQuestion: String { question.trimmingCharacters(in: .whitespacesAndNewlines) }
    private var awardCategory: NPAward? { NPAward.all.first { $0.id == award } }
    private var questionShown: String { kind == "award" ? (awardCategory?.question ?? "") : trimmedQuestion }
    private var questionReady: Bool {
        kind == "award" ? awardCategory != nil : trimmedQuestion.count >= 5 && (!hasOptions || filled.count >= 2)
    }
    private var whoReady: Bool { chosenGroup != nil || event != nil || !people.isEmpty || link }
    private var ready: Bool { questionReady && whoReady && !busy }
    private var chosen: MyGroup? { groups.first { $0.id == chosenGroup } }
    private var terrainKey: String { event.map { "e:\($0)" } ?? chosenGroup.map { "g:\($0)" } ?? "" }
    /// Patates possibles : drapeau du serveur ET réglage de la base (prono_bag), un groupe ou une soirée, et jamais pour
    /// un trophée ni une réponse libre (conformité 🔴 1–4).
    private var patatesPossible: Bool {
        store.features.patates && bagOn && !terrainKey.isEmpty && kind != "award" && kind != "text"
    }
    private var usesPatates: Bool { patatesPossible && patates }
    private var revealChoosable: Bool { !["text", "majority", "award"].contains(kind) }
    private var unitShown: String {
        unit == "other" ? customUnit.trimmingCharacters(in: .whitespaces) : unit
    }
    private var lineText: String { NPDates.half(line) }
    private var overUnderLabels: [String] {
        let u = unitShown.isEmpty ? "" : " \(unitShown)"
        return ["Plus de \(lineText)\(u)", "Moins de \(lineText)\(u)"]
    }
    private var pronoEmoji: String {
        if kind == "award" { return awardCategory?.emoji ?? "🏆" }
        return template?.emoji ?? NPKind.of(kind).emoji
    }
    private var coverColor: String? { chosen?.color ?? (event != nil ? "lemon" : "lavender") }
    private var place: (String, String)? {
        if let chosen { return (chosen.emoji, chosen.name) }
        if event != nil { return ("🎉", "La soirée") }
        return nil
    }
    private var terrainName: String { chosen.map { "sac de « \($0.name) »" } ?? (event != nil ? "sac de la soirée" : "") }
    private var audience: String {
        if let chosen { return "ce que verra « \(chosen.name) »" }
        return event != nil ? "ce que verront les invités" : "ce que verra la bande"
    }

    // MARK: - Écran

    var body: some View {
        ZStack {
            NPBackground()
            ScrollViewReader { proxy in
                ScrollView {
                    stepContent
                        .padding(.horizontal, 20)
                        .padding(.top, 8)
                        .padding(.bottom, 28)
                }
                .scrollDismissesKeyboard(.interactively)
                .onChange(of: focused) { field in
                    guard let field else { return }
                    Motion.animate(Motion.smooth) { proxy.scrollTo(field, anchor: .center) }
                }
            }
            .id(step)
            .transition(reduceMotion ? .opacity : .asymmetric(
                insertion: .move(edge: forward ? .trailing : .leading).combined(with: .opacity),
                removal: .opacity))
        }
        // La barre du bas disparaît pendant la saisie : rien n'est caché derrière le clavier (bouton OK au-dessus).
        .safeAreaInset(edge: .bottom) { if focused == nil { bottomBar } }
        .navigationTitle("Nouveau prono")
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(step == .question || step == .settings)
        .toolbar {
            ToolbarItem(placement: .principal) { stepHeader }
            if step == .question || step == .settings {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button { go(step == .settings ? .question : .template) } label: {
                        Image(systemName: "chevron.left").font(.body.weight(.bold)).foregroundStyle(NP.t1)
                            .frame(width: 44, height: 44).npGlass(22)
                    }
                    .accessibilityLabel("Étape précédente")
                    .accessibilityIdentifier("prono-back")
                }
            }
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("OK") { hideKeyboard() }.bold().accessibilityIdentifier("prono-keyboard-done")
            }
        }
        .task {
            guard !loaded else { return }
            loaded = true
            chosenGroup = group
            await loadChoices()
        }
        .task(id: terrainKey) { await loadBag() }
        .sheet(isPresented: $askTerms) {
            TermsAcceptSheet(store: store.moderation) { accepted in if accepted { create() } }
        }
        .sheet(isPresented: $pickingEnd) { endPicker }
        .sheet(isPresented: $showQR) { qrSheet }
    }

    @ViewBuilder private var stepContent: some View {
        switch step {
        case .template: templateStep
        case .question: questionStep
        case .settings: settingsStep
        case .launched: launchedStep
        }
    }

    private var stepHeader: some View {
        let names: [Step: String] = [.template: "Modèle", .question: "Question", .settings: "Réglages", .launched: "Prono lancé"]
        let name = names[step] ?? ""
        return VStack(spacing: 6) {
            if step == .launched {
                Text(name).font(.subheadline.weight(.semibold)).foregroundStyle(NP.t2)
            } else {
                (Text(name).bold().foregroundColor(NP.t1) + Text(" · \(step.rawValue) sur 3").foregroundColor(NP.t2))
                    .font(.subheadline)
                HStack(spacing: 6) {
                    ForEach(1...3, id: \.self) { i in
                        Capsule()
                            .fill(i <= step.rawValue ? NP.lavender : NP.t3.opacity(0.35))
                            .frame(width: i == step.rawValue ? 40 : 22, height: 5)
                            .shadow(color: i == step.rawValue ? NP.lavender.opacity(0.7) : .clear, radius: 6)
                    }
                }
            }
        }
        .animation(Motion.pick(NP.spring, reduced: reduceMotion), value: step)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(step == .launched ? name : "Étape \(step.rawValue) sur 3 : \(name)")
    }

    @ViewBuilder private var bottomBar: some View {
        switch step {
        case .question:
            NPBottom {
                NPPrimary(title: "Continuer", trailing: "arrow.right", enabled: questionReady) {
                    go(.settings)
                }
                .accessibilityIdentifier("prono-next")
            }
        case .settings:
            NPBottom {
                VStack(spacing: 10) {
                    if let error {
                        Text(error).font(.footnote.weight(.semibold)).foregroundStyle(NP.amber)
                            .multilineTextAlignment(.center).accessibilityIdentifier("prono-error")
                    }
                    Text(summary).font(.footnote.weight(.semibold)).foregroundStyle(NP.t2)
                        .multilineTextAlignment(.center)
                    NPPrimary(title: "Lancer le prono", leading: "🔮", enabled: ready, busy: busy) { create() }
                        .accessibilityIdentifier("prono-publish")
                }
            }
        default: EmptyView()
        }
    }

    // MARK: - 1. Modèle

    private var templateStep: some View {
        LazyVStack(alignment: .leading, spacing: 0, pinnedViews: [.sectionHeaders]) {
            Text("Qu'est-ce qu'on prédit ?")
                .font(.np(.largeTitle)).foregroundStyle(NP.t1)
                .accessibilityAddTraits(.isHeader)
            Text("Prends un modèle, tout reste modifiable.")
                .font(.callout).foregroundStyle(NP.t2).padding(.top, 6)
            Section {
                if loadingTemplates {
                    ProgressView().frame(maxWidth: .infinity).padding(40)
                }
                ForEach(NPFamily.all.filter { family == "all" || family == $0.key }, id: \.key) { fam in
                    familySection(fam)
                }
                if family == "all" {
                    scratchSection.padding(.top, 28)
                    Label("Pour l'honneur, entre amis : jamais d'argent ni de boisson en jeu.", systemImage: "info.circle")
                        .font(.footnote).foregroundStyle(NP.t2).padding(.top, 16)
                }
            } header: {
                familyChips.padding(.vertical, 10).background(NP.bg.opacity(0.92))
            }
        }
    }

    private var familyChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                NPChip(text: "Tout", selected: family == "all") { pickFamily("all") }
                ForEach(NPFamily.all, id: \.key) { f in
                    NPChip(text: "\(f.emoji) \(f.name)", selected: family == f.key) { pickFamily(f.key) }
                }
            }
            .padding(.horizontal, 20)
        }
        .padding(.horizontal, -20)
    }

    @ViewBuilder private func familySection(_ fam: NPFamily) -> some View {
        let items = templates.filter { $0.family == fam.key }
        if let first = items.first {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text("\(fam.emoji) \(fam.name)").font(.np(.title2)).foregroundStyle(NP.t1)
                    Text(fam.subtitle).font(.footnote.weight(.semibold)).foregroundStyle(NP.t2)
                }
                .accessibilityElement(children: .combine)
                .accessibilityAddTraits(.isHeader)
                featured(first, fam)
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: typeSize.isAccessibilitySize ? 1 : 2), spacing: 12) {
                    ForEach(items.dropFirst()) { tile($0, fam) }
                }
            }
            .padding(.top, 28)
        }
    }

    private func featured(_ t: NPTemplate, _ fam: NPFamily) -> some View {
        let g = GroupLook.gradient(fam.color)
        return Button { pick(t) } label: {
            HStack(alignment: .center, spacing: 12) {
                VStack(alignment: .leading, spacing: 8) {
                    NPKindBadge(kind: t.kind)
                    Text(t.title).font(.np(.title2)).foregroundStyle(NP.t1).multilineTextAlignment(.leading)
                    if let hint = t.hint, !hint.isEmpty {
                        Text(hint).font(.subheadline).foregroundStyle(NP.t2).multilineTextAlignment(.leading)
                    }
                }
                Spacer(minLength: 0)
                Text(t.emoji ?? NPKind.of(t.kind).emoji).font(.system(size: 52))
                    .frame(width: 92, height: 92)
                    .background(Circle().fill(.white.opacity(0.12)))
                    .accessibilityHidden(true)
            }
            .padding(18)
            .frame(maxWidth: .infinity, minHeight: 128, alignment: .leading)
            .background {
                ZStack {
                    NP.s1
                    LinearGradient(stops: [.init(color: .clear, location: 0.42), .init(color: g.to.opacity(0.95), location: 1)],
                                   startPoint: .leading, endPoint: .trailing)
                    RadialGradient(colors: [g.from.opacity(0.3), .clear], center: .topTrailing, startRadius: 0, endRadius: 160)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(NP.line))
        }
        .buttonStyle(NPPress())
        .accessibilityLabel("Modèle : \(t.title), \(NPKind.of(t.kind).label)")
        .accessibilityIdentifier("prono-template-\(t.id)")
    }

    private func tile(_ t: NPTemplate, _ fam: NPFamily) -> some View {
        let g = GroupLook.gradient(fam.color)
        return Button { pick(t) } label: {
            VStack(alignment: .leading, spacing: 10) {
                Text(t.emoji ?? NPKind.of(t.kind).emoji).font(.system(size: 24))
                    .frame(width: 44, height: 44)
                    .background(LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing),
                                in: RoundedRectangle(cornerRadius: 13, style: .continuous))
                    .accessibilityHidden(true)
                Text(t.title).font(.np(.headline)).foregroundStyle(NP.t1).multilineTextAlignment(.leading)
                Spacer(minLength: 0)
                NPKindBadge(kind: t.kind)
            }
            .padding(14)
            .frame(maxWidth: .infinity, minHeight: 156, alignment: .topLeading)
            .background {
                ZStack {
                    NP.s1
                    RadialGradient(colors: [g.to.opacity(0.3), .clear], center: .topLeading, startRadius: 0, endRadius: 160)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(NP.line))
        }
        .buttonStyle(NPPress())
        .accessibilityLabel("Modèle : \(t.title), \(NPKind.of(t.kind).label)")
        .accessibilityIdentifier("prono-template-\(t.id)")
    }

    private var scratchSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("✏️ Partir de zéro").font(.np(.title2)).foregroundStyle(NP.t1).accessibilityAddTraits(.isHeader)
            Text("Choisis la forme de la réponse, tu écris la question.").font(.subheadline).foregroundStyle(NP.t2)
            VStack(spacing: 0) {
                ForEach(Array(NPKind.all.enumerated()), id: \.element.id) { i, k in
                    Button { pickKind(k.id) } label: {
                        HStack(spacing: 14) {
                            NPKindTile(kind: k.id, size: 44)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(k.label).font(.body.weight(.semibold)).foregroundStyle(NP.t1)
                                Text(k.line).font(.footnote).foregroundStyle(NP.t2)
                            }
                            Spacer(minLength: 0)
                            Image(systemName: "chevron.right").font(.footnote.weight(.bold)).foregroundStyle(NP.t3)
                        }
                        .padding(.horizontal, 14)
                        .frame(minHeight: 64)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(NPPress())
                    .accessibilityLabel("\(k.label) : \(k.line)")
                    .accessibilityIdentifier("prono-kind-\(k.id)")
                    if i < NPKind.all.count - 1 { Divider().overlay(NP.line).padding(.leading, 72) }
                }
            }
            .npGlass(24)
            .padding(.top, 8)
        }
    }

    // MARK: - 2. La question

    private var questionStep: some View {
        VStack(alignment: .leading, spacing: 0) {
            liveLabel
            previewCard(launched: false).padding(.top, 10)
            if kind == "award" {
                awardSection
            } else {
                NPLabel(text: "Type de réponse").padding(.top, 28)
                kindChips.padding(.top, 10)
                questionField.padding(.top, 24)
                answersSection
                rulesSection
            }
        }
    }

    private var liveLabel: some View {
        HStack(spacing: 8) {
            Circle().fill(NP.mint).frame(width: 8, height: 8)
                .overlay(Circle().stroke(NP.mint, lineWidth: 2).scaleEffect(pulse ? 2.4 : 1).opacity(pulse ? 0 : 0.8))
                .onAppear {
                    guard !reduceMotion else { return }
                    withAnimation(.easeOut(duration: 1.6).repeatForever(autoreverses: false)) { pulse = true }
                }
            Text("APERÇU EN DIRECT").font(.footnote.weight(.semibold)).tracking(1.2).foregroundStyle(NP.t1)
            Spacer(minLength: 8)
            Text(audience).font(.footnote).foregroundStyle(NP.t2).lineLimit(1)
        }
        .accessibilityElement(children: .combine)
    }

    private func previewCard(launched: Bool) -> some View {
        NPCard(kind: kind,
               question: kind == "award" ? (awardCategory?.label ?? "Choisis un trophée") : trimmedQuestion,
               options: kind == "overunder" ? overUnderLabels : filled,
               awardEmoji: awardCategory?.emoji,
               coverColor: coverColor, emoji: pronoEmoji, place: place,
               endText: step == .question ? nil : NPDates.short(end),
               launched: launched, patates: launched && usesPatates)
            .animation(Motion.pick(NP.spring, reduced: reduceMotion), value: filled)
            .accessibilityIdentifier("prono-preview")
    }

    private var kindChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(NPKind.all.filter { $0.id != "award" }) { k in
                    NPChip(text: k.label, icon: k.icon, selected: kind == k.id) { setKind(k.id) }
                        .accessibilityIdentifier("prono-type-\(k.id)")
                }
            }
            .padding(.horizontal, 20)
        }
        .padding(.horizontal, -20)
    }

    private var questionField: some View {
        VStack(alignment: .leading, spacing: 10) {
            NPLabel(text: "Ta question")
            VStack(alignment: .trailing, spacing: 6) {
                TextField(NPKind.of(kind).placeholder, text: Binding(get: { question }, set: { v in
                    if v.contains("\n") {
                        question = String(v.replacingOccurrences(of: "\n", with: "").prefix(120))
                        focused = hasOptions ? .option(0) : nil
                    } else {
                        question = String(v.prefix(120))
                    }
                }), axis: .vertical)
                .font(.np(.title3)).foregroundStyle(NP.t1)
                .lineLimit(1...4)
                .submitLabel(.next)
                .focused($focused, equals: .question)
                .accessibilityIdentifier("prono-question")
                Text("\(question.count) / 120").font(.footnote.monospacedDigit()).foregroundStyle(NP.t3)
                    .accessibilityHidden(true)
            }
            .padding(16)
            .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(NP.lavender.opacity(focused == .question ? 0.22 : 0)).padding(-4))
            .npGlass(16, stroke: focused == .question ? NP.lavender : NP.line, width: focused == .question ? 2 : 1)
            .id(Field.question)
        }
    }

    @ViewBuilder private var answersSection: some View {
        switch kind {
        case "choice", "majority": optionsSection.padding(.top, 28)
        case "overunder": lineSection.padding(.top, 28)
        case "number", "when": notOverSection.padding(.top, 28)
        case "yesno": NPInfo(text: "Deux réponses créées d'office : ✓ Oui et ✕ Non.").padding(.top, 20)
        case "person": NPInfo(text: "Chacun choisit quelqu'un de la bande ; tu donnes la bonne personne à la fin.").padding(.top, 20)
        default: NPInfo(text: "Chacun écrit sa réponse, cachée jusqu'à l'heure de fin ; ensuite tu coches les bonnes.").padding(.top, 20)
        }
    }

    private var optionsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                NPLabel(text: kind == "majority" ? "Les choix" : "Les réponses")
                Spacer()
                NPCount(text: "\(options.count) sur 8")
            }
            if kind == "majority" {
                Text("À la fin, la réponse la plus choisie l'emporte : devine ce que pense la bande.")
                    .font(.footnote).foregroundStyle(NP.t2)
            }
            ForEach(options.indices, id: \.self) { i in optionRow(i) }
            if options.count < 8 {
                Button {
                    Haptics.selection()
                    Motion.animate(NP.spring) { options.append("") }
                    focused = .option(options.count - 1)
                } label: {
                    Label("Ajouter une réponse", systemImage: "plus")
                        .font(.headline).foregroundStyle(NP.lavenderText)
                        .padding(.leading, 20)
                        .frame(maxWidth: .infinity, minHeight: 58, alignment: .leading)
                        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .strokeBorder(NP.lineStrong, style: StrokeStyle(lineWidth: 1.5, dash: [5, 5])))
                        .contentShape(Rectangle())
                }
                .buttonStyle(NPPress())
                .accessibilityIdentifier("prono-option-add")
            }
        }
    }

    private func optionRow(_ i: Int) -> some View {
        let shape = NP.shape(i)
        return HStack(spacing: 12) {
            NPShapeMark(index: i, size: 36)
            TextField("Réponse \(i + 1)", text: Binding(
                get: { i < options.count ? options[i] : "" },
                set: { if i < options.count { options[i] = String($0.prefix(60)) } }))
            .font(.body.weight(.semibold)).foregroundStyle(NP.t1)
            .focused($focused, equals: .option(i))
            .submitLabel(i + 1 < options.count ? .next : .done)
            .onSubmit { focused = i + 1 < options.count ? .option(i + 1) : nil }
            .accessibilityLabel("Réponse \(i + 1), \(shape.name)")
            .accessibilityIdentifier("prono-option-\(i)")
            Menu {
                Button { move(i, by: -1) } label: { Label("Monter", systemImage: "arrow.up") }.disabled(i == 0)
                Button { move(i, by: 1) } label: { Label("Descendre", systemImage: "arrow.down") }.disabled(i + 1 >= options.count)
                Button(role: .destructive) { remove(i) } label: { Label("Retirer", systemImage: "trash") }.disabled(options.count <= 2)
            } label: {
                Image(systemName: "line.3.horizontal").font(.body.weight(.semibold)).foregroundStyle(NP.t3)
                    .frame(width: 44, height: 44).contentShape(Rectangle())
            }
            .accessibilityLabel("Déplacer ou retirer la réponse \(i + 1)")
        }
        .padding(.leading, 11)
        .padding(.trailing, 4)
        .frame(minHeight: 58)
        .npGlass(18, stroke: focused == .option(i) ? NP.lavender : NP.line, width: focused == .option(i) ? 2 : 1)
        .id(Field.option(i))
        .transition(reduceMotion ? .opacity : .scale(scale: 0.96).combined(with: .opacity))
    }

    private var lineSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                NPLabel(text: "La ligne")
                Spacer()
                NPCount(text: "en demi-unité")
            }
            VStack(spacing: 18) {
                HStack {
                    NPRound(icon: "minus", label: "Baisser la ligne") { stepLine(-1) }.disabled(line <= 0.5)
                    Spacer()
                    VStack(spacing: 0) {
                        Text(lineText)
                            .font(.system(size: lineDigits, weight: .heavy).width(.expanded).monospacedDigit())
                            .foregroundStyle(LinearGradient(colors: [.white, NP.lavender], startPoint: .top, endPoint: .bottom))
                            .contentTransition(.numericText())
                            .minimumScaleFactor(0.5).lineLimit(1)
                        if !unitShown.isEmpty {
                            Text(unitShown).font(.title3.weight(.semibold)).foregroundStyle(NP.t2)
                        }
                    }
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("Ligne : \(lineText) \(unitShown)")
                    .accessibilityAdjustableAction { dir in stepLine(dir == .increment ? 1 : -1) }
                    .accessibilityIdentifier("prono-line")
                    Spacer()
                    NPRound(icon: "plus", label: "Monter la ligne") { stepLine(1) }
                }
                NPAxis(line: line)
            }
            .padding(20)
            .npGlass(24)
            Text("Toujours une demi-unité : jamais d'égalité possible.").font(.subheadline).foregroundStyle(NP.t2)
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(["buts", "points", "minutes", "personnes"], id: \.self) { u in
                        NPChip(text: u, selected: unit == u) { unit = u }
                    }
                    NPChip(text: "Autre…", selected: unit == "other") { unit = "other"; focused = .unit }
                }
                .padding(.horizontal, 20)
            }
            .padding(.horizontal, -20)
            if unit == "other" {
                TextField("Ton unité (ex. : chansons)", text: Binding(get: { customUnit }, set: { customUnit = String($0.prefix(20)) }))
                    .font(.body.weight(.semibold))
                    .focused($focused, equals: .unit)
                    .submitLabel(.done)
                    .onSubmit { focused = nil }
                    .padding(.horizontal, 16).frame(minHeight: 52)
                    .npGlass(16, stroke: focused == .unit ? NP.lavender : NP.line, width: focused == .unit ? 2 : 1)
                    .id(Field.unit)
                    .accessibilityIdentifier("prono-unit")
            }
        }
    }

    private var notOverSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            NPLabel(text: "Comment on compte")
            Toggle(isOn: $notOver) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Sans dépasser").font(.headline).foregroundStyle(NP.t1)
                    Text(kind == "when" ? "Seules les heures avant la vraie heure comptent." : "Seuls les nombres sous le vrai nombre comptent.")
                        .font(.footnote).foregroundStyle(NP.t2)
                }
            }
            .tint(NP.lavenderDeep)
            .padding(16)
            .npGlass(20)
            .accessibilityIdentifier("prono-not-over")
            Text(kind == "when"
                 ? "L'heure la plus proche l'emporte ; le moment venu, « C'est arrivé ! » donne l'heure exacte."
                 : "Le nombre le plus proche l'emporte.")
                .font(.footnote).foregroundStyle(NP.t2)
        }
    }

    private var rulesSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                NPLabel(text: "Comment on tranche ?")
                Spacer()
                NPCount(text: "Facultatif")
            }
            TextField("Ex. : d'après le tableau d'affichage", text: Binding(get: { rules }, set: { rules = String($0.prefix(200)) }), axis: .vertical)
                .font(.body).foregroundStyle(NP.t1)
                .lineLimit(1...4)
                .focused($focused, equals: .rules)
                .padding(16)
                .frame(minHeight: 56, alignment: .leading)
                .npGlass(16, stroke: focused == .rules ? NP.lavender : NP.line, width: focused == .rules ? 2 : 1)
                .id(Field.rules)
                .accessibilityIdentifier("prono-rules")
            if let s = template?.rules, !s.isEmpty, rules != s {
                Button { Haptics.selection(); rules = s } label: {
                    Label(s, systemImage: "sparkles")
                        .font(.subheadline.weight(.semibold)).foregroundStyle(NP.lavenderText)
                        .padding(.horizontal, 14).frame(minHeight: 44)
                        .background(NP.lavender.opacity(0.12), in: Capsule())
                        .overlay(Capsule().strokeBorder(NP.lavender.opacity(0.35)))
                }
                .buttonStyle(NPPress())
                .accessibilityHint("Recopie cette règle")
            }
            Text("Écris-le avant que la bande joue : ensuite, on peut seulement le compléter.")
                .font(.footnote).foregroundStyle(NP.t2)
        }
        .padding(.top, 28)
    }

    private var awardSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                NPLabel(text: "Le trophée")
                Spacer()
                NPCount(text: "que du positif")
            }
            .padding(.top, 28)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: typeSize.isAccessibilitySize ? 1 : 2), spacing: 12) {
                ForEach(NPAward.all) { a in
                    let selected = award == a.id
                    Button {
                        Haptics.selection()
                        Motion.animate(NP.spring) { award = a.id }
                    } label: {
                        VStack(alignment: .leading, spacing: 10) {
                            Text(a.emoji).font(.title2).frame(width: 40, height: 40)
                                .background(NP.t1.opacity(0.08), in: Circle())
                                .accessibilityHidden(true)
                            Text(a.label).font(.subheadline.weight(.bold)).foregroundStyle(NP.t1)
                                .multilineTextAlignment(.leading).lineLimit(3)
                            Spacer(minLength: 0)
                        }
                        .padding(14)
                        .frame(maxWidth: .infinity, minHeight: 98, alignment: .topLeading)
                        .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(selected ? NP.lemon.opacity(0.12) : .clear))
                        .npGlass(18, stroke: selected ? NP.lemon : NP.line, width: selected ? 2 : 1)
                        .overlay(alignment: .topTrailing) {
                            if selected {
                                Image(systemName: "checkmark").font(.caption.weight(.heavy)).foregroundStyle(Color(red: 0.23, green: 0.16, blue: 0))
                                    .frame(width: 24, height: 24).background(NP.lemon, in: Circle())
                                    .overlay(Circle().stroke(NP.bg, lineWidth: 2))
                                    .offset(x: 6, y: -6)
                                    .transition(.scale.combined(with: .opacity))
                            }
                        }
                    }
                    .buttonStyle(NPPress())
                    .accessibilityLabel(a.label)
                    .accessibilityAddTraits(selected ? .isSelected : [])
                    .accessibilityIdentifier("prono-award-\(a.id)")
                }
            }
            NPLabel(text: "La question").padding(.top, 16)
            VStack(alignment: .leading, spacing: 8) {
                Text(awardCategory?.question ?? "Choisis un trophée : Party écrit la question.")
                    .font(.np(.title3)).foregroundStyle(awardCategory == nil ? NP.t3 : NP.t1)
                Label("Écrite par Party pour chaque trophée", systemImage: "lock.fill")
                    .font(.footnote.weight(.semibold)).foregroundStyle(NP.t2)
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .npGlass(20)
            .accessibilityElement(children: .combine)
            NPLabel(text: "Comment ça marche").padding(.top, 16)
            VStack(spacing: 0) {
                howRow("🗳️", "Chacun vote pour une personne,", " jamais pour soi.")
                Divider().overlay(NP.line).padding(.leading, 64)
                howRow("🔒", "Votes cachés", " jusqu'au dévoilement, 3 votes au moins.")
                Divider().overlay(NP.line).padding(.leading, 64)
                howRow("🏅", "Seul le ou la gagnant·e est annoncé·e,", " jamais les autres scores.")
                Divider().overlay(NP.line).padding(.leading, 64)
                howRow("🙋", "Chacun peut se retirer", " de la liste des nommés.")
            }
            .npGlass(24)
            Text("Pour l'honneur : jamais de patates pour un trophée.").font(.footnote).foregroundStyle(NP.t2)
        }
    }

    private func howRow(_ emoji: String, _ bold: String, _ rest: String) -> some View {
        HStack(alignment: .top, spacing: 14) {
            Text(emoji).frame(width: 34, height: 34).background(NP.t1.opacity(0.08), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                .accessibilityHidden(true)
            (Text(bold).bold().foregroundColor(NP.t1) + Text(rest).foregroundColor(NP.t2)).font(.subheadline)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16).padding(.vertical, 14)
        .accessibilityElement(children: .combine)
    }

    // MARK: - 3. Réglages

    private var settingsStep: some View {
        VStack(alignment: .leading, spacing: 0) {
            recapBand
            whoSection.padding(.top, 28)
            endSection.padding(.top, 28)
            if patatesPossible { patatesSection.padding(.top, 28) }
            if kind != "award" { pointsSection.padding(.top, 28) }
            if revealChoosable { revealSection.padding(.top, 28) }
        }
    }

    private var recapBand: some View {
        let k = NPKind.of(kind)
        let detail: String = {
            switch kind {
            case "choice", "majority": return "\(k.label) · \(filled.count) réponses"
            case "overunder": return "\(k.label) · ligne \(lineText) \(unitShown)"
            default: return k.label
            }
        }()
        return Button { go(.question) } label: {
            HStack(spacing: 0) {
                Text(pronoEmoji).font(.system(size: 30))
                    .frame(width: 68, height: 68)
                    .background(NP.cover(coverColor))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text(questionShown).font(.np(.headline)).foregroundStyle(NP.t1).lineLimit(1)
                    Label(detail, systemImage: k.icon).font(.footnote).foregroundStyle(NP.t2).lineLimit(1)
                }
                .padding(.horizontal, 14)
                Spacer(minLength: 0)
                Text("Modifier").font(.subheadline.weight(.bold)).foregroundStyle(NP.lavenderText).padding(.trailing, 14)
            }
            .frame(minHeight: 68)
            .npGlass(18)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .buttonStyle(NPPress())
        .accessibilityLabel("\(questionShown), \(detail). Modifier")
        .accessibilityIdentifier("prono-recap")
    }

    private var whoSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            NPLabel(text: "Qui joue")
            VStack(spacing: 10) {
                if event != nil {
                    NPRadioCard(selected: true, title: "Les participants de la soirée", detail: "Présent ou Peut-être, et l'organisation") {
                        GroupTile(emoji: "🎉", color: "lemon", size: 48)
                    } action: {}
                } else {
                    if groups.isEmpty {
                        Text("Pas encore de groupe : joue avec des personnes choisies ou un lien.")
                            .font(.subheadline).foregroundStyle(NP.t2)
                    }
                    ForEach(groups) { g in
                        NPRadioCard(selected: chosenGroup == g.id, title: "\(g.emoji) \(g.name)",
                                    detail: g.members.map { "\($0) membre\($0 > 1 ? "s" : ""), tous prévenus" } ?? "Tout le groupe est prévenu") {
                            GroupTile(emoji: g.emoji, color: g.color, size: 48)
                        } action: {
                            Haptics.selection()
                            Motion.animate(NP.spring) { chosenGroup = chosenGroup == g.id ? nil : g.id }
                        }
                        .accessibilityIdentifier("prono-group-\(g.id)")
                    }
                }
            }
            .accessibilityElement(children: .contain)
            .accessibilityIdentifier("prono-group-picker")
            if event == nil {
                NPFlow(spacing: 4) {
                    Text("Ou").foregroundStyle(NP.t2)
                    NavigationLink {
                        PronoPeoplePicker(suggestions: suggestions, selected: $people)
                    } label: {
                        Text("des personnes choisies").bold().foregroundStyle(NP.lavenderText).frame(minHeight: 44)
                    }
                    .accessibilityIdentifier("prono-people")
                    Text(",").foregroundStyle(NP.t2)
                    Button {
                        Haptics.selection()
                        Motion.animate(NP.spring) { link.toggle() }
                    } label: {
                        Text(link ? "un lien ✓" : "un lien").bold().foregroundStyle(NP.lavenderText).frame(minHeight: 44)
                    }
                    .accessibilityAddTraits(link ? .isSelected : [])
                    .accessibilityIdentifier("prono-link")
                    Text("· pour l'honneur").foregroundStyle(NP.t2)
                }
                .font(.subheadline)
                if !people.isEmpty || link {
                    HStack(spacing: 8) {
                        if !people.isEmpty {
                            NPRemovable(text: "👥 \(people.count) personne\(people.count > 1 ? "s" : "")") { people = [] }
                        }
                        if link { NPRemovable(text: "🔗 Lien à partager") { link = false } }
                    }
                }
            }
        }
    }

    private var endSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            NPLabel(text: "Fin des réponses")
            LazyVGrid(columns: [GridItem(.adaptive(minimum: typeSize.isAccessibilitySize ? 150 : 72), spacing: 8)], spacing: 8) {
                ForEach(NPDates.quick()) { q in
                    endTile(top: q.top, bottom: q.bottom, selected: endChoice == q.id) {
                        endChoice = q.id
                        end = q.date
                    }
                    .accessibilityIdentifier("prono-end-\(q.id)")
                }
                endTile(top: "Choisir…", bottom: nil, icon: "calendar", selected: endChoice == "custom") { pickingEnd = true }
                    .accessibilityIdentifier("prono-end-custom")
            }
            HStack(spacing: 14) {
                Image(systemName: "clock").font(.title3.weight(.semibold)).foregroundStyle(NP.amber)
                    .frame(width: 44, height: 44).background(NP.amber.opacity(0.14), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(NPDates.dayLong(end)).font(.headline).foregroundStyle(NP.t1)
                    Text(NPDates.relative(end)).font(.footnote).foregroundStyle(NP.t2)
                }
                Spacer(minLength: 8)
                Text(NPDates.time(end))
                    .font(.system(size: endDigits, weight: .heavy).width(.expanded).monospacedDigit())
                    .foregroundStyle(NP.t1)
                    .contentTransition(.numericText())
            }
            .padding(16)
            .npGlass(20)
            .animation(Motion.pick(NP.spring, reduced: reduceMotion), value: end)
            .accessibilityElement(children: .combine)
            .accessibilityIdentifier("prono-end")
        }
    }

    private func endTile(top: String, bottom: String?, icon: String? = nil, selected: Bool, action: @escaping () -> Void) -> some View {
        Button {
            Haptics.selection()
            Motion.animate(NP.spring) { action() }
        } label: {
            VStack(spacing: 3) {
                if let icon { Image(systemName: icon).font(.subheadline) }
                Text(top).font(.subheadline.weight(.bold)).lineLimit(1).minimumScaleFactor(0.8)
                if let bottom { Text(bottom).font(.system(.callout, weight: .heavy).width(.expanded).monospacedDigit()) }
            }
            .foregroundStyle(selected ? NP.bg : NP.t1)
            .frame(maxWidth: .infinity, minHeight: 62)
            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(selected ? NP.t1 : .clear))
            .npGlass(16, stroke: selected ? .clear : NP.line)
        }
        .buttonStyle(NPPress())
        .accessibilityLabel([top, bottom].compactMap { $0 }.joined(separator: " "))
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private var endPicker: some View {
        NavigationStack {
            ScrollView {
                DatePicker("Fin des réponses", selection: Binding(get: { end }, set: { end = $0; endChoice = "custom" }),
                           in: Date().addingTimeInterval(600)..., displayedComponents: [.date, .hourAndMinute])
                    .datePickerStyle(.graphical)
                    .tint(NP.lavenderDeep)
                    .environment(\.timeZone, NPDates.zone)
                    .padding()
            }
            .navigationTitle("Fin des réponses")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("OK") { endChoice = "custom"; pickingEnd = false }.bold().accessibilityIdentifier("prono-end-ok")
                }
            }
        }
        .presentationDetents([.large])
    }

    private var patatesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                NPLabel(text: "Patates 🥔")
                Spacer()
                if !terrainName.isEmpty { NPCount(text: terrainName) }
            }
            HStack(spacing: 12) {
                NPChoiceCard(emoji: "🥔", title: "Avec patates", detail: "De 0 à 20 chacun", selected: patates) {
                    patates = true
                }
                .accessibilityIdentifier("prono-patates-on")
                NPChoiceCard(emoji: "🏅", title: "Pour l'honneur", detail: "Seulement des points", selected: !patates) {
                    patates = false
                }
                .accessibilityIdentifier("prono-patates-off")
            }
            if patates {
                VStack(spacing: 14) {
                    HStack(alignment: .top, spacing: 4) {
                        patateStep("🥔", "On plante", "0 à 20 de ton sac")
                        Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(NP.t3).padding(.top, 22)
                        patateStep("🌱", "Le champ", "grandit en secret")
                        Image(systemName: "chevron.right").font(.caption.weight(.bold)).foregroundStyle(NP.t3).padding(.top, 22)
                        patateStep("🧺", "La récolte", "pour qui a vu juste")
                    }
                    .accessibilityElement(children: .combine)
                    Divider().overlay(NP.amber.opacity(0.25))
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "info.circle").foregroundStyle(NP.amber).accessibilityHidden(true)
                        (Text("Les patates n'ont aucune valeur : ").bold().foregroundColor(NP.t1)
                         + Text("elles ne s'achètent pas, ne se vendent pas, ne s'échangent pas. Personne n'a vu juste ? Chacun récupère les siennes.")
                            .foregroundColor(NP.t2))
                            .font(.subheadline)
                    }
                    .accessibilityElement(children: .combine)
                    .accessibilityIdentifier("prono-patates-no-value")
                }
                .padding(16)
                .background(RoundedRectangle(cornerRadius: 20, style: .continuous).fill(NP.amberSurface))
                .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(NP.amber.opacity(0.25)))
                .transition(.opacity)
            }
        }
    }

    private func patateStep(_ emoji: String, _ title: String, _ detail: String) -> some View {
        VStack(spacing: 6) {
            Text(emoji).font(.title2).frame(width: 48, height: 48)
                .background(NP.t1.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            Text(title).font(.subheadline.weight(.heavy)).foregroundStyle(NP.t1)
            Text(detail).font(.caption).foregroundStyle(NP.t2).multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }

    private var pointsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            NPLabel(text: "Points au classement")
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline, spacing: 12) {
                    Text("\(points)").font(.system(size: pointsDigits, weight: .heavy).width(.expanded).monospacedDigit())
                        .foregroundStyle(NP.t1).contentTransition(.numericText())
                    Text(points > 1 ? "points pour qui voit juste" : "point pour qui voit juste")
                        .font(.headline).foregroundStyle(NP.t2)
                }
                .accessibilityHidden(true)
                Slider(value: Binding(get: { Double(points) }, set: { v in
                    let n = Int(v.rounded())
                    if n != points { Haptics.selection(); Motion.animate(Motion.snappy) { points = n } }
                }), in: 1...10, step: 1)
                .tint(NP.lavender)
                .accessibilityLabel("Points pour qui voit juste")
                .accessibilityValue("\(points)")
                .accessibilityIdentifier("prono-points")
                HStack { Text("1"); Spacer(); Text("5"); Spacer(); Text("10") }
                    .font(.caption.monospacedDigit()).foregroundStyle(NP.t3).accessibilityHidden(true)
            }
            .padding(18)
            .npGlass(24)
        }
    }

    private var revealSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            NPLabel(text: "Dévoilement")
            HStack(alignment: .top, spacing: 12) {
                NPChoiceCard(emoji: "⏳", title: "À la fin", detail: "Tout s'ouvre seul à l'heure de fin.", selected: reveal == "close", tile: true) {
                    reveal = "close"
                }
                .accessibilityIdentifier("prono-reveal-close")
                NPChoiceCard(emoji: "🎤", title: "Avec le résultat", detail: "Tu dévoiles en donnant la bonne réponse.", selected: reveal == "result", tile: true) {
                    reveal = "result"
                }
                .accessibilityIdentifier("prono-reveal-result")
            }
        }
    }

    private var summary: String {
        let who: String = {
            if let chosen { return chosen.members.map { "\($0) \(chosen.name)" } ?? chosen.name }
            if event != nil { return "les participants" }
            if !people.isEmpty { return "\(people.count) personne\(people.count > 1 ? "s" : "")" }
            return link ? "par lien" : "choisis qui joue"
        }()
        return [who, "fin \(NPDates.short(end))", usesPatates ? "avec patates 🥔" : "pour l'honneur"].joined(separator: " · ")
    }

    // MARK: - 4. C'est lancé !

    private var launchedStep: some View {
        VStack(spacing: 0) {
            ZStack {
                NPRays(spinning: rays && !reduceMotion)
                    .frame(width: 640, height: 640)
                    .allowsHitTesting(false)
                Circle().stroke(NP.lavender, lineWidth: 2)
                    .frame(width: 220, height: 220)
                    .scaleEffect(ripple ? 1 : 0.5).opacity(ripple ? 0 : (sealIn ? 0.5 : 0))
                seal
                    .scaleEffect(sealIn ? 1 : 1.35).opacity(sealIn ? 1 : 0)
            }
            .frame(height: 190)
            .padding(.top, 8)
            VStack(spacing: 10) {
                Text("C'est lancé !").font(.system(.largeTitle, design: .rounded, weight: .heavy)).foregroundStyle(NP.t1)
                    .accessibilityAddTraits(.isHeader)
                (Text(launchedWho).bold().foregroundColor(NP.t1)
                 + Text(" Les réponses restent scellées jusqu'au dévoilement.").foregroundColor(NP.t2))
                    .font(.callout).multilineTextAlignment(.center)
            }
            .padding(.top, 12)
            .opacity(textIn ? 1 : 0).offset(y: textIn || reduceMotion ? 0 : 14)
            previewCard(launched: true)
                .padding(.top, 26)
                .opacity(cardIn ? 1 : 0).offset(y: cardIn || reduceMotion ? 0 : 24)
            VStack(alignment: .leading, spacing: 10) {
                NPLabel(text: "Invite la bande")
                if let url = createdURL {
                    linkField(url)
                    HStack(spacing: 10) {
                        ShareLink(item: url, subject: Text("Un prono pour toi"), message: Text(questionShown)) {
                            NPShareTile(icon: "square.and.arrow.up", title: "Partager…", tint: Color(red: 0.24, green: 0.55, blue: 1))
                        }
                        .accessibilityIdentifier("prono-share")
                        Button { Haptics.tap(); showQR = true } label: {
                            NPShareTile(icon: "qrcode", title: "QR code", tint: NP.lavender)
                        }
                        .accessibilityIdentifier("prono-qr")
                    }
                    .buttonStyle(NPPress())
                    Text("Aucune récompense pour le partage : c'est juste pour inviter.")
                        .font(.caption).foregroundStyle(NP.t3)
                }
                NPPrimary(title: "Jouer maintenant", trailing: "arrow.right", enabled: createdID != nil) {
                    if let createdID { created(createdID) }
                }
                .padding(.top, 14)
                .accessibilityIdentifier("prono-play-now")
                Button { dismiss() } label: {
                    Text("Voir mes pronos").font(.headline).foregroundStyle(NP.lavenderText)
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .accessibilityIdentifier("prono-see-list")
            }
            .padding(.top, 28)
            .opacity(shareIn ? 1 : 0)
        }
        .onAppear(perform: choreograph)
    }

    private var seal: some View {
        ZStack(alignment: .bottomTrailing) {
            Circle().fill(NP.cover(coverColor)).frame(width: 112, height: 112)
                .overlay(Circle().fill(NP.s1).padding(4))
                .overlay(Circle().fill(NP.glass).padding(4))
                .overlay(Text(pronoEmoji).font(.system(size: 50)))
                .shadow(color: GroupLook.gradient(coverColor).to.opacity(0.5), radius: 24)
            Image(systemName: "lock.fill").font(.system(size: 14, weight: .bold)).foregroundStyle(.white)
                .frame(width: 34, height: 34).background(NP.lavenderDeep, in: Circle())
                .overlay(Circle().stroke(NP.bg, lineWidth: 3))
                .offset(x: 2, y: 2)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Prono scellé")
    }

    private var launchedWho: String {
        if let chosen { return "Tout le groupe « \(chosen.name) » est prévenu." }
        if event != nil { return "Les participants sont prévenus." }
        if !people.isEmpty { return people.count > 1 ? "\(people.count) personnes sont prévenues." : "1 personne est prévenue." }
        return "Partage le lien : qui l'ouvre se connecte à Party, puis joue."
    }

    private func linkField(_ url: URL) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "link").foregroundStyle(NP.t2).accessibilityHidden(true)
            (Text(url.host ?? "").foregroundColor(NP.t1) + Text(url.path).foregroundColor(NP.t2))
                .font(.subheadline.weight(.semibold)).lineLimit(1).truncationMode(.tail)
            Spacer(minLength: 4)
            Button {
                UIPasteboard.general.url = url
                Haptics.success()
                Motion.animate(Motion.snappy) { copied = true }
                Task {
                    try? await Task.sleep(nanoseconds: 1_500_000_000)
                    Motion.animate(Motion.snappy) { copied = false }
                }
            } label: {
                Label(copied ? "Copié ✓" : "Copier", systemImage: copied ? "checkmark" : "doc.on.doc")
                    .font(.headline).foregroundStyle(.white)
                    .padding(.horizontal, 16).frame(minHeight: 44)
                    .background(NP.lavenderDeep, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .accessibilityLabel(copied ? "Lien copié" : "Copier le lien")
            .accessibilityIdentifier("prono-copy-link")
        }
        .padding(.leading, 16).padding(.trailing, 6)
        .frame(minHeight: 56)
        .npGlass(18)
    }

    private var qrSheet: some View {
        NavigationStack {
            VStack(spacing: 20) {
                if let url = createdURL, let image = NPQR.image(url.absoluteString) {
                    Image(uiImage: image).interpolation(.none).resizable().scaledToFit()
                        .padding(20)
                        .background(.white, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                        .padding(.horizontal, 32)
                        .accessibilityLabel("QR code du prono")
                }
                Text(questionShown).font(.np(.title3)).foregroundStyle(NP.t1).multilineTextAlignment(.center).padding(.horizontal, 24)
                Text("Scanne avec l'appareil photo pour jouer.").font(.subheadline).foregroundStyle(NP.t2)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(NP.bg.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("OK") { showQR = false }.bold() }
            }
        }
    }

    private func choreograph() {
        guard !sealIn else { return }
        if reduceMotion {
            withAnimation(.easeInOut(duration: 0.15)) { sealIn = true; textIn = true; cardIn = true; shareIn = true }
            Haptics.success()
            return
        }
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 120_000_000)
            withAnimation(.spring(response: 0.42, dampingFraction: 0.6)) { sealIn = true }
            withAnimation(.easeOut(duration: 0.7)) { ripple = true }
            Haptics.success()
            rays = true
            try? await Task.sleep(nanoseconds: 180_000_000)
            withAnimation(NP.spring) { textIn = true }
            try? await Task.sleep(nanoseconds: 120_000_000)
            withAnimation(.spring(response: 0.5, dampingFraction: 0.8)) { cardIn = true }
            try? await Task.sleep(nanoseconds: 180_000_000)
            withAnimation(.easeOut(duration: 0.3)) { shareIn = true }
        }
    }

    // MARK: - Actions

    private func go(_ next: Step) {
        hideKeyboard()
        forward = next.rawValue > step.rawValue
        Haptics.selection()
        Motion.animate(Motion.smooth) { step = next }
        if next == .question && kind != "award" && trimmedQuestion.isEmpty {
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: 450_000_000)
                focused = .question
            }
        }
    }

    private func pickFamily(_ key: String) {
        Haptics.selection()
        Motion.animate(Motion.snappy) { family = key }
    }

    private func pick(_ t: NPTemplate) {
        apply(t)
        go(.question)
    }

    /// Recopie un modèle (question, réponses, ligne, trophée) ; tout reste modifiable.
    private func apply(_ t: NPTemplate) {
        template = t
        kind = NPKind.of(t.kind).id
        question = String((t.question ?? t.title).prefix(120))
        options = (t.options ?? []).isEmpty ? ["", ""] : Array((t.options ?? []).prefix(8))
        if options.count < 2 { options.append("") }
        if let l = t.line { line = l == l.rounded() ? l + 0.5 : l }
        if let u = t.unit, !u.isEmpty {
            if ["buts", "points", "minutes", "personnes"].contains(u) { unit = u } else { unit = "other"; customUnit = u }
        }
        award = kind == "award" ? (t.award.flatMap { a in NPAward.all.first { $0.id == a }?.id }) : nil
        rules = ""
        notOver = false
    }

    private func pickKind(_ k: String) {
        template = nil
        kind = k
        question = ""
        options = ["", ""]
        award = nil
        rules = ""
        notOver = false
        go(.question)
    }

    private func setKind(_ k: String) {
        guard k != kind else { return }
        Haptics.selection()
        Motion.animate(NP.spring) {
            kind = k
            if (k == "choice" || k == "majority") && options.count < 2 { options = ["", ""] }
        }
    }

    private func move(_ i: Int, by d: Int) {
        let j = i + d
        guard options.indices.contains(i), options.indices.contains(j) else { return }
        Haptics.selection()
        Motion.animate(NP.spring) { options.swapAt(i, j) }
    }

    private func remove(_ i: Int) {
        guard options.count > 2, options.indices.contains(i) else { return }
        focused = nil
        Haptics.tap()
        Motion.animate(NP.spring) { _ = options.remove(at: i) }
    }

    private func stepLine(_ d: Int) {
        let next = line + Double(d)
        guard next >= 0.5, next <= 999.5 else { return }
        Haptics.selection()
        Motion.animate(NP.spring) { line = next }
    }

    private func hideKeyboard() {
        focused = nil
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }

    private func loadChoices() async {
        // Mes groupes (jamais Membres Vendredi Party : la base le refuse aussi), les personnes croisées et les modèles.
        let list: [NPTemplate] = (try? await store.call("prono_templates")) ?? []
        Motion.animate(Motion.smooth) {
            templates = list.filter { !$0.mentionsAlcohol }
            loadingTemplates = false
        }
        // Modèle choisi depuis la liste : on complète avec la version de la base (réponses, ligne, trophée) tant que
        // la question n'a pas été retouchée.
        if let initialTemplate, let full = templates.first(where: { $0.id == initialTemplate.id }),
           template?.id == full.id, question == String((full.question ?? full.title).prefix(120)) {
            apply(full)
        }
        if let list: [MyGroup] = try? await store.call("my_groups_overview") { groups = list.filter { !$0.system && $0.member } }
        if let list: [PronoFace] = try? await store.call("prono_suggestions") { suggestions = list }
    }

    /// Le sac du terrain (prono_bag) : sa réponse dit aussi si la base a les patates allumées.
    private func loadBag() async {
        guard store.features.patates, !terrainKey.isEmpty else { bagOn = false; return }
        struct Bag: Decodable { let balance: Int?; let patatesOn: Bool? }
        var args: [String: Any] = [:]
        if let event { args["event_id"] = event } else if let chosenGroup { args["group_id"] = chosenGroup }
        let bag: Bag?? = try? await store.call("prono_bag", args)
        bagOn = (bag ?? nil).map { $0.patatesOn != false } ?? false
    }

    private func create() {
        guard ready else { return }
        guard end > Date().addingTimeInterval(600) else {
            Haptics.warning()
            error = "Choisis une fin dans au moins 10 minutes."
            return
        }
        busy = true
        error = nil
        var body: [String: Any] = [
            "question": questionShown, "kind": kind, "points": kind == "award" ? 1 : points,
            "closes_at": ISO8601DateFormatter().string(from: end),
            "reveal": revealChoosable ? reveal : "close",
            "people": Array(people), "link": link,
            "patates": usesPatates,
        ]
        if hasOptions { body["options"] = filled }
        if kind == "overunder" {
            body["line"] = line
            body["options"] = overUnderLabels
        }
        if kind == "number" || kind == "when" { body["not_over"] = notOver }
        if kind == "award", let award { body["award"] = award }
        let r = rules.trimmingCharacters(in: .whitespacesAndNewlines)
        if !r.isEmpty, kind != "award" { body["rules"] = r }
        if let template { body["template"] = template.id }
        if let event { body["event_id"] = event } else if let chosenGroup { body["group_id"] = chosenGroup }
        Task {
            defer { busy = false }
            do {
                let made: NPCreated = try await store.call("prono_create", ["body": body])
                createdID = made.id
                let path = made.link?.path ?? "/events/prono/\(made.id)"
                createdURL = URL(string: path, relativeTo: AppConfig.baseURL)?.absoluteURL
                forward = true
                Motion.animate(Motion.smooth) { step = .launched }
                await store.refreshBadge()
            } catch PartyAPIError.termsRequired {
                askTerms = true
            } catch {
                Haptics.error()
                self.error = PronosStore.message(error)
            }
        }
    }
}

/// Choisir des personnes croisées dans Party (événements, groupes) ; jamais tout le site. Pour l'honneur seulement.
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
                            .foregroundStyle(selected.contains(f.id) ? NP.lavenderDeep : .secondary)
                    }
                }
                .accessibilityAddTraits(selected.contains(f.id) ? .isSelected : [])
            }
        }
        .searchable(text: $search, prompt: "Chercher")
        .scrollContentBackground(.hidden)
        .background(NP.bg.ignoresSafeArea())
        .navigationTitle("Des personnes")
    }
}

// MARK: - Données de l'écran

/// Modèle prêt de la base (prono_templates) ; jamais d'alcool (filtré aussi ici, par sécurité).
private struct NPTemplate: Decodable, Identifiable, Hashable {
    let id: String
    let kind: String
    let emoji: String?
    let title: String
    let question: String?
    let options: [String]?
    let line: Double?
    let award: String?
    let hint: String?
    let rules: String?
    let unit: String?
    let family: String?

    private enum CodingKeys: String, CodingKey { case id, kind, emoji, title, question, options, line, award, hint, rules, unit, family }

    init(id: String, kind: String, emoji: String?, title: String, question: String?, hint: String?) {
        self.id = id
        self.kind = kind
        self.emoji = emoji
        self.title = title
        self.question = question
        self.hint = hint
        options = nil
        line = nil
        award = nil
        rules = nil
        unit = nil
        family = NPTemplate.family(raw: nil, id: id, kind: kind, title: title)
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(String.self, forKey: .id)
        kind = try c.decode(String.self, forKey: .kind)
        emoji = try c.decodeIfPresent(String.self, forKey: .emoji)
        title = try c.decode(String.self, forKey: .title)
        question = try c.decodeIfPresent(String.self, forKey: .question)
        options = try? c.decodeIfPresent([String].self, forKey: .options)
        line = try? c.decodeIfPresent(Double.self, forKey: .line)
        award = try c.decodeIfPresent(String.self, forKey: .award)
        hint = try c.decodeIfPresent(String.self, forKey: .hint)
        rules = try c.decodeIfPresent(String.self, forKey: .rules)
        unit = try c.decodeIfPresent(String.self, forKey: .unit)
        let raw = try c.decodeIfPresent(String.self, forKey: .family)
        family = NPTemplate.family(raw: raw, id: id, kind: kind, title: title)
    }

    /// Famille d'affichage : celle de la base si elle la donne, sinon devinée (Soirée, Sport, La bande, Votes).
    private static func family(raw: String?, id: String, kind: String, title: String) -> String {
        if let raw, NPFamily.all.contains(where: { $0.key == raw }) { return raw }
        let t = (id + " " + title).lowercased().folding(options: .diacriticInsensitive, locale: Locale(identifier: "fr"))
        if kind == "award" || ["prefere", "theme", "vote"].contains(where: t.contains) { return "votes" }
        if ["match", "foot", "sport", "but", "ping", "baby", "tournoi", "score", "equipe", "course"].contains(where: t.contains) { return "sport" }
        if kind == "majority" || ["bande", "karaoke"].contains(where: t.contains) { return "bande" }
        return "soiree"
    }

    var mentionsAlcohol: Bool {
        let t = ([title, question ?? "", hint ?? ""] + (options ?? [])).joined(separator: " ").lowercased()
            .folding(options: .diacriticInsensitive, locale: Locale(identifier: "fr"))
        return ["biere", "alcool", "vodka", "shot", "cocktail", "gorgee", "whisky", "rhum", "tequila", "pinte", "ivre",
                "cuite", "bourre", "vin ", "champagne", "beer", "apero"].contains(where: t.contains)
    }
}

private struct NPCreated: Decodable {
    struct Link: Decodable { let token: String?; let path: String? }
    let id: String
    let link: Link?
}

private struct NPFamily {
    let key, emoji, name, subtitle, color: String
    static let all = [
        NPFamily(key: "soiree", emoji: "🌙", name: "Soirée", subtitle: "pour ce soir", color: "coral"),
        NPFamily(key: "sport", emoji: "⚽", name: "Sport", subtitle: "match, tournoi, baby-foot", color: "mint"),
        NPFamily(key: "bande", emoji: "👯", name: "La bande", subtitle: "entre vous", color: "sky"),
        NPFamily(key: "votes", emoji: "🏆", name: "Votes", subtitle: "la bande décide", color: "rose"),
    ]
}

private struct NPKind: Identifiable {
    let id, label, icon, line, color, emoji, placeholder: String
    static let all = [
        NPKind(id: "choice", label: "Choix", icon: "square.grid.2x2.fill", line: "De 2 à 8 réponses, une seule juste", color: "lavender", emoji: "🔮", placeholder: "Le match de ce soir : qui l'emporte ?"),
        NPKind(id: "yesno", label: "Oui / Non", icon: "checkmark.circle", line: "Ça arrive, ou pas ?", color: "mint", emoji: "🤔", placeholder: "Léa chante au karaoké ?"),
        NPKind(id: "overunder", label: "Plus / Moins", icon: "arrow.up.arrow.down", line: "Au-dessus ou sous la ligne", color: "sky", emoji: "📈", placeholder: "Plus ou moins de 7,5 buts ?"),
        NPKind(id: "number", label: "Nombre", icon: "scope", line: "Le plus proche l'emporte", color: "coral", emoji: "🎯", placeholder: "Combien sur la piste à minuit ?"),
        NPKind(id: "when", label: "Heure", icon: "clock", line: "À quelle heure ça arrive ?", color: "lemon", emoji: "⏰", placeholder: "À quelle heure Marc arrive ?"),
        NPKind(id: "person", label: "Une personne", icon: "person.crop.circle", line: "Quelqu'un de la bande", color: "rose", emoji: "🙋", placeholder: "Qui arrive en dernier ?"),
        NPKind(id: "text", label: "Réponse libre", icon: "text.bubble", line: "Chacun écrit, tu tranches à la fin", color: "slate", emoji: "💬", placeholder: "Le thème de la prochaine soirée ?"),
        NPKind(id: "majority", label: "Devine la bande", icon: "person.3.fill", line: "Trouve ce que la majorité choisira", color: "sky", emoji: "🧠", placeholder: "Tu préfères : montagne ou mer ?"),
        NPKind(id: "award", label: "Trophée", icon: "trophy.fill", line: "Un prix positif, voté par tous", color: "lemon", emoji: "🏆", placeholder: ""),
    ]
    static func of(_ id: String) -> NPKind { all.first { $0.id == id } ?? all[0] }
}

/// Trophées : liste FERMÉE et positive (private.prono_award_categories) ; la question est écrite par Party.
private struct NPAward: Identifiable {
    let id, emoji, label, question: String
    static let all = [
        NPAward(id: "ambiance", emoji: "🎉", label: "Ambianceur·euse", question: "Qui met le plus l'ambiance ce soir ?"),
        NPAward(id: "piste", emoji: "💃", label: "Roi / Reine de la piste", question: "Qui est le roi ou la reine de la piste ce soir ?"),
        NPAward(id: "fou_rire", emoji: "😂", label: "Fou rire", question: "Qui nous a le plus fait rire ce soir ?"),
        NPAward(id: "look", emoji: "👗", label: "Meilleur look", question: "Qui a le meilleur look ce soir ?"),
        NPAward(id: "chef", emoji: "🍳", label: "Chef·fe de la soirée", question: "Qui est le chef ou la cheffe de la soirée ?"),
        NPAward(id: "voix", emoji: "🎤", label: "Voix d'or", question: "Qui a la voix d'or ce soir ?"),
        NPAward(id: "accueil", emoji: "🤝", label: "Le / la plus accueillant·e", question: "Qui est le ou la plus accueillant·e ce soir ?"),
        NPAward(id: "danse", emoji: "🕺", label: "Danse de la soirée", question: "Qui a fait la danse de la soirée ?"),
    ]
}

/// Dates en heure de Suisse : puces rapides de fin, libellés.
private enum NPDates {
    static let zone = TimeZone(identifier: "Europe/Zurich") ?? .current
    static let calendar: Calendar = {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = zone
        c.locale = Locale(identifier: "fr_CH")
        c.firstWeekday = 2
        return c
    }()

    struct Quick: Identifiable { let id, top, bottom: String; let date: Date }

    static func at(days: Int, hour: Int, from now: Date = Date()) -> Date {
        let day = calendar.date(byAdding: .day, value: days, to: calendar.startOfDay(for: now)) ?? now
        return calendar.date(bySettingHour: hour, minute: 0, second: 0, of: day) ?? day
    }

    static func quick(now: Date = Date()) -> [Quick] {
        var list: [Quick] = []
        let tonight = at(days: 0, hour: 23, from: now)
        if tonight > now.addingTimeInterval(1800) { list.append(Quick(id: "tonight", top: "Ce soir", bottom: "23:00", date: tonight)) }
        list.append(Quick(id: "tomorrow", top: "Demain", bottom: "20:00", date: at(days: 1, hour: 20, from: now)))
        let from = calendar.date(byAdding: .day, value: 2, to: calendar.startOfDay(for: now)) ?? now
        if let sat = calendar.nextDate(after: from, matching: DateComponents(hour: 20, minute: 0, weekday: 7), matchingPolicy: .nextTime) {
            list.append(Quick(id: "saturday", top: "Samedi", bottom: "20:00", date: sat))
        }
        if list.count < 3 { list.append(Quick(id: "week", top: "Dans 1 sem.", bottom: "20:00", date: at(days: 7, hour: 20, from: now))) }
        return list
    }

    private static func format(_ pattern: String, _ d: Date) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "fr_CH")
        f.timeZone = zone
        f.dateFormat = pattern
        return f.string(from: d)
    }

    static func dayLong(_ d: Date) -> String {
        let s = format("EEE d MMMM", d)
        return s.prefix(1).uppercased() + s.dropFirst()
    }

    static func time(_ d: Date) -> String { format("HH:mm", d) }
    static func short(_ d: Date) -> String { format("EEE HH:mm", d) }

    static func relative(_ d: Date, now: Date = Date()) -> String {
        let n = calendar.dateComponents([.day], from: calendar.startOfDay(for: now), to: calendar.startOfDay(for: d)).day ?? 0
        switch n {
        case ..<1: return "aujourd'hui"
        case 1: return "demain"
        default: return "dans \(n) jours"
        }
    }

    /// « 7,5 » (toujours une demi-unité pour Plus / Moins).
    static func half(_ v: Double) -> String {
        v == v.rounded() ? String(Int(v)) : String(format: "%.1f", v).replacingOccurrences(of: ".", with: ",")
    }
}

private enum NPQR {
    static func image(_ text: String) -> UIImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let out = filter.outputImage?.transformed(by: CGAffineTransform(scaleX: 12, y: 12)),
              let cg = CIContext().createCGImage(out, from: out.extent) else { return nil }
        return UIImage(cgImage: cg)
    }
}

// MARK: - Jetons et petites pièces (direction C « Néon club », maquettes 2-*)
// Locaux à cet écran : le kit commun (PronoKit.swift) peut les remplacer sans rien changer au parcours.

private enum NP {
    static func rgb(_ v: UInt32) -> UIColor {
        UIColor(red: CGFloat((v >> 16) & 0xFF) / 255, green: CGFloat((v >> 8) & 0xFF) / 255, blue: CGFloat(v & 0xFF) / 255, alpha: 1)
    }
    static func dyn(_ dark: UInt32, _ light: UInt32, _ darkAlpha: CGFloat = 1, _ lightAlpha: CGFloat = 1) -> Color {
        Color(UIColor { t in
            t.userInterfaceStyle == .dark ? rgb(dark).withAlphaComponent(darkAlpha) : rgb(light).withAlphaComponent(lightAlpha)
        })
    }
    static func hex(_ v: UInt32) -> Color { Color(rgb(v)) }

    static let bg = dyn(0x0E0A1F, 0xF6F3FF)
    static let s1 = dyn(0x1A1433, 0xFFFFFF)
    static let glass = dyn(0x251D47, 0xFFFFFF, 0.8, 0.82)
    static let line = dyn(0xFFFFFF, 0x1D1530, 0.08, 0.09)
    static let lineStrong = dyn(0xFFFFFF, 0x1D1530, 0.14, 0.16)
    static let t1 = dyn(0xF4F1FF, 0x1D1530)
    static let t2 = dyn(0xA79FC7, 0x554C78)
    static let t3 = dyn(0x8F88AE, 0x6A6290)
    static let lavender = hex(0xB9A7FF)
    static let lavenderDeep = hex(0x7B6CF6)
    static let lavenderText = dyn(0xC9BCFF, 0x5B4BD6)
    static let mint = hex(0x5BE3A6)
    static let lemon = hex(0xFFE27A)
    static let lemonText = dyn(0xFFE27A, 0x8A6200)
    static let amber = dyn(0xFFB347, 0xB86A00)
    static let amberSurface = dyn(0x1F1828, 0xFFF7EA)
    static let actionFill = hex(0xD42A76)
    static let action = LinearGradient(colors: [hex(0xE52A80), hex(0xD42A76)], startPoint: .top, endPoint: .bottom)
    static let spring = Animation.spring(response: 0.35, dampingFraction: 0.7)

    struct ShapeInfo { let symbol: String; let color: Color; let name: String }
    static let shapes = [
        ShapeInfo(symbol: "triangle.fill", color: hex(0xFF5FA2), name: "triangle"),
        ShapeInfo(symbol: "diamond.fill", color: hex(0x4D9BFF), name: "losange"),
        ShapeInfo(symbol: "circle.fill", color: hex(0xFFC24D), name: "rond"),
        ShapeInfo(symbol: "square.fill", color: hex(0x3FD08F), name: "carré"),
        ShapeInfo(symbol: "star.fill", color: hex(0xA08CFF), name: "étoile"),
        ShapeInfo(symbol: "hexagon.fill", color: hex(0xFF8A5C), name: "hexagone"),
        ShapeInfo(symbol: "seal.fill", color: hex(0x5BE3A6), name: "sceau"),
        ShapeInfo(symbol: "heart.fill", color: hex(0xFFE27A), name: "cœur"),
    ]
    static func shape(_ i: Int) -> ShapeInfo { shapes[i % shapes.count] }

    static func cover(_ color: String?) -> LinearGradient {
        let g: (from: Color, to: Color) = color == "slate" ? (hex(0x9C95C2), hex(0x5E5784)) : GroupLook.gradient(color)
        return LinearGradient(colors: [g.from, g.to], startPoint: .topLeading, endPoint: .bottomTrailing)
    }
}

private extension Font {
    static func np(_ style: Font.TextStyle) -> Font { .system(style, design: .rounded, weight: .heavy) }
}

private extension View {
    func npGlass(_ radius: CGFloat = 20, stroke: Color = NP.line, width: CGFloat = 1) -> some View {
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        return background { ZStack { shape.fill(.ultraThinMaterial); shape.fill(NP.glass) } }
            .overlay(shape.strokeBorder(stroke, lineWidth: width))
    }
}

private struct NPBackground: View {
    var body: some View {
        ZStack {
            NP.bg
            RadialGradient(colors: [NP.lavenderDeep.opacity(0.28), .clear], center: .topLeading, startRadius: 0, endRadius: 420)
            RadialGradient(colors: [NP.hex(0xFF4F9A).opacity(0.14), .clear], center: .topTrailing, startRadius: 0, endRadius: 360)
        }
        .ignoresSafeArea()
    }
}

private struct NPPress: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduce
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduce ? 0.96 : 1)
            .animation(reduce ? .easeOut(duration: 0.15) : NP.spring, value: configuration.isPressed)
    }
}

private struct NPLabel: View {
    let text: String
    var body: some View {
        Text(text.uppercased()).font(.footnote.weight(.semibold)).tracking(1.1).foregroundStyle(NP.t2)
            .accessibilityAddTraits(.isHeader)
    }
}

private struct NPCount: View {
    let text: String
    var body: some View {
        Text(text).font(.footnote.weight(.semibold)).foregroundStyle(NP.t2)
            .padding(.horizontal, 10).padding(.vertical, 5)
            .background(NP.t1.opacity(0.07), in: Capsule())
    }
}

private struct NPInfo: View {
    let text: String
    var body: some View {
        Label(text, systemImage: "info.circle").font(.subheadline).foregroundStyle(NP.t2)
            .padding(16).frame(maxWidth: .infinity, alignment: .leading).npGlass(18)
    }
}

private struct NPChip: View {
    let text: String
    var icon: String? = nil
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            Haptics.selection()
            action()
        } label: {
            HStack(spacing: 6) {
                if let icon { Image(systemName: icon).font(.subheadline.weight(.semibold)) }
                Text(text).font(.body.weight(.semibold))
            }
            .foregroundStyle(selected ? NP.bg : NP.t1)
            .padding(.horizontal, 16)
            .frame(minHeight: 36)
            .background(Capsule().fill(selected ? NP.t1 : .clear))
            .overlay(Capsule().strokeBorder(selected ? .clear : NP.lineStrong))
            .shadow(color: selected ? NP.t1.opacity(0.25) : .clear, radius: 8)
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(NPPress())
        .accessibilityLabel(text)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }
}

private struct NPKindBadge: View {
    let kind: String
    var body: some View {
        let k = NPKind.of(kind)
        Label(k.label, systemImage: k.icon)
            .font(.caption.weight(.bold)).foregroundStyle(NP.t1)
            .padding(.horizontal, 10).frame(minHeight: 28)
            .background(NP.t1.opacity(0.1), in: Capsule())
    }
}

private struct NPKindTile: View {
    let kind: String
    var size: CGFloat = 44
    var body: some View {
        let k = NPKind.of(kind)
        Image(systemName: k.icon).font(.system(size: size * 0.42, weight: .semibold)).foregroundStyle(.white)
            .frame(width: size, height: size)
            .background(NP.cover(k.color), in: RoundedRectangle(cornerRadius: 13, style: .continuous))
            .accessibilityHidden(true)
    }
}

private struct NPShapeMark: View {
    let index: Int
    var size: CGFloat = 36
    var body: some View {
        let s = NP.shape(index)
        Image(systemName: s.symbol).font(.system(size: size * 0.44, weight: .bold)).foregroundStyle(s.color)
            .frame(width: size, height: size)
            .background(s.color.opacity(0.16), in: RoundedRectangle(cornerRadius: size * 0.3, style: .continuous))
            .accessibilityHidden(true)
    }
}

private struct NPRound: View {
    let icon: String
    let label: String
    let action: () -> Void
    @Environment(\.isEnabled) private var enabled
    var body: some View {
        Button(action: action) {
            Image(systemName: icon).font(.title2.weight(.semibold)).foregroundStyle(NP.t1)
                .frame(width: 56, height: 56)
                .background(Circle().fill(NP.t1.opacity(0.06)))
                .overlay(Circle().strokeBorder(NP.lineStrong))
                .opacity(enabled ? 1 : 0.4)
        }
        .buttonStyle(NPPress())
        .accessibilityLabel(label)
    }
}

private struct NPPrimary: View {
    let title: String
    var leading: String? = nil
    var trailing: String? = nil
    var enabled = true
    var busy = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if busy {
                    ProgressView().tint(.white)
                } else {
                    if let leading { Text(leading) }
                    Text(title)
                    if let trailing { Image(systemName: trailing) }
                }
            }
            .font(.system(.title3, design: .rounded, weight: .heavy))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 58)
            .background(NP.action, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(.white.opacity(0.18)))
            .shadow(color: NP.actionFill.opacity(enabled ? 0.45 : 0), radius: 16, y: 6)
            .opacity(enabled ? 1 : 0.4)
        }
        .buttonStyle(NPPress())
        .disabled(!enabled || busy)
    }
}

private struct NPBottom<Content: View>: View {
    @ViewBuilder let content: Content
    var body: some View {
        content
            .padding(.horizontal, 20).padding(.top, 14).padding(.bottom, 8)
            .background(LinearGradient(colors: [NP.bg.opacity(0), NP.bg.opacity(0.92), NP.bg], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea())
    }
}

private struct NPRadioCard<Cover: View>: View {
    let selected: Bool
    let title: String
    let detail: String
    @ViewBuilder let cover: Cover
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                cover
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(.headline).foregroundStyle(NP.t1).multilineTextAlignment(.leading)
                    Text(detail).font(.footnote).foregroundStyle(NP.t2).multilineTextAlignment(.leading)
                }
                Spacer(minLength: 0)
                NPRadio(selected: selected)
            }
            .padding(.horizontal, 14).padding(.vertical, 10)
            .frame(minHeight: 72)
            .npGlass(20, stroke: selected ? NP.lavender : NP.line, width: selected ? 2 : 1)
            .shadow(color: selected ? NP.lavender.opacity(0.3) : .clear, radius: 12)
        }
        .buttonStyle(NPPress())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(title), \(detail)")
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
    }
}

private struct NPRadio: View {
    let selected: Bool
    var body: some View {
        ZStack {
            Circle().strokeBorder(selected ? .clear : NP.t3, lineWidth: 2)
            if selected {
                Circle().fill(NP.lavenderDeep)
                Image(systemName: "checkmark").font(.caption.weight(.heavy)).foregroundStyle(.white)
            }
        }
        .frame(width: 28, height: 28)
        .accessibilityHidden(true)
    }
}

private struct NPChoiceCard: View {
    let emoji: String
    let title: String
    let detail: String
    let selected: Bool
    var tile = false
    let action: () -> Void

    var body: some View {
        Button {
            Haptics.selection()
            Motion.animate(NP.spring) { action() }
        } label: {
            VStack(alignment: .leading, spacing: 6) {
                HStack(alignment: .top) {
                    Text(emoji).font(.title)
                        .frame(width: tile ? 48 : nil, height: tile ? 48 : nil)
                        .background(tile ? NP.t1.opacity(0.08) : .clear, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    Spacer(minLength: 0)
                    NPRadio(selected: selected)
                }
                Text(title).font(.np(.headline)).foregroundStyle(NP.t1).multilineTextAlignment(.leading)
                Text(detail).font(.footnote).foregroundStyle(NP.t2).multilineTextAlignment(.leading)
            }
            .padding(16)
            .frame(maxWidth: .infinity, minHeight: tile ? 132 : 98, alignment: .topLeading)
            .npGlass(20, stroke: selected ? NP.lavender : NP.line, width: selected ? 2 : 1)
        }
        .buttonStyle(NPPress())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(title), \(detail)")
        .accessibilityAddTraits(selected ? [.isButton, .isSelected] : .isButton)
    }
}

private struct NPRemovable: View {
    let text: String
    let remove: () -> Void
    var body: some View {
        Button {
            Haptics.tap()
            Motion.animate(NP.spring) { remove() }
        } label: {
            HStack(spacing: 6) {
                Text(text)
                Image(systemName: "xmark").font(.caption2.weight(.heavy))
            }
            .font(.footnote.weight(.semibold)).foregroundStyle(NP.lavenderText)
            .padding(.horizontal, 12).frame(minHeight: 36)
            .background(NP.lavender.opacity(0.12), in: Capsule())
            .frame(minHeight: 44)
        }
        .accessibilityLabel("\(text), retirer")
    }
}

private struct NPShareTile: View {
    let icon: String
    let title: String
    let tint: Color
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon).font(.title3.weight(.semibold)).foregroundStyle(tint)
                .frame(width: 44, height: 44).background(tint.opacity(0.16), in: RoundedRectangle(cornerRadius: 13, style: .continuous))
            Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(NP.t1)
        }
        .frame(maxWidth: .infinity, minHeight: 84)
        .padding(.vertical, 8)
        .npGlass(20)
    }
}

/// Règle graphique de Plus / Moins : zone « Moins » à gauche, « Plus » à droite, la ligne lavande glisse.
private struct NPAxis: View {
    let line: Double
    var body: some View {
        let lo = (line / 5).rounded(.down) * 5
        let frac = CGFloat((line - lo) / 5)
        GeometryReader { geo in
            let w = geo.size.width
            let x = w * frac
            ZStack(alignment: .topLeading) {
                Capsule().fill(LinearGradient(colors: [NP.hex(0x3D8BFF).opacity(0.1), NP.hex(0x3D8BFF).opacity(0.45)], startPoint: .leading, endPoint: .trailing))
                    .frame(width: max(x - 5, 0), height: 30)
                    .overlay(alignment: .trailing) {
                        if x > 80 { Text("▼ Moins").font(.footnote.weight(.bold)).foregroundStyle(NP.hex(0x8FD6FF)).padding(.trailing, 10) }
                    }
                Capsule().fill(LinearGradient(colors: [NP.hex(0xFF4F9A).opacity(0.45), NP.hex(0xFF4F9A).opacity(0.1)], startPoint: .leading, endPoint: .trailing))
                    .frame(width: max(w - x - 5, 0), height: 30)
                    .overlay(alignment: .leading) {
                        if w - x > 80 { Text("▲ Plus").font(.footnote.weight(.bold)).foregroundStyle(NP.hex(0xFF8FC0)).padding(.leading, 10) }
                    }
                    .offset(x: x + 5)
                RoundedRectangle(cornerRadius: 2).fill(NP.lavender)
                    .frame(width: 3, height: 44)
                    .shadow(color: NP.lavender, radius: 6)
                    .offset(x: x - 1.5, y: -7)
                ForEach(0...5, id: \.self) { i in
                    Text("\(Int(lo) + i)").font(.footnote.weight(.semibold).monospacedDigit()).foregroundStyle(NP.t2)
                        .position(x: min(max(w * CGFloat(i) / 5, 10), w - 10), y: 56)
                }
            }
        }
        .frame(height: 66)
        .animation(NP.spring, value: line)
        .accessibilityHidden(true)
    }
}

/// Aperçu en direct : la carte de la liste (couverture du groupe, question, réponses à formes, sceaux, fin).
private struct NPCard: View {
    let kind: String
    let question: String
    let options: [String]
    let awardEmoji: String?
    let coverColor: String?
    let emoji: String
    let place: (String, String)?
    let endText: String?
    let launched: Bool
    let patates: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            cover
            VStack(alignment: .leading, spacing: 14) {
                questionText
                answers
                footer
            }
            .padding(.horizontal, 18).padding(.vertical, 16)
        }
        .background(NP.s1)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(NP.line))
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(GroupLook.gradient(coverColor).to.opacity(0.45))
                .blur(radius: 40).offset(y: 16)
        )
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Aperçu de la carte : \(question.isEmpty ? "question à écrire" : question). \(NPKind.of(kind).label)")
    }

    private var cover: some View {
        ZStack {
            NP.cover(coverColor)
            Text(emoji).font(.system(size: 104))
                .grayscale(1).blendMode(.softLight).opacity(0.75)
                .rotationEffect(.degrees(-12))
                .frame(maxWidth: .infinity, alignment: .trailing)
                .offset(x: 20, y: 10)
            HStack {
                if let place {
                    Text("\(place.0) \(place.1)").font(.subheadline.weight(.bold)).foregroundStyle(.white).lineLimit(1)
                        .padding(.horizontal, 12).frame(minHeight: 32)
                        .background(.black.opacity(0.28), in: Capsule())
                }
                Spacer(minLength: 8)
                Label(NPKind.of(kind).label, systemImage: NPKind.of(kind).icon)
                    .font(.subheadline.weight(.bold)).foregroundStyle(NP.hex(0x1D1530))
                    .padding(.horizontal, 12).frame(minHeight: 32)
                    .background(.white.opacity(0.92), in: Capsule())
            }
            .padding(.horizontal, 12)
            .frame(maxHeight: .infinity, alignment: .top)
            .padding(.top, 12)
        }
        .frame(height: 74)
        .clipped()
    }

    @ViewBuilder private var questionText: some View {
        if kind == "award" {
            HStack(spacing: 6) {
                if let awardEmoji { Text(awardEmoji) }
                Text(question)
            }
            .font(.np(.title2)).foregroundStyle(NP.lemonText)
        } else {
            Text(question.isEmpty ? "Ta question ici…" : question)
                .font(.np(.title2)).foregroundStyle(question.isEmpty ? NP.t3 : NP.t1)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    @ViewBuilder private var answers: some View {
        switch kind {
        case "choice", "majority":
            NPFlow(spacing: 8) {
                let shown = options.isEmpty ? ["Réponse 1", "Réponse 2"] : options
                ForEach(Array(shown.enumerated()), id: \.offset) { i, label in
                    HStack(spacing: 10) {
                        NPShapeMark(index: i, size: 28)
                        Text(label).font(.body.weight(.semibold)).foregroundStyle(options.isEmpty ? NP.t3 : NP.t1).lineLimit(1)
                    }
                    .padding(.leading, 5).padding(.trailing, 14).frame(minHeight: 40)
                    .background(NP.t1.opacity(0.05), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(NP.line))
                    .transition(.scale(scale: 0.9).combined(with: .opacity))
                }
            }
        case "yesno":
            halves([("checkmark", "Oui", NP.mint), ("xmark", "Non", NP.hex(0xFF5FA2))])
        case "overunder":
            halves([("triangle.fill", options.first ?? "Plus", NP.hex(0xFF5FA2)), ("arrowtriangle.down.fill", options.last ?? "Moins", NP.hex(0x4D9BFF))])
        case "number", "when":
            HStack(spacing: 10) {
                Image(systemName: kind == "when" ? "clock" : "scope").foregroundStyle(NP.lavender)
                Text(kind == "when" ? "--:--" : "?").font(.system(.title, weight: .heavy).width(.expanded).monospacedDigit()).foregroundStyle(NP.t3)
                Text(kind == "when" ? "l'heure la plus proche" : "le plus proche").font(.subheadline).foregroundStyle(NP.t2)
            }
        case "person", "award":
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: -8) {
                    ForEach(0..<4, id: \.self) { i in
                        Circle().fill(NP.t1.opacity(0.12 + Double(i) * 0.03)).frame(width: 40, height: 40)
                            .overlay(Circle().stroke(NP.s1, lineWidth: 2))
                    }
                    Text(kind == "award" ? "Vote pour quelqu'un" : "Choisis quelqu'un").font(.subheadline).foregroundStyle(NP.t2).padding(.leading, 18)
                }
                if kind == "award" {
                    HStack(spacing: 8) {
                        badge("🏅 Pour l'honneur")
                        badge("3 votes au moins")
                    }
                }
            }
        default:
            Text("Réponse libre, cachée jusqu'à la fin").font(.subheadline).foregroundStyle(NP.t3)
                .padding(.horizontal, 14).frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(NP.lineStrong, style: StrokeStyle(lineWidth: 1.5, dash: [5, 5])))
        }
    }

    private func badge(_ text: String) -> some View {
        Text(text).font(.footnote.weight(.semibold)).foregroundStyle(NP.t1)
            .padding(.horizontal, 10).frame(minHeight: 28).background(NP.t1.opacity(0.08), in: Capsule())
    }

    private func halves(_ items: [(String, String, Color)]) -> some View {
        HStack(spacing: 10) {
            ForEach(items, id: \.1) { icon, label, color in
                HStack(spacing: 8) {
                    Image(systemName: icon).font(.subheadline.weight(.heavy))
                    Text(label).font(.system(.headline, design: .rounded, weight: .heavy)).lineLimit(1).minimumScaleFactor(0.7)
                }
                .foregroundStyle(color)
                .frame(maxWidth: .infinity, minHeight: 64)
                .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(color.opacity(0.3)))
            }
        }
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                HStack(spacing: -10) {
                    ForEach(0..<3, id: \.self) { _ in
                        Circle().strokeBorder(NP.t3, style: StrokeStyle(lineWidth: 1.2, dash: [3, 3])).frame(width: 30, height: 30)
                    }
                }
                Text(launched ? "Personne n'a encore joué" : "À toi de lancer").font(.subheadline).foregroundStyle(NP.t2)
                Spacer(minLength: 0)
                if !launched { endChip }
            }
            if launched {
                HStack {
                    if patates {
                        Text("🥔 0 dans le champ").font(.subheadline.weight(.bold)).foregroundStyle(NP.amber)
                            .padding(.horizontal, 12).frame(minHeight: 32).background(NP.amber.opacity(0.16), in: Capsule())
                    }
                    Spacer(minLength: 0)
                    endChip
                }
            }
        }
    }

    private var endChip: some View {
        Label(endText ?? "fin à choisir", systemImage: "clock")
            .font(.subheadline.weight(.semibold)).foregroundStyle(NP.t1)
            .padding(.horizontal, 12).frame(minHeight: 32)
            .background(NP.t1.opacity(0.07), in: Capsule())
    }
}

/// Rayons de lumière derrière le sceau (très légers, 10 %), qui tournent en 40 s ; immobiles si Réduire les animations.
private struct NPRays: View {
    let spinning: Bool
    @State private var angle = 0.0
    var body: some View {
        ZStack {
            AngularGradient(gradient: Gradient(colors: (0..<24).map { $0.isMultiple(of: 2) ? Color.white.opacity(0.10) : .clear }), center: .center)
                .rotationEffect(.degrees(angle))
                .mask(RadialGradient(colors: [.black, .clear], center: .center, startRadius: 40, endRadius: 320))
            RadialGradient(colors: [NP.hex(0xFF4F9A).opacity(0.28), NP.hex(0xFFB347).opacity(0.1), .clear], center: .center, startRadius: 0, endRadius: 200)
        }
        .onChange(of: spinning) { on in
            guard on else { return }
            withAnimation(.linear(duration: 40).repeatForever(autoreverses: false)) { angle = 360 }
        }
        .accessibilityHidden(true)
    }
}

/// Éléments qui passent à la ligne (pastilles de l'aperçu, phrase « Ou des personnes choisies, un lien »).
private struct NPFlow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, widest: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(ProposedViewSize(width: width, height: nil))
            if x > 0 && x + size.width > width { y += line + spacing; x = 0; line = 0 }
            x += size.width + spacing
            line = max(line, size.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: proposal.width ?? widest, height: y + line)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for view in subviews {
            let size = view.sizeThatFits(ProposedViewSize(width: bounds.width, height: nil))
            if x > bounds.minX && x + size.width > bounds.maxX { x = bounds.minX; y += line + spacing; line = 0 }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(width: min(size.width, bounds.width), height: size.height))
            x += size.width + spacing
            line = max(line, size.height)
        }
    }
}
