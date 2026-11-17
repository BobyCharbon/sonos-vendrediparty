import SwiftUI

/// Un prono (maquette du 17.11, écrans 3 à 5) : jouer d'un toucher (réponse cachée, modifiable jusqu'à la fin), donner le
/// résultat (organisateur, une fois fermé), puis le dévoilement : bonne réponse, répartition avec les visages, gagnants.
/// Pour l'honneur seulement. Le signal temps réel n'est pas suivi ici : la page se relit au retour et en tirant.
struct PronoDetailView: View {
    @ObservedObject var store: PronosStore
    let id: String
    @State private var prono: Prono?
    @State private var error: String?
    @State private var busy = false
    @State private var askTerms = false
    @State private var retry: (() -> Void)?
    @State private var number = ""
    @State private var text = ""
    @State private var resultOption: String?
    @State private var resultPerson: String?
    @State private var resultNumber = ""
    @State private var winners: Set<String> = []
    @State private var newEnd = Date()
    @State private var editingEnd = false
    @State private var confirmCancel = false
    @State private var reportTarget: ReportTargetRef?
    @State private var revealShown = false

    struct ReportTargetRef: Identifiable { let id: String; let author: String? }

    var body: some View {
        ScrollView {
            if let p = prono {
                VStack(alignment: .leading, spacing: 14) {
                    head(p)
                    switch p.state {
                    case "open": play(p)
                    case "closed": closed(p)
                    case "done": done(p)
                    default: Text("Ce prono a été annulé : aucun point n'est compté.").foregroundStyle(.secondary)
                    }
                    if let error { Text(error).font(.footnote).foregroundStyle(.red).transition(.opacity) }
                    if p.revealed, p.state != "done", let answers = p.answers { answersList(p, answers) }
                    if p.mine { organizer(p) } else {
                        Button("Signaler ce prono") { reportTarget = .init(id: p.id, author: nil) }
                            .font(.footnote).frame(maxWidth: .infinity)
                    }
                    Text("Proposé par \(p.creator.me == true ? "toi" : p.creator.name) · \(PronoFormat.short(p.createdAt))")
                        .font(.caption).foregroundStyle(.secondary).frame(maxWidth: .infinity)
                }
                .padding(16)
                .motion(Motion.smooth, value: p.state)
                .motion(Motion.snappy, value: p.myAnswer)
            } else if let error {
                VStack(spacing: 10) {
                    Text("Prono introuvable").font(.title3.bold())
                    Text(error).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
                .padding(40)
            } else {
                ProgressView().padding(.top, 60)
            }
        }
        .background(AppConfig.background.ignoresSafeArea())
        .navigationTitle(prono?.group?.name ?? "Prono")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable { await load() }
        .task { await load() }
        .sheet(isPresented: $askTerms) {
            TermsAcceptSheet(store: store.moderation) { accepted in if accepted { retry?() } }
        }
        .sheet(item: $reportTarget) { target in
            PronoReportSheet(store: store, prono: id, author: target.author)
        }
    }

    // MARK: En-tête

    private func head(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                switch p.state {
                case "open": PronoChip(text: p.revealed ? "Ouvert" : "🔒 Réponses cachées · \(PronoFormat.stateLine(state: p.state, closesAt: p.closesAt, revealed: p.revealed).lowercased())", tone: PronoLook.lavender)
                case "closed": PronoChip(text: PronoFormat.stateLine(state: p.state, closesAt: p.closesAt, revealed: p.revealed), tone: PronoLook.coral)
                case "done": PronoChip(text: "🏆 Terminé", tone: PronoLook.mint)
                default: PronoChip(text: "Annulé", tone: .secondary)
                }
            }
            Text(PronoFormat.place(group: p.group, event: p.event, creator: p.creator)).font(.footnote).foregroundStyle(.secondary)
            Text(p.question).font(.system(size: 28, weight: .heavy, design: .rounded)).fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            Text("\(PronoFormat.points(p.points)) pour une bonne réponse\(p.kind == "number" ? " · le plus proche gagne" : "")")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    // MARK: Jouer

    @ViewBuilder
    private func play(_ p: Prono) -> some View {
        if !p.canAnswer {
            Text("Ce prono ne t'est pas ouvert.").foregroundStyle(.secondary)
        } else {
            VStack(alignment: .leading, spacing: 10) {
                switch p.kind {
                case "choice":
                    ForEach(Array(p.options.enumerated()), id: \.element.id) { i, o in
                        choiceButton(o.label, on: p.myAnswer?.optionId == o.id, id: "prono-choice-\(i)") { answer(p, ["option_id": o.id]) }
                    }
                case "person":
                    people(p.candidates ?? [], selected: p.myAnswer?.personId) { answer(p, ["person_id": $0]) }
                case "number":
                    HStack {
                        TextField("Ton nombre", text: $number).keyboardType(.decimalPad).font(.title2.weight(.bold))
                            .padding(12).background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 14))
                        Button(p.myAnswer == nil ? "Valider" : "Changer") {
                            if let n = Double(number.replacingOccurrences(of: ",", with: ".")) { answer(p, ["number": n]) }
                        }
                        .buttonStyle(.borderedProminent).tint(PronoLook.action).disabled(busy || Double(number.replacingOccurrences(of: ",", with: ".")) == nil)
                    }
                default:
                    TextField("Ta réponse", text: $text).padding(12).background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 14))
                    Button(p.myAnswer == nil ? "Valider" : "Changer ma réponse") { answer(p, ["text": text.trimmingCharacters(in: .whitespaces)]) }
                        .buttonStyle(.borderedProminent).tint(PronoLook.action).frame(maxWidth: .infinity)
                        .disabled(busy || text.trimmingCharacters(in: .whitespaces).isEmpty)
                }
                seal(p)
                played(p)
            }
            .onAppear {
                if number.isEmpty, let n = p.myAnswer?.number { number = PronoFormat.number(n) }
                if text.isEmpty, let t = p.myAnswer?.text { text = t }
            }
        }
    }

    private func choiceButton(_ label: String, on: Bool, id: String, action: @escaping () -> Void) -> some View {
        Button { Haptics.selection(); action() } label: {
            HStack {
                Text(label).font(.headline).foregroundStyle(.primary)
                Spacer()
                if on {
                    Image(systemName: "checkmark").font(.footnote.weight(.heavy)).foregroundStyle(.white)
                        .frame(width: 28, height: 28).background(PronoLook.accent, in: Circle())
                        .transition(.scale.combined(with: .opacity))
                }
            }
            .padding(.horizontal, 16).frame(minHeight: 60)
            .background(on ? AnyShapeStyle(LinearGradient(colors: [PronoLook.accent.opacity(0.28), PronoLook.lavender.opacity(0.16)], startPoint: .leading, endPoint: .trailing))
                        : AnyShapeStyle(PronoLook.surface), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(on ? PronoLook.accent : .clear, lineWidth: 2))
            .shadow(color: on ? PronoLook.accent.opacity(0.4) : .clear, radius: 12)
        }
        .buttonStyle(.plain)
        .disabled(busy)
        .accessibilityAddTraits(on ? .isSelected : [])
        .accessibilityIdentifier(id)
    }

    private func people(_ list: [PronoFace], selected: String?, pick: @escaping (String) -> Void) -> some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 88), spacing: 10)], spacing: 10) {
            ForEach(list) { face in
                Button { Haptics.selection(); pick(face.id) } label: {
                    VStack(spacing: 6) {
                        Initials(name: face.name, photo: face.photo, size: 48)
                        Text(face.label).font(.footnote.weight(.semibold)).lineLimit(1).foregroundStyle(.primary)
                    }
                    .frame(maxWidth: .infinity).padding(.vertical, 12)
                    .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(selected == face.id ? PronoLook.accent : .clear, lineWidth: 2))
                }
                .buttonStyle(.plain)
                .accessibilityAddTraits(selected == face.id ? .isSelected : [])
            }
        }
    }

    private func seal(_ p: Prono) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "lock.fill").foregroundStyle(.white).frame(width: 42, height: 42)
                .background(LinearGradient(colors: [Color(hex: 0xCBBDFF), Color(hex: 0x7B6CF6)], startPoint: .topLeading, endPoint: .bottomTrailing),
                            in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .symbolEffectBounce(p.myAnswer)
            VStack(alignment: .leading, spacing: 2) {
                Text(p.myAnswer == nil ? "Ta réponse restera cachée" : "Ta réponse est enregistrée et cachée").font(.subheadline.weight(.bold))
                Text("Personne ne la voit avant \(p.reveal == "close" ? "la fin des pronos" : "le résultat"), pas même \(p.mine ? "toi en tant qu'organisateur" : p.creator.name). Tu peux changer jusqu'au \(PronoFormat.short(p.closesAt)).")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
        .padding(14)
        .background(PronoLook.lavender.opacity(0.10), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoLook.lavender.opacity(0.35), lineWidth: 1))
    }

    private func played(_ p: Prono) -> some View {
        let missing = max(0, p.players - p.answered.count)
        return HStack(spacing: 10) {
            if !p.answered.isEmpty { PronoFaces(faces: Array(p.answered.suffix(8))) }
            Text(p.answered.isEmpty ? "Personne n'a encore joué" : "\(p.answered.count) \(p.answered.count > 1 ? "personnes ont joué" : "personne a joué")\(missing > 0 ? " · \(missing) pas encore" : "")")
                .font(.footnote).foregroundStyle(.secondary)
        }
    }

    // MARK: Fermé : le résultat

    @ViewBuilder
    private func closed(_ p: Prono) -> some View {
        if !p.mine {
            VStack(alignment: .leading, spacing: 10) {
                Text("En attente du résultat de \(p.creator.name)").font(.headline)
                Text(p.myAnswer.map { "Ta réponse : \(p.label(option: $0.optionId, number: $0.number, text: $0.text, person: nil, personId: $0.personId))." } ?? "Tu n'as pas joué.")
                    .font(.subheadline).foregroundStyle(.secondary)
                played(p)
            }
        } else if p.answered.isEmpty {
            Text("Personne n'a joué : tu peux annuler ce prono ou déplacer la fin.").foregroundStyle(.secondary)
        } else {
            VStack(alignment: .leading, spacing: 10) {
                Text("Quel est le résultat ?").font(.system(size: 24, weight: .heavy, design: .rounded))
                Text("\(p.answered.count) \(p.answered.count > 1 ? "personnes ont joué" : "personne a joué"). Tout le monde verra le résultat et les gagnants dès que tu valides.")
                    .font(.footnote).foregroundStyle(.secondary)
                switch p.kind {
                case "choice":
                    ForEach(Array(p.options.enumerated()), id: \.element.id) { i, o in
                        resultRow(o.label, detail: o.count.map { "\($0) réponse\($0 > 1 ? "s" : "")" }, on: resultOption == o.id, id: "prono-result-\(i)") { resultOption = o.id }
                    }
                case "person":
                    people(p.candidates ?? [], selected: resultPerson) { resultPerson = $0 }
                case "number":
                    TextField("Le vrai résultat", text: $resultNumber).keyboardType(.decimalPad).font(.title2.weight(.bold))
                        .padding(12).background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 14))
                default:
                    ForEach(p.answers ?? []) { a in
                        resultRow(a.hidden == true ? "Réponse masquée" : (a.text ?? ""), detail: a.user.label, on: winners.contains(a.user.id), id: "prono-winner-\(a.user.id)") {
                            if winners.contains(a.user.id) { winners.remove(a.user.id) } else { winners.insert(a.user.id) }
                        }
                    }
                }
                Button {
                    Haptics.press()
                    var body: [String: Any] = [:]
                    switch p.kind {
                    case "choice": body["option_id"] = resultOption ?? ""
                    case "person": body["person_id"] = resultPerson ?? ""
                    case "number": body["number"] = Double(resultNumber.replacingOccurrences(of: ",", with: ".")) ?? 0
                    default: body["winners"] = Array(winners)
                    }
                    act("prono_result", ["id": p.id, "body": body]) { Haptics.success() }
                } label: {
                    Text(p.kind == "text" ? "🎉 Dévoiler · \(winners.count) gagnant\(winners.count > 1 ? "s" : "")" : "🎉 Dévoiler le résultat").bold().frame(maxWidth: .infinity).padding(.vertical, 6)
                }
                .buttonStyle(.borderedProminent).tint(PronoLook.action)
                .disabled(busy || !resultReady(p))
                .accessibilityIdentifier("prono-reveal-button")
            }
        }
    }

    private func resultReady(_ p: Prono) -> Bool {
        switch p.kind {
        case "choice": return resultOption != nil
        case "person": return resultPerson != nil
        case "number": return Double(resultNumber.replacingOccurrences(of: ",", with: ".")) != nil
        default: return true
        }
    }

    private func resultRow(_ label: String, detail: String?, on: Bool, id: String, action: @escaping () -> Void) -> some View {
        Button { Haptics.selection(); action() } label: {
            HStack(spacing: 12) {
                Image(systemName: on ? "checkmark.circle.fill" : "circle").font(.title3).foregroundStyle(on ? PronoLook.mint : .secondary)
                Text(label).font(.headline).foregroundStyle(.primary)
                Spacer()
                if let detail { Text(detail).font(.footnote).foregroundStyle(.secondary) }
            }
            .padding(.horizontal, 14).frame(minHeight: 56)
            .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(on ? PronoLook.mint : .clear, lineWidth: 2))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(on ? .isSelected : [])
        .accessibilityIdentifier(id)
    }

    // MARK: Dévoilement

    private func done(_ p: Prono) -> some View {
        let total = max(1, p.answers?.count ?? 0)
        return VStack(spacing: 14) {
            VStack(spacing: 6) {
                Text("🏆").font(.system(size: 44))
                    .frame(width: 84, height: 84)
                    .background(LinearGradient(colors: [Color(hex: 0xFFEA9C), PronoLook.coral], startPoint: .topLeading, endPoint: .bottomTrailing),
                                in: RoundedRectangle(cornerRadius: 26, style: .continuous))
                    .shadow(color: PronoLook.coral.opacity(0.55), radius: 20, y: 8)
                    .scaleEffect(revealShown ? 1 : 0.6)
                if !p.resultLabel.isEmpty { Text("\(p.resultLabel) !").font(.system(size: 30, weight: .heavy, design: .rounded)) }
                if let mine = p.myAnswer {
                    if mine.winner == true {
                        Text("Tu avais vu juste · +\(PronoFormat.points(p.points))").font(.subheadline.bold()).foregroundStyle(PronoLook.lemon)
                    } else {
                        Text("Ta réponse : \(p.label(option: mine.optionId, number: mine.number, text: mine.text, person: nil, personId: mine.personId))")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }
                } else {
                    Text("Tu n'as pas joué.").font(.subheadline).foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity).padding(.vertical, 14)
            .background(RadialGradient(colors: [PronoLook.lemon.opacity(0.22), .clear], center: .top, startRadius: 0, endRadius: 220))

            if p.kind == "choice" {
                ForEach(p.options) { o in
                    let who = (p.answers ?? []).filter { $0.optionId == o.id }.map(\.user)
                    bar(o.label, faces: who, count: o.count ?? who.count, total: total, good: o.correct == true)
                }
            } else if p.kind == "person" {
                let groups = Dictionary(grouping: p.answers ?? [], by: { $0.person?.id ?? "" }).sorted { $0.value.count > $1.value.count }
                ForEach(groups, id: \.key) { key, rows in
                    bar(rows.first?.person?.label ?? "—", faces: rows.map(\.user), count: rows.count, total: total, good: p.result?.person?.id == key)
                }
            } else {
                ForEach(p.answers ?? []) { a in
                    HStack(spacing: 12) {
                        Initials(name: a.user.name, photo: a.user.photo, size: 30)
                        Text(p.label(option: a.optionId, number: a.number, text: a.text, person: a.person)).font(.headline)
                        Spacer()
                        Text(a.user.label).font(.caption).foregroundStyle(.secondary)
                        if a.winner { Text("🏆") }
                    }
                    .padding(12)
                    .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(a.winner ? PronoLook.lemon : .clear, lineWidth: 2))
                }
            }
            Text("LES GAGNANTS").font(.footnote.weight(.bold)).foregroundStyle(.secondary)
            if let winners = p.winners, !winners.isEmpty {
                LazyVGrid(columns: [GridItem(.adaptive(minimum: 74), spacing: 10)], spacing: 10) {
                    ForEach(Array(winners.enumerated()), id: \.element.id) { i, w in
                        VStack(spacing: 4) {
                            Initials(name: w.name, photo: w.photo, size: 52)
                                .overlay(Circle().stroke(PronoLook.lemon, lineWidth: 3))
                                .shadow(color: PronoLook.lemon.opacity(0.55), radius: 10)
                            Text(w.label).font(.footnote.bold()).lineLimit(1)
                            Text("+\(p.points)").font(.caption.bold()).foregroundStyle(PronoLook.lemon)
                        }
                        .scaleEffect(revealShown ? 1 : 0.4)
                        .opacity(revealShown ? 1 : 0)
                        .animation(Motion.pick(Motion.bouncy).delay(0.25 + Double(i) * 0.08), value: revealShown)
                    }
                }
            } else {
                Text("Personne n'avait vu juste.").foregroundStyle(.secondary)
            }
        }
        .accessibilityIdentifier("prono-reveal")
        .onAppear { Motion.animate(Motion.bouncy) { revealShown = true } }
    }

    private func bar(_ label: String, faces: [PronoFace], count: Int, total: Int, good: Bool) -> some View {
        HStack(spacing: 10) {
            Text(label).font(.subheadline.weight(.semibold)).lineLimit(1).frame(width: 84, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 10).fill(.white.opacity(0.07))
                    RoundedRectangle(cornerRadius: 10)
                        .fill(good ? AnyShapeStyle(LinearGradient(colors: [PronoLook.mint, Color(hex: 0x22B07D)], startPoint: .leading, endPoint: .trailing))
                              : AnyShapeStyle(PronoLook.surface2))
                        .frame(width: revealShown ? geo.size.width * max(count > 0 ? 0.12 : 0, Double(count) / Double(total)) : 0)
                    PronoFaces(faces: Array(faces.prefix(6)), size: 22).padding(.leading, 6)
                }
            }
            .frame(height: 32)
            Text("\(count)").foregroundStyle(.secondary).frame(width: 22, alignment: .trailing)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label) : \(count) réponse\(count > 1 ? "s" : "")\(good ? ", bonne réponse" : "")")
    }

    private func answersList(_ p: Prono, _ answers: [PronoShownAnswer]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("LES RÉPONSES").font(.footnote.weight(.bold)).foregroundStyle(.secondary)
            ForEach(answers) { a in
                HStack(spacing: 12) {
                    Initials(name: a.user.name, photo: a.user.photo, size: 30)
                    VStack(alignment: .leading) {
                        Text(p.label(option: a.optionId, number: a.number, text: a.text, person: a.person)).font(.headline)
                        Text(a.user.label).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    if p.kind == "text", a.user.me != true, a.hidden != true {
                        Button("Signaler") { reportTarget = .init(id: "\(p.id):\(a.user.id)", author: a.user.id) }.font(.footnote)
                    }
                }
                .padding(12)
                .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
        }
    }

    // MARK: Organisation

    @ViewBuilder
    private func organizer(_ p: Prono) -> some View {
        if p.state == "open" || p.state == "closed" {
            VStack(alignment: .leading, spacing: 12) {
                Text("ORGANISATION").font(.footnote.weight(.bold)).foregroundStyle(.secondary)
                if p.state == "open" {
                    if let path = p.link?.path, let url = URL(string: path, relativeTo: AppConfig.baseURL)?.absoluteURL {
                        HStack {
                            ShareLink(item: url, subject: Text("Un prono pour toi"), message: Text(p.question)) {
                                Label("Partager le lien", systemImage: "square.and.arrow.up").frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent).tint(PronoLook.action)
                            Button("Arrêter", role: .destructive) { act("prono_set_link", ["id": p.id, "active": false]) }.buttonStyle(.bordered)
                        }
                    } else {
                        Button { act("prono_set_link", ["id": p.id, "active": true]) } label: { Label("Créer un lien", systemImage: "link").frame(maxWidth: .infinity) }
                            .buttonStyle(.bordered)
                    }
                    Text("Qui l'ouvre se connecte à Party, puis joue. Le lien s'arrête à la fin des pronos.").font(.caption).foregroundStyle(.secondary)
                }
                if p.canMoveEnd, !(p.reveal == "close" && p.revealed) {
                    DatePicker("Fin des pronos", selection: $newEnd, in: Date().addingTimeInterval(60)..., displayedComponents: [.date, .hourAndMinute])
                        .onAppear { if !editingEnd, let d = p.closes { newEnd = max(d, Date().addingTimeInterval(120)) } }
                        .onChange(of: newEnd) { _ in editingEnd = true }
                    HStack {
                        Button("Déplacer la fin") {
                            editingEnd = false
                            act("prono_update", ["id": p.id, "body": ["closes_at": ISO8601DateFormatter().string(from: newEnd)]])
                        }
                        .buttonStyle(.bordered).disabled(!editingEnd)
                        if p.state == "open" {
                            Button("Fermer maintenant") { act("prono_close_now", ["id": p.id]) }.buttonStyle(.bordered)
                        }
                    }
                }
                if p.locked { Text("Quelqu'un a joué : la question et les choix ne changent plus.").font(.caption).foregroundStyle(.secondary) }
                Button(role: .destructive) { confirmCancel = true } label: {
                    Text(p.state == "closed" ? "Pas de résultat (annuler le prono)" : "Annuler le prono").frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .confirmationDialog("Annuler ce prono ?", isPresented: $confirmCancel, titleVisibility: .visible) {
                    Button("Oui, annuler : aucun point", role: .destructive) { act("prono_cancel", ["id": p.id]) }
                }
                PronoHonour(points: p.points)
            }
            .padding(14)
            .background(PronoLook.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        }
    }

    // MARK: Appels

    private func load() async {
        do {
            let p: Prono = try await store.call("prono_get", ["id": id])
            Motion.animate(Motion.smooth) { prono = p }
            error = nil
        } catch {
            self.error = PronosStore.message(error)
        }
    }

    private func answer(_ p: Prono, _ value: [String: Any]) {
        act("prono_answer", ["id": p.id, "answer": value]) { Haptics.success() }
    }

    private func act(_ fn: String, _ args: [String: Any], done: (() -> Void)? = nil) {
        busy = true
        error = nil
        Task {
            defer { busy = false }
            do {
                let p: Prono = try await store.call(fn, args)
                Motion.animate(Motion.smooth) { prono = p }
                done?()
                await store.refreshBadge()
            } catch PartyAPIError.termsRequired {
                retry = { act(fn, args, done: done) }
                askTerms = true
            } catch {
                Haptics.error()
                Motion.animate(Motion.fade) { self.error = PronosStore.message(error) }
            }
        }
    }
}

private extension View {
    /// Petit rebond du cadenas quand la réponse change (iOS 17) ; rien avant.
    @ViewBuilder
    func symbolEffectBounce<V: Equatable>(_ value: V) -> some View {
        if #available(iOS 17.0, *) { symbolEffect(.bounce, value: value) } else { self }
    }
}

/// « Signaler » un prono ou une réponse libre : une raison, un mot facultatif (la file des modérateurs le reçoit).
struct PronoReportSheet: View {
    @ObservedObject var store: PronosStore
    let prono: String
    let author: String?
    @Environment(\.dismiss) private var dismiss
    @State private var reason = "other"
    @State private var comment = ""
    @State private var sent = false
    @State private var error: String?

    private let reasons = [("harassment", "Harcèlement"), ("shocking", "Contenu choquant"), ("spam", "Spam"), ("scam", "Arnaque ou vente"), ("other", "Autre")]

    var body: some View {
        NavigationStack {
            Form {
                if sent {
                    Text("Merci : les modérateurs vont regarder. La personne n'est pas prévenue.")
                } else {
                    Picker("Raison", selection: $reason) { ForEach(reasons, id: \.0) { Text($0.1).tag($0.0) } }.pickerStyle(.inline)
                    TextField("Un mot (facultatif)", text: $comment, axis: .vertical)
                    if let error { Text(error).foregroundStyle(.red) }
                }
            }
            .navigationTitle(author == nil ? "Signaler ce prono" : "Signaler cette réponse")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button(sent ? "Fermer" : "Annuler") { dismiss() } }
                if !sent {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Envoyer") {
                            Task {
                                do {
                                    let note: Any = comment.isEmpty ? NSNull() : comment
                                    if let author {
                                        try await store.run("prono_report_answer", ["id": prono, "author": author, "reason": reason, "comment": note])
                                    } else {
                                        try await store.run("report_content", ["p_kind": "prono", "p_target": prono, "p_reason": reason, "p_comment": note])
                                    }
                                    Haptics.success()
                                    sent = true
                                } catch {
                                    self.error = PronosStore.message(error)
                                }
                            }
                        }
                    }
                }
            }
        }
        .presentationDetents([.medium, .large])
    }
}
