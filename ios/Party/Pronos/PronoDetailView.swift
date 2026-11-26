// Compilé dans la BETA seulement (et les recettes E2E_HOOKS) : absent du binaire de l'App Store (Pronos, contrôle Apple du 26.11).
#if BETA || E2E_HOOKS

import SwiftUI
import UIKit

/// Un prono (Pronos v2, maquettes 3-* et 4-*, direction C « Néon club ») : la fiche (couverture, question, « Comment on
/// tranche ? », compte à rebours), la réponse par type, les patates à planter (0 à 20, fictives et sans valeur), le
/// sceau, la contestation, les réactions, l'organisation repliée ; puis le dévoilement (PronoRevealView, joué une fois)
/// et le résultat. La base décide de tout (réponses cachées, partage du champ) ; l'app ne fait qu'appeler le relais.
struct PronoDetailView: View {
    @ObservedObject var store: PronosStore
    let id: String
    /// Choix présélectionné (toucher d'une pastille dans la liste) : jamais de réponse directe, on scelle ici.
    let preselect: String?

    init(store: PronosStore, id: String, preselect: String? = nil) {
        self.store = store
        self.id = id
        self.preselect = preselect
    }

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var prono: Prono?
    @State private var error: String?
    @State private var busy = false
    @State private var askTerms = false
    @State private var retry: (() -> Void)?

    // Réponse en cours (pas encore scellée)
    @State private var drafted = false
    @State private var editing = false
    @State private var option: String?
    @State private var person: String?
    @State private var number: Double = 0
    @State private var numberSet = false
    @State private var typing = false
    @State private var numberText = ""
    @State private var dragStart: Double?
    @State private var when = Date()
    @State private var whenSet = false
    @State private var text = ""
    @State private var stake = 0
    @State private var dropTick = 0
    @State private var peek = false
    @State private var sealedPop = true
    @State private var breathe = false

    // Résultat (organisateur)
    @State private var resultOption: String?
    @State private var resultPerson: String?
    @State private var resultNumber = ""
    @State private var resultTime = Date()
    @State private var winners: Set<String> = []
    @State private var confirmHappened = false

    // Organisation
    @State private var orgOpen = false
    @State private var newEnd = Date()
    @State private var choosingEnd = false
    @State private var manualTime = false
    @State private var confirmCancel = false
    @State private var copied = false

    // Feuilles
    @State private var reportTarget: ReportTargetRef?
    @State private var contesting = false
    @State private var contestReason = ""
    @State private var showReveal = false

    struct ReportTargetRef: Identifiable { let id: String; let author: String? }

    private static let reactions = ["😂", "🔥", "🥔", "👀", "🤯", "👏"]

    var body: some View {
        ScrollView {
            if let p = prono {
                content(p)
                    .motion(Motion.smooth, value: p.state)
                    .motion(Motion.snappy, value: p.myAnswer)
            } else if let error {
                VStack(spacing: 10) {
                    Text("Prono introuvable").font(.title3.bold()).foregroundStyle(PronoInk.t1)
                    Text(error).foregroundStyle(PronoInk.t2).multilineTextAlignment(.center)
                }
                .padding(40).padding(.top, 80)
            } else {
                ProgressView().padding(.top, 140)
            }
        }
        .ignoresSafeArea(edges: .top)
        .scrollDismissesKeyboard(.interactively)
        .background(PronoInk.bg.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            if let p = prono, showsSealBar(p) { sealBar(p) }
        }
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(.hidden, for: .navigationBar)
        .toolbar { toolbar }
        .refreshable { await load() }
        .task { await load() }
        .sheet(isPresented: $askTerms) {
            TermsAcceptSheet(store: store.moderation) { accepted in if accepted { retry?() } }
        }
        .sheet(item: $reportTarget) { target in
            PronoReportSheet(store: store, prono: id, author: target.author)
        }
        .sheet(isPresented: $contesting) { contestSheet }
        .fullScreenCover(isPresented: $showReveal) {
            if let p = prono { PronoRevealView(prono: p, patates: patatesOn(p)) { showReveal = false } }
        }
    }

    @ToolbarContentBuilder
    private var toolbar: some ToolbarContent {
        ToolbarItemGroup(placement: .navigationBarTrailing) {
            if let p = prono {
                if let url = linkURL(p), p.state == "open" {
                    ShareLink(item: url, subject: Text("Un prono pour toi"), message: Text(p.question)) {
                        Image(systemName: "square.and.arrow.up")
                    }
                    .accessibilityLabel("Partager le lien du prono")
                }
                Menu {
                    if p.state == "done", p.kind != "text" {
                        Button { showReveal = true } label: { Label("Revoir le dévoilement", systemImage: "sparkles") }
                    }
                    if !p.mine {
                        Button(role: .destructive) { reportTarget = .init(id: p.id, author: nil) } label: { Label("Signaler ce prono", systemImage: "flag") }
                    }
                    if p.mine, p.state == "open" || p.state == "closed" {
                        Button { Motion.animate(Motion.smooth) { orgOpen = true } } label: { Label("Organisation", systemImage: "gearshape") }
                    }
                } label: {
                    Image(systemName: "ellipsis")
                }
                .accessibilityLabel("Plus")
                .accessibilityIdentifier("prono-more")
            }
        }
    }

    // MARK: Fiche

    private func patatesOn(_ p: Prono) -> Bool {
        (pronoOpt(p.patates) ?? false) && (pronoOpt(p.patatesOn) ?? false)
            && (pronoOpt(pronoOpt(store.features)?.patates) ?? false)
            && p.kind != "award" && p.kind != "text"
    }

    private func sealed(_ p: Prono) -> Bool { p.myAnswer != nil && !editing }

