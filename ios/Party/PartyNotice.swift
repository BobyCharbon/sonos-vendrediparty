import SwiftUI
import WebKit

/// Message pour tout le monde (avis eb710b132330) : maintenance, information ou annonce, ou serveur en cours de
/// mise à jour. La page le lit (app/static/notice.js) et le décrit à l'app (`PartyNative.notice.update`) ; l'app le
/// dessine par-dessus la page ET ses écrans natifs (Réglages, Musique…), donc sur tous les onglets.
struct PartyNoticeState: Equatable {
    enum Kind: String { case maintenance, info, announce, down }

    let id: String
    let kind: Kind
    let title: String
    let message: String
    /// Root / admin : une maintenance ne lui bloque pas l'app (bandeau + « Gérer »).
    let admin: Bool

    /// Écran qui couvre toute l'app (mise à jour en cours) ; sinon un bandeau en haut.
    var blocks: Bool { kind == .down || (kind == .maintenance && !admin) }
    /// Information et annonce se ferment d'un ✕ (pour ce message-là).
    var closable: Bool { kind == .info || kind == .announce }

    init(id: String, kind: Kind, title: String, message: String, admin: Bool) {
        self.id = id
        self.kind = kind
        self.title = title
        self.message = message
        self.admin = admin
    }

    init?(message body: Any) {
        guard let d = body as? [String: Any], let id = d["id"] as? String, !id.isEmpty,
              let raw = d["kind"] as? String, let kind = Kind(rawValue: raw),
              let title = d["title"] as? String else { return nil }
        self.init(id: id, kind: kind, title: String(title.prefix(80)),
                  message: String(((d["message"] as? String) ?? "").prefix(400)), admin: d["admin"] as? Bool ?? false)
    }

    var symbol: String {
        switch kind {
        case .maintenance, .down: return "wrench.and.screwdriver.fill"
        case .info: return "info.circle.fill"
        case .announce: return "megaphone.fill"
        }
    }
}

/// `PartyNative.notice.update(state | null)` (page principale seulement) → message natif.
final class PartyNoticeHandler: NSObject, WKScriptMessageHandler {
    static let handler = "partyNotice"
    private weak var model: WebModel?

    init(model: WebModel) {
        self.model = model
    }

    @MainActor
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, AppConfig.isInternal(message.frameInfo.securityOrigin.url) else { return }
        model?.showNotice(PartyNoticeState(message: message.body))
    }
}

/// Le message, par-dessus toute l'app : écran « Mise à jour en cours » ou bandeau en haut.
struct PartyNoticeView: View {
    let notice: PartyNoticeState
    let topInset: CGFloat
    let close: () -> Void
    let manage: () -> Void

    var body: some View {
        if notice.blocks {
            cover
        } else {
            banner
        }
    }

    private var cover: some View {
        VStack(spacing: 14) {
            Image(systemName: notice.symbol)
                .font(.system(size: 44, weight: .semibold))
                .foregroundStyle(Palette.accent)
            Text(notice.title).font(.title2.weight(.bold)).multilineTextAlignment(.center)
            if !notice.message.isEmpty {
                Text(notice.message).font(.body).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            HStack(spacing: 10) {
                ProgressView().tint(.secondary)
                Text(notice.kind == .down ? "Reconnexion automatique" : "Ça revient tout seul")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            .padding(.top, 4)
        }
        .padding(28)
        .frame(maxWidth: 360)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 26, style: .continuous))
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.opacity(0.55).ignoresSafeArea())
        .contentShape(Rectangle())
        .accessibilityElement(children: .combine)
        .accessibilityAddTraits(.isModal)
        .accessibilityIdentifier("party-notice-cover")
    }

    private var banner: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: notice.symbol)
                .font(.title3)
                .foregroundStyle(notice.kind == .info ? Color.secondary : Palette.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text(notice.kind == .maintenance ? "\(notice.title) · affiché à tous" : notice.title)
                    .font(.subheadline.weight(.semibold))
                if !notice.message.isEmpty {
                    Text(notice.message).font(.footnote).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
            if notice.closable {
                Button(action: close) {
                    Image(systemName: "xmark").font(.footnote.weight(.bold))
                        .frame(width: 30, height: 30)
                        .background(.thinMaterial, in: Circle())
                }
                .accessibilityLabel("Masquer ce message")
            } else if notice.admin {
                Button("Gérer", action: manage)
                    .font(.footnote.weight(.semibold))
                    .buttonStyle(.bordered)
            }
        }
        .padding(14)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
            .strokeBorder(notice.kind == .info ? Color.white.opacity(0.08) : Palette.accent.opacity(0.8), lineWidth: 1.5))
        .shadow(color: .black.opacity(0.35), radius: 14, y: 6)
        .padding(.horizontal, 12)
        .padding(.top, topInset + 6)
        .frame(maxWidth: 560)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("party-notice-banner")
    }
}
