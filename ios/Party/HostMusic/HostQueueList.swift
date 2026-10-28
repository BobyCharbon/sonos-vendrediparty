import SwiftUI
import UIKit

/// File d'attente de l'hôte : chaque titre a sa poignée « réorganiser » (≡) à droite. Appui long sur la poignée,
/// puis glisser vers le haut ou le bas : le titre suit le doigt, les autres s'écartent, et au lâcher il prend
/// cette place (un seul déplacement côté Sonos). Ailleurs sur la ligne, appui long ou « … » : les autres actions.
struct HostQueueList: View {
    let tracks: [AdminState.QueueTrack]
    let editable: Bool
    let receivedAt: Date
    let busy: Set<String>
    /// Glissement en cours : la page arrête de défiler pendant ce temps.
    @Binding var dragging: Bool
    let action: (AdminState.QueueTrack, String) -> Void
    let move: (AdminState.QueueTrack, Int) -> Void
    let artwork: (String) async -> UIImage?

    static let rowHeight: CGFloat = 68
    @State private var lifted: Int?
    @State private var offset: CGFloat = 0
    @State private var target: Int?

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(tracks.enumerated()), id: \.element.id) { index, track in
                row(track, index: index)
                    .frame(height: Self.rowHeight)
                    .offset(y: shift(for: index))
                    .zIndex(lifted == index ? 1 : 0)
                    .animation(lifted == index ? nil : .spring(response: 0.28, dampingFraction: 0.85), value: target)
            }
        }
    }

    /// Décalage d'une ligne pendant le glissement : la ligne prise suit le doigt, celles qu'elle survole s'écartent.
    private func shift(for index: Int) -> CGFloat {
        guard let lifted, let target else { return 0 }
        if index == lifted { return offset }
        if lifted < target, index > lifted, index <= target { return -Self.rowHeight }
        if lifted > target, index >= target, index < lifted { return Self.rowHeight }
        return 0
    }

    private func row(_ track: AdminState.QueueTrack, index: Int) -> some View {
        let isLifted = lifted == index
        return HStack(spacing: 10) {
            // Appui long sur le titre (pas sur la poignée) : les actions. La poignée, elle, sert à glisser.
            HStack(spacing: 10) {
                HostArtwork(path: track.art, load: artwork)
                VStack(alignment: .leading, spacing: 2) {
                    Text(track.title).font(.subheadline.weight(.semibold)).lineLimit(1)
                    Text(track.artist).font(.caption).foregroundStyle(.secondary).lineLimit(1)
                    HStack(spacing: 6) {
                        if let by = track.by { Text("ajouté par \(by)").font(.caption2.weight(.semibold)).foregroundStyle(Palette.accent) }
                        let eta = PassageTime.text(eta: track.eta, receivedAt: receivedAt)
                        if !eta.isEmpty { Text(eta).font(.caption2).foregroundStyle(.secondary) }
                        if let service = track.service { Text(service).font(.caption2).foregroundStyle(.secondary) }
                    }
                    .lineLimit(1)
                }
                Spacer(minLength: 4)
            }
            .contentShape(Rectangle())
            .contextMenu { if editable && lifted == nil { actions(track, index: index) } }
            if editable {
                if busy.contains("q.\(track.id)") {
                    ProgressView().frame(width: 32)
                } else {
                    actionsMenu(track, index: index)
                }
                handle(index: index)
            }
        }
        .padding(.horizontal, 10)
        .frame(maxHeight: .infinity)
        .background(isLifted ? Palette.mine : (track.isRequest ? Palette.mine.opacity(0.55) : Palette.card),
                    in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .padding(.vertical, 3)
        .scaleEffect(isLifted ? 1.03 : 1)
        .shadow(color: .black.opacity(isLifted ? 0.45 : 0), radius: 12, y: 6)
    }

    private func actionsMenu(_ track: AdminState.QueueTrack, index: Int) -> some View {
        Menu {
            actions(track, index: index)
        } label: {
            Image(systemName: "ellipsis.circle").font(.title3).foregroundStyle(.secondary).frame(width: 32, height: 44)
        }
        .accessibilityLabel("Actions pour \(track.title)")
    }

    @ViewBuilder
    private func actions(_ track: AdminState.QueueTrack, index: Int) -> some View {
        if index > 0 {
            Button { action(track, "next") } label: { Label("Jouer ensuite", systemImage: "text.line.first.and.arrowtriangle.forward") }
            Button { action(track, "up") } label: { Label("Monter", systemImage: "arrow.up") }
        }
        if index < tracks.count - 1 {
            Button { action(track, "down") } label: { Label("Descendre", systemImage: "arrow.down") }
        }
        Button { action(track, "play") } label: { Label("Jouer maintenant", systemImage: "play.fill") }
        Button(role: .destructive) { action(track, "remove") } label: { Label("Retirer", systemImage: "trash") }
    }

    /// Poignée : seul endroit d'où l'on fait glisser (appui long, puis on bouge le doigt).
    private func handle(index: Int) -> some View {
        Image(systemName: "line.3.horizontal")
            .font(.title3.weight(.semibold))
            .foregroundStyle(lifted == index ? Palette.accent : .secondary)
            .frame(width: 40, height: Self.rowHeight)
            .contentShape(Rectangle())
            // Priorité sur le défilement de la page : une fois l'appui long reconnu, le doigt déplace le titre.
            .highPriorityGesture(
                LongPressGesture(minimumDuration: 0.25)
                    // Repère de l'écran : la ligne bouge avec le doigt, son propre repère fausserait la distance.
                    .sequenced(before: DragGesture(minimumDistance: 0, coordinateSpace: .global))
                    .onChanged { value in
                        guard case .second(true, let drag) = value else { return }
                        if lifted == nil { lift(index) }
                        offset = drag?.translation.height ?? 0
                        let next = QueueOrder.index(from: index, translation: offset, rowHeight: Self.rowHeight, count: tracks.count)
                        if next != target {
                            target = next
                            UISelectionFeedbackGenerator().selectionChanged()
                        }
                    }
                    .onEnded { _ in drop() }
            )
            .accessibilityElement()
            .accessibilityLabel("Réorganiser")
            .accessibilityIdentifier("Réorganiser")
            .accessibilityAddTraits(.isButton)
            .accessibilityHint("Appui long puis glisser vers le haut ou le bas ; ou « … » pour monter, descendre, jouer ensuite")
    }

    private func lift(_ index: Int) {
        lifted = index
        target = index
        dragging = true
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
    }

    private func drop() {
        defer {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.85)) {
                lifted = nil
                target = nil
                offset = 0
            }
            dragging = false
        }
        guard let lifted, let target, let position = QueueOrder.targetPosition(in: tracks, from: lifted, to: target) else { return }
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
        move(tracks[lifted], position)
    }
}

/// Pochette d'un titre : chargée avec la session du site (/art pour les pochettes Sonos), gardée en mémoire.
struct HostArtwork: View {
    let path: String
    let load: (String) async -> UIImage?
    var size: CGFloat = 46
    @State private var image: UIImage?

    var body: some View {
        Group {
            if let image {
                Image(uiImage: image).resizable().scaledToFill()
            } else {
                Image(systemName: "music.note").foregroundStyle(.secondary)
            }
        }
        .frame(width: size, height: size)
        .background(Color.white.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .task(id: path) { image = path.isEmpty ? nil : await load(path) }
        .accessibilityHidden(true)
    }
}
