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
                    .frame(width: RowMetrics.smallThumbnailSize, height: RowMetrics.smallThumbnailSize)
                    .background(statusColor.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                VStack(alignment: .leading, spacing: 4) {
                    Text(submission.displayTitle)
                        .font(.listTitle)
                        .foregroundStyle(Color.textPrimary)
                        .lineLimit(2)

                    Text(submission.url)
                        .font(.listMono)
                        .foregroundStyle(Color.textTertiary)
                        .lineLimit(1)

                    HStack(spacing: 6) {
                        if let date = submission.statusDateDisplay {
                            Text(date)
                                .font(.listCaption)
                                .foregroundStyle(Color.textSecondary)
                        }
                        Spacer()
                        if submission.isSelfSubmission {
                            TextBadge(text: "Submitted", color: .blue)
                        }
                        TextBadge(text: submission.statusLabel, color: statusColor)
                    }

                    if let error = submission.errorDisplayText {
                        Text(error)
                            .font(.listCaption)
                            .foregroundStyle(Color.statusDestructive)
                            .lineLimit(2)
                            .padding(.top, 2)
                    }
                }
            }
            .padding(.vertical, Spacing.rowVertical)
            .padding(.horizontal, Spacing.rowHorizontal)

            Divider()
                .padding(.leading, Spacing.rowHorizontal + RowMetrics.smallThumbnailSize + 12)
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
