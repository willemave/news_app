//
//  SwipeableCard.swift
//  newsly
//
//  Wrapper that adds swipe gesture to any content
//

import SwiftUI

struct SwipeableCard<Content: View>: View {
    let content: Content
    let onDismiss: () async -> Void

    @State private var dragOffset: CGSize = .zero
    @State private var isRemoving = false

    init(onDismiss: @escaping () async -> Void, @ViewBuilder content: () -> Content) {
        self.content = content()
        self.onDismiss = onDismiss
    }

    var body: some View {
        content
            .offset(x: dragOffset.width, y: dragOffset.height)
            .rotationEffect(.degrees(Double(dragOffset.width) / 30))
            .opacity(isRemoving ? 0 : 1)
            .gesture(
                DragGesture()
                    .onChanged { value in
                        guard !isRemoving else { return }
                        dragOffset = value.translation
                    }
                    .onEnded { value in
                        guard !isRemoving else { return }
                        handleGestureEnd(translation: value.translation, velocity: value.predictedEndTranslation)
                    }
            )
    }

    private func handleGestureEnd(translation: CGSize, velocity: CGSize) {
        let swipeThreshold: CGFloat = 100
        let velocityThreshold: CGFloat = 300

        // Calculate velocity
        let horizontalVelocity = velocity.width - translation.width
        let verticalVelocity = velocity.height - translation.height

        // Check if swipe left or up with sufficient distance or velocity
        let shouldDismiss = (translation.width < -swipeThreshold || horizontalVelocity < -velocityThreshold) ||
                            (translation.height < -swipeThreshold || verticalVelocity < -velocityThreshold)

        if shouldDismiss {
            dismissCard(in: translation)
        } else {
            // Spring back to center
            withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                dragOffset = .zero
            }
        }
    }

    private func dismissCard(in direction: CGSize) {
        isRemoving = true

        // Animate off screen in direction of swipe
        let offScreenDistance: CGFloat = 500
        let finalOffset: CGSize

        if abs(direction.width) > abs(direction.height) {
            // Horizontal swipe - go left
            finalOffset = CGSize(width: -offScreenDistance, height: direction.height)
        } else {
            // Vertical swipe - go up
            finalOffset = CGSize(width: direction.width, height: -offScreenDistance)
        }

        withAnimation(.easeOut(duration: 0.4)) {
            dragOffset = finalOffset
        }

        // Call onDismiss after animation
        Task {
            try? await Task.sleep(nanoseconds: 400_000_000) // 0.4 seconds
            await onDismiss()
        }
    }
}
