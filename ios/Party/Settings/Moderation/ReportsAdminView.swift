import SwiftUI

/// Réglages › Administration › Signalements (droit « Modérer les signalements ») : la file, le contenu signalé (copie prise
/// au moment du signalement) et les actions, notées au Journal. Suspendre et bannir visent le COMPTE (jamais une IP) et
/// demandent aussi le droit « Bannir ou réintégrer un compte » (la base le vérifie).
struct ReportsAdminView: View {
    @ObservedObject var store: ModerationStore
    /// Admin : adresse de contact publiée et « Exiger les CGU ».
    let isAdmin: Bool
    @State private var status = "open"
    @State private var email = ""

    private static let filters = [("open", "À traiter"), ("actioned", "Traités"), ("dismissed", "Classés"), ("all", "Tous")]

    var body: some View {
        List {
            Section {
                Picker("Signalements", selection: $status) {
                    ForEach(Self.filters, id: \.0) { Text($0.1).tag($0.0) }
                }
                .pickerStyle(.segmented)
                .listRowBackground(Color.clear)
            }
            if let reports = store.queue?.reports {
                if reports.isEmpty {
                    Section { Text(status == "open" ? "Aucun signalement à traiter. 🎉" : "Rien ici.").foregroundStyle(.secondary) }
                }
                ForEach(reports) { report in
                    ReportRow(store: store, report: report, status: status).motionTransition(.opacity)
                }
            } else if let error = store.error {
                Section { Text(error).foregroundStyle(.red) }
            } else {
                Section { ProgressView() }
            }
            if isAdmin, let settings = store.queue?.settings {
                Section {
                    TextField("Adresse de contact", text: $email)
                        .keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button("Enregistrer l'adresse") { Task { await store.saveSettings(contactEmail: email.trimmingCharacters(in: .whitespaces), termsEnforced: nil) } }
                        .disabled(store.busy.contains("settings"))
                    Toggle("Exiger les conditions d'utilisation", isOn: Binding(get: { settings.termsEnforced }, set: { on in
                        Task { await store.saveSettings(contactEmail: nil, termsEnforced: on) }
                    }))
                } header: {
                    Text("Réglages de la modération")
                } footer: {
                    Text("L'adresse s'affiche dans les conditions d'utilisation (exigée par Apple et Google). Exiger : la base refuse tout message ou nom tant que le compte n'a pas accepté les conditions ; à activer une fois l'app iPhone à jour partout.")
                }
                .onAppear { if email.isEmpty { email = settings.contactEmail ?? "" } }
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(AppConfig.background.ignoresSafeArea())
        .motion(Motion.smooth, value: store.queue?.reports.map(\.id))
        .navigationTitle("Signalements")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: status) { await store.loadQueue(status) }
        .refreshable { await store.loadQueue(status) }
        .overlay(alignment: .bottom) {
            NoticeBanner(notice: (store.notice ?? store.error.flatMap { store.queue == nil ? nil : $0 })
                .map { NoticeBanner.Notice(text: $0, tone: store.notice == nil ? .error : .success) }) {
                store.notice = nil
                store.error = nil
            }
        }
    }
}

private struct ReportRow: View {
    @ObservedObject var store: ModerationStore
    let report: ModerationReport
    let status: String
    @State private var note = ""
    @State private var days = 7
    @State private var confirmBan = false

    var body: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(report.reasonLabel).font(.caption.weight(.bold)).padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Color.orange.opacity(0.25), in: Capsule())
                    Text([report.kindLabel, report.place].filter { !$0.isEmpty }.joined(separator: " · "))
                        .font(.caption).foregroundStyle(.secondary)
                }
                if let user = report.user {
                    HStack(spacing: 10) {
                        Initials(name: user.name, photo: user.photo, size: 36)
                        VStack(alignment: .leading) {
                            Text(user.name + (report.banned ? " · accès retiré" : "")).font(.subheadline.weight(.semibold))
                            Text("\(report.userReports) signalement(s) sur ce compte\(report.sameTarget > 1 ? " · \(report.sameTarget) sur ce contenu" : "")")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
                if let photo = report.photo.flatMap(URL.init(string:)) {
                    AsyncImage(url: photo) { $0.resizable().scaledToFill() } placeholder: { ProgressView() }
                        .frame(width: 160, height: 160).clipShape(RoundedRectangle(cornerRadius: 12))
                        .accessibilityLabel("Photo signalée")
                }
                if !report.text.isEmpty {
                    Text(report.text).padding(10).frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.white.opacity(0.06), in: RoundedRectangle(cornerRadius: 10))
                }
                Text("Signalé par \(report.reporter)\(report.comment.map { " : « \($0) »" } ?? "")")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if report.status == "open" {
                TextField("Note (envoyée avec l'avertissement)", text: $note, axis: .vertical)
                Button("Masquer le contenu") { act(.hide) }.accessibilityIdentifier("moderate-hide")
                if report.user != nil {
                    Button("Avertir") { act(.warn) }
                    Picker("Suspendre", selection: $days) {
                        ForEach([1, 7, 30], id: \.self) { Text("\($0) jour\($0 > 1 ? "s" : "")").tag($0) }
                    }
                    Button("Suspendre \(days) jour\(days > 1 ? "s" : "")") { act(.suspend) }
                    Button("Bannir le compte", role: .destructive) { confirmBan = true }
                }
                Button("Classer sans suite") { act(.dismiss) }.foregroundStyle(.secondary)
            } else {
                Text([ModerationReport.resolutions[report.resolution ?? ""] ?? report.status, report.handledBy.map { "par \($0)" },
                      report.note.map { "« \($0) »" }].compactMap { $0 }.joined(separator: " · "))
                    .font(.footnote.weight(.semibold))
            }
            if report.banned {
                Button("Réintégrer \(report.user?.name ?? "le compte")") { Task { await store.lift(report) } }
            }
        }
        .disabled(store.busy.contains(report.id))
        .confirmationDialog("Bannir ce compte ?", isPresented: $confirmBan, titleVisibility: .visible) {
            Button("Bannir", role: .destructive) { act(.ban) }
        } message: {
            Text("Le compte n'aura plus accès à Party jusqu'à ce qu'un modérateur le réintègre. Seul ce compte est visé.")
        }
    }

    private func act(_ action: ModerationAction) {
        Haptics.tap()
        Task { await store.act(report, action, note: note, days: action == .suspend ? days : nil, status: status) }
    }
}
