//
//  CardStackView.swift
//  newsly
//
//  Optimized stack with index-based rendering
//

import SwiftUI

struct CardStackView: View {
    let groups: [NewsGroup]
    let onDismiss: (String) async -> Void
    let onConvert: (Int) async -> Void

    @State private var currentIndex: Int = 0

    var body: some View {
        ZStack(alignment: .top) {
            if currentIndex >= groups.count {
                // Empty state - all cards swiped away
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
            } else {
                // Background placeholder cards
                ForEach(0..<min(2, groups.count - currentIndex), id: \.self) { offset in
                    let cardIndex = currentIndex + offset + 1
                    if cardIndex < groups.count {
                        PlaceholderCard(
                            scale: 1.0 - CGFloat(offset + 1) * 0.05,
                            yOffset: CGFloat(offset + 1) * 8
                        )
                        .zIndex(Double(10 - offset))
                    }
                }

                // Top card with full content
                SwipeableCard(onDismiss: {
                    handleCardDismissed()
                }) {
                    NewsGroupCard(
                        group: groups[currentIndex],
                        onConvert: onConvert
                    )
                }
                .id(currentIndex)  // Force view identity change for smooth data updates
                .zIndex(100)
            }
        }
        .padding(.horizontal, 16)
        .animation(.easeInOut(duration: 0.2), value: currentIndex)
    }

    private func handleCardDismissed() {
        let dismissedGroupId = groups[currentIndex].id

        // Update index immediately (synchronous, no view recreation lag)
        currentIndex += 1

        // Call async operations in background
        Task {
            await onDismiss(dismissedGroupId)
        }
    }
}
