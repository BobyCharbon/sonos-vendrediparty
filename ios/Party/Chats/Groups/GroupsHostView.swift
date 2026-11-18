import SwiftUI

/// Ce que les écrans des groupes ouvrent hors d'eux : la discussion (onglet Discussions), la fiche d'un événement et
/// « Créer un événement pour le groupe » (onglet Événements, web), les Pronos (écrans natifs, poussés sur place).
/// Donné par l'app (PartyApp) ; `leave` ferme d'abord l'écran qui porte les groupes (plein écran ou feuille).
struct GroupHub {
    var pronos: PronosStore?
    /// Ferme l'écran des groupes, puis fait l'action (le temps que la fermeture se termine).
    var leave: @MainActor (_ then: @escaping @MainActor () -> Void) -> Void
    var openChat: @MainActor (String) -> Void
    var openEvent: @MainActor (String) -> Void
    var createEvent: @MainActor (String) -> Void

    /// Le même, porté par une feuille (infos d'une discussion) : la feuille se ferme d'abord.
    func closing(_ dismiss: DismissAction) -> GroupHub {
        var hub = self
        hub.leave = { then in
            dismiss()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { then() }
        }
        return hub
    }
}

private struct GroupHubKey: EnvironmentKey {
    static let defaultValue: GroupHub? = nil
}

extension EnvironmentValues {
    var groupHub: GroupHub? {
        get { self[GroupHubKey.self] }
        set { self[GroupHubKey.self] = newValue }
    }
}

/// Écran des groupes ouvert par `OpenGroupPageAction` (Réglages › Groupes, « Nouveau groupe » des Discussions, page d'un
/// groupe) : plein écran natif avec sa propre pile, ✕ pour revenir.
enum GroupRoute: Identifiable, Equatable {
    case list
    case page(String)
    case create

    var id: String {
        switch self {
        case .list: return "list"
        case .page(let id): return "page:\(id)"
        case .create: return "create"
        }
    }

    /// nil : la liste ; « new » : la création ; un UUID : sa page ; nil pour tout autre texte.
    static func from(_ target: String?) -> GroupRoute? {
        guard let target else { return .list }
        if target == "new" { return .create }
        return UUID(uuidString: target).map { .page($0.uuidString.lowercased()) }
    }
}

struct GroupsHostView: View {
    @State var route: GroupRoute
    let close: () -> Void
    @State private var path: [GroupScreen] = []

    var body: some View {
        NavigationStack(path: $path) {
            root
                .toolbar {
                    ToolbarItem(placement: .navigationBarLeading) {
                        Button { close() } label: { Image(systemName: "xmark").font(.body.weight(.semibold)) }
                            .accessibilityLabel("Fermer")
                            .accessibilityIdentifier("groups-close")
                    }
                }
                .navigationDestination(for: GroupScreen.self) { screen in
                    screen.view(onGone: gone) { id in path = path.dropLast() + [.page(id)] }
                }
        }
        .tint(PronoTheme.lav)
    }

    @ViewBuilder private var root: some View {
        switch route {
        case .list: GroupsListView()
        case .page(let id): GroupPageView(groupID: id, onGone: gone)
        case .create:
            NewGroupView { id in
                Motion.animate(Motion.smooth) { route = .page(id) }
                path = []
            }
        }
    }

    /// Groupe quitté ou supprimé : retour à la liste (relue), ou fermeture si l'on était venu pour ce groupe.
    private func gone() {
        if route == .list { path = [] } else { close() }
    }
}

/// Écrans poussés dans la pile des groupes.
enum GroupScreen: Hashable {
    case page(String)
    case settings(String)
    case invite(String)
    case pronos(String)
    case create

    /// created : groupe créé depuis la liste, sa page remplace la création.
    @MainActor @ViewBuilder func view(onGone: @escaping () -> Void, created: @escaping (String) -> Void = { _ in }) -> some View {
        switch self {
        case .create: NewGroupView(done: created)
        case .page(let id): GroupPageView(groupID: id, onGone: onGone)
        case .settings(let id): GroupSettingsView(groupID: id, onGone: onGone)
        case .invite(let id): GroupInviteView(groupID: id)
        case .pronos(let id): GroupPronosView(groupID: id)
        }
    }
}

/// Pronos du groupe : la liste native des Pronos, filtrée sur ce groupe (classement compris).
struct GroupPronosView: View {
    let groupID: String
    @Environment(\.groupHub) private var hub

    var body: some View {
        if let store = hub?.pronos {
            PronosListView(store: store, group: groupID)
        } else {
            Text("Les pronos ne sont pas disponibles pour l'instant.").foregroundStyle(PronoTheme.t2).padding()
        }
    }
}
