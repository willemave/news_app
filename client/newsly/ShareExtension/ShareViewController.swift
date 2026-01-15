//
//  ShareViewController.swift
//  ShareExtension
//
//  Created by Willem Ave on 12/21/25.
//

import UIKit
import UniformTypeIdentifiers

fileprivate enum LinkHandlingMode: String, CaseIterable {
    case addContent
    case addLinks
    case shareAndChat

    var title: String {
        switch self {
        case .addContent:
            return "Add content"
        case .addLinks:
            return "Add links"
        case .shareAndChat:
            return "Add & chat"
        }
    }

    var description: String {
        switch self {
        case .addContent:
            return "Summarize the shared page in Newsly."
        case .addLinks:
            return "Also crawl important links found on the page."
        case .shareAndChat:
            return "Add the link and open a chat summary."
        }
    }
}

final class ShareViewController: UIViewController {

    private var sharedURL: URL?
    private var linkHandlingMode: LinkHandlingMode = .addContent
    private var optionViews: [LinkHandlingMode: OptionRowView] = [:]

    private let contentStack = UIStackView()
    private let titleLabel = UILabel()
    private let optionsStack = UIStackView()
    private let submitButton = UIButton(type: .system)

    override func viewDidLoad() {
        super.viewDidLoad()

        view.backgroundColor = .systemBackground

        if let accessGroup = SharedContainer.keychainAccessGroup {
            KeychainManager.shared.configure(accessGroup: accessGroup)
        }

        configureLayout()
        configureOptions()
        configureSubmitButton()

        extractSharedURL()
        updateSubmitState()
        updateSelectionUI()

        let sharedURLString = sharedURL?.absoluteString ?? "nil"
        print("🔗 [ShareExt] viewDidLoad sharedURL=\(sharedURLString)")
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()

        let targetSize = contentStack.systemLayoutSizeFitting(
            CGSize(width: view.bounds.width - 32, height: UIView.layoutFittingCompressedSize.height),
            withHorizontalFittingPriority: .required,
            verticalFittingPriority: .fittingSizeLevel
        )
        let safeHeight = view.safeAreaInsets.top + view.safeAreaInsets.bottom
        let targetHeight = targetSize.height + safeHeight + 16
        preferredContentSize = CGSize(width: view.bounds.width, height: targetHeight)
    }

    // MARK: - Layout

