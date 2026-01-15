//
//  ShareViewController.swift
//  ShareExtension
//
//  Created by Willem Ave on 12/21/25.
//

import UIKit
import Social
import UniformTypeIdentifiers

fileprivate enum LinkHandlingMode: String, CaseIterable {
    case addContent
    case addLinks
    case shareAndChat

    var displayName: String {
        switch self {
        case .addContent:
            return "Add content"
        case .addLinks:
            return "Add links"
        case .shareAndChat:
            return "Add & chat"
        }
    }
}

class ShareViewController: SLComposeServiceViewController {

    private var sharedURL: URL?
    private var linkHandlingMode: LinkHandlingMode = .addContent

    override func viewDidLoad() {
        super.viewDidLoad()

        // Configure keychain with shared access group (same as main app)
        if let accessGroup = SharedContainer.keychainAccessGroup {
            KeychainManager.shared.configure(accessGroup: accessGroup)
        }

        // Customize UI
        hideDescriptionField()
        navigationItem.rightBarButtonItem?.title = "Submit"

        extractSharedURL()
        print("🔗 [ShareExt] viewDidLoad sharedURL=\(sharedURL?.absoluteString ?? "nil")")
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        let minHeight: CGFloat = 520
        let targetHeight = max(view.bounds.height, minHeight)
        preferredContentSize = CGSize(width: view.bounds.width, height: targetHeight)
        print("🔗 [ShareExt] preferredContentSize=\(preferredContentSize)")
    }

    override func isContentValid() -> Bool {
        return sharedURL != nil
    }

    override func didSelectPost() {
        guard let url = sharedURL else {
            showError("No URL found")
            return
        }

        Task {
            do {
                try await submitURL(url)
                await MainActor.run {
                    self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                }
            } catch {
                await MainActor.run {
                    self.showError(error.localizedDescription)
                }
            }
        }
    }

    override func configurationItems() -> [Any]! {
        let items: [SLComposeSheetConfigurationItem] = LinkHandlingMode.allCases.compactMap {
            mode -> SLComposeSheetConfigurationItem? in
            guard let item = SLComposeSheetConfigurationItem() else { return nil }
            item.title = mode.displayName
            item.value = mode == linkHandlingMode ? "Selected" : nil
            item.tapHandler = { [weak self] in
                self?.linkHandlingMode = mode
                self?.reloadConfigurationItems()
            }
            return item
        }
        print(
            "🔗 [ShareExt] configurationItems count=\(items.count) sharedURL=\(sharedURL?.absoluteString ?? "nil") mode=\(linkHandlingMode.rawValue)"
        )
        return items
    }

    // MARK: - URL Extraction

    private func extractSharedURL() {
        guard let extensionItems = extensionContext?.inputItems as? [NSExtensionItem] else {
            return
        }

        for item in extensionItems {
            guard let attachments = item.attachments else { continue }

            for attachment in attachments {
                // Try URL type first
                if attachment.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                    attachment.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { [weak self] item, _ in
                        if let url = item as? URL {
                            DispatchQueue.main.async {
                                self?.sharedURL = url
                                self?.validateContent()
                                print("🔗 [ShareExt] extracted URL=\(url.absoluteString)")
                                self?.reloadConfigurationItems()
                            }
                        }
                    }
                    return
                }

                // Try plain text (might be a URL string)
                if attachment.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                    attachment.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { [weak self] item, _ in
                        if let text = item as? String, let url = URL(string: text), url.scheme != nil {
                            DispatchQueue.main.async {
                                self?.sharedURL = url
                                self?.validateContent()
                                print("🔗 [ShareExt] extracted text URL=\(url.absoluteString)")
                                self?.reloadConfigurationItems()
                            }
                        }
                    }
                    return
                }
            }
        }
    }

    // MARK: - API Submission

    private func submitURL(_ url: URL) async throws {
        // Debug: Check what we can access
        let keychainToken = KeychainManager.shared.getToken(key: .accessToken)
        let sharedToken = SharedContainer.userDefaults.string(forKey: "accessToken")

        // Extra debug: check if we can create the UserDefaults with the suite name
        if let groupId = SharedContainer.appGroupId {
            let directDefaults = UserDefaults(suiteName: groupId)
            let directToken = directDefaults?.string(forKey: "accessToken")
            let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: groupId)
            print("🔐 [ShareExt] Direct UserDefaults(\(groupId)) exists: \(directDefaults != nil)")
            print("🔐 [ShareExt] Direct token: \(directToken != nil ? "found" : "nil")")
            print("🔐 [ShareExt] Container URL: \(containerURL?.path ?? "nil")")
        }

        print("🔐 [ShareExt] Keychain token: \(keychainToken != nil ? "found" : "nil")")
        print("🔐 [ShareExt] SharedDefaults token: \(sharedToken != nil ? "found (\(sharedToken!.prefix(20))...)" : "nil")")
        print("🔐 [ShareExt] App group: \(SharedContainer.appGroupId ?? "nil")")

        // Get auth token - try keychain first, then shared UserDefaults as fallback
        let token: String
        if let keychainToken = keychainToken {
            token = keychainToken
        } else if let sharedToken = sharedToken {
            token = sharedToken
        } else {
            throw ShareError.notAuthenticated
        }

        // Build request
        let baseURL = AppSettings.shared.baseURL
        guard let requestURL = URL(string: "\(baseURL)/api/content/submit") else {
            throw ShareError.invalidURL
        }

        var request = URLRequest(url: requestURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

        let body: [String: Any] = [
            "url": url.absoluteString,
            "crawl_links": linkHandlingMode == .addLinks,
            "share_and_chat": linkHandlingMode == .shareAndChat,
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw ShareError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            if httpResponse.statusCode == 401 {
                throw ShareError.notAuthenticated
            }
            let message = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw ShareError.serverError(message)
        }
    }

    // MARK: - Error Handling

    private func showError(_ message: String) {
        let alert = UIAlertController(
            title: "Error",
            message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in
            self.extensionContext?.cancelRequest(withError: ShareError.userCancelled)
        })
        present(alert, animated: true)
    }

    // MARK: - Link Handling

    private func hideDescriptionField() {
        placeholder = ""
        textView.text = ""
        textView.isEditable = false
        textView.isSelectable = false
        textView.isHidden = true
    }
}

// MARK: - Errors

enum ShareError: LocalizedError {
    case notAuthenticated
    case invalidURL
    case invalidResponse
    case serverError(String)
    case userCancelled

    var errorDescription: String? {
        switch self {
        case .notAuthenticated:
            return "Please sign in to the Newsly app first"
        case .invalidURL:
            return "Invalid URL"
        case .invalidResponse:
            return "Invalid server response"
        case .serverError(let message):
            return message
        case .userCancelled:
            return "Cancelled"
        }
    }
}
