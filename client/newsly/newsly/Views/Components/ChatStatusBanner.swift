//
//  ChatStatusBanner.swift
//  newsly
//
//  Created by Assistant on 12/6/25.
//

import SwiftUI

/// A small banner that shows the status of an active chat session
struct ChatStatusBanner: View {
    let session: ActiveChatSession
    let onTap: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            // Status indicator
            statusIndicator

            // Message
            VStack(alignment: .leading, spacing: 2) {
                Text(statusTitle)
                    .font(.subheadline)
                    .fontWeight(.medium)

                Text(session.contentTitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(1)
            }

            Spacer()

            // Action button or dismiss
            actionButton
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(backgroundColor)
        .cornerRadius(12)
        .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .onTapGesture {
            if case .completed = session.status {
                onTap()
            }
        }
    }

    @ViewBuilder
    private var statusIndicator: some View {
        switch session.status {
        case .processing:
            ProgressView()
                .scaleEffect(0.8)
                .frame(width: 24, height: 24)

        case .completed:
            Image(systemName: "checkmark.circle.fill")
                .font(.title3)
                .foregroundColor(.green)

        case .failed:
            Image(systemName: "exclamationmark.circle.fill")
                .font(.title3)
                .foregroundColor(.red)
        }
    }

    private var statusTitle: String {
        switch session.status {
        case .processing:
            return "Analyzing..."
        case .completed:
            return "Analysis ready"
        case .failed(let error):
            return "Failed: \(error)"
        }
    }

    @ViewBuilder
    private var actionButton: some View {
        switch session.status {
        case .processing:
            // Show elapsed time or just a subtle indicator
            EmptyView()

        case .completed:
            Button(action: onTap) {
                Text("Open")
                    .font(.subheadline)
                    .fontWeight(.semibold)
            }
            .buttonStyle(.borderedProminent)
            .buttonBorderShape(.capsule)
            .controlSize(.small)

        case .failed:
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }

    private var backgroundColor: Color {
        switch session.status {
        case .processing:
            return Color(.systemBackground)
        case .completed:
            return Color(.systemBackground)
        case .failed:
            return Color.red.opacity(0.1)
        }
    }
}

#Preview {
    VStack(spacing: 16) {
        ChatStatusBanner(
            session: ActiveChatSession(
                id: 1,
                contentId: 1,
                contentTitle: "Understanding Modern AI Systems",
                messageId: 1,
                status: .processing
            ),
            onTap: {},
            onDismiss: {}
        )

        ChatStatusBanner(
            session: ActiveChatSession(
                id: 2,
                contentId: 2,
                contentTitle: "The Future of Web Development",
                messageId: 2,
                status: .completed
            ),
            onTap: {},
            onDismiss: {}
        )

        ChatStatusBanner(
            session: ActiveChatSession(
                id: 3,
                contentId: 3,
                contentTitle: "Some Article",
                messageId: 3,
                status: .failed("Network error")
            ),
            onTap: {},
            onDismiss: {}
        )
    }
    .padding()
    .background(Color(.secondarySystemBackground))
}
