//
//  SubmissionStatusRow.swift
//  newsly
//
//  Created by Assistant on 1/14/26.
//

import SwiftUI

struct SubmissionStatusRow: View {
    let submission: SubmissionStatusItem

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(alignment: .top, spacing: 12) {
                // Status icon
                statusIcon
                    .frame(width: 40, height: 40)
                    .background(statusColor.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                VStack(alignment: .leading, spacing: 4) {
                    // Title row with badges
                    Text(submission.displayTitle)
                        .font(.headline)
                        .lineLimit(2)

                    // URL
                    Text(submission.url)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)

                    // Metadata row
                    HStack(spacing: 6) {
                        if let date = submission.statusDateDisplay {
                            Text(date)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        if submission.isSelfSubmission {
                            badge(text: "Submitted", color: .blue)
                        }
                        badge(text: submission.statusLabel, color: statusColor)
                    }

                    // Error message if present
                    if let error = submission.errorDisplayText {
                        Text(error)
                            .font(.caption)
                            .foregroundStyle(.red)
                            .lineLimit(2)
                            .padding(.top, 2)
                    }
                }
            }
            .padding(.vertical, 12)

            Divider()
                .padding(.leading, 52) // Inset to align with text (icon 40 + spacing 12)
        }
    }

    private var statusIcon: some View {
        Image(systemName: statusIconName)
            .font(.system(size: 16, weight: .medium))
            .foregroundStyle(statusColor)
    }

    private var statusIconName: String {
        switch submission.status.lowercased() {
        case "failed":
            return "exclamationmark.triangle.fill"
        case "skipped":
            return "forward.fill"
        case "processing":
            return "arrow.triangle.2.circlepath"
        case "completed":
            return "checkmark.circle.fill"
        case "new", "pending":
            return "clock.fill"
        default:
            return "questionmark.circle.fill"
        }
    }

    private var statusColor: Color {
        switch submission.status.lowercased() {
        case "failed":
            return .red
        case "skipped":
            return .orange
        case "processing":
            return .blue
        case "new", "pending":
            return .gray
        default:
            return .gray
        }
    }

    private func badge(text: String, color: Color) -> some View {
        Text(text.uppercased())
            .font(.caption2)
            .fontWeight(.semibold)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}

#Preview {
    SubmissionStatusRow(
        submission: SubmissionStatusItem(
            id: 1,
            contentType: "article",
            url: "https://example.com",
            sourceUrl: nil,
            title: "Example submission",
            status: "processing",
            errorMessage: nil,
            createdAt: "2025-01-01T12:00:00Z",
            processedAt: nil,
            submittedVia: "share_sheet",
            isSelfSubmission: true
        )
    )
    .padding()
}
