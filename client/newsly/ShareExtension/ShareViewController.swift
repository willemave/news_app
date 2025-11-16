//
//  ShareViewController.swift
//  ShareExtension
//
//  Created by Assistant on 11/19/25.
//

import SwiftUI
import UIKit
import UniformTypeIdentifiers

final class ShareViewController: UIViewController {
    override func viewDidLoad() {
        super.viewDidLoad()

        if let accessGroup = SharedContainer.keychainAccessGroup {
            KeychainManager.shared.configure(accessGroup: accessGroup)
        }

        extractSharedURL { [weak self] url in
            DispatchQueue.main.async {
                self?.presentShareView(url: url)
            }
        }
    }

    private func presentShareView(url: URL?) {
        let shareView = ShareSubmissionView(sharedURL: url, extensionContext: extensionContext)
        let hosting = UIHostingController(rootView: shareView)
        addChild(hosting)
        hosting.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(hosting.view)
        NSLayoutConstraint.activate([
            hosting.view.topAnchor.constraint(equalTo: view.topAnchor),
            hosting.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            hosting.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            hosting.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
        hosting.didMove(toParent: self)
    }

    private func extractSharedURL(completion: @escaping (URL?) -> Void) {
        guard let items = extensionContext?.inputItems as? [NSExtensionItem] else {
            completion(nil)
            return
        }

        for item in items {
            guard let attachments = item.attachments else { continue }
            for provider in attachments where provider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
                provider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { item, _ in
                    if let url = item as? URL {
                        completion(url)
                    } else if let url = (item as? NSURL)?.absoluteURL {
                        completion(url)
                    } else {
                        completion(nil)
                    }
                }
                return
            }
        }

        completion(nil)
    }
}

private enum ShareSubmissionState {
    case idle
    case submitting
    case success(String)
    case failure(String)
}

struct ShareSubmissionView: View {
    let sharedURL: URL?
    let extensionContext: NSExtensionContext?

    @State private var state: ShareSubmissionState = .idle

    var body: some View {
        VStack(spacing: 16) {
            Text("Send to Newsly")
                .font(.headline)

            if let url = sharedURL {
                Text(url.absoluteString)
                    .font(.footnote)
                    .multilineTextAlignment(.center)
                    .lineLimit(4)
            } else {
                Text("No URL detected in this share. Only URL shares are supported.")
                    .font(.footnote)
                    .multilineTextAlignment(.center)
            }

            switch state {
            case .idle:
                Button {
                    guard let url = sharedURL else {
                        state = .failure("No shareable URL found.")
                        return
                    }
                    submit(url: url)
                } label: {
                    Label("Submit URL", systemImage: "paperplane.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(sharedURL == nil)
            case .submitting:
                ProgressView("Submitting…")
            case .success(let message):
                Label(message, systemImage: "checkmark.circle.fill")
                    .foregroundStyle(.green)
                Button("Close") {
                    extensionContext?.completeRequest(returningItems: nil)
                }
            case .failure(let message):
                Label(message, systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
                Button("Dismiss") {
                    extensionContext?.cancelRequest(withError: NSError(domain: "ShareExtension", code: 1))
                }
            }

            Spacer()
        }
        .padding()
        .onAppear {
            guard case .idle = state, let url = sharedURL else { return }
            submit(url: url)
        }
    }

    private func submit(url: URL) {
        guard let scheme = url.scheme?.lowercased(), scheme == "http" || scheme == "https" else {
            state = .failure("Only http/https URLs are supported.")
            return
        }

        state = .submitting
        Task {
            do {
                let response = try await ContentService.shared.submitContent(url: url)
                await MainActor.run {
                    state = .success(response.message)
                }
            } catch {
                await MainActor.run {
                    state = .failure(error.localizedDescription)
                }
            }
        }
    }
}

