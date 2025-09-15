import Foundation
import UIKit

// Thin, main-actor utility for opening ChatGPT.
@MainActor
final class ChatGPTDeepLink {
    private static let appStoreURL = URL(string: "https://apps.apple.com/us/app/chatgpt/id6448311069")!
    private static let deepLinkCandidates: [String] = [
        "chatgpt://chat/new",
        "chatgpt://",
        "com.openai.chat://",
        "openai://"
    ]

    static func openPreferApp(fallbackWebURL: URL, completion: ((Bool) -> Void)? = nil) {
        // First, try opening the universal link directly – iOS may route it into the app.
        UIApplication.shared.open(fallbackWebURL, options: [:]) { ok in
            if ok { completion?(true); return }

            // Next, try known custom URL schemes (no payload support but may land in app).
            if let urlToOpen = deepLinkCandidates
                .compactMap({ URL(string: $0) })
                .first(where: { UIApplication.shared.canOpenURL($0) }) {
                UIApplication.shared.open(urlToOpen, options: [:], completionHandler: completion)
                return
            }
            // Finally, App Store
            UIApplication.shared.open(appStoreURL, options: [:], completionHandler: completion)
        }
    }

    static func openUniversalOrWeb(_ url: URL) {
        UIApplication.shared.open(url, options: [:], completionHandler: nil)
    }
}
