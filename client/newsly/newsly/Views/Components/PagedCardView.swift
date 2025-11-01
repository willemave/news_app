//
//  PagedCardView.swift
//  newsly
//
//  Button-based navigation using TabView paging (replaces swipe gestures)
//

import SwiftUI

struct PagedCardView: View {
    let groups: [NewsGroup]
    let onDismiss: (String) async -> Void
    let onConvert: (Int) async -> Void

    // Track dismissed group IDs for immediate visual feedback
    @State private var dismissedGroupIds: Set<String> = []

    // Current page index (always reset to 0 when visibleGroups changes)
    @State private var currentIndex: Int = 0

    // Button state during async operations
    @State private var isProcessing: Bool = false

    // Visible groups = not read AND not dismissed
    private var visibleGroups: [NewsGroup] {
        groups.filter { group in
            !group.isRead && !dismissedGroupIds.contains(group.id)
        }
    }

    var body: some View {
        GeometryReader { geometry in
            VStack(spacing: 0) {
                if visibleGroups.isEmpty {
                    // Empty state - all cards dismissed
                    VStack(spacing: 16) {
                        Image(systemName: "newspaper")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("No more news")
                            .font(.title3)
                            .foregroundColor(.secondary)
                        Text("Pull to refresh")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    // Paged card view
                    TabView(selection: $currentIndex) {
                        ForEach(Array(visibleGroups.enumerated()), id: \.element.id) { index, group in
                            NewsGroupCard(
                                group: group,
                                onConvert: onConvert
                            )
                            .tag(index)
                            .padding(.horizontal, 16)
                        }
                    }
                    .tabViewStyle(.page)
                    .indexViewStyle(.page(backgroundDisplayMode: .always))
                    .frame(maxHeight: geometry.size.height - 100)

                    // Next/Done button
                    Button(action: {
                        handleNextTapped()
                    }) {
                        HStack(spacing: 6) {
                            if isProcessing {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                    .scaleEffect(0.9)
                            } else {
                                Text(visibleGroups.count == 1 ? "Done" : "Next")
                                    .font(.body)
                                    .fontWeight(.medium)
                                Image(systemName: "arrow.right.circle.fill")
                                    .font(.body)
                            }
                        }
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(
                            RoundedRectangle(cornerRadius: 10)
                                .fill(Color.accentColor)
                        )
                    }
                    .disabled(isProcessing || visibleGroups.isEmpty)
                    .opacity(isProcessing ? 0.6 : 1.0)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 8)
                }
            }
        }
        .animation(.easeInOut(duration: 0.2), value: visibleGroups.count)
        .onChange(of: groups.count) { oldCount, newCount in
            // Clean up dismissed IDs that are no longer in the groups array
            if newCount < oldCount {
                let currentGroupIds = Set(groups.map { $0.id })
                dismissedGroupIds = dismissedGroupIds.intersection(currentGroupIds)
            }

            // On refresh (count goes to 0 or significantly changes), clear dismissed set
            if newCount == 0 || abs(newCount - oldCount) > 10 {
                dismissedGroupIds.removeAll()
                currentIndex = 0
            }
        }
        .onChange(of: visibleGroups.count) { _, _ in
            // Reset to first page when visible groups change
            if !visibleGroups.isEmpty && currentIndex >= visibleGroups.count {
                currentIndex = 0
            }
        }
    }

    private func handleNextTapped() {
        // Guard: ensure we have visible groups
        guard !visibleGroups.isEmpty, currentIndex < visibleGroups.count else {
            return
        }

        // Prevent rapid taps
        guard !isProcessing else { return }

        let dismissedGroup = visibleGroups[currentIndex]

        // Mark as processing
        isProcessing = true

        // Mark as dismissed immediately (synchronous - instant visual feedback)
        dismissedGroupIds.insert(dismissedGroup.id)

        // Reset to first page (will show next card since current is now filtered out)
        currentIndex = 0

        // Call async operations in background (backend update)
        Task {
            await onDismiss(dismissedGroup.id)
            // Reset processing state
            isProcessing = false
        }
    }
}
