import PhotosUI
import SwiftUI
import VisionKit

/// « Scanner un ticket » (assistant IA) : le ticket est pris avec le scanner de documents d'iOS (bords recadrés,
/// lisible) ou choisi dans les photos, lu par l'IA, puis il remplit la dépense ; la personne choisit pour qui.
struct ReceiptScanSection: View {
    @ObservedObject var store: TricountStore
    /// Ticket déjà lu (résumé affiché à la place des boutons).
    let read: TC.Receipt?
    /// Ticket lu et sa photo (jointe à la dépense comme ticket).
    let onRead: (TC.Receipt, Data) -> Void
    @State private var scanning = false
    @State private var showScanner = false
    @State private var photo: PhotosPickerItem?

    var body: some View {
        Section {
            if scanning {
                HStack(spacing: 12) {
                    ProgressView()
                    Text("Lecture du ticket…").foregroundStyle(.secondary)
                }
                .padding(.vertical, 6)
            } else if let read {
                summary(read)
            } else {
                buttons
            }
        } footer: {
            if read == nil && !scanning {
                Text("L'IA lit le montant, la date et les articles. Tu choisis ensuite pour qui.")
            }
        }
        .sheet(isPresented: $showScanner) {
            DocumentScanner { image in
                showScanner = false
                if let image, let data = image.jpegData(compressionQuality: 0.9) { send(data) }
            }
            .ignoresSafeArea()
        }
        .onChange(of: photo) { item in
            Task {
                guard let data = try? await item?.loadTransferable(type: Data.self) else { return }
                photo = nil
                send(data)
            }
        }
    }

    private var buttons: some View {
        HStack(spacing: 10) {
            if VNDocumentCameraViewController.isSupported {
                Button { showScanner = true } label: {
                    Label("Scanner un ticket", systemImage: "doc.viewfinder").frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .accessibilityIdentifier("tc-scan")
            }
            PhotosPicker(selection: $photo, matching: .images) {
                Label(VNDocumentCameraViewController.isSupported ? "Photo" : "Lire un ticket (photo)", systemImage: "photo")
                    .frame(maxWidth: VNDocumentCameraViewController.isSupported ? nil : .infinity)
            }
            .buttonStyle(.bordered)
            .accessibilityIdentifier("tc-scan-photo")
        }
        .tint(Palette.accent)
        .listRowBackground(Color.clear)
        .listRowInsets(EdgeInsets())
    }

    private func summary(_ r: TC.Receipt) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Label(r.summary.isEmpty ? r.title : r.summary, systemImage: "sparkles")
                .font(.subheadline.weight(.semibold))
            if !r.items.isEmpty {
                DisclosureGroup("\(r.items.count) article\(r.items.count > 1 ? "s" : "") sur le ticket") {
                    ForEach(Array(r.items.enumerated()), id: \.offset) { _, item in
                        HStack {
                            Text(item.quantity > 1 ? "\(item.quantity.formatted()) × \(item.label)" : item.label).lineLimit(2)
                            Spacer()
                            Text(Money.text(item.amount_cents, r.currency)).monospacedDigit().foregroundStyle(.secondary)
                        }
                        .font(.footnote)
                    }
                }
                .font(.footnote)
            }
        }
        .padding(.vertical, 4)
        .accessibilityIdentifier("tc-scan-summary")
    }

    private func send(_ data: Data) {
        guard let jpeg = ExpenseEditor.jpeg(data) else { return }
        scanning = true
        Task {
            if let r = await store.readReceipt(jpeg) { onRead(r, jpeg) }
            scanning = false
        }
    }
}

/// Scanner de documents d'iOS (recadrage automatique) ; renvoie la première page, ou rien si on annule.
struct DocumentScanner: UIViewControllerRepresentable {
    let done: (UIImage?) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(done: done) }

    func makeUIViewController(context: Context) -> VNDocumentCameraViewController {
        let scanner = VNDocumentCameraViewController()
        scanner.delegate = context.coordinator
        return scanner
    }

    func updateUIViewController(_ controller: VNDocumentCameraViewController, context: Context) {}

    final class Coordinator: NSObject, VNDocumentCameraViewControllerDelegate {
        let done: (UIImage?) -> Void
        init(done: @escaping (UIImage?) -> Void) { self.done = done }

        func documentCameraViewController(_ controller: VNDocumentCameraViewController, didFinishWith scan: VNDocumentCameraScan) {
            done(scan.pageCount > 0 ? scan.imageOfPage(at: 0) : nil)
        }
        func documentCameraViewControllerDidCancel(_ controller: VNDocumentCameraViewController) { done(nil) }
        func documentCameraViewController(_ controller: VNDocumentCameraViewController, didFailWithError error: Error) { done(nil) }
    }
}

/// Administration › Assistant IA : coût du mois (plafond par personne), qui l'utilise, derniers appels.
/// Qui y a droit se règle dans Rôles et droits (« Utiliser l'assistant IA »).
struct AIUsageView: View {
    @ObservedObject var store: TricountStore

    var body: some View {
        List {
            if let u = store.aiUsage {
                Section {
                    LabeledContent("Ce mois-ci", value: Self.dollars(u.month_cost_usd))
                    LabeledContent("Plafond par personne", value: Self.dollars(u.budget_usd) + " / mois")
                    LabeledContent("Modèle", value: u.model)
                    if !u.configured {
                        Label("Clé API absente sur le serveur : l'assistant est éteint", systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.orange).font(.footnote)
                    }
                } footer: {
                    Text("Qui peut l'utiliser : Administration du groupe › Rôles et droits › « Utiliser l'assistant IA ».")
                }
                Section("Par personne") {
                    if u.people.isEmpty { Text("Personne ce mois-ci").foregroundStyle(.secondary) }
                    ForEach(u.people) { p in
                        HStack {
                            Text(p.name)
                            Spacer()
                            Text("\(p.calls) × · \(Self.dollars(p.cost_usd))").monospacedDigit().foregroundStyle(.secondary)
                        }
                    }
                }
                if !u.recent.isEmpty {
                    Section("Derniers appels") {
                        ForEach(Array(u.recent.prefix(20).enumerated()), id: \.offset) { _, c in
                            HStack {
                                VStack(alignment: .leading) {
                                    Text(c.feature == "receipt" ? "Ticket lu" : c.feature)
                                    Text("\(c.name ?? "?") · \(Date(timeIntervalSince1970: c.at).formatted(date: .abbreviated, time: .shortened))")
                                        .font(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                                Text(Self.dollars(c.cost_usd)).monospacedDigit().foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            } else if let error = store.error {
                Text(error).foregroundStyle(.secondary)
            } else {
                ProgressView()
            }
        }
        .navigationTitle("Assistant IA")
        .task { await store.loadAIUsage() }
        .refreshable { await store.loadAIUsage() }
    }

    static func dollars(_ usd: Double) -> String { String(format: "%.2f $", usd) }
}
