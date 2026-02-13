//
//  AncientScrollRevealView.swift
//  newsly
//
//  Created by Assistant on 2/10/26.
//

import SpriteKit
import SwiftUI

struct AncientScrollRevealView: View {
    let obfuscatedSeed: UInt64
    let showsPhysics: Bool
    let onProgressChanged: (Double) -> Void

    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    @State private var physicsScene = RevealPhysicsScene(size: CGSize(width: 1, height: 1))
    @State private var lastDragPoint: CGPoint?
    @State private var lastDragTime: Date?
    @State private var cumulativeSwipeDistance: CGFloat = 0

    var body: some View {
        GeometryReader { proxy in
            let canvasSize = proxy.size

            ZStack {
                background
                gridOverlay

                SpriteView(scene: physicsScene, options: [.allowsTransparency])
                    .allowsHitTesting(false)

                topTextOverlay
            }
            .clipped()
            .contentShape(Rectangle())
            .gesture(swipeGesture(in: canvasSize))
            .onAppear {
                configureScene(for: canvasSize)
            }
            .onChange(of: canvasSize) { _, newSize in
                configureScene(for: newSize)
            }
            .onChange(of: reduceMotion) { _, _ in
                configureScene(for: canvasSize)
            }
            .onDisappear {
                physicsScene.isPaused = true
            }
        }
    }

    private var background: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.05, green: 0.08, blue: 0.12),
                    Color(red: 0.08, green: 0.10, blue: 0.16),
                    Color(red: 0.10, green: 0.12, blue: 0.18)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            RadialGradient(
                colors: [
                    Color(red: 0.30, green: 0.36, blue: 0.44).opacity(0.22),
                    .clear
                ],
                center: .topTrailing,
                startRadius: 40,
                endRadius: 420
            )

            RadialGradient(
                colors: [
                    Color(red: 0.22, green: 0.26, blue: 0.32).opacity(0.18),
                    .clear
                ],
                center: .bottomLeading,
                startRadius: 30,
                endRadius: 360
            )
        }
    }

    private var gridOverlay: some View {
        Canvas { context, size in
            let spacing: CGFloat = 24
            let lineColor = Color.white.opacity(0.03)

            var x: CGFloat = 0
            while x <= size.width {
                var path = Path()
                path.move(to: CGPoint(x: x, y: 0))
                path.addLine(to: CGPoint(x: x, y: size.height))
                context.stroke(path, with: .color(lineColor), lineWidth: 0.5)
                x += spacing
            }

            var y: CGFloat = 0
            while y <= size.height {
                var path = Path()
                path.move(to: CGPoint(x: 0, y: y))
                path.addLine(to: CGPoint(x: size.width, y: y))
                context.stroke(path, with: .color(lineColor), lineWidth: 0.5)
                y += spacing
            }
        }
        .blendMode(.overlay)
        .allowsHitTesting(false)
    }

    private var topTextOverlay: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Willem News")
                .font(.system(size: 36, weight: .semibold, design: .rounded))
                .foregroundStyle(Color.white.opacity(0.90))

            Text("Curated updates and concise summaries, minus the noise.")
                .font(.callout.weight(.regular))
                .foregroundStyle(Color.white.opacity(0.74))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(24)
        .allowsHitTesting(false)
    }

    private func swipeGesture(in canvasSize: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 0, coordinateSpace: .local)
            .onChanged { value in
                handleSwipe(value: value, canvasSize: canvasSize)
            }
            .onEnded { _ in
                lastDragPoint = nil
                lastDragTime = nil
            }
    }

    private func handleSwipe(value: DragGesture.Value, canvasSize: CGSize) {
        guard canvasSize.width > 0, canvasSize.height > 0 else { return }
        guard showsPhysics, !reduceMotion else { return }

        let clampedPoint = CGPoint(
            x: min(max(0, value.location.x), canvasSize.width),
            y: min(max(0, value.location.y), canvasSize.height)
        )

        var velocity = CGVector.zero
        if let lastPoint = lastDragPoint, let lastTime = lastDragTime {
            let dt = max(0.001, value.time.timeIntervalSince(lastTime))
            let dx = clampedPoint.x - lastPoint.x
            let dy = clampedPoint.y - lastPoint.y
            velocity = CGVector(dx: dx / dt, dy: dy / dt)
            cumulativeSwipeDistance += hypot(dx, dy)

            onProgressChanged(min(1, Double(cumulativeSwipeDistance / 900)))
        }

        physicsScene.applySwipe(
            at: CGPoint(x: clampedPoint.x, y: canvasSize.height - clampedPoint.y),
            velocity: CGVector(dx: velocity.dx, dy: -velocity.dy)
        )

        lastDragPoint = clampedPoint
        lastDragTime = value.time
    }

    private func configureScene(for canvasSize: CGSize) {
        guard canvasSize.width > 0, canvasSize.height > 0 else { return }
        physicsScene.isPaused = false
        physicsScene.configure(seed: obfuscatedSeed, isEnabled: showsPhysics && !reduceMotion)
        physicsScene.updateBounds(to: canvasSize)
    }
}
