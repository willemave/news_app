//
//  LiveVoiceAmbientBackground.swift
//  newsly
//

import SwiftUI

struct LiveVoiceAmbientBackground: View {
    let energy: Float
    let isActive: Bool

    private var normalizedEnergy: Double {
        Double(min(1, max(0, energy)))
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            let t = timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, size in
                drawMorphingBlobs(context: &context, size: size, time: t)
            }
            .blur(radius: 60 - CGFloat(normalizedEnergy) * 20)
            .drawingGroup()
        }
        .ignoresSafeArea()
        .opacity(isActive ? 1 : 0)
        .animation(.easeInOut(duration: 0.8), value: isActive)
    }

    // MARK: - Morphing Gradient Blobs

    private func drawMorphingBlobs(context: inout GraphicsContext, size: CGSize, time: Double) {
        let cx = size.width / 2
        let cy = size.height / 2
        let e = normalizedEnergy

        // Base drift speed ramps up with energy
        let speedMul = 1.0 + e * 2.5

        let blobs: [(color: Color, baseRadius: CGFloat, xPhase: Double, yPhase: Double, baseSpeed: Double, drift: Double)] = [
            (.earthTerracotta, 200, 0,   0,   0.3,  50),
            (.earthSage,       160, 1.5, 2.0, 0.25, 70),
            (.earthClayMuted,  180, 3.0, 1.0, 0.35, 60),
            (.earthWoodWarm,   140, 4.5, 3.5, 0.2,  80),
            (.earthTerracotta.opacity(0.6), 120, 2.2, 4.0, 0.4, 90),
            (.earthSage.opacity(0.5), 100, 5.0, 1.5, 0.45, 100),
        ]

        for blob in blobs {
            let speed = blob.baseSpeed * speedMul
            let driftRange = blob.drift + e * 60

            let dx = sin(time * speed + blob.xPhase) * driftRange
            let dy = cos(time * speed * 0.7 + blob.yPhase) * driftRange * 0.8

            // Radius pulses with energy
            let breathe = sin(time * speed * 2.0 + blob.xPhase) * 15 * e
            let r = blob.baseRadius + CGFloat(e) * 60 + CGFloat(breathe)

            let blobCenter = CGPoint(x: cx + dx, y: cy + dy)
            let rect = CGRect(
                x: blobCenter.x - r,
                y: blobCenter.y - r,
                width: r * 2,
                height: r * 2
            )

            // Opacity increases with energy — blobs become more vivid
            let opacity = 0.4 + e * 0.45

            context.fill(
                Ellipse().path(in: rect),
                with: .color(blob.color.opacity(opacity))
            )
        }
    }
}
