//
//  PagedCardView.swift
//  newsly
//
//  Vertical, page-based navigation with swipe gestures
//

import SwiftUI
import UIKit

struct PagedCardView: View {
    let groups: [NewsGroup]
    let onMarkRead: (String) async -> Void
    let onConvert: (Int) async -> Void
    let onNearEnd: () async -> Void

    @State private var currentIndex: Int = 0
    @State private var dragOffset: CGFloat = 0
    @State private var inFlightReads: Set<String> = []

    private let swipeDistanceThreshold: CGFloat = 120
    private let swipeVelocityThreshold: CGFloat = 900

    var body: some View {
        GeometryReader { geometry in
            let cardHeight = max(geometry.size.height - 80, 320)

            VStack(spacing: 0) {
                if groups.isEmpty {
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
                    ZStack(alignment: .top) {
                        ForEach(Array(groups.enumerated()), id: \.element.id) { index, group in
                            NewsGroupCard(
                                group: group,
                                onConvert: onConvert
                            )
                            .frame(maxWidth: .infinity, minHeight: cardHeight, maxHeight: cardHeight)
                            .padding(.horizontal, 16)
                            .offset(y: offsetForCard(at: index, height: cardHeight))
                            .animation(.interactiveSpring(response: 0.32, dampingFraction: 0.85), value: currentIndex)
                            .animation(.interactiveSpring(response: 0.32, dampingFraction: 0.85), value: dragOffset)
                        }
                    }
                    .frame(maxHeight: cardHeight)
                    .clipped()
                    .contentShape(Rectangle())
                    // MinimumDistance keeps taps on links higher priority than swipes
                    .simultaneousGesture(dragGesture(cardHeight: cardHeight), including: .subviews)
                }
            }
            .padding(.top, -8)
        }
        .onChange(of: groups.count) { _, newCount in
            let clampedIndex = min(currentIndex, max(newCount - 1, 0))
            if clampedIndex != currentIndex {
                currentIndex = clampedIndex
            }
        }
    }

    private func offsetForCard(at index: Int, height: CGFloat) -> CGFloat {
        CGFloat(index - currentIndex) * height + dragOffset
    }

    private func dragGesture(cardHeight: CGFloat) -> some Gesture {
        DragGesture(minimumDistance: 28)
            .onChanged { value in
                dragOffset = value.translation.height
            }
            .onEnded { value in
                handleDragEnd(
                    translation: value.translation.height,
                    predictedEnd: value.predictedEndTranslation.height
                )
            }
    }

    private func handleDragEnd(translation: CGFloat, predictedEnd: CGFloat) {
        let oldIndex = currentIndex
        let velocity = predictedEnd - translation
        var targetIndex = currentIndex

        if translation < -swipeDistanceThreshold || velocity < -swipeVelocityThreshold {
            targetIndex = min(currentIndex + 1, groups.count - 1)
        } else if translation > swipeDistanceThreshold || velocity > swipeVelocityThreshold {
            targetIndex = max(currentIndex - 1, 0)
        }

        withAnimation(.interactiveSpring(response: 0.32, dampingFraction: 0.85)) {
            currentIndex = targetIndex
            dragOffset = 0
        }

        if targetIndex != oldIndex {
            handlePageChange(from: oldIndex, to: targetIndex)
        }
    }

    private func handlePageChange(from oldIndex: Int, to newIndex: Int) {
        triggerHaptic()

        if newIndex > oldIndex {
            markGroupAsReadIfNeeded(oldIndex)
        }

        if newIndex >= groups.count - 2 {
            Task { await onNearEnd() }
        }
    }

    private func markGroupAsReadIfNeeded(_ index: Int) {
        guard groups.indices.contains(index) else { return }
        let group = groups[index]
        guard !group.isRead, !inFlightReads.contains(group.id) else { return }

        inFlightReads.insert(group.id)
        Task {
            await onMarkRead(group.id)
            inFlightReads.remove(group.id)
        }
    }

    private func triggerHaptic() {
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.impactOccurred()
    }
}