    private func content(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            PronoCoverBand(group: p.group, event: p.event, height: p.state == "open" && sealed(p) ? 200 : 236)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 20) {
                head(p)
                if let rules = pronoOpt(p.rules), !rules.trimmingCharacters(in: .whitespaces).isEmpty, p.state != "done" {
                    rulesCard(rules)
                }
                switch p.state {
                case "open": openSection(p)
                case "closed": closedSection(p)
                case "done": resultSection(p)
                default: cancelledCard(p)
                }
                if let error {
                    Text(error).font(.footnote).foregroundStyle(PronoInk.retreat).transition(.opacity)
                }
                if p.revealed, p.state != "done", let answers = p.answers { answersList(p, answers) }
                if p.mine, p.state == "open" || p.state == "closed" { organisation(p) }
                footer(p)
            }
            .padding(.horizontal, 20)
            .padding(.top, -64)
            .padding(.bottom, 24)
        }
    }

    private func head(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                if let g = p.group {
                    GroupTile(emoji: g.emoji, color: g.color, size: 34)
                    Text(g.name).font(.subheadline.weight(.bold)).foregroundStyle(PronoInk.t1).lineLimit(1)
                } else if let e = p.event {
                    GroupTile(emoji: "🎉", color: "lavender", size: 34)
                    Text(e.title).font(.subheadline.weight(.bold)).foregroundStyle(PronoInk.t1).lineLimit(1)
                }
                Text(p.mine ? "ton prono" : "prono de \(p.creator.name)").font(.subheadline).foregroundStyle(PronoInk.t2).lineLimit(1)
            }
            Text(p.question)
                .font(.system(size: 30, weight: .heavy, design: .rounded))
                .foregroundStyle(PronoInk.t1)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            PronoFlow(spacing: 8) {
                chip { if p.kind == "award" { Text("🏆") } else { Image(systemName: PronoKind.symbol(p.kind)).font(.caption.weight(.bold)) }; Text(kindLabel(p.kind)) }
                if pronoOpt(p.notOver) ?? false { chip { Image(systemName: "arrow.down.to.line"); Text("Sans dépasser") } }
                if patatesOn(p) {
                    chip(tone: PronoInk.patate) { Text("🎊"); Text("Avec confettis") }
                } else if p.kind == "award" {
                    chip { Text("Pour l'honneur, sans confettis") }
                } else {
                    chip { Text(p.kind == "text" ? "\(PronoFormat.points(p.points)), pour l'honneur" : PronoFormat.points(p.points)) }
                }
                if p.mine, p.state == "open", !p.answered.isEmpty { chip { Text("\(p.answered.count) \(p.answered.count > 1 ? "ont joué" : "a joué")") } }
            }
        }
    }

    private func kindLabel(_ kind: String) -> String {
        switch kind {
        case "choice": return "Choix"
        case "yesno": return "Oui ou non"
        case "overunder": return "Plus ou moins"
        case "number": return "Nombre"
        case "when": return "Heure"
        case "person": return "Une personne"
        case "award": return "Trophée"
        case "majority": return "Majorité"
        default: return "Réponse libre"
        }
    }

    private func chip<Content: View>(tone: Color? = nil, @ViewBuilder _ label: () -> Content) -> some View {
        HStack(spacing: 6) { label() }
            .font(.footnote.weight(.semibold))
            .foregroundStyle(tone ?? PronoInk.t1)
            .padding(.horizontal, 12).frame(minHeight: 30)
            .background((tone ?? Color.white).opacity(tone == nil ? 0.06 : 0.12), in: Capsule())
            .overlay(Capsule().stroke(tone?.opacity(0.5) ?? PronoInk.line, lineWidth: 1))
            .accessibilityElement(children: .combine)
    }

    private func card<Content: View>(fill: Color = PronoInk.glass, stroke: Color = PronoInk.line, radius: CGFloat = 24, padding: CGFloat = 18, @ViewBuilder _ content: () -> Content) -> some View {
        content()
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(fill, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous).stroke(stroke, lineWidth: 1))
    }

    private func iconTile(_ systemName: String, tint: Color = PronoInk.lavender, size: CGFloat = 34) -> some View {
        Image(systemName: systemName).font(.system(size: size * 0.45, weight: .semibold)).foregroundStyle(tint)
            .frame(width: size, height: size)
            .background(tint.opacity(0.16), in: RoundedRectangle(cornerRadius: size * 0.3, style: .continuous))
            .accessibilityHidden(true)
    }

    private func rulesCard(_ rules: String) -> some View {
        card(radius: 20) {
            HStack(alignment: .top, spacing: 12) {
                iconTile("scalemass")
                VStack(alignment: .leading, spacing: 2) {
                    Text("Comment on tranche ?").font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.t1)
                    Text(rules).font(.subheadline).foregroundStyle(PronoInk.t2).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func footer(_ p: Prono) -> some View {
        HStack(spacing: 4) {
            Text("Proposé par \(p.creator.me == true ? "toi" : p.creator.name) · \(PronoFormat.short(p.createdAt))")
            if !p.mine {
                Text("·")
                Button("Signaler") { reportTarget = .init(id: p.id, author: nil) }.underline()
                    .accessibilityIdentifier("prono-report")
            }
        }
        .font(.caption).foregroundStyle(PronoInk.t3)
        .frame(maxWidth: .infinity)
        .padding(.top, 8)
    }

    // MARK: Ouvert

    @ViewBuilder
    private func openSection(_ p: Prono) -> some View {
        if let d = p.closes { PronoCountdown(closesAt: d) }
        if !p.canAnswer {
            Text("Ce prono ne t'est pas ouvert.").foregroundStyle(PronoInk.t2)
        } else if sealed(p) {
            sealedCard(p)
            sealsGrid(p)
            if patatesOn(p) { fieldCard(p, sealed: true) }
            if patatesOn(p) { reminder(refill: false) }
            reactionsRow(p, trailing: "en attendant la fin")
        } else {
            answerSection(p)
            if !p.answered.isEmpty, p.kind != "award" { sealsPreview(p) }
            if patatesOn(p) {
                plantCard(p)
                reminder(refill: true)
            } else if p.kind != "award" {
                honour(p)
            }
        }
    }

    private func honour(_ p: Prono) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text("🏅")
            Text("Pour l'honneur : une bonne réponse = \(PronoFormat.points(p.points)) au classement. Aucun argent, aucun lot.")
                .font(.footnote).foregroundStyle(PronoInk.t2)
        }
        .accessibilityElement(children: .combine)
    }

    private func reminder(refill: Bool) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "info.circle").foregroundStyle(PronoInk.t3)
            Text("Les confettis n'ont aucune valeur : ils ne s'achètent pas, ne se vendent pas, ne s'échangent pas.\(refill ? " Ton sac remonte à 100 🎊 chaque lundi." : "")")
        }
        .font(.footnote).foregroundStyle(PronoInk.t3)
        .accessibilityElement(children: .combine)
    }

    // MARK: Répondre

    private var optionKinds: Set<String> { PronoRead.optionKinds }

    @ViewBuilder
    private func answerSection(_ p: Prono) -> some View {
        switch p.kind {
        case "yesno": yesNo(p)
        case "overunder": overUnder(p)
        case "majority": majority(p)
        case "number": numberPicker(p)
        case "when": timePicker(p)
        case "person": personGrid(p, award: false)
        case "award": awardSection(p)
        case "text": freeText(p)
        default:
            VStack(alignment: .leading, spacing: 10) {
                PronoSectionLabel("Ta réponse", trailing: "un toucher")
                ForEach(Array(p.options.enumerated()), id: \.element.id) { i, o in
                    PronoChoicePill(label: o.label, shape: i, selected: option == o.id) { pick(option: o.id) }
                        .disabled(busy)
                        .accessibilityIdentifier("prono-choice-\(i)")
                }
            }
        }
    }

    private func pick(option id: String) {
        guard option != id else { return }
        PronoHaptics.selection()
        Motion.animate(.spring(response: 0.35, dampingFraction: 0.7)) { option = id }
    }

    private func pick(person id: String) {
        guard person != id else { return }
        PronoHaptics.selection()
        Motion.animate(.spring(response: 0.35, dampingFraction: 0.7)) { person = id }
    }

    private func selectBadge(_ color: Color) -> some View {
        Image(systemName: "checkmark").font(.system(size: 12, weight: .heavy)).foregroundStyle(Color(hex: 0x1D1530))
            .frame(width: 26, height: 26).background(color, in: Circle())
            .transition(.scale.combined(with: .opacity))
            .accessibilityHidden(true)
    }

    private func yesNo(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            PronoSectionLabel("Ta réponse", trailing: "un toucher")
            HStack(spacing: 12) {
                ForEach(Array(p.options.prefix(2).enumerated()), id: \.element.id) { i, o in
                    let mark = PronoMark.of(kind: "yesno", index: i)
                    let on = option == o.id
                    Button { pick(option: o.id) } label: {
                        VStack(spacing: 14) {
                            Image(systemName: mark.symbol).font(.system(size: 30, weight: .heavy))
                                .foregroundStyle(on ? Color(hex: 0x1D1530) : mark.color)
                                .frame(width: 76, height: 76)
                                .background(on ? AnyShapeStyle(mark.color) : AnyShapeStyle(mark.color.opacity(0.16)), in: i == 0 ? AnyShape(Circle()) : AnyShape(RoundedRectangle(cornerRadius: 22, style: .continuous)))
                            Text(o.label).font(.system(size: 40, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1).minimumScaleFactor(0.6).lineLimit(1)
                        }
                        .frame(maxWidth: .infinity, minHeight: 168)
                        .background(choiceFill(on, mark.color), in: RoundedRectangle(cornerRadius: 28, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 28, style: .continuous).stroke(on ? mark.color : PronoInk.line, lineWidth: on ? 2 : 1))
                        .overlay(alignment: .topTrailing) { if on { selectBadge(mark.color).padding(12) } }
                        .shadow(color: on ? mark.color.opacity(0.35) : .clear, radius: 24)
                    }
                    .buttonStyle(PronoPressStyle())
                    .disabled(busy)
                    .accessibilityLabel(o.label)
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityIdentifier("prono-choice-\(i)")
                }
            }
        }
    }

    private func choiceFill(_ on: Bool, _ color: Color) -> AnyShapeStyle {
        on ? AnyShapeStyle(LinearGradient(colors: [color.opacity(0.22), color.opacity(0.06)], startPoint: .top, endPoint: .bottom))
           : AnyShapeStyle(PronoInk.glass)
    }

    private func overUnder(_ p: Prono) -> some View {
        let line = pronoOpt(p.line)
        let lineText = line.map(PronoFormat.number) ?? "—"
        return VStack(spacing: 0) {
            ForEach(Array(p.options.prefix(2).enumerated()), id: \.element.id) { i, o in
                if i == 1 {
                    ZStack {
                        PronoHLine().stroke(style: StrokeStyle(lineWidth: 1.5, dash: [6, 5])).foregroundStyle(PronoInk.gold.opacity(0.7)).frame(height: 2)
                        Text(lineText).font(.system(size: 40, weight: .heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoInk.gold)
                            .padding(.horizontal, 22).frame(minHeight: 64)
                            .background(PronoInk.bg, in: Capsule())
                            .overlay(Capsule().stroke(PronoInk.gold, lineWidth: 2))
                            .accessibilityLabel("La ligne : \(lineText)")
                    }
                    .padding(.vertical, 8)
                }
                let mark = PronoMark.of(kind: "overunder", index: i)
                let on = option == o.id
                Button { pick(option: o.id) } label: {
                    HStack(spacing: 14) {
                        PronoMarkTile(mark: mark, size: 52, filled: on)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(o.label).font(.system(size: 22, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                            if let line {
                                Text(i == 0 ? "\(Int(line.rounded(.up))) ou plus" : "\(Int(line.rounded(.down))) ou moins").font(.subheadline).foregroundStyle(PronoInk.t2)
                            }
                        }
                        Spacer()
                        if on { selectBadge(mark.color) } else { Circle().stroke(PronoInk.t3, lineWidth: 2).frame(width: 26, height: 26) }
                    }
                    .padding(.horizontal, 16).frame(minHeight: 84)
                    .background(choiceFill(on, mark.color), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).stroke(on ? mark.color : PronoInk.line, lineWidth: on ? 2 : 1))
                    .shadow(color: on ? mark.color.opacity(0.3) : .clear, radius: 20)
                }
                .buttonStyle(PronoPressStyle())
                .disabled(busy)
                .accessibilityElement(children: .combine)
                .accessibilityAddTraits(on ? .isSelected : [])
                .accessibilityIdentifier("prono-choice-\(i)")
            }
            Label("Une demi-unité : il n'y a jamais d'égalité avec la ligne.", systemImage: "info.circle")
                .font(.footnote).foregroundStyle(PronoInk.t3).frame(maxWidth: .infinity, alignment: .leading).padding(.top, 10)
        }
    }

    @ViewBuilder
    private func majority(_ p: Prono) -> some View {
        card(fill: PronoInk.mint.opacity(0.08), stroke: PronoInk.mint.opacity(0.4)) {
            HStack(alignment: .top, spacing: 12) {
                Text("👥").font(.title)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Devine ce que pense la bande").font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.t1)
                    Text("Ce n'est pas ton goût qui compte : choisis ce que la majorité va choisir.").font(.subheadline).foregroundStyle(PronoInk.t2)
                }
            }
        }
        .accessibilityElement(children: .combine)
        if p.options.count == 2 {
            HStack(spacing: 12) {
                ForEach(Array(p.options.enumerated()), id: \.element.id) { i, o in
                    let mark = PronoMark.of(kind: "majority", index: i)
                    let on = option == o.id
                    Button { pick(option: o.id) } label: {
                        VStack(spacing: 12) {
                            HStack { PronoMarkTile(mark: mark, size: 32, filled: on); Spacer(); if on { selectBadge(mark.color) } }
                            Text(o.label).font(.system(size: 24, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                                .multilineTextAlignment(.center).minimumScaleFactor(0.7).frame(maxHeight: .infinity)
                        }
                        .padding(14).frame(maxWidth: .infinity, minHeight: 190)
                        .background(choiceFill(on, mark.color), in: RoundedRectangle(cornerRadius: 28, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 28, style: .continuous).stroke(on ? mark.color : PronoInk.line, lineWidth: on ? 2 : 1))
                        .shadow(color: on ? mark.color.opacity(0.35) : .clear, radius: 24)
                    }
                    .buttonStyle(PronoPressStyle())
                    .disabled(busy)
                    .accessibilityLabel(o.label)
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityIdentifier("prono-choice-\(i)")
                }
            }
            .overlay {
                Text("ou").font(.headline.weight(.heavy)).foregroundStyle(PronoInk.t1)
                    .frame(width: 52, height: 52).background(PronoInk.bg, in: Circle())
                    .accessibilityHidden(true)
            }
        } else {
            ForEach(Array(p.options.enumerated()), id: \.element.id) { i, o in
                PronoChoicePill(label: o.label, shape: i, selected: option == o.id) { pick(option: o.id) }
                    .disabled(busy)
                    .accessibilityIdentifier("prono-choice-\(i)")
            }
        }
    }

    private func setNumber(_ n: Double) {
        let v = max(0, n)
        let old = number
        number = v
        numberSet = true
        if Int(v.rounded()) != Int(old.rounded()) {
            let i = Int(v.rounded())
            if i <= 20 || i % 5 == 0 { PronoHaptics.selection() }
        }
    }

    private func numberPicker(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            PronoSectionLabel("Ta réponse", trailing: numberSet ? nil : "fais tourner")
            HStack {
                roundButton("minus", label: "Moins un") { setNumber((number - 1).rounded()) }
                Spacer()
                Text(numberSet ? PronoFormat.number(number) : "?")
                    .font(.system(size: 96, weight: .heavy).width(.expanded)).monospacedDigit()
                    .foregroundStyle(LinearGradient(colors: [PronoInk.t1, PronoInk.patateFill.opacity(0.9)], startPoint: .top, endPoint: .bottom))
                    .contentTransition(.numericText())
                    .lineLimit(1).minimumScaleFactor(0.4)
                    .accessibilityLabel(numberSet ? "Ta réponse : \(PronoFormat.number(number))" : "Pas encore de nombre")
                Spacer()
                roundButton("plus", label: "Plus un") { setNumber((number + 1).rounded()) }
            }
            ruler
            Button { Motion.animate(Motion.snappy) { typing.toggle() } } label: {
                Label("Taper un nombre", systemImage: "keyboard").font(.subheadline.weight(.semibold)).foregroundStyle(PronoInk.lavender)
            }
            .frame(maxWidth: .infinity, minHeight: 44)
            if typing {
                TextField("Ton nombre", text: $numberText)
                    .keyboardType(.decimalPad).font(.title2.weight(.bold)).foregroundStyle(PronoInk.t1)
                    .padding(14).background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .onChange(of: numberText) { v in
                        if let n = Double(v.replacingOccurrences(of: ",", with: ".")) { number = max(0, n); numberSet = true }
                    }
                    .accessibilityIdentifier("prono-number")
            }
            if pronoOpt(p.notOver) ?? false {
                card(fill: PronoInk.gold.opacity(0.08), stroke: PronoInk.gold.opacity(0.4), radius: 20) {
                    HStack(alignment: .top, spacing: 12) {
                        iconTile("arrowtriangle.down.fill", tint: PronoInk.gold)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Sans dépasser").font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.gold)
                            Text("Le plus proche sans aller au-dessus l'emporte.").font(.subheadline).foregroundStyle(PronoInk.t2)
                        }
                    }
                }
                .accessibilityElement(children: .combine)
            }
        }
    }

    private func roundButton(_ symbol: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol).font(.title3.weight(.bold)).foregroundStyle(PronoInk.t1)
                .frame(width: 56, height: 56).background(PronoInk.glass, in: Circle())
                .overlay(Circle().stroke(PronoInk.line))
        }
        .buttonStyle(PronoPressStyle())
        .accessibilityLabel(label)
    }

    /// Molette à crans : un trait par unité, un grand trait tous les 5 ; glisser fait tourner (14 pt par unité).
    private var ruler: some View {
        let center = number.rounded()
        return Canvas { ctx, size in
            let step: CGFloat = 14
            let mid = size.width / 2
            let span = Int(size.width / step / 2) + 1
            for k in -span...span {
                let v = Int(center) + k
                guard v >= 0 else { continue }
                let x = mid + CGFloat(k) * step - CGFloat(number - center) * step
                let major = v % 5 == 0
                let h: CGFloat = major ? 26 : 14
                var path = Path()
                path.move(to: CGPoint(x: x, y: 14))
                path.addLine(to: CGPoint(x: x, y: 14 + h))
                let fade = 1 - min(1, abs(x - mid) / mid)
                ctx.stroke(path, with: .color(Color.white.opacity(0.15 + 0.6 * fade)), lineWidth: major ? 2 : 1)
                if major {
                    ctx.draw(Text("\(v)").font(.caption.weight(.bold)).foregroundColor(Color(white: 0.75).opacity(0.3 + 0.7 * fade)), at: CGPoint(x: x, y: size.height - 10))
                }
            }
            var needle = Path()
            needle.move(to: CGPoint(x: mid, y: 8))
            needle.addLine(to: CGPoint(x: mid, y: 46))
            ctx.stroke(needle, with: .color(Color(hex: 0xFF4F9A)), lineWidth: 3)
        }
        .frame(height: 76)
        .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(PronoInk.line))
        .contentShape(Rectangle())
        .gesture(DragGesture(minimumDistance: 2)
            .onChanged { g in
                if dragStart == nil { dragStart = number }
                setNumber(((dragStart ?? 0) - Double(g.translation.width / 14)).rounded())
            }
            .onEnded { _ in dragStart = nil })
        .accessibilityElement()
        .accessibilityLabel("Molette du nombre")
        .accessibilityValue(numberSet ? PronoFormat.number(number) : "aucun")
        .accessibilityAdjustableAction { dir in
            switch dir {
            case .increment: setNumber(number + 1)
            case .decrement: setNumber(number - 1)
            @unknown default: break
            }
        }
        .accessibilityIdentifier("prono-number-wheel")
    }

    private func quickTimes() -> [Date] {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = PronoRead.zurich
        let now = Date()
        let minute = cal.component(.minute, from: now)
        let base = cal.date(byAdding: .minute, value: minute < 30 ? 30 - minute : 60 - minute, to: now) ?? now
        let start = cal.date(bySetting: .second, value: 0, of: base) ?? base
        return (0..<4).map { start.addingTimeInterval(Double($0) * 1800) }
    }

    private func timePicker(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            PronoSectionLabel("Ta réponse", trailing: "heure de Suisse")
            VStack(spacing: 4) {
                Text(whenSet ? PronoRead.time(when) : "--:--")
                    .font(.system(size: 84, weight: .heavy).width(.expanded)).monospacedDigit()
                    .foregroundStyle(PronoInk.t1).lineLimit(1).minimumScaleFactor(0.5)
                    .contentTransition(.numericText())
                Text(pronoOpt(p.notOver) ?? false ? "La plus proche sans dépasser l'emporte" : "L'heure la plus proche l'emporte")
                    .font(.subheadline.weight(.semibold)).foregroundStyle(PronoInk.t2)
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .combine)
            DatePicker("Ton heure", selection: Binding(get: { when }, set: { when = $0; whenSet = true; PronoHaptics.selection() }), displayedComponents: [.hourAndMinute])
                .datePickerStyle(.wheel).labelsHidden()
                .frame(maxWidth: .infinity)
                .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .environment(\.timeZone, PronoRead.zurich)
                .accessibilityIdentifier("prono-when")
            DatePicker("Jour", selection: Binding(get: { when }, set: { when = $0; whenSet = true }), displayedComponents: [.date])
                .environment(\.timeZone, PronoRead.zurich)
                .foregroundStyle(PronoInk.t2)
            HStack(spacing: 8) {
                ForEach(quickTimes(), id: \.self) { d in
                    Button {
                        PronoHaptics.selection()
                        Motion.animate(Motion.snappy) { when = d; whenSet = true }
                    } label: {
                        Text(PronoRead.time(d)).font(.subheadline.weight(.bold)).monospacedDigit().foregroundStyle(PronoInk.t1)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(PronoInk.line))
                    }
                    .buttonStyle(PronoPressStyle())
                }
            }
        }
    }

    private func personGrid(_ p: Prono, award: Bool) -> some View {
        let list = (p.candidates ?? []).filter { !award || $0.me != true }
        let ring: [Color] = award ? [PronoInk.lavender, PronoInk.lavenderDeep] : [PronoInk.gold, Color(hex: 0xFFB347)]
        return VStack(alignment: .leading, spacing: 12) {
            PronoSectionLabel(award ? "Ton vote" : "Ta réponse", trailing: award ? "une personne" : "\(list.count) personnes")
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 16) {
                ForEach(Array(list.enumerated()), id: \.element.id) { i, face in
                    let on = person == face.id
                    Button { pick(person: face.id) } label: {
                        VStack(spacing: 8) {
                            Initials(name: face.name, photo: face.photo, size: 72)
                                .padding(on ? 4 : 0)
                                .overlay(Circle().stroke(LinearGradient(colors: ring, startPoint: .top, endPoint: .bottom), lineWidth: on ? 4 : 0))
                                .overlay(alignment: .bottomTrailing) { if on { selectBadge(ring[0]) } }
                                .shadow(color: on ? ring[0].opacity(0.5) : .clear, radius: 16)
                                .scaleEffect(on ? 1.06 : 1)
                            Text(face.label).font(.subheadline.weight(.semibold)).foregroundStyle(on ? ring[0] : PronoInk.t1).lineLimit(1)
                        }
                        .frame(maxWidth: .infinity, minHeight: 104)
                    }
                    .buttonStyle(PronoPressStyle())
                    .disabled(busy)
                    .accessibilityLabel(face.label)
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityIdentifier("prono-person-\(i)")
                }
            }
        }
    }

    @ViewBuilder
    private func awardSection(_ p: Prono) -> some View {
        let award = PronoRead.award(p)
        card {
            VStack(spacing: 10) {
                Text(award.emoji).font(.system(size: 64))
                    .frame(width: 128, height: 128)
                    .background(RadialGradient(colors: [PronoInk.gold, Color(hex: 0xFFB347)], center: .topLeading, startRadius: 4, endRadius: 140), in: Circle())
                    .shadow(color: PronoInk.gold.opacity(0.5), radius: 30)
                Text("🏆 Trophée de la soirée\(p.event.map { " · \($0.title)" } ?? "")").font(.footnote.weight(.bold)).foregroundStyle(PronoInk.gold)
                Text(award.name).font(.system(size: 28, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1).multilineTextAlignment(.center)
                PronoFlow(spacing: 8) {
                    chip { Text("Pour l'honneur, sans confettis") }
                    chip { Text("\(p.answered.count) \(p.answered.count > 1 ? "ont voté" : "a voté")") }
                }
            }
            .frame(maxWidth: .infinity)
        }
        .accessibilityElement(children: .combine)
        personGrid(p, award: true)
        card(radius: 20) {
            Toggle(isOn: Binding(get: { pronoOpt(p.optout) ?? false }, set: { v in act("prono_optout", ["id": p.id, "out": v]) })) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Ne pas me proposer").font(.headline).foregroundStyle(PronoInk.t1)
                    Text("Tu n'apparais plus dans la liste de ce trophée. Tu peux toujours voter.").font(.footnote).foregroundStyle(PronoInk.t2)
                }
            }
            .tint(PronoInk.lavenderDeep)
            .disabled(busy)
            .accessibilityIdentifier("prono-optout")
        }
        Label("Le trophée se dévoile à la fin, s'il y a au moins 3 votes.", systemImage: "info.circle").font(.footnote).foregroundStyle(PronoInk.t3)
    }

    private func freeText(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            PronoSectionLabel("Ta réponse", trailing: "en quelques mots")
            VStack(alignment: .leading, spacing: 10) {
                TextField("Ta réponse", text: Binding(get: { text }, set: { text = String($0.prefix(80)) }), axis: .vertical)
                    .font(.system(size: 28, weight: .bold, design: .rounded)).foregroundStyle(PronoInk.t1)
                    .lineLimit(1...3)
                    .accessibilityIdentifier("prono-text")
                HStack {
                    Text("Les réponses passent le filtre de Party").font(.footnote).foregroundStyle(PronoInk.t3)
                    Spacer()
                    Text("\(text.count)/80").font(.footnote.weight(.heavy)).monospacedDigit().foregroundStyle(PronoInk.t2)
                }
            }
            .padding(18)
            .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
            card(radius: 20) {
                HStack(alignment: .top, spacing: 12) {
                    iconTile("checkmark")
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Qui coche les bonnes réponses ?").font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.t1)
                        Text("\(p.mine ? "Toi" : p.creator.name), à la fin. Toutes les réponses apparaissent alors.").font(.subheadline).foregroundStyle(PronoInk.t2)
                    }
                }
            }
            .accessibilityElement(children: .combine)
        }
    }

    // MARK: Planter des patates

    private func maxStake(_ p: Prono) -> Int {
        let bag = pronoOpt(p.bag)
        let cap = bag?.maxStake ?? 20
        guard let balance = bag?.balance else { return min(20, cap) }
        return max(0, min(cap, 20, balance + (p.myAnswer?.stake ?? 0)))
    }

    private func setStake(_ n: Int, _ p: Prono) {
        let v = min(max(0, n), maxStake(p))
        guard v != stake else { return }
        PronoHaptics.soft()
        Motion.animate(.spring(response: 0.3, dampingFraction: 0.6)) { stake = v; dropTick += 1 }
    }

    private func optionMark(_ p: Prono, _ id: String?) -> (PronoMark, String)? {
        guard let i = PronoRead.markIndex(p, option: id) else { return nil }
        return (.of(kind: p.kind, index: i), p.options[i].label)
    }

    private func plantCard(_ p: Prono) -> some View {
        let cap = maxStake(p)
        return VStack(alignment: .leading, spacing: 18) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Lancer des confettis").font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.t1)
                    Text("Facultatif, de 0 à \(cap)").font(.subheadline).foregroundStyle(PronoInk.t2)
                }
                Spacer()
                if let balance = pronoOpt(p.bag)?.balance { PronoBagChip(balance: balance) }
            }
            VStack(spacing: 4) {
                HStack(alignment: .center, spacing: 6) {
                    Text("\(stake)")
                        .font(.system(size: 68, weight: .heavy).width(.expanded)).monospacedDigit()
                        .foregroundStyle(PronoInk.patate)
                        .contentTransition(.numericText())
                    Text("🎊").font(.system(size: 44)).rotationEffect(.degrees(-12))
                        .id(dropTick)
                        .transition(reduceMotion ? .opacity : .offset(y: -36).combined(with: .opacity))
                }
                if stake > 0, let m = optionMark(p, option) {
                    HStack(spacing: 6) {
                        Text("lancés sur").foregroundStyle(PronoInk.t2)
                        Image(systemName: m.0.symbol).foregroundStyle(m.0.color).font(.caption.weight(.heavy))
                        Text(m.1).fontWeight(.bold).foregroundStyle(PronoInk.t1).lineLimit(1)
                    }
                    .font(.subheadline)
                } else if stake == 0 {
                    Text("Tu joues sans confettis").font(.subheadline).foregroundStyle(PronoInk.t2)
                }
            }
            .frame(maxWidth: .infinity)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(stake == 0 ? "Aucun confetti lancé" : "\(stake) confettis lancés")
            PronoPatateSlider(value: Binding(get: { stake }, set: { setStake($0, p) }), maximum: cap)
                .accessibilityIdentifier("prono-stake")
            HStack(spacing: 8) {
                ForEach([0, 5, 10, 20], id: \.self) { n in
                    let on = stake == n
                    Button { setStake(n, p) } label: {
                        Text(n == 0 ? "Sans" : "\(n)")
                            .font(.headline.weight(.heavy)).monospacedDigit()
                            .foregroundStyle(on ? PronoInk.onPatate : PronoInk.t1)
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .background(on ? AnyShapeStyle(PronoInk.patateFill) : AnyShapeStyle(PronoInk.glass), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(on ? .clear : PronoInk.line))
                    }
                    .buttonStyle(PronoPressStyle())
                    .disabled(n > cap)
                    .accessibilityLabel(n == 0 ? "Sans confettis" : "\(n) confettis")
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityIdentifier("prono-stake-\(n)")
                }
            }
            Divider().overlay(PronoInk.line)
            fieldLine(p)
            if optionKinds.contains(p.kind) || p.kind == "person" {
                ruleLine(ok: true, title: "Tu vois juste :", detail: "tu te partages la piste avec ceux qui ont vu juste, selon ce que chacun a lancé.")
                ruleLine(ok: false, title: "Pas cette fois :", detail: "tes confettis partent au balai. Personne n'a vu juste : tout le monde les récupère.")
            }
        }
        .padding(18)
        .background(PronoInk.s1, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
        .shadow(color: .black.opacity(0.35), radius: 20, y: 18)
    }

    private func fieldRule(_ p: Prono) -> String {
        switch p.kind {
        case "number", "when": return "Le plus proche remporte la piste. Égalité : partagée selon ce que chacun a lancé."
        case "majority": return "La réponse la plus choisie l'emporte. Égalité : tout le monde récupère ses confettis."
        default: return "Les confettis de tout le monde, sur toutes les réponses."
        }
    }

    private func fieldLine(_ p: Prono, mine: Bool = false) -> some View {
        let total = pronoOpt(p.field)?.total ?? 0
        let planters = pronoOpt(p.field)?.planters ?? 0
        return HStack(alignment: .top, spacing: 12) {
            Text("🎊").font(.title2).frame(width: 48, height: 48)
                .background(PronoInk.patateFill.opacity(0.14), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                (Text("\(total) 🎊 ").font(.headline.weight(.heavy)).monospacedDigit()
                 + Text("sur la piste · \(planters) joueur\(planters > 1 ? "s" : "")").font(.headline))
                    .foregroundStyle(PronoInk.t1)
                Text(mine ? "Dont tes \(p.myAnswer?.stake ?? 0) 🎊. La répartition reste cachée jusqu'à la fin." : fieldRule(p))
                    .font(.subheadline).foregroundStyle(PronoInk.t2).fixedSize(horizontal: false, vertical: true)
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func ruleLine(ok: Bool, title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: ok ? "checkmark.circle.fill" : "xmark.square.fill").foregroundStyle(ok ? PronoInk.mint : PronoInk.miss)
            (Text(title).bold().foregroundColor(PronoInk.t1) + Text(" ") + Text(detail).foregroundColor(PronoInk.t2)).font(.subheadline)
        }
        .accessibilityElement(children: .combine)
    }

    private func fieldCard(_ p: Prono, sealed: Bool) -> some View {
        card {
            VStack(alignment: .leading, spacing: 14) {
                fieldLine(p, mine: sealed && (p.myAnswer?.stake ?? 0) > 0)
                if let bag = pronoOpt(p.bag) {
                    Divider().overlay(PronoInk.line)
                    HStack {
                        PronoBagChip(balance: bag.balance)
                        Spacer()
                        Text("Remonte à 100 🎊 lundi").font(.subheadline).foregroundStyle(PronoInk.t2)
                    }
                }
            }
        }
    }

    // MARK: Sceller

    private func showsSealBar(_ p: Prono) -> Bool { p.state == "open" && p.canAnswer && !sealed(p) }

    private func ready(_ p: Prono) -> Bool {
        if optionKinds.contains(p.kind) { return option != nil }
        switch p.kind {
        case "person", "award": return person != nil
        case "number": return numberSet
        case "when": return whenSet
        default: return !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }

    private func draftLabel(_ p: Prono) -> String? {
        guard ready(p) else { return nil }
        if optionKinds.contains(p.kind) { return p.options.first { $0.id == option }?.label }
        switch p.kind {
        case "person", "award": return p.candidates?.first { $0.id == person }?.label
        case "number": return PronoFormat.number(number)
        case "when": return PronoRead.time(when)
        default: return text
        }
    }

    private func sealBar(_ p: Prono) -> some View {
        VStack(spacing: 8) {
            if let label = draftLabel(p) {
                HStack(spacing: 6) {
                    if let m = optionMark(p, option) { Image(systemName: m.0.symbol).foregroundStyle(m.0.color).font(.caption.weight(.heavy)) }
                    Text(label).fontWeight(.bold).foregroundStyle(PronoInk.t1).lineLimit(1)
                    if patatesOn(p), stake > 0 { Text("avec").foregroundStyle(PronoInk.t2); Text("\(stake) 🎊").fontWeight(.heavy).monospacedDigit().foregroundStyle(PronoInk.t1) }
                }
                .font(.subheadline)
                .accessibilityElement(children: .combine)
            }
            PronoPrimaryButton(p.kind == "award" ? "Sceller mon vote" : "Sceller ma réponse", systemImage: "lock.fill") { seal(p) }
                .disabled(busy || !ready(p))
                .accessibilityIdentifier("prono-seal")
            HStack(spacing: 12) {
                if p.myAnswer != nil {
                    Button("Garder ma réponse") {
                        Motion.animate(Motion.smooth) { editing = false; drafted = false; draft(p) }
                    }
                    .font(.footnote.weight(.semibold)).foregroundStyle(PronoInk.lavender)
                }
                Text(p.kind == "award" ? "Ton vote reste caché, tu peux le changer jusqu'à la fin." : "Tu pourras changer jusqu'à \(p.closes.map(PronoRead.moment) ?? "la fin").")
                    .font(.footnote).foregroundStyle(PronoInk.t3)
            }
        }
        .padding(.horizontal, 20).padding(.top, 26).padding(.bottom, 6)
        // Fond plein sous le bouton (court fondu en haut) : le texte de la fiche ne passe plus à travers.
        .background(VStack(spacing: 0) {
            LinearGradient(colors: [PronoInk.bg.opacity(0), PronoInk.bg], startPoint: .top, endPoint: .bottom).frame(height: 22)
            PronoInk.bg
        }.ignoresSafeArea())
    }

    private func seal(_ p: Prono) {
        var answer: [String: Any] = [:]
        if optionKinds.contains(p.kind) { answer["option_id"] = option ?? "" } else {
            switch p.kind {
            case "person", "award": answer["person_id"] = person ?? ""
            case "number": answer["number"] = number
            case "when": answer["answer_at"] = ISO8601DateFormatter().string(from: when)
            default: answer["text"] = text.trimmingCharacters(in: .whitespacesAndNewlines)
            }
        }
        if patatesOn(p) { answer["stake"] = stake }
        Haptics.press()
        act("prono_answer", ["id": p.id, "answer": answer]) {
            PronoHaptics.success()
            sealedPop = reduceMotion
            editing = false
            withAnimation(Motion.pick(.spring(response: 0.42, dampingFraction: 0.6))) { sealedPop = true }
        }
    }

    // MARK: Scellé

    private func sealedCard(_ p: Prono, canChange: Bool = true) -> some View {
        let mine = PronoRead.mine(p) ?? ""
        let g = GroupLook.gradient(p.group?.color)
        return VStack(spacing: 14) {
            ZStack(alignment: .bottomTrailing) {
                Circle().fill(g.to.opacity(breathe ? 0.85 : 0.55)).frame(width: 190, height: 190).blur(radius: 40)
                    .frame(width: 132, height: 132)
                PronoSeal(emoji: p.group?.emoji ?? (p.kind == "award" ? "🏆" : "🔮"), color: p.group?.color ?? (p.kind == "award" ? "lemon" : "lavender"), size: 132)
                Image(systemName: "lock.fill").font(.system(size: 18, weight: .bold)).foregroundStyle(.white)
                    .frame(width: 42, height: 42).background(Color(hex: 0x160F2C), in: Circle())
                    .overlay(Circle().stroke(PronoInk.s1, lineWidth: 3))
            }
            .scaleEffect(sealedPop ? 1 : 1.35)
            .rotationEffect(.degrees(sealedPop ? 0 : -10))
            .accessibilityHidden(true)
            Text(p.kind == "award" ? "Vote scellé" : "Réponse scellée")
                .font(.system(size: 28, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                .accessibilityLabel("Ta réponse est enregistrée et cachée. \(p.kind == "award" ? "Vote scellé" : "Réponse scellée")")
                .accessibilityIdentifier("prono-sealed")
            Text("Personne ne voit ta réponse, pas même \(p.mine ? "toi qui l'organises" : "l'organisateur"). Tout se dévoile \(p.reveal == "result" ? "avec le résultat" : "à la fin"), pour tout le monde en même temps.")
                .font(.subheadline).foregroundStyle(PronoInk.t2).multilineTextAlignment(.center).frame(maxWidth: 300)
            HStack(spacing: 10) {
                ZStack {
                    Text(mine).font(.headline).foregroundStyle(PronoInk.t1).lineLimit(1)
                        .blur(radius: peek ? 0 : 7)
                    if !peek {
                        Label("Maintiens pour voir", systemImage: "eye").font(.subheadline.weight(.semibold)).foregroundStyle(PronoInk.t1)
                    }
                }
                .frame(maxWidth: .infinity, minHeight: 52)
                .background(Color.white.opacity(0.04), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(style: StrokeStyle(lineWidth: 1.2, dash: [5, 4])).foregroundStyle(PronoInk.t3))
                .onLongPressGesture(minimumDuration: 0.12, maximumDistance: 40, pressing: { down in withAnimation(Motion.pick(.easeOut(duration: 0.15))) { peek = down } }, perform: {})
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Ta réponse : \(mine)\((p.myAnswer?.stake ?? 0) > 0 ? ", avec \(p.myAnswer?.stake ?? 0) confettis" : "")")
                .accessibilityIdentifier("prono-peek")
                if canChange { Button {
                    Haptics.tap()
                    Motion.animate(Motion.smooth) { drafted = false; draft(p); editing = true }
                } label: {
                    Text("Changer").font(.headline).foregroundStyle(PronoInk.t1)
                        .padding(.horizontal, 18).frame(minHeight: 52)
                        .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(PronoInk.line))
                }
                .buttonStyle(PronoPressStyle())
                .accessibilityIdentifier("prono-change") }
            }
            if canChange, let d = p.closes {
                Text("\(patatesOn(p) ? "Réponse et confettis changeables" : "Réponse changeable") jusqu'à \(PronoRead.moment(d)).")
                    .font(.footnote).foregroundStyle(PronoInk.t3).multilineTextAlignment(.center)
            }
        }
        .padding(20)
        .frame(maxWidth: .infinity)
        .background(LinearGradient(colors: [Color(hex: 0x251D47).opacity(0.8), PronoInk.s1], startPoint: .top, endPoint: .bottom), in: RoundedRectangle(cornerRadius: 28, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 28, style: .continuous).stroke(PronoInk.line))
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 2.4).repeatForever(autoreverses: true)) { breathe = true }
        }
    }

    private func sealFace(_ face: PronoFace, color: String?) -> some View {
        VStack(spacing: 6) {
            ZStack(alignment: .topLeading) {
                PronoSeal(emoji: "", color: color, size: 50)
                    .overlay(Initials(name: face.name, photo: face.photo, size: 28).overlay(Circle().stroke(.white, lineWidth: 1.5)))
                if face.me == true {
                    Image(systemName: "checkmark").font(.system(size: 9, weight: .heavy)).foregroundStyle(Color(hex: 0x1D1530))
                        .frame(width: 18, height: 18).background(PronoInk.mint, in: Circle()).offset(x: -4, y: -4)
                }
            }
            Text(face.label).font(.caption.weight(.semibold)).foregroundStyle(PronoInk.t1).lineLimit(1)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(face.label)
    }

    private func sealsGrid(_ p: Prono) -> some View {
        let faces = p.answered.filter { $0.me == true } + p.answered.filter { $0.me != true }
        let missing = max(0, p.players - p.answered.count)
        return VStack(alignment: .leading, spacing: 10) {
            PronoSectionLabel("Les sceaux", trailing: "\(p.answered.count) \(p.answered.count > 1 ? "ont joué" : "a joué")\(missing > 0 ? ", \(missing) pas encore" : "")")
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 5), spacing: 14) {
                ForEach(faces) { f in sealFace(f, color: p.group?.color) }
                ForEach(0..<min(missing, 10), id: \.self) { _ in
                    VStack(spacing: 6) {
                        Circle().stroke(style: StrokeStyle(lineWidth: 1.5, dash: [4, 4])).foregroundStyle(PronoInk.t3)
                            .overlay(Text("?").font(.headline).foregroundStyle(PronoInk.t3))
                            .frame(width: 50, height: 50)
                        Text(" ").font(.caption)
                    }
                    .accessibilityHidden(true)
                }
            }
            .padding(16)
            .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
        }
    }

    private func sealsPreview(_ p: Prono) -> some View {
        let shown = Array(p.answered.prefix(3))
        return card(radius: 20) {
            HStack(spacing: 14) {
                HStack(spacing: -10) {
                    ForEach(shown) { f in
                        PronoSeal(emoji: "", color: p.group?.color, size: 40)
                            .overlay(Initials(name: f.name, photo: f.photo, size: 24))
                    }
                    if p.answered.count > 3 {
                        Text("+\(p.answered.count - 3)").font(.subheadline.weight(.heavy)).foregroundStyle(PronoInk.t1)
                            .frame(width: 40, height: 40).background(PronoInk.s1, in: Circle())
                    }
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(p.answered.count) \(p.answered.count > 1 ? "réponses déjà scellées" : "réponse déjà scellée")").font(.headline).foregroundStyle(PronoInk.t1)
                        .contentTransition(.numericText())
                    Text("Cachées à tout le monde jusqu'à la fin.").font(.subheadline).foregroundStyle(PronoInk.t2)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

    // MARK: Réactions

    private func reactionsRow(_ p: Prono, trailing: String?) -> some View {
        let list = pronoOpt(p.reactions) ?? []
        let emojis = Self.reactions.filter { $0 != "🥔" || patatesOn(p) }
        return VStack(alignment: .leading, spacing: 10) {
            PronoSectionLabel("Réactions", trailing: trailing)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: emojis.count), spacing: 8) {
                ForEach(emojis, id: \.self) { e in
                    let r = list.first { $0.emoji == e }
                    let mine = r?.mine ?? false
                    let count = r?.count ?? 0
                    Button {
                        Haptics.tap()
                        act("prono_react", ["id": p.id, "emoji": e])
                    } label: {
                        HStack(spacing: 4) {
                            // La base garde « 🥔 » (contrainte de prono_react) ; l'écran montre des confettis.
                            Text(e == "🥔" ? "🎊" : e)
                            if count > 0 { Text("\(count)").font(.subheadline.weight(.heavy)).monospacedDigit().contentTransition(.numericText()) }
                        }
                        .foregroundStyle(PronoInk.t1)
                        .frame(maxWidth: .infinity, minHeight: 44)
                        .background(mine ? PronoInk.lavender.opacity(0.2) : PronoInk.glass, in: Capsule())
                        .overlay(Capsule().stroke(mine ? PronoInk.lavender : PronoInk.line, lineWidth: mine ? 1.5 : 1))
                    }
                    .buttonStyle(PronoPressStyle(scale: 1.1))
                    .accessibilityLabel("\(e == "🥔" ? "Réaction confettis" : e), \(count)")
                    .accessibilityAddTraits(mine ? .isSelected : [])
                    .accessibilityIdentifier("prono-react-\(Self.reactions.firstIndex(of: e) ?? 0)")
                }
            }
        }
    }

    // MARK: Fermé : le résultat

    @ViewBuilder
    private func closedSection(_ p: Prono) -> some View {
        card(fill: PronoInk.soon.opacity(0.09), stroke: PronoInk.soon.opacity(0.45), radius: 20) {
            HStack(spacing: 12) {
                iconTile("hourglass", tint: PronoInk.soon, size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Réponses fermées").font(.footnote.weight(.semibold)).foregroundStyle(PronoInk.soon)
                    Text(closedLine(p)).font(.headline).foregroundStyle(PronoInk.t1)
                }
            }
        }
        .accessibilityElement(children: .combine)
        if !p.mine {
            if p.myAnswer != nil { sealedCard(p, canChange: false) } else { Text("Tu n'as pas joué.").foregroundStyle(PronoInk.t2) }
            if !p.answered.isEmpty { sealsGrid(p) }
        } else if p.answered.isEmpty {
            Text("Personne n'a joué : tu peux annuler ce prono ou déplacer la fin.").foregroundStyle(PronoInk.t2)
        } else if p.kind == "majority" || p.kind == "award" {
            Text(p.kind == "majority" ? "Le résultat se fait tout seul : la réponse la plus choisie l'emporte." : "Le trophée se dévoile tout seul s'il y a au moins 3 votes.")
                .foregroundStyle(PronoInk.t2)
            sealsGrid(p)
        } else {
            resultForm(p)
        }
    }

    private func closedLine(_ p: Prono) -> String {
        if p.kind == "majority" || p.kind == "award" { return "Le dévoilement arrive tout seul" }
        return p.mine ? "À toi de donner le résultat" : "Résultat attendu de \(p.creator.name)"
    }

    private func resultForm(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Quel est le résultat ?").font(.system(size: 26, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
            Text("\(p.answered.count) \(p.answered.count > 1 ? "personnes ont joué" : "personne a joué"). Tout le monde verra le résultat dès que tu valides ; les joueurs ont 12 h pour le contester.")
                .font(.footnote).foregroundStyle(PronoInk.t2)
            resultInputs(p)
            PronoPrimaryButton(p.kind == "text" ? "🎉 Dévoiler · \(winners.count) bonne\(winners.count > 1 ? "s" : "") réponse\(winners.count > 1 ? "s" : "")" : "🎉 Dévoiler le résultat") {
                Haptics.press()
                var body: [String: Any] = [:]
                if optionKinds.contains(p.kind) { body["option_id"] = resultOption ?? "" } else {
                    switch p.kind {
                    case "person": body["person_id"] = resultPerson ?? ""
                    case "number": body["number"] = Double(resultNumber.replacingOccurrences(of: ",", with: ".")) ?? 0
                    case "when": body["time"] = ISO8601DateFormatter().string(from: resultTime)
                    default: body["winners"] = Array(winners)
                    }
                }
                act("prono_result", ["id": p.id, "body": body]) { PronoHaptics.success() }
            }
            .disabled(busy || !resultReady(p))
            .accessibilityIdentifier("prono-reveal-button")
        }
    }

    @ViewBuilder
    private func resultInputs(_ p: Prono) -> some View {
        if optionKinds.contains(p.kind) {
            ForEach(Array(p.options.enumerated()), id: \.element.id) { i, o in
                resultRow(o.label, mark: .of(kind: p.kind, index: i), detail: o.count.map { "\($0) réponse\($0 > 1 ? "s" : "")" }, on: resultOption == o.id, id: "prono-result-\(i)") { resultOption = o.id }
            }
        } else {
            switch p.kind {
            case "person":
                LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 12), count: 3), spacing: 14) {
                    ForEach(Array((p.candidates ?? []).enumerated()), id: \.element.id) { i, face in
                        let on = resultPerson == face.id
                        Button { PronoHaptics.selection(); resultPerson = face.id } label: {
                            VStack(spacing: 6) {
                                Initials(name: face.name, photo: face.photo, size: 56)
                                    .overlay(Circle().stroke(PronoInk.mint, lineWidth: on ? 3 : 0))
                                Text(face.label).font(.footnote.weight(.semibold)).foregroundStyle(PronoInk.t1).lineLimit(1)
                            }
                            .frame(maxWidth: .infinity, minHeight: 84)
                        }
                        .buttonStyle(.plain)
                        .accessibilityAddTraits(on ? .isSelected : [])
                        .accessibilityIdentifier("prono-result-\(i)")
                    }
                }
            case "number":
                TextField("Le vrai résultat", text: $resultNumber).keyboardType(.decimalPad).font(.title2.weight(.bold)).foregroundStyle(PronoInk.t1)
                    .padding(14).background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .accessibilityIdentifier("prono-result-number")
            case "when":
                if pronoOpt(p.canHappen) ?? false { happenedCard(p) }
                DatePicker("L'heure exacte", selection: $resultTime, displayedComponents: [.date, .hourAndMinute])
                    .environment(\.timeZone, PronoRead.zurich).foregroundStyle(PronoInk.t1)
                    .accessibilityIdentifier("prono-result-time")
            default:
                ForEach(p.answers ?? []) { a in
                    resultRow(a.hidden == true ? "Réponse masquée" : (a.text ?? ""), mark: nil, detail: a.user.label, on: winners.contains(a.user.id), id: "prono-winner-\(a.user.id)") {
                        if winners.contains(a.user.id) { winners.remove(a.user.id) } else { winners.insert(a.user.id) }
                    }
                }
            }
        }
    }

    private func resultReady(_ p: Prono) -> Bool {
        if optionKinds.contains(p.kind) { return resultOption != nil }
        switch p.kind {
        case "person": return resultPerson != nil
        case "number": return Double(resultNumber.replacingOccurrences(of: ",", with: ".")) != nil
        default: return true
        }
    }

    private func resultRow(_ label: String, mark: PronoMark?, detail: String?, on: Bool, id: String, action: @escaping () -> Void) -> some View {
        Button { PronoHaptics.selection(); action() } label: {
            HStack(spacing: 12) {
                if let mark { PronoMarkTile(mark: mark, size: 36, filled: on, tint: on ? PronoInk.mint : nil) }
                Text(label).font(.headline).foregroundStyle(PronoInk.t1)
                Spacer()
                if let detail { Text(detail).font(.footnote).foregroundStyle(PronoInk.t2) }
                Image(systemName: on ? "checkmark.circle.fill" : "circle").font(.title3).foregroundStyle(on ? PronoInk.mint : PronoInk.t3)
            }
            .padding(.horizontal, 14).frame(minHeight: 60)
            .background(on ? PronoInk.mint.opacity(0.1) : PronoInk.glass, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(on ? PronoInk.mint : PronoInk.line, lineWidth: on ? 2 : 1))
        }
        .buttonStyle(PronoPressStyle())
        .accessibilityAddTraits(on ? .isSelected : [])
        .accessibilityIdentifier(id)
    }

    private func happenedCard(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("C'est arrivé ?").font(.system(size: 22, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                Spacer()
                TimelineView(.periodic(from: .now, by: 1)) { tl in
                    Text(PronoRead.time(tl.date)).font(.system(size: 30, weight: .heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoInk.mint)
                }
                .accessibilityHidden(true)
            }
            Text("Touche au moment où ça arrive : l'heure exacte est notée, puis tout se dévoile.").font(.subheadline).foregroundStyle(PronoInk.t2)
            Button { confirmHappened = true } label: {
                Label("C'est arrivé !", systemImage: "clock").font(.system(size: 20, weight: .heavy, design: .rounded))
                    .foregroundStyle(Color(hex: 0x0E2A1F))
                    .frame(maxWidth: .infinity, minHeight: 58)
                    .background(PronoInk.mint, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .buttonStyle(PronoPressStyle())
            .disabled(busy)
            .accessibilityIdentifier("prono-happened")
            .confirmationDialog("Noter maintenant comme l'heure exacte ?", isPresented: $confirmHappened, titleVisibility: .visible) {
                Button("C'est arrivé : dévoiler") {
                    act("prono_result", ["id": p.id, "body": ["time": ISO8601DateFormatter().string(from: Date())]]) { PronoHaptics.success() }
                }
            }
        }
        .padding(18)
        .background(LinearGradient(colors: [PronoInk.mint.opacity(0.14), PronoInk.mint.opacity(0.04)], startPoint: .top, endPoint: .bottom), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.mint.opacity(0.5)))
    }

    // MARK: Terminé : le résultat

    private func right(_ p: Prono) -> Bool { p.myAnswer?.winner == true }
    private func unanimous(_ p: Prono) -> Bool {
        let answers = p.answers ?? []
        return pronoOpt(p.unanimous) ?? (answers.count > 1 && answers.allSatisfy(\.winner))
    }

    @ViewBuilder
    private func resultSection(_ p: Prono) -> some View {
        trancheLine(p)
        contestBlock(p)
        if p.kind == "award" {
            laureateCard(p)
        } else {
            if p.kind != "text" { goodAnswerCard(p) }
            youCard(p)
            distribution(p)
            if p.kind != "text", p.kind != "number", p.kind != "when", !(p.answers ?? []).isEmpty { playersList(p) }
        }
        reactionsRow(p, trailing: nil)
        if patatesOn(p), let bag = pronoOpt(p.bag) { bagCard(p, balance: bag.balance) }
        if patatesOn(p) { reminder(refill: false) }
        if right(p), !unanimous(p) {
            ShareLink(item: "🔮 J'avais vu juste : « \(p.question) » (Party)") {
                Text("🔮 Partager « J'avais vu juste »").font(.system(size: 18, weight: .heavy, design: .rounded)).foregroundStyle(.white)
                    .frame(maxWidth: .infinity, minHeight: 58)
                    .background(LinearGradient(colors: [PronoInk.actionFrom, PronoInk.action], startPoint: .leading, endPoint: .trailing), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .accessibilityIdentifier("prono-share-right")
        }
    }

    @ViewBuilder
    private func trancheLine(_ p: Prono) -> some View {
        if p.kind != "majority", p.kind != "award" {
            let played = (p.answers ?? []).contains { $0.user.id == p.creator.id }
            HStack(spacing: 8) {
                Initials(name: p.creator.name, photo: p.creator.photo, size: 24)
                (Text("Tranché par ") + Text(p.creator.me == true ? "toi" : p.creator.name).bold() + Text(played ? " · a joué aussi" : ""))
                    .font(.subheadline).foregroundStyle(PronoInk.t2)
            }
            .accessibilityElement(children: .combine)
        }
    }

    @ViewBuilder
    private func contestBlock(_ p: Prono) -> some View {
        if let c = pronoOpt(p.contest), !(pronoOpt(p.settled) ?? false) {
            let contested = pronoOpt(c.contested) ?? false
            let left = PronoRead.remaining(pronoOpt(c.until) ?? nil)
            card(fill: PronoInk.soon.opacity(0.09), stroke: PronoInk.soon.opacity(0.45), radius: 20, padding: 14) {
                HStack(spacing: 12) {
                    iconTile(contested ? "scalemass" : "hourglass", tint: PronoInk.soon, size: 40)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(contested ? "Résultat contesté" : (patatesOn(p) ? "Confettis en attente" : "Résultat donné"))
                            .font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.soon)
                        Text(contested ? "Vote ouvert\(left.map { " encore \($0)" } ?? "")" : "\(left.map { "\($0) pour contester" } ?? "Contestation possible")\(patatesOn(p) ? " · puis dans les sacs" : "")")
                            .font(.footnote).foregroundStyle(PronoInk.t2)
                    }
                    Spacer(minLength: 4)
                    if !contested, pronoOpt(c.canContest) ?? false {
                        Button { contestReason = ""; error = nil; contesting = true } label: {
                            Text("Contester").font(.subheadline.weight(.bold)).foregroundStyle(PronoInk.soon)
                                .padding(.horizontal, 16).frame(minHeight: 44)
                                .background(PronoInk.soon.opacity(0.12), in: Capsule())
                                .overlay(Capsule().stroke(PronoInk.soon.opacity(0.6)))
                        }
                        .buttonStyle(PronoPressStyle())
                        .accessibilityIdentifier("prono-contest")
                    }
                }
            }
            if contested {
                contestVote(p, fair: pronoOpt(c.fair) ?? 0, unfair: pronoOpt(c.unfair) ?? 0, myVote: pronoOpt(c.myVote) ?? nil, canVote: pronoOpt(c.canVote) ?? false)
            }
        }
    }

    private func contestVote(_ p: Prono, fair: Int, unfair: Int, myVote: Bool?, canVote: Bool) -> some View {
        let pending = max(0, (p.answers?.count ?? p.players) - 1 - fair - unfair)
        let total = max(1, fair + unfair + pending)
        return card {
            VStack(alignment: .leading, spacing: 14) {
                Text("Le résultat est-il juste ?").font(.system(size: 24, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                HStack(spacing: 6) {
                    Text("Résultat donné :").foregroundStyle(PronoInk.t2)
                    Text(PronoRead.result(p)).bold().foregroundStyle(PronoInk.t1)
                }
                .font(.subheadline)
                if canVote {
                    HStack(spacing: 10) {
                        voteButton("Oui", symbol: "checkmark", color: PronoInk.shape(1), on: myVote == true) { act("prono_contest_vote", ["id": p.id, "fair": true]) { Haptics.tap() } }
                            .accessibilityIdentifier("prono-contest-fair")
                        voteButton("Non", symbol: "xmark", color: PronoInk.shape(0), on: myVote == false) { act("prono_contest_vote", ["id": p.id, "fair": false]) { Haptics.tap() } }
                            .accessibilityIdentifier("prono-contest-unfair")
                    }
                }
                GeometryReader { geo in
                    HStack(spacing: 3) {
                        Capsule().fill(PronoInk.shape(1)).frame(width: geo.size.width * CGFloat(fair) / CGFloat(total))
                        Capsule().fill(PronoInk.shape(0)).frame(width: geo.size.width * CGFloat(unfair) / CGFloat(total))
                        Capsule().fill(Color.white.opacity(0.08))
                    }
                }
                .frame(height: 10)
                .accessibilityHidden(true)
                HStack {
                    Label("Oui \(fair)", systemImage: "circle.fill").labelStyle(DotLabel(color: PronoInk.shape(1)))
                    Spacer()
                    Label("Non \(unfair)", systemImage: "square.fill").labelStyle(DotLabel(color: PronoInk.shape(0)))
                    Spacer()
                    Text("\(pending) pas encore").foregroundStyle(PronoInk.t2)
                }
                .font(.subheadline.weight(.semibold)).foregroundStyle(PronoInk.t1)
                Divider().overlay(PronoInk.line)
                Text("Si le Non l'emporte, ou en cas d'égalité, le prono est annulé\(patatesOn(p) ? " et tous les confettis sont rendus" : "").")
                    .font(.footnote).foregroundStyle(PronoInk.t2)
                Text("\(p.creator.me == true ? "Tu ne votes pas : c'est toi qui as tranché." : "\(p.creator.name) ne vote pas.") Tu peux changer ton vote jusqu'à la fin.")
                    .font(.footnote).foregroundStyle(PronoInk.t2)
            }
        }
    }

    private func voteButton(_ title: String, symbol: String, color: Color, on: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 10) {
                Image(systemName: symbol).font(.subheadline.weight(.heavy)).foregroundStyle(on ? Color(hex: 0x1D1530) : color)
                    .frame(width: 32, height: 32).background(on ? AnyShapeStyle(color) : AnyShapeStyle(color.opacity(0.16)), in: Circle())
                Text(title).font(.headline).foregroundStyle(PronoInk.t1)
            }
            .frame(maxWidth: .infinity, minHeight: 64)
            .background(on ? color.opacity(0.14) : PronoInk.glass, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(on ? color : PronoInk.line, lineWidth: on ? 2 : 1))
        }
        .buttonStyle(PronoPressStyle())
        .disabled(busy)
        .accessibilityAddTraits(on ? .isSelected : [])
    }

    private var contestSheet: some View {
        let count = contestReason.trimmingCharacters(in: .whitespacesAndNewlines).count
        return NavigationStack {
            VStack(alignment: .leading, spacing: 16) {
                Text("Les joueurs votent pendant 24 h pour dire si le résultat est juste. \(prono?.creator.me == true ? "Toi, qui l'as donné, tu ne votes pas." : "\(prono?.creator.name ?? "L'organisateur"), qui l'a donné, ne vote pas.")")
                    .font(.subheadline).foregroundStyle(PronoInk.t2)
                VStack(alignment: .leading, spacing: 8) {
                    TextField("Pourquoi ? En une phrase.", text: Binding(get: { contestReason }, set: { contestReason = String($0.prefix(140)) }), axis: .vertical)
                        .font(.headline).foregroundStyle(PronoInk.t1).lineLimit(2...4)
                        .accessibilityIdentifier("prono-contest-reason")
                    HStack {
                        Text("Obligatoire, de 3 à 140 caractères").font(.footnote).foregroundStyle(PronoInk.t3)
                        Spacer()
                        Text("\(contestReason.count)/140").font(.footnote.weight(.heavy)).monospacedDigit().foregroundStyle(PronoInk.t2)
                    }
                }
                .padding(16)
                .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(PronoInk.lavender.opacity(0.7), lineWidth: 1.5))
                if let error { Text(error).font(.footnote).foregroundStyle(PronoInk.retreat) }
                PronoPrimaryButton("Envoyer la contestation") {
                    guard let p = prono else { return }
                    act("prono_contest", ["id": p.id, "reason": contestReason.trimmingCharacters(in: .whitespacesAndNewlines)]) {
                        PronoHaptics.soft()
                        contesting = false
                    }
                }
                .disabled(busy || count < 3 || count > 140)
                .accessibilityIdentifier("prono-contest-send")
                Text("Tu ne peux contester qu'une fois.").font(.footnote).foregroundStyle(PronoInk.t3).frame(maxWidth: .infinity)
                Spacer()
            }
            .padding(20)
            .background(PronoInk.s1.ignoresSafeArea())
            .navigationTitle("Contester le résultat")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Fermer") { contesting = false } }
            }
        }
        .presentationDetents([.medium, .large])
    }

    private func goodAnswerCard(_ p: Prono) -> some View {
        let index = p.options.firstIndex { $0.correct == true || $0.id == p.result?.optionId }
        let right = pronoOpt(p.rarity)?.right ?? (p.answers ?? []).filter(\.winner).count
        let of = pronoOpt(p.rarity)?.of ?? (p.answers?.count ?? 0)
        return card(fill: PronoInk.mint.opacity(0.08), stroke: PronoInk.mint.opacity(0.45)) {
            VStack(alignment: .leading, spacing: 12) {
                Text(p.kind == "number" ? "Le vrai compte" : (p.kind == "when" ? "L'heure exacte" : "La bonne réponse"))
                    .font(.footnote.weight(.heavy)).kerning(1.2).foregroundStyle(PronoInk.mint)
                HStack(spacing: 14) {
                    if let index { PronoMarkTile(mark: .of(kind: p.kind, index: index), size: 48, filled: true, tint: PronoInk.mint) }
                    Text(PronoRead.result(p))
                        .font(p.kind == "number" || p.kind == "when" ? .system(size: 64, weight: .heavy).width(.expanded) : .system(size: 32, weight: .heavy, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(p.kind == "number" || p.kind == "when" ? PronoInk.mint : PronoInk.t1)
                        .lineLimit(2).minimumScaleFactor(0.6)
                }
                if of > 0 {
                    Text(unanimous(p) ? "🤝 Unanimes !" : (right == 0 ? "Personne ne l'avait vu" : "🔮 \(right == 1 ? "Seul·e 1" : "Seuls \(right)") sur \(of) l'avai\(right == 1 ? "t" : "ent") vu"))
                        .font(.subheadline.weight(.bold)).foregroundStyle(right == 0 ? PronoInk.t2 : PronoInk.crown)
                        .padding(.horizontal, 12).frame(minHeight: 32)
                        .background(PronoInk.gold.opacity(0.1), in: Capsule())
                        .overlay(Capsule().stroke(PronoInk.gold.opacity(0.35)))
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func youCard(_ p: Prono) -> some View {
        let played = p.myAnswer != nil
        let won = right(p)
        let all = unanimous(p)
        let myStake = p.myAnswer?.stake ?? 0
        let answers = p.answers ?? []
        let nobody = !answers.isEmpty && !answers.contains(where: \.winner)
        let harvest = PronoRead.harvest(p)
        let settled = pronoOpt(p.settled) ?? false
        let winnersStake = answers.filter(\.winner).reduce(0) { $0 + ($1.stake ?? 0) }
        let field = pronoOpt(p.field)?.total ?? answers.reduce(0) { $0 + ($1.stake ?? 0) }
        let tone: Color = all ? PronoInk.lavender : (won ? PronoInk.mint : PronoInk.miss)
        let title = !played ? "Tu n'as pas joué" : (all ? "Vu juste, comme tous" : (won ? "Tu avais vu juste" : "Pas cette fois"))
        let patates = patatesOn(p) && myStake > 0
        return card(fill: PronoInk.s1) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(spacing: 14) {
                    ZStack {
                        Circle().fill(won && !all ? PronoInk.mint : tone.opacity(0.18))
                        if all { Text("🤝") } else if won {
                            Image(systemName: "checkmark").font(.title3.weight(.heavy)).foregroundStyle(Color(hex: 0x1D1530))
                        } else { Circle().stroke(PronoInk.miss, lineWidth: 3).frame(width: 18, height: 18) }
                    }
                    .frame(width: 48, height: 48)
                    .accessibilityHidden(true)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(title).font(.system(size: 20, weight: .bold, design: .rounded)).foregroundStyle(PronoInk.t1)
                        Text(youDetail(p, played: played, won: won, all: all, patates: patates, settled: settled))
                            .font(.subheadline).foregroundStyle(PronoInk.t2).fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer(minLength: 4)
                    if patates {
                        HStack(spacing: 2) {
                            Text(won && !all && !nobody ? "+\(harvest)" : "\(myStake)")
                                .font(.system(size: 34, weight: .heavy).width(.expanded)).monospacedDigit()
                                .foregroundStyle(won && !all && !nobody ? PronoInk.mint : (all || nobody ? PronoInk.lavender : PronoInk.miss))
                            Text("🎊").font(.title2).rotationEffect(.degrees(-12))
                        }
                        .accessibilityElement(children: .ignore)
                        .accessibilityLabel(won && !all && !nobody ? "Tu ramasses \(harvest) confettis" : (all || nobody ? "\(myStake) confettis rendus" : "\(myStake) confettis au balai"))
                    } else if won, !all {
                        Text("+\(p.points)").font(.system(size: 30, weight: .heavy).width(.expanded)).foregroundStyle(PronoInk.mint)
                            .accessibilityLabel("Plus \(PronoFormat.points(p.points))")
                    }
                }
                if patates, won, !all, winnersStake > 0 {
                    GeometryReader { geo in
                        HStack(spacing: 2) {
                            Capsule().fill(PronoInk.mint).frame(width: geo.size.width * CGFloat(myStake) / CGFloat(winnersStake))
                            Capsule().fill(PronoInk.mint.opacity(0.25))
                        }
                    }
                    .frame(height: 12)
                    .accessibilityHidden(true)
                    Text("La piste (\(field) 🎊) est partagée entre ceux qui ont vu juste, selon ce que chacun a lancé : \(myStake) sur \(winnersStake), c'est \(harvest) 🎊 pour toi.")
                        .font(.subheadline).foregroundStyle(PronoInk.t2).fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .overlay(alignment: .top) { Capsule().fill(tone).frame(height: 2).padding(.horizontal, 28) }
        .accessibilityElement(children: .combine)
    }

    private func youDetail(_ p: Prono, played: Bool, won: Bool, all: Bool, patates: Bool, settled: Bool) -> String {
        if !played { return "Ta réponse aurait été cachée jusqu'au bout." }
        if all { return patates ? "Personne ne perd rien : tes confettis sont rendus." : "Tout le monde a ses points." }
        if won { return patates ? "Tu ramasses\(settled ? "" : " · en attente")" : "+\(PronoFormat.points(p.points)) au classement" }
        let said = PronoRead.mine(p) ?? "—"
        let good = PronoRead.result(p)
        return good.isEmpty ? "Tu avais dit \(said)." : "Tu avais dit \(said). La bonne : \(good)."
    }

    @ViewBuilder
    private func distribution(_ p: Prono) -> some View {
        let answers = p.answers ?? []
        if optionKinds.contains(p.kind) || p.kind == "person" {
            let total = max(1, answers.count)
            VStack(alignment: .leading, spacing: 10) {
                PronoSectionLabel("La répartition", trailing: patatesOn(p) ? "\(pronoOpt(p.field)?.total ?? 0) 🎊 sur la piste" : nil)
                VStack(spacing: 8) {
                    if p.kind == "person" {
                        let groups = Dictionary(grouping: answers) { $0.person?.id ?? "" }.sorted { $0.value.count > $1.value.count }
                        ForEach(groups, id: \.key) { key, rows in
                            barRow(p, label: rows.first?.person?.label ?? "—", mark: nil, faces: rows.map(\.user), count: rows.count, total: total,
                                   stake: rows.reduce(0) { $0 + ($1.stake ?? 0) }, good: (p.result?.person?.id ?? p.winners?.first?.id) == key)
                        }
                    } else {
                        let byOption = pronoOpt(pronoOpt(p.field)?.byOption) ?? []
                        ForEach(Array(p.options.enumerated()), id: \.element.id) { i, o in
                            let who = answers.filter { $0.optionId == o.id }
                            barRow(p, label: o.label, mark: .of(kind: p.kind, index: i), faces: who.map(\.user), count: o.count ?? who.count, total: total,
                                   stake: byOption.first { $0.optionId == o.id }?.total ?? who.reduce(0) { $0 + ($1.stake ?? 0) },
                                   good: o.correct == true || p.result?.optionId == o.id)
                        }
                    }
                }
                .padding(10)
                .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
            }
        } else if p.kind == "number" || p.kind == "when" {
            closestBlock(p)
        } else if p.kind == "text", !answers.isEmpty {
            answersList(p, answers)
        }
    }

    private func barRow(_ p: Prono, label: String, mark: PronoMark?, faces: [PronoFace], count: Int, total: Int, stake: Int, good: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                if let mark { PronoMarkTile(mark: mark, size: 28, filled: good, tint: good ? PronoInk.mint : PronoInk.miss) }
                Text(label).font(.system(.headline, design: .rounded)).foregroundStyle(good ? PronoInk.t1 : PronoInk.t2).lineLimit(1)
                Spacer()
                if patatesOn(p) { Text("\(stake) 🎊 ·").font(.footnote).monospacedDigit().foregroundStyle(PronoInk.t2) }
                Text("\(count)").font(.headline.weight(.heavy)).monospacedDigit().foregroundStyle(PronoInk.t1)
            }
            GeometryReader { geo in
                let w = max(10, geo.size.width * CGFloat(count) / CGFloat(total))
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.white.opacity(0.07))
                    Capsule().fill(good ? AnyShapeStyle(PronoInk.mint) : AnyShapeStyle(PronoInk.lavender.opacity(0.35))).frame(width: count > 0 ? w : 0)
                    if !faces.isEmpty {
                        PronoAvatarStack(faces: Array(faces.prefix(5)), extra: max(0, faces.count - 5), size: 24).offset(x: max(0, w - 14))
                    }
                }
            }
            .frame(height: 24)
        }
        .padding(12)
        .background(good ? PronoInk.mint.opacity(0.1) : Color.clear, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(good ? PronoInk.mint : PronoInk.line, lineWidth: good ? 1.5 : 1))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label) : \(count) réponse\(count > 1 ? "s" : "")\(good ? ", bonne réponse" : "")")
    }

    /// Nombre et heure : l'axe (vraie valeur en menthe, chaque réponse à sa place) puis du plus proche au plus loin.
    @ViewBuilder
    private func closestBlock(_ p: Prono) -> some View {
        let truth = PronoRead.resultValue(p)
        let rows = (p.answers ?? []).compactMap { a -> (PronoShownAnswer, Double)? in PronoRead.value(p, a).map { (a, $0) } }
            .sorted { abs($0.1 - (truth ?? 0)) < abs($1.1 - (truth ?? 0)) }
        if let truth, !rows.isEmpty {
            VStack(alignment: .leading, spacing: 10) {
                PronoSectionLabel("Les réponses", trailing: "🎯 le plus proche")
                PronoAxis(points: rows.map { .init(id: $0.0.user.id, face: $0.0.user, value: $0.1, winner: $0.0.winner) }, truth: truth,
                          format: { p.kind == "when" ? PronoRead.time(Date(timeIntervalSince1970: $0 * 60)) : PronoFormat.number($0) })
                    .frame(height: 200)
                    .padding(14)
                    .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
                PronoSectionLabel("Du plus proche au plus loin")
                VStack(spacing: 0) {
                    ForEach(Array(rows.enumerated()), id: \.offset) { i, row in
                        let gap = abs(row.1 - truth)
                        let rank = (rows.firstIndex { abs(abs($0.1 - truth) - gap) < 0.0001 } ?? i) + 1
                        closestRow(p, row.0, rank: rank, gap: gap)
                        if i < rows.count - 1 { Divider().overlay(PronoInk.line).padding(.leading, 64) }
                    }
                }
                .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
            }
        }
    }

    private func closestRow(_ p: Prono, _ a: PronoShownAnswer, rank: Int, gap: Double) -> some View {
        let said = p.kind == "when" ? PronoRead.time(a.answerAt) : (a.number.map(PronoFormat.number) ?? "—")
        let gapText = p.kind == "when" ? "à \(Int(gap.rounded())) min" : "à \(PronoFormat.number((gap * 100).rounded() / 100))"
        let stake = a.stake ?? 0
        return HStack(spacing: 12) {
            Text("\(rank)").font(.headline.weight(.heavy)).monospacedDigit().foregroundStyle(a.winner ? PronoInk.mint : PronoInk.t2).frame(width: 20)
            Initials(name: a.user.name, photo: a.user.photo, size: 36)
                .overlay(Circle().stroke(a.user.me == true ? Color.white : .clear, lineWidth: 2))
            VStack(alignment: .leading, spacing: 2) {
                Text(a.user.label).font(.headline).foregroundStyle(PronoInk.t1)
                Text("a dit \(said)\(patatesOn(p) && stake > 0 ? " · \(stake) 🎊" : "")").font(.subheadline).monospacedDigit().foregroundStyle(PronoInk.t2)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 2) {
                Text((a.winner ? "🎯 " : "") + gapText).font(.footnote.weight(.bold)).monospacedDigit().foregroundStyle(PronoInk.t1)
                    .padding(.horizontal, 8).frame(minHeight: 24).background(Color.white.opacity(0.08), in: Capsule())
                harvestLine(p, a)
            }
        }
        .padding(.horizontal, 14).frame(minHeight: 60)
        .background(a.user.me == true ? Color.white.opacity(0.04) : .clear)
        .accessibilityElement(children: .combine)
    }

    @ViewBuilder
    private func harvestLine(_ p: Prono, _ a: PronoShownAnswer) -> some View {
        let stake = a.stake ?? 0
        if patatesOn(p), stake > 0 {
            let refunded = unanimous(p) || !(p.answers ?? []).contains(where: \.winner)
            if refunded {
                Text("rendus").font(.footnote).foregroundStyle(PronoInk.lavender)
            } else if a.winner {
                Text("\(pronoOpt(a.harvest).map { "\($0)" } ?? "…") 🎊 ramassés").font(.footnote.weight(.bold)).monospacedDigit().foregroundStyle(PronoInk.mint)
            } else {
                Text("au balai").font(.footnote).foregroundStyle(PronoInk.t2)
            }
        } else if a.winner, !patatesOn(p) {
            Text("+\(p.points)").font(.footnote.weight(.bold)).foregroundStyle(PronoInk.mint)
        }
    }

    private func playersList(_ p: Prono) -> some View {
        let answers = (p.answers ?? []).sorted { ($0.user.me == true ? 2 : ($0.winner ? 1 : 0)) > ($1.user.me == true ? 2 : ($1.winner ? 1 : 0)) }
        return VStack(alignment: .leading, spacing: 10) {
            PronoSectionLabel("Les joueurs · \(answers.count)", trailing: patatesOn(p) ? "lancés → ramassés" : nil)
            VStack(spacing: 0) {
                ForEach(Array(answers.enumerated()), id: \.element.id) { i, a in
                    HStack(spacing: 12) {
                        Initials(name: a.user.name, photo: a.user.photo, size: 40)
                            .overlay(Circle().stroke(a.user.me == true ? Color.white : .clear, lineWidth: 2))
                            .overlay(alignment: .bottomTrailing) {
                                if a.winner {
                                    Image(systemName: "checkmark").font(.system(size: 8, weight: .heavy)).foregroundStyle(Color(hex: 0x1D1530))
                                        .frame(width: 16, height: 16).background(PronoInk.mint, in: Circle())
                                }
                            }
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 6) {
                                Text(a.user.label).font(.headline).foregroundStyle(PronoInk.t1)
                                if a.user.id == p.creator.id {
                                    Text("a tranché").font(.caption).foregroundStyle(PronoInk.t2).padding(.horizontal, 6).padding(.vertical, 2).background(Color.white.opacity(0.08), in: Capsule())
                                }
                            }
                            HStack(spacing: 4) {
                                if let i = PronoRead.markIndex(p, option: a.optionId) {
                                    let m = PronoMark.of(kind: p.kind, index: i)
                                    Image(systemName: m.symbol).font(.caption2.weight(.heavy)).foregroundStyle(a.winner ? PronoInk.mint : PronoInk.t3)
                                }
                                Text(PronoRead.answer(p, option: a.optionId, number: a.number, text: a.text, person: a.person, personId: nil, at: a.answerAt))
                            }
                            .font(.subheadline).foregroundStyle(PronoInk.t2).lineLimit(1)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 2) {
                            harvestLine(p, a)
                            if patatesOn(p), let s = a.stake, s > 0 { Text("\(s) 🎊 lancés").font(.caption).monospacedDigit().foregroundStyle(PronoInk.t3) }
                        }
                    }
                    .padding(.horizontal, 14).frame(minHeight: 64)
                    .accessibilityElement(children: .combine)
                    if i < answers.count - 1 { Divider().overlay(PronoInk.line).padding(.leading, 66) }
                }
            }
            .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
        }
    }

    private func laureateCard(_ p: Prono) -> some View {
        let award = PronoRead.award(p)
        let face = p.result?.person ?? p.winners?.first
        let votes = face.map { f in (p.answers ?? []).filter { $0.person?.id == f.id }.count } ?? 0
        return card {
            VStack(spacing: 10) {
                Text("🏆 Trophée de la soirée").font(.footnote.weight(.heavy)).foregroundStyle(PronoInk.crown)
                Text("\(award.emoji) \(award.name)").font(.system(size: 26, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1).multilineTextAlignment(.center)
                if let face {
                    Initials(name: face.name, photo: face.photo, size: 104)
                        .padding(5)
                        .overlay(Circle().stroke(AngularGradient(colors: [PronoInk.gold, Color(hex: 0xFFB347), PronoInk.gold], center: .center), lineWidth: 5))
                        .shadow(color: PronoInk.gold.opacity(0.5), radius: 26)
                    Text(face.label).font(.system(size: 32, weight: .heavy, design: .rounded)).foregroundStyle(PronoInk.t1)
                    Text("choisi·e par \(votes) des \(p.answers?.count ?? 0) votants").font(.subheadline).foregroundStyle(PronoInk.t2)
                } else {
                    Text("Pas assez de votes pour dévoiler ce trophée.").font(.subheadline).foregroundStyle(PronoInk.t2)
                }
                Text("Pour la gloire : aucun trophée ne rapporte de confettis.").font(.footnote).foregroundStyle(PronoInk.t3).opacity(pronoOpt(pronoOpt(store.features)?.patates) ?? false ? 1 : 0)
            }
            .frame(maxWidth: .infinity)
        }
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("prono-laureate")
    }

    private func bagCard(_ p: Prono, balance: Int) -> some View {
        let pending = !(pronoOpt(p.settled) ?? false) && right(p) && !unanimous(p) ? PronoRead.harvest(p) : 0
        return VStack(alignment: .leading, spacing: 10) {
            if let g = p.group { PronoSectionLabel(g.name) } else if let e = p.event { PronoSectionLabel(e.title) }
            card {
                HStack(spacing: 14) {
                    Text("🎊").font(.title).frame(width: 52, height: 52).background(PronoInk.patateFill.opacity(0.14), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Ton sac").font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.t1)
                        Text("Remonte à 100 lundi s'il est en dessous").font(.subheadline).foregroundStyle(PronoInk.t2)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 2) {
                        Text("\(balance) 🎊").font(.system(size: 30, weight: .heavy).width(.expanded)).monospacedDigit().foregroundStyle(PronoInk.t1)
                        if pending > 0 { Text("+\(pending) en attente").font(.footnote.weight(.semibold)).foregroundStyle(PronoInk.soon) }
                    }
                }
            }
            .accessibilityElement(children: .combine)
        }
    }

    private func cancelledCard(_ p: Prono) -> some View {
        card(radius: 20) {
            HStack(alignment: .top, spacing: 12) {
                iconTile("xmark.circle", tint: PronoInk.miss)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Prono annulé").font(.system(.headline, design: .rounded)).foregroundStyle(PronoInk.t1)
                    Text(patatesOn(p) ? "Tous les confettis lancés sont rendus ; aucun point n'est compté." : "Aucun point n'est compté.")
                        .font(.subheadline).foregroundStyle(PronoInk.t2)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }

    private func answersList(_ p: Prono, _ answers: [PronoShownAnswer]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            PronoSectionLabel("Les réponses")
            ForEach(answers) { a in
                HStack(spacing: 12) {
                    Initials(name: a.user.name, photo: a.user.photo, size: 32)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(PronoRead.answer(p, option: a.optionId, number: a.number, text: a.hidden == true ? nil : a.text, person: a.person, personId: nil, at: a.answerAt))
                            .font(.headline).foregroundStyle(PronoInk.t1)
                        Text(a.user.label).font(.caption).foregroundStyle(PronoInk.t2)
                    }
                    Spacer()
                    if a.winner { Image(systemName: "checkmark.circle.fill").foregroundStyle(PronoInk.mint).accessibilityLabel("Bonne réponse") }
                    if p.kind == "text", a.user.me != true, a.hidden != true {
                        Button("Signaler") { reportTarget = .init(id: "\(p.id):\(a.user.id)", author: a.user.id) }
                            .font(.footnote).foregroundStyle(PronoInk.t2).frame(minHeight: 44)
                    }
                }
                .padding(.horizontal, 14).padding(.vertical, 8)
                .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(a.winner ? PronoInk.mint : PronoInk.line))
            }
        }
    }

    // MARK: Organisation (repliée)

    private func linkURL(_ p: Prono) -> URL? {
        p.link?.path.flatMap { URL(string: $0, relativeTo: AppConfig.baseURL)?.absoluteURL }
    }

    private func moveEnd(_ p: Prono, to date: Date) {
        act("prono_update", ["id": p.id, "body": ["closes_at": ISO8601DateFormatter().string(from: date)]]) { Haptics.tap() }
    }

    private func midnight(after d: Date) -> Date {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = PronoRead.zurich
        return cal.date(byAdding: .day, value: 1, to: cal.startOfDay(for: d)) ?? d
    }

    private func orgRow<Trailing: View>(_ symbol: String, title: String, detail: String?, tint: Color = PronoInk.t1, @ViewBuilder trailing: () -> Trailing) -> some View {
        HStack(spacing: 14) {
            iconTile(symbol, tint: tint, size: 44)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(.headline, design: .rounded)).foregroundStyle(tint)
                if let detail { Text(detail).font(.subheadline).foregroundStyle(PronoInk.t2).fixedSize(horizontal: false, vertical: true) }
            }
            Spacer(minLength: 6)
            trailing()
        }
    }

    private func glassButton(_ title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title).font(.subheadline.weight(.bold)).foregroundStyle(PronoInk.t1)
                .padding(.horizontal, 16).frame(minHeight: 44)
                .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(PronoInk.line))
        }
        .buttonStyle(PronoPressStyle())
        .disabled(busy)
    }

    private func organisation(_ p: Prono) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Button {
                Haptics.tap()
                Motion.animate(Motion.smooth) { orgOpen.toggle() }
            } label: {
                orgRow("gearshape", title: "Organisation", detail: orgOpen ? "Toi seul vois ces réglages" : "Lien, fin, résultat, annulation") {
                    Image(systemName: "chevron.down").font(.subheadline.weight(.bold)).foregroundStyle(PronoInk.t2)
                        .rotationEffect(.degrees(orgOpen ? 180 : 0))
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityAddTraits(.isHeader)
            .accessibilityValue(orgOpen ? "ouverte" : "repliée")
            .accessibilityIdentifier("prono-org-toggle")
            if orgOpen { orgContent(p).transition(.opacity.combined(with: .move(edge: .top))) }
        }
        .padding(16)
        .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).stroke(PronoInk.line))
    }

    @ViewBuilder
    private func orgContent(_ p: Prono) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: "lock.fill").foregroundStyle(PronoInk.lavender)
            Text("Toi non plus, tu ne vois pas les réponses avant la fin. C'est ce qui rend le prono juste.").font(.subheadline).foregroundStyle(PronoInk.t1)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(PronoInk.lavender.opacity(0.14), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .accessibilityElement(children: .combine)
        if p.state == "open", p.kind == "when", pronoOpt(p.canHappen) ?? false { happenedCard(p) }
        if p.state == "open" {
            if let url = linkURL(p) {
                orgRow("link", title: "Lien pour inviter", detail: "Qui l'ouvre se connecte à Party, puis joue. Il s'arrête à la fin.") {
                    glassButton(copied ? "Copié ✓" : "Copier") {
                        UIPasteboard.general.url = url
                        Haptics.success()
                        copied = true
                        Task { try? await Task.sleep(nanoseconds: 2_000_000_000); copied = false }
                    }
                    .accessibilityIdentifier("prono-link-copy")
                }
                HStack(spacing: 10) {
                    ShareLink(item: url, subject: Text("Un prono pour toi"), message: Text(p.question)) {
                        Label("Partager le lien", systemImage: "square.and.arrow.up").font(.subheadline.weight(.bold)).frame(maxWidth: .infinity, minHeight: 44)
                    }
                    .foregroundStyle(PronoInk.t1)
                    .background(PronoInk.glass, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    glassButton("Arrêter") { act("prono_set_link", ["id": p.id, "active": false]) }
                }
            } else {
                orgRow("link", title: "Lien pour inviter", detail: "Qui l'ouvre se connecte à Party, puis joue.") {
                    glassButton("Créer") { act("prono_set_link", ["id": p.id, "active": true]) }
                        .accessibilityIdentifier("prono-link-create")
                }
            }
        }
        if p.canMoveEnd, !(p.reveal == "close" && p.revealed), let closes = p.closes {
            Divider().overlay(PronoInk.line)
            orgRow("timer", title: "Déplacer la fin", detail: "Aujourd'hui : \(PronoRead.moment(closes))") { EmptyView() }
            HStack(spacing: 8) {
                let base = max(closes, Date())
                glassButton("+30 min") { moveEnd(p, to: base.addingTimeInterval(1800)) }.frame(maxWidth: .infinity)
                glassButton("+1 h") { moveEnd(p, to: base.addingTimeInterval(3600)) }.frame(maxWidth: .infinity)
                glassButton("Minuit") { moveEnd(p, to: midnight(after: base)) }.frame(maxWidth: .infinity)
                glassButton("Choisir…") {
                    newEnd = max(closes, Date().addingTimeInterval(120))
                    Motion.animate(Motion.snappy) { choosingEnd.toggle() }
                }
                .frame(maxWidth: .infinity)
            }
            if choosingEnd {
                DatePicker("Nouvelle fin", selection: $newEnd, in: Date().addingTimeInterval(60)..., displayedComponents: [.date, .hourAndMinute])
                    .environment(\.timeZone, PronoRead.zurich).foregroundStyle(PronoInk.t1)
                glassButton("Déplacer la fin") { choosingEnd = false; moveEnd(p, to: newEnd) }
            }
        }
        if p.state == "open", p.kind == "when", pronoOpt(p.canHappen) ?? false {
            Divider().overlay(PronoInk.line)
            Button { Motion.animate(Motion.snappy) { manualTime.toggle() } } label: {
                orgRow("pencil", title: "Donner le résultat", detail: "Saisir l'heure à la main") {
                    Image(systemName: "chevron.right").foregroundStyle(PronoInk.t2).rotationEffect(.degrees(manualTime ? 90 : 0))
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            if manualTime {
                DatePicker("L'heure exacte", selection: $resultTime, displayedComponents: [.date, .hourAndMinute])
                    .environment(\.timeZone, PronoRead.zurich).foregroundStyle(PronoInk.t1)
                glassButton("Valider cette heure") {
                    act("prono_result", ["id": p.id, "body": ["time": ISO8601DateFormatter().string(from: resultTime)]]) { PronoHaptics.success() }
                }
            }
        }
        if p.state == "open" {
            Divider().overlay(PronoInk.line)
            orgRow("lock", title: "Fermer les réponses", detail: "Plus personne ne peut répondre ni changer.") {
                glassButton("Fermer") { act("prono_close_now", ["id": p.id]) }
                    .accessibilityLabel("Fermer maintenant")
                    .accessibilityIdentifier("prono-close-now")
            }
        }
        if p.locked {
            Text("Quelqu'un a joué : la question et les choix ne changent plus.")
                .font(.footnote).foregroundStyle(PronoInk.t3)
        }
        Divider().overlay(PronoInk.line)
        Button { confirmCancel = true } label: {
            orgRow("xmark.circle", title: p.state == "closed" ? "Pas de résultat (annuler)" : "Annuler le prono",
                   detail: patatesOn(p) ? "Tous les confettis sont rendus. Confirmation demandée." : "Aucun point n'est compté. Confirmation demandée.",
                   tint: PronoInk.retreat) { EmptyView() }
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("prono-cancel")
        .confirmationDialog("Annuler ce prono ?", isPresented: $confirmCancel, titleVisibility: .visible) {
            Button(patatesOn(p) ? "Oui, annuler : confettis rendus" : "Oui, annuler : aucun point", role: .destructive) { act("prono_cancel", ["id": p.id]) }
        }
    }

    // MARK: Appels

    private func revealKey(_ p: Prono) -> String {
        let me = p.answers?.first { $0.user.me == true }?.user.id ?? (p.mine ? p.creator.id : "spectateur")
        return "prono.reveal.seen.\(p.id).\(me)"
    }

    /// Reprend la réponse scellée (ou la présélection de la liste) dans le brouillon.
    private func draft(_ p: Prono) {
        guard !drafted else { return }
        drafted = true
        if let m = p.myAnswer {
            option = m.optionId
            person = m.personId
            if let n = m.number { number = n; numberSet = true; numberText = PronoFormat.number(n) }
            if let at = pronoOpt(m.answerAt).flatMap(PronoFormat.date) { when = at; whenSet = true }
            text = m.text ?? ""
            stake = m.stake ?? 0
        } else if let preselect {
            if p.options.contains(where: { $0.id == preselect }) { option = preselect }
            if p.candidates?.contains(where: { $0.id == preselect }) == true { person = preselect }
        }
        if !numberSet, let line = pronoOpt(p.line) { number = line.rounded() }
        stake = min(stake, maxStake(p))
    }

    private func seen(_ p: Prono) {
        guard p.state == "done", p.kind != "text" else { return }
        let key = revealKey(p)
        guard !UserDefaults.standard.bool(forKey: key) else { return }
        UserDefaults.standard.set(true, forKey: key)
        showReveal = true
    }

    private func load() async {
        do {
            let p: Prono = try await store.call("prono_get", ["id": id])
            Motion.animate(Motion.smooth) { prono = p }
            error = nil
            draft(p)
            seen(p)
        } catch {
            self.error = PronosStore.message(error)
        }
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
                if p.myAnswer == nil { editing = false }
                seen(p)
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

/// Appui : échelle 0,97 (ou plus grande pour une réaction), retour au ressort.
struct PronoPressStyle: ButtonStyle {
    var scale: CGFloat = 0.97
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed && !reduceMotion ? scale : 1)
            .animation(.spring(response: 0.3, dampingFraction: 0.6), value: configuration.isPressed)
    }
}

/// Ligne horizontale (la ligne du Plus / Moins).
struct PronoHLine: Shape {
    func path(in rect: CGRect) -> Path {
        Path { p in p.move(to: CGPoint(x: rect.minX, y: rect.midY)); p.addLine(to: CGPoint(x: rect.maxX, y: rect.midY)) }
    }
}

private struct DotLabel: LabelStyle {
    let color: Color
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 6) {
            configuration.icon.font(.system(size: 8)).foregroundStyle(color)
            configuration.title
        }
    }
}

/// Puces qui passent à la ligne (iOS 16 : Layout).
struct PronoFlow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, line: CGFloat = 0, widest: CGFloat = 0
        for s in subviews {
            let size = s.sizeThatFits(.unspecified)
            if x > 0, x + size.width > width { x = 0; y += line + spacing; line = 0 }
            x += size.width + spacing
            line = max(line, size.height)
            widest = max(widest, x - spacing)
        }
        return CGSize(width: min(widest, width), height: y + line)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, line: CGFloat = 0
        for s in subviews {
            let size = s.sizeThatFits(.unspecified)
            if x > bounds.minX, x + size.width > bounds.maxX { x = bounds.minX; y += line + spacing; line = 0 }
            s.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            line = max(line, size.height)
        }
    }
}

