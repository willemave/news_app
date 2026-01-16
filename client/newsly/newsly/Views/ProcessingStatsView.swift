//
//  ProcessingStatsView.swift
//  newsly
//
//  Created by Assistant on 1/16/26.
//

import SwiftUI

struct ProcessingStatsView: View {
    @StateObject private var statsService = LongFormStatsService.shared

    var body: some View {
        List {
            Section {
                statRow(
                    title: "Processing",
                    subtitle: "Pending or running",
                    count: statsService.processingCount,
                    icon: "clock.arrow.circlepath",
                    color: .teal
                )
                statRow(
                    title: "Unread",
                    subtitle: "Ready to read",
                    count: statsService.unreadCount,
                    icon: "tray",
                    color: .blue
                )
                statRow(
                    title: "Read",
                    subtitle: "Completed",
                    count: statsService.readCount,
                    icon: "checkmark.circle.fill",
                    color: .green
                )
                statRow(
                    title: "Favorited",
                    subtitle: "Saved items",
                    count: statsService.favoritedCount,
                    icon: "star.fill",
                    color: .yellow
                )
                statRow(
                    title: "Total",
                    subtitle: "In your long-form inbox",
                    count: statsService.totalCount,
                    icon: "doc.text",
                    color: .gray
                )
            } header: {
                Text("Long-form")
            } footer: {
                Text("Counts include articles, podcasts, and YouTube.")
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Processing Stats")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await statsService.refreshStats()
        }
    }

    private func statRow(
        title: String,
        subtitle: String,
        count: Int,
        icon: String,
        color: Color
    ) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(.white)
                .frame(width: 28, height: 28)
                .background(color.gradient)
                .clipShape(RoundedRectangle(cornerRadius: 6))
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                Text(subtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Text("\(count)")
                .font(.callout)
                .fontWeight(.semibold)
                .foregroundStyle(.primary)
        }
        .padding(.vertical, 2)
    }
}

#Preview {
    NavigationStack {
        ProcessingStatsView()
    }
}
