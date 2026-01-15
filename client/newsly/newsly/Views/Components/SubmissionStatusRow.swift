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
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(submission.displayTitle)
                    .font(.body)
                    .lineLimit(2)

                Spacer(minLength: 8)

                if submission.isSelfSubmission {
                    badge(text: "Submitted", color: .blue)
                }

                badge(text: submission.statusLabel, color: statusColor)
            }

            if let date = submission.statusDateDisplay {
                Text(date)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let error = submission.errorDisplayText {
                Text(error)
                    .font(.caption)
                    .foregroundStyle(.red)
                    .lineLimit(3)
            }
        }
        .padding(.vertical, 4)
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
