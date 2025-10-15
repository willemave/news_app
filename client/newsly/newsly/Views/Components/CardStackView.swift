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
        GeometryReader { geometry in
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
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    // Background placeholder cards (show 3 cards behind)
                    ForEach(0..<min(3, groups.count - currentIndex), id: \.self) { offset in
                        let cardIndex = currentIndex + offset + 1
                        if cardIndex < groups.count {
                            PlaceholderCard(
                                scale: 1.0 - CGFloat(offset + 1) * 0.03,
                                yOffset: CGFloat(offset + 1) * 6
                            )
                            .zIndex(Double(10 - offset))
                        }
                    }

                    // Top card with full content
                    if currentIndex < groups.count {
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
            }
            .frame(maxHeight: geometry.size.height - 40)  // Leave space for tab bar
            .padding(.horizontal, 16)
            .padding(.top, 8)
        }
        .animation(.easeInOut(duration: 0.2), value: currentIndex)
        .onChange(of: groups.count) { oldCount, newCount in
            // Reset index when groups are refreshed or prevent out-of-bounds
            if newCount > oldCount || currentIndex >= newCount {
                currentIndex = 0
            }
        }
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
