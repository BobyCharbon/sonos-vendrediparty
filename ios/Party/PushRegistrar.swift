import UIKit
import UserNotifications

enum PushError: LocalizedError {
    case denied
    case registrationFailed(String)

    var errorDescription: String? {
        switch self {
        case .denied: return "Notifications refusées : autorise-les pour Party ! dans les réglages du téléphone"
        case .registrationFailed(let reason): return "Inscription aux notifications impossible : \(reason)"
        }
    }
}

/// Demande la permission, inscrit l'appareil auprès d'APNs et rend le jeton à la page.
@MainActor
final class PushRegistrar {
    static let shared = PushRegistrar()

    /// Le serveur doit viser api.sandbox.push.apple.com pour une app signée en développement.
    static let environment: String = {
        #if DEBUG
        return "sandbox"
        #else
        return "production"
        #endif
    }()

    private var waiting: [CheckedContinuation<String, Error>] = []

    func status() async -> String {
        switch await UNUserNotificationCenter.current().notificationSettings().authorizationStatus {
        case .authorized, .provisional, .ephemeral: return "granted"
        case .denied: return "denied"
        default: return "default"
        }
    }

    func register() async throws -> String {
        let granted = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
        guard granted else { throw PushError.denied }
        return try await withCheckedThrowingContinuation { continuation in
            waiting.append(continuation)
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    /// Clé de la page (push.js, portée « / ») où l'abonnement natif de cet appareil est gardé.
    static let pageKey = "vp_native_push:/"

    /// Abonnement de cet appareil, au format attendu par le serveur (app/push.py, valid_native_subscription).
    func device() async throws -> [String: Any] {
        let token = try await register()
        return ["endpoint": "apns:\(token)",
                "apns": ["token": token, "environment": Self.environment, "topic": Bundle.main.bundleIdentifier ?? ""]]
    }

    func deliver(token: Data) {
        let hex = token.map { String(format: "%02x", $0) }.joined()
        finish { $0.resume(returning: hex) }
    }

    func fail(_ error: Error) {
        finish { $0.resume(throwing: PushError.registrationFailed(error.localizedDescription)) }
    }

    private func finish(_ resume: (CheckedContinuation<String, Error>) -> Void) {
        let pending = waiting
        waiting = []
        pending.forEach(resume)
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions options: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        // Secouer le téléphone (Biskit, jeux) ne doit jamais ouvrir « Annuler la saisie » (avis 51dbdb4c1957).
        application.applicationSupportsShakeToEdit = false
        Task { @MainActor in TrackActivities.watchAtLaunch() }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken token: Data) {
        Task { @MainActor in PushRegistrar.shared.deliver(token: token) }
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        Task { @MainActor in PushRegistrar.shared.fail(error) }
    }

    /// App ouverte : la notification s'affiche quand même, comme sur la PWA.
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification) async
        -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    /// Toucher d'une notification : on ouvre son adresse (`"url"` dans la charge utile APNs, comme `data.url` en Web Push).
    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
        let info = response.notification.request.content.userInfo
        guard let raw = info["url"] as? String,
              let url = URL(string: raw, relativeTo: AppConfig.baseURL)?.absoluteURL else { return }
        await MainActor.run { NotificationCenter.default.post(name: .partyOpenURL, object: url) }
    }
}
