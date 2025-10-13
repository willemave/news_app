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
                        handleGestureEnd(translation: value.translation, predictedEnd: value.predictedEndTranslation)
                    }
            )
    }

    private func handleGestureEnd(translation: CGSize, predictedEnd: CGSize) {
        let swipeThreshold: CGFloat = 100
        let velocityThreshold: CGFloat = 300

        // Calculate velocity from difference between predicted end and current position
        let horizontalVelocity = abs(predictedEnd.width - translation.width)
        let verticalVelocity = abs(predictedEnd.height - translation.height)

        // Check if swipe left or up with sufficient distance or velocity
        let isSwipingLeft = translation.width < -swipeThreshold || (translation.width < 0 && horizontalVelocity > velocityThreshold)
        let isSwipingUp = translation.height < -swipeThreshold || (translation.height < 0 && verticalVelocity > velocityThreshold)

        let shouldDismiss = isSwipingLeft || isSwipingUp

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

        withAnimation(.easeOut(duration: 0.6)) {
            dragOffset = finalOffset
        }

        // Call onDismiss after animation
        Task {
            try? await Task.sleep(nanoseconds: 600_000_000) // 0.6 seconds
            await onDismiss()
        }
    }
}