/// Axe « le plus proche » (4-resultat-nombre / 4-resultat-heure) : vraie valeur en menthe, chaque réponse à sa place,
/// un couloir de plus quand deux visages se touchent (moins de 31 pt).
struct PronoAxis: View {
    struct Point: Identifiable {
        let id: String
        let face: PronoFace
        let value: Double
        let winner: Bool
    }

    let points: [Point]
    let truth: Double
    let format: (Double) -> String

    var body: some View {
        GeometryReader { geo in
            let values = points.map(\.value) + [truth]
            let lo0 = values.min() ?? 0, hi0 = values.max() ?? 1
            let pad = max(1, (hi0 - lo0) * 0.08)
            let lo = lo0 - pad, hi = hi0 + pad
            let w = geo.size.width
            let base = geo.size.height - 28
            let x: (Double) -> CGFloat = { CGFloat(($0 - lo) / (hi - lo)) * w }
            let lanes = laneOf(x)
            ZStack(alignment: .topLeading) {
                Path { p in p.move(to: CGPoint(x: 0, y: base)); p.addLine(to: CGPoint(x: w, y: base)) }
                    .stroke(Color.white.opacity(0.2), lineWidth: 1)
                ForEach(0..<5, id: \.self) { k in
                    let v = lo + (hi - lo) * Double(k) / 4
                    Path { p in p.move(to: CGPoint(x: x(v), y: base - 4)); p.addLine(to: CGPoint(x: x(v), y: base + 4)) }
                        .stroke(Color.white.opacity(0.3), lineWidth: 1)
                    Text(format(v.rounded())).font(.caption.weight(.semibold)).monospacedDigit().foregroundStyle(PronoInk.t2)
                        .fixedSize().position(x: min(max(x(v), 16), w - 16), y: base + 16)
                }
                Path { p in p.move(to: CGPoint(x: x(truth), y: 30)); p.addLine(to: CGPoint(x: x(truth), y: base)) }
                    .stroke(PronoInk.mint, lineWidth: 3)
                    .shadow(color: PronoInk.mint.opacity(0.6), radius: 7)
                Text(format(truth)).font(.headline.weight(.heavy)).monospacedDigit().foregroundStyle(Color(hex: 0x1D1530))
                    .padding(.horizontal, 10).frame(height: 28).background(PronoInk.mint, in: Capsule())
                    .fixedSize().position(x: min(max(x(truth), 30), w - 30), y: 14)
                ForEach(points) { pt in
                    let lane = lanes[pt.id] ?? 0
                    let y = base - 20 - CGFloat(lane) * 36
                    Path { p in p.move(to: CGPoint(x: x(pt.value), y: y + 14)); p.addLine(to: CGPoint(x: x(pt.value), y: base)) }
                        .stroke(Color.white.opacity(0.25), lineWidth: 1)
                    Initials(name: pt.face.name, photo: pt.face.photo, size: 28)
                        .overlay(Circle().stroke(pt.winner ? PronoInk.mint : (pt.face.me == true ? Color.white : .clear), lineWidth: 2.5))
                        .position(x: x(pt.value), y: y)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Bonne valeur : \(format(truth)). " + points.prefix(5).map { "\($0.face.label) : \(format($0.value))" }.joined(separator: ", "))
    }

    private func laneOf(_ x: (Double) -> CGFloat) -> [String: Int] {
        var lanes: [String: Int] = [:]
        var lastX: [CGFloat] = []
        for pt in points.sorted(by: { $0.value < $1.value }) {
            let px = x(pt.value)
            var lane = 0
            while lane < lastX.count, px - lastX[lane] < 31 { lane += 1 }
            lane = min(lane, 3)
            if lane < lastX.count { lastX[lane] = px } else { lastX.append(px) }
            lanes[pt.id] = lane
        }
        return lanes
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

    private let reasons = [("harassment", "Harcèlement"), ("shocking", "Contenu choquant"), ("money", "Demande d'argent / vente de confettis"),
                           ("spam", "Spam"), ("scam", "Arnaque ou vente"), ("other", "Autre")]

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
#endif
