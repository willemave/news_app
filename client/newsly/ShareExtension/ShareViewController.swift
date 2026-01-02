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
    case fetch
    case crawl
    case subscribeToFeed

    var displayName: String {
        switch self {
        case .fetch:
            return "Fetch this page"
        case .crawl:
            return "Crawl links on page"
        case .subscribeToFeed:
            return "Subscribe to feed"
        }
    }

    var placeholderText: String {
        switch self {
        case .fetch:
            return "Add a note (optional)"
        case .crawl:
            return "Add crawl instructions (optional)"
        case .subscribeToFeed:
            return "Add feed notes (optional)"
        }
    }
}

class ShareViewController: SLComposeServiceViewController {

    private var sharedURL: URL?
    private var linkHandlingMode: LinkHandlingMode = .fetch

    override func viewDidLoad() {
        super.viewDidLoad()

        // Configure keychain with shared access group (same as main app)
        if let accessGroup = SharedContainer.keychainAccessGroup {
            KeychainManager.shared.configure(accessGroup: accessGroup)
        }

        // Customize UI
        updatePlaceholder()
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
                try await submitURL(url, note: contentText)
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
        guard let item = SLComposeSheetConfigurationItem() else {
            print("🔗 [ShareExt] configurationItems item=nil sharedURL=\(sharedURL?.absoluteString ?? "nil")")
            return []
        }
        item.title = "Link handling"
        item.value = linkHandlingMode.displayName
        item.tapHandler = { [weak self] in
            self?.presentLinkModePicker()
        }
        print("🔗 [ShareExt] configurationItems item=ok sharedURL=\(sharedURL?.absoluteString ?? "nil") mode=\(linkHandlingMode.rawValue)")
        return [item]
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

    private func submitURL(_ url: URL, note: String?) async throws {
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

        var body: [String: Any] = [
            "url": url.absoluteString,
            "crawl_links": linkHandlingMode == .crawl,
            "subscribe_to_feed": linkHandlingMode == .subscribeToFeed,
        ]
        if let trimmed = note?.trimmingCharacters(in: .whitespacesAndNewlines),
           !trimmed.isEmpty {
            body["instruction"] = trimmed
        }
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

    private func updatePlaceholder() {
        placeholder = linkHandlingMode.placeholderText
        navigationItem.rightBarButtonItem?.title = linkHandlingMode == .subscribeToFeed
            ? "Subscribe"
            : "Submit"
    }

    private func presentLinkModePicker() {
        let controller = LinkHandlingViewController(selectedMode: linkHandlingMode) { [weak self] mode in
            guard let self else { return }
            self.linkHandlingMode = mode
            self.updatePlaceholder()
            self.reloadConfigurationItems()
        }
        pushConfigurationViewController(controller)
    }
}

final class LinkHandlingViewController: UITableViewController {
    private let modes = LinkHandlingMode.allCases
    private var selectedMode: LinkHandlingMode
    private let onSelect: (LinkHandlingMode) -> Void

    fileprivate init(
        selectedMode: LinkHandlingMode,
        onSelect: @escaping (LinkHandlingMode) -> Void
    ) {
        self.selectedMode = selectedMode
        self.onSelect = onSelect
        super.init(style: .insetGrouped)
        title = "Link handling"
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        modes.count
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let cell = UITableViewCell(style: .default, reuseIdentifier: nil)
        let mode = modes[indexPath.row]
        cell.textLabel?.text = mode.displayName
        cell.accessoryType = mode == selectedMode ? .checkmark : .none
        return cell
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        let mode = modes[indexPath.row]
        selectedMode = mode
        onSelect(mode)
        navigationController?.popViewController(animated: true)
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
