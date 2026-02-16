//
//  LiveVoiceSphereView.swift
//  newsly
//

import SwiftUI

struct LiveVoiceSphereView: View {
    let energy: Float
    let isSpeaking: Bool
    let isListening: Bool
    let isThinking: Bool

    private var normalizedEnergy: CGFloat {
        CGFloat(min(1, max(0, energy)))
    }

    var body: some View {
        TimelineView(.animation) { timeline in
            let t = timeline.date.timeIntervalSinceReferenceDate
            Canvas { context, size in
                let center = CGPoint(x: size.width / 2, y: size.height / 2)
                drawAmbientGlow(context: &context, center: center, time: t)
                drawOrganicCore(context: &context, center: center, time: t)
                drawInnerRing(context: &context, center: center, time: t)
                drawOuterRing(context: &context, center: center, time: t)
            }
        }
        .frame(width: 280, height: 280)
        .accessibilityHidden(true)
    }

    // MARK: - Ambient Glow

    private func drawAmbientGlow(context: inout GraphicsContext, center: CGPoint, time: Double) {
        let breathe = sin(time * 0.8) * 0.03
        let baseRadius: CGFloat = 130 + CGFloat(breathe) * 130
        let energyBoost: CGFloat = normalizedEnergy * 20
        let radius = baseRadius + energyBoost

        let glowOpacity: Double = isSpeaking ? 0.35 : (isListening ? 0.25 : 0.15)
        let hue = isSpeaking
            ? 0.52 + sin(time * 1.5) * 0.04
            : (isThinking ? 0.58 + sin(time * 0.6) * 0.03 : 0.54)

        let color = Color(hue: hue, saturation: 0.7, brightness: 0.9).opacity(glowOpacity)

        let rect = CGRect(
            x: center.x - radius,
            y: center.y - radius * 0.95,
            width: radius * 2,
            height: radius * 1.9
        )
        var glow = context
        glow.addFilter(.blur(radius: 40))
        glow.fill(Ellipse().path(in: rect), with: .color(color))
    }

    // MARK: - Organic Blob Core

    private func drawOrganicCore(context: inout GraphicsContext, center: CGPoint, time: Double) {
        let baseRadius: CGFloat = 85
        let idleBreath = sin(time * 1.1) * 3
        let energyScale = 1.0 + Double(normalizedEnergy) * 0.18
        let thinkingPulse = isThinking ? sin(time * 2.0) * 4 : 0

        let blobOffsets: [(dx: Double, dy: Double, phase: Double, speed: Double)] = [
            (0, 0, 0, 1.0),
            (0.6, 0.3, 1.2, 1.3),
            (-0.5, 0.5, 2.5, 0.9),
            (0.3, -0.6, 3.8, 1.1),
        ]

        for (i, blob) in blobOffsets.enumerated() {
            let angle = time * blob.speed + blob.phase
            let dx = sin(angle) * blob.dx * 8
            let dy = cos(angle * 0.7) * blob.dy * 8
            let blobRadius = (baseRadius + idleBreath + thinkingPulse) * energyScale
            let blobCenter = CGPoint(
                x: center.x + dx,
                y: center.y + dy
            )
            let rect = CGRect(
                x: blobCenter.x - blobRadius,
                y: blobCenter.y - blobRadius,
                width: blobRadius * 2,
                height: blobRadius * 2
            )

            let opacity: Double = i == 0 ? 0.95 : 0.35
            let saturation = isThinking ? 0.5 : 0.75
            let hue = 0.52 + Double(i) * 0.03 + sin(time * 0.5 + blob.phase) * 0.02

            let innerColor = Color(hue: hue, saturation: saturation, brightness: 0.95)
            let outerColor = Color(hue: hue + 0.08, saturation: saturation, brightness: 0.6)

            let gradient = Gradient(colors: [
                innerColor.opacity(opacity),
                outerColor.opacity(opacity * 0.4),
            ])
            let shading = GraphicsContext.Shading.radialGradient(
                gradient,
                center: blobCenter,
                startRadius: 10,
                endRadius: blobRadius
            )

            var blobCtx = context
            if i > 0 {
                blobCtx.addFilter(.blur(radius: 6))
            }
            blobCtx.fill(Circle().path(in: rect), with: shading)
        }
    }

    // MARK: - Inner Ring

    private func drawInnerRing(context: inout GraphicsContext, center: CGPoint, time: Double) {
        let baseRadius: CGFloat = 108
        let energyBounce = Double(normalizedEnergy) * 12
        let idlePulse = sin(time * 1.3) * 2
        let radius = baseRadius + energyBounce + idlePulse

        let ringOpacity: Double
        if isListening {
            ringOpacity = 0.4 + Double(normalizedEnergy) * 0.5
        } else if isSpeaking {
            ringOpacity = 0.5 + Double(normalizedEnergy) * 0.4
        } else {
            ringOpacity = 0.15 + sin(time * 0.9) * 0.05
        }

        let rect = CGRect(
            x: center.x - radius,
            y: center.y - radius,
            width: radius * 2,
            height: radius * 2
        )
        context.stroke(
            Circle().path(in: rect),
            with: .color(Color.white.opacity(ringOpacity)),
            lineWidth: 1.2
        )
    }

    // MARK: - Outer Ring

    private func drawOuterRing(context: inout GraphicsContext, center: CGPoint, time: Double) {
        let baseRadius: CGFloat = 128
        let energyBounce = Double(normalizedEnergy) * 18
        let idlePulse = sin(time * 0.9 + 0.5) * 2
        let delayedTime = time - 0.05
        let delayedBreath = sin(delayedTime * 1.1) * 2
        let radius = baseRadius + energyBounce + idlePulse + delayedBreath

        let ringOpacity: Double
        if isListening {
            ringOpacity = 0.25 + Double(normalizedEnergy) * 0.5
        } else if isSpeaking {
            ringOpacity = 0.3 + Double(normalizedEnergy) * 0.45
        } else {
            ringOpacity = 0.08 + sin(time * 0.7) * 0.04
        }

        let rect = CGRect(
            x: center.x - radius,
            y: center.y - radius,
            width: radius * 2,
            height: radius * 2
        )
        context.stroke(
            Circle().path(in: rect),
            with: .color(Color.cyan.opacity(ringOpacity)),
            lineWidth: 0.8
        )
    }
}
