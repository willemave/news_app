//
//  CardStackView.swift
//  newsly
//
//  Stack of swipeable cards with depth effect
//

import SwiftUI

struct CardStackView: View {
    let groups: [NewsGroup]
    let onDismiss: (String) async -> Void
    let onConvert: (Int) async -> Void

    var body: some View {
        ZStack {
            if groups.isEmpty {
                // Empty state
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
                // Show up to 3 cards for depth effect
                ForEach(Array(groups.prefix(3).enumerated()), id: \.element.id) { index, group in
                    let isTop = index == 0

                    SwipeableCard(onDismiss: {
                        await onDismiss(group.id)
                    }) {
                        NewsGroupCard(
                            group: group,
                            onConvert: onConvert
                        )
                    }
                    .allowsHitTesting(isTop)
                    .scaleEffect(1.0 - CGFloat(index) * 0.05)
                    .offset(y: CGFloat(index) * 8)
                    .zIndex(Double(groups.count - index))
                }
            }
        }
        .padding(.horizontal, 16)
    }
}