    private func configureLayout() {
        contentStack.axis = .vertical
        contentStack.spacing = 16
        contentStack.alignment = .fill
        contentStack.translatesAutoresizingMaskIntoConstraints = false
        contentStack.setContentHuggingPriority(.required, for: .vertical)

        titleLabel.text = "How should Newsly handle this link?"
        titleLabel.font = .preferredFont(forTextStyle: .headline)
        titleLabel.numberOfLines = 0

        optionsStack.axis = .vertical
        optionsStack.spacing = 12
        optionsStack.alignment = .fill
        optionsStack.setContentHuggingPriority(.required, for: .vertical)
        optionsStack.setContentCompressionResistancePriority(.required, for: .vertical)

        submitButton.heightAnchor.constraint(equalToConstant: 44).isActive = true

        contentStack.addArrangedSubview(titleLabel)
        contentStack.addArrangedSubview(optionsStack)
        contentStack.addArrangedSubview(submitButton)

        view.addSubview(contentStack)

        NSLayoutConstraint.activate([
            contentStack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16),
            contentStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 16),
            contentStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -16),
            contentStack.bottomAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -16),
        ])
    }

    private func configureOptions() {
        LinkHandlingMode.allCases.forEach { mode in
            let optionView = OptionRowView(title: mode.title, description: mode.description)
            optionView.addTarget(self, action: #selector(handleOptionTapped(_:)), for: .touchUpInside)
            optionsStack.addArrangedSubview(optionView)
            optionViews[mode] = optionView
        }
    }

    private func configureSubmitButton() {
        var configuration = UIButton.Configuration.filled()
        configuration.title = "Submit"
        configuration.cornerStyle = .medium
        submitButton.configuration = configuration
        submitButton.addTarget(self, action: #selector(handleSubmitTapped), for: .touchUpInside)
    }

    private func updateSelectionUI() {
        optionViews.forEach { mode, view in
            view.isSelected = (mode == linkHandlingMode)
        }
    }

    private func updateSubmitState() {
        submitButton.isEnabled = sharedURL != nil
    }

    @objc private func handleOptionTapped(_ sender: OptionRowView) {
        guard let match = optionViews.first(where: { $0.value == sender })?.key else { return }
        linkHandlingMode = match
        updateSelectionUI()
    }

    @objc private func handleSubmitTapped() {
        guard let url = sharedURL else {
            showError("No URL found")
            return
        }

        submitButton.isEnabled = false

        Task {
            do {
                try await submitURL(url)
                await MainActor.run {
                    self.extensionContext?.completeRequest(returningItems: [], completionHandler: nil)
                }
            } catch {
                await MainActor.run {
                    self.updateSubmitState()
                    self.showError(error.localizedDescription)
                }
            }
        }
    }

    // MARK: - URL Extraction

    private func extractSharedURL() {
        guard let extensionItems = extensionContext?.inputItems as? [NSExtensionItem] else {
            return
        }

        for item in extensionItems {
            guard let attachments = item.attachments else { continue }

            for attachment in attachments {
                if attachment.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                    attachment.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { [weak self] item, _ in
                        if let url = item as? URL {
                            self?.updateSharedURL(url)
                            return
                        }
                        if let text = item as? String, let url = URL(string: text), url.scheme != nil {
                            self?.updateSharedURL(url)
                        }
                    }
                }

                if attachment.hasItemConformingToTypeIdentifier(UTType.plainText.identifier) {
                    attachment.loadItem(forTypeIdentifier: UTType.plainText.identifier, options: nil) { [weak self] item, _ in
                        if let text = item as? String {
                            let urls = self?.extractURLs(from: text) ?? []
                            if let firstURL = urls.first {
                                self?.updateSharedURL(firstURL)
                                for url in urls.dropFirst() {
                                    self?.updateSharedURL(url)
                                }
                            } else if let url = URL(string: text), url.scheme != nil {
                                self?.updateSharedURL(url)
                            }
                        }
                    }
                }
            }
        }
    }

    private func updateSharedURL(_ candidate: URL) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            let best = self.preferredURL(current: self.sharedURL, candidate: candidate)
            guard best != self.sharedURL else { return }
            self.sharedURL = best
            self.updateSubmitState()
            print("🔗 [ShareExt] extracted URL=\(best.absoluteString)")
        }
    }

    private func preferredURL(current: URL?, candidate: URL) -> URL {
        guard let current else { return candidate }
        let candidateScore = scoreURL(candidate)
        let currentScore = scoreURL(current)
        if candidateScore > currentScore {
            return candidate
        }
        if candidateScore == currentScore,
           candidate.absoluteString.count > current.absoluteString.count {
            return candidate
        }
        return current
    }

    private func scoreURL(_ url: URL) -> Int {
        var score = 0
        if let scheme = url.scheme?.lowercased(), scheme == "http" || scheme == "https" {
            score += 1
        }
        if let components = URLComponents(url: url, resolvingAgainstBaseURL: false) {
            if let items = components.queryItems, !items.isEmpty {
                score += 2
                score += min(items.count, 3)
            }
            if let fragment = components.fragment, !fragment.isEmpty {
                score += 1
            }
        }
        return score
    }

    private func extractURLs(from text: String) -> [URL] {
        guard let detector = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) else {
            return []
        }
        let range = NSRange(text.startIndex..<text.endIndex, in: text)
        return detector.matches(in: text, options: [], range: range).compactMap { match in
            match.url
        }
    }

    // MARK: - API Submission

    private func submitURL(_ url: URL) async throws {
        let keychainToken = KeychainManager.shared.getToken(key: .accessToken)
        let sharedToken = SharedContainer.userDefaults.string(forKey: "accessToken")

        if let groupId = SharedContainer.appGroupId {
            let directDefaults = UserDefaults(suiteName: groupId)
            let directToken = directDefaults?.string(forKey: "accessToken")
            let containerURL = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: groupId)
            print("🔐 [ShareExt] Direct UserDefaults(\(groupId)) exists: \(directDefaults != nil)")
            let directTokenStatus = directToken != nil ? "found" : "nil"
            let containerPath = containerURL?.path ?? "nil"
            print("🔐 [ShareExt] Direct token: \(directTokenStatus)")
            print("🔐 [ShareExt] Container URL: \(containerPath)")
        }

        let keychainTokenStatus = keychainToken != nil ? "found" : "nil"
        let sharedTokenStatus = sharedToken != nil ? "found (\(sharedToken!.prefix(20))...)" : "nil"
        let appGroupId = SharedContainer.appGroupId ?? "nil"
        print("🔐 [ShareExt] Keychain token: \(keychainTokenStatus)")
        print("🔐 [ShareExt] SharedDefaults token: \(sharedTokenStatus)")
        print("🔐 [ShareExt] App group: \(appGroupId)")

        let token: String
        if let keychainToken = keychainToken {
            token = keychainToken
        } else if let sharedToken = sharedToken {
            token = sharedToken
        } else {
            throw ShareError.notAuthenticated
        }

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
}

// MARK: - UI Components

private final class OptionRowView: UIControl {

    private let titleLabel = UILabel()
    private let descriptionLabel = UILabel()
    private let indicatorView = UIImageView()

    init(title: String, description: String) {
        super.init(frame: .zero)

        layer.cornerRadius = 12
        layer.borderWidth = 1
        layer.borderColor = UIColor.separator.cgColor
        backgroundColor = .secondarySystemBackground
        isUserInteractionEnabled = true

        titleLabel.text = title
        titleLabel.font = UIFont.preferredFont(forTextStyle: .body)
        titleLabel.textColor = .label

        descriptionLabel.text = description
        descriptionLabel.font = UIFont.preferredFont(forTextStyle: .footnote)
        descriptionLabel.textColor = .secondaryLabel
        descriptionLabel.numberOfLines = 0

        indicatorView.tintColor = .systemBlue
        indicatorView.setContentHuggingPriority(.required, for: .horizontal)
        indicatorView.setContentCompressionResistancePriority(.required, for: .horizontal)

        let labelsStack = UIStackView(arrangedSubviews: [titleLabel, descriptionLabel])
        labelsStack.axis = .vertical
        labelsStack.spacing = 4
        labelsStack.alignment = .fill

        let rowStack = UIStackView(arrangedSubviews: [indicatorView, labelsStack])
        rowStack.axis = .horizontal
        rowStack.alignment = .center
        rowStack.spacing = 12
        rowStack.translatesAutoresizingMaskIntoConstraints = false
        rowStack.isUserInteractionEnabled = false

        addSubview(rowStack)

        NSLayoutConstraint.activate([
            rowStack.topAnchor.constraint(equalTo: topAnchor, constant: 12),
            rowStack.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 12),
            rowStack.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -12),
            rowStack.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -12),
            indicatorView.widthAnchor.constraint(equalToConstant: 22),
            indicatorView.heightAnchor.constraint(equalToConstant: 22),
        ])

        updateSelectionState()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override var isSelected: Bool {
        didSet {
            updateSelectionState()
        }
    }

    override var isHighlighted: Bool {
        didSet {
            updateSelectionState()
        }
    }

    private func updateSelectionState() {
        if isSelected {
            indicatorView.image = UIImage(systemName: "checkmark.circle.fill")
            layer.borderColor = UIColor.systemBlue.cgColor
        } else {
            indicatorView.image = UIImage(systemName: "circle")
            layer.borderColor = UIColor.separator.cgColor
        }

        if isHighlighted {
            backgroundColor = UIColor.systemGray6
        } else {
            backgroundColor = isSelected ? UIColor.systemBackground : UIColor.secondarySystemBackground
        }
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
