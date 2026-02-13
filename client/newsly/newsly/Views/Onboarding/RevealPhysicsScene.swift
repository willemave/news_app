//
//  RevealPhysicsScene.swift
//  newsly
//
//  Created by Assistant on 2/10/26.
//

import CoreGraphics
import SpriteKit
import UIKit

struct GlyphPhraseCycler {
    private let phrase: [Character]
    private(set) var index: Int = 0

    init(phrase: String) {
        let fallback = phrase.isEmpty ? "Willem News" : phrase
        self.phrase = Array(fallback)
    }

    mutating func nextCharacter(skipSpaces: Bool = true) -> Character {
        guard !phrase.isEmpty else { return "W" }
        var attempts = 0
        while attempts < phrase.count {
            let character = phrase[index]
            index = (index + 1) % phrase.count
            attempts += 1
            if skipSpaces && character == " " {
                continue
            }
            return character
        }
        return "W"
    }
}

enum SwipeImpulseModel {
    static func normalizedImpulse(distance: CGFloat, influenceRadius: CGFloat) -> CGFloat {
        guard influenceRadius > 0 else { return 0 }
        let falloff = 1 - (distance / influenceRadius)
        return max(0, min(1, falloff))
    }

    static func impulseVector(
        from touchPoint: CGPoint,
        to nodePoint: CGPoint,
        dragVelocity: CGVector,
        influenceRadius: CGFloat,
        baseForce: CGFloat
    ) -> CGVector {
        let dx = nodePoint.x - touchPoint.x
        let dy = nodePoint.y - touchPoint.y
        let distance = max(0.0001, hypot(dx, dy))
        let normalized = normalizedImpulse(distance: distance, influenceRadius: influenceRadius)
        guard normalized > 0 else { return .zero }

        let awayX = dx / distance
        let awayY = dy / distance
        let velocityScale: CGFloat = 0.00022

        return CGVector(
            dx: (awayX * baseForce + dragVelocity.dx * velocityScale) * normalized,
            dy: (awayY * baseForce + -dragVelocity.dy * velocityScale) * normalized
        )
    }
}

final class RevealPhysicsScene: SKScene {
    private static let glyphPhrase = "Willem News curates your feed and summarizes what matters."

    private let glyphNodeName = "rainGlyph"
    private let wallNodeNames = ["leftWall", "rightWall"]
    private let maxGlyphNodes = 220
    private let spawnInterval: TimeInterval = 0.11
    private let influenceRadius: CGFloat = 220
    private let baseImpulseForce: CGFloat = 1.70

    private let palette: [UIColor] = [
        UIColor(red: 0.78, green: 0.84, blue: 0.92, alpha: 1.0),
        UIColor(red: 0.68, green: 0.79, blue: 0.86, alpha: 1.0),
        UIColor(red: 0.85, green: 0.80, blue: 0.72, alpha: 1.0),
    ]
    private let fontNames: [String] = [
        "AvenirNext-Regular",
        "AvenirNext-Medium",
        "HelveticaNeue-Medium",
        "Futura-Medium",
    ]

    private var phraseCycler = GlyphPhraseCycler(phrase: glyphPhrase)
    private var spawnAccumulator: TimeInterval = 0
    private var lastUpdateTimestamp: TimeInterval = 0
    private var floatDriftPhase: TimeInterval = 0
    private var rainActive = true
    private var laneCount: Int = 12
    private var seededGenerator = LCG(seed: 0x5A17)

    override init(size: CGSize) {
        super.init(size: size)
        scaleMode = .resizeFill
        backgroundColor = .clear
        physicsWorld.gravity = CGVector(dx: 0.0, dy: -1.45)
    }

    required init?(coder aDecoder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func didMove(to view: SKView) {
        super.didMove(to: view)
        updateBounds(to: size)
    }

    override func didChangeSize(_ oldSize: CGSize) {
        super.didChangeSize(oldSize)
        updateBounds(to: size)
    }

    func configure(seed: UInt64, isEnabled: Bool) {
        rainActive = isEnabled
        seededGenerator = LCG(seed: seed)
        phraseCycler = GlyphPhraseCycler(phrase: Self.glyphPhrase)
        children
            .filter { $0.name == glyphNodeName }
            .forEach { $0.removeFromParent() }
    }

    func updateBounds(to newSize: CGSize) {
        guard newSize.width > 0, newSize.height > 0 else { return }
        if size != newSize {
            size = newSize
        }
        anchorPoint = .zero
        laneCount = max(9, Int(newSize.width / 30))
        configureWalls(for: newSize)
    }

    func applySwipe(at point: CGPoint, velocity: CGVector) {
        guard rainActive else { return }

        for node in children where node.name == glyphNodeName {
            guard let body = node.physicsBody else { continue }
            let impulse = SwipeImpulseModel.impulseVector(
                from: point,
                to: node.position,
                dragVelocity: velocity,
                influenceRadius: influenceRadius,
                baseForce: baseImpulseForce
            )
            guard impulse != .zero else { continue }
            body.isResting = false
            body.applyImpulse(impulse)
            body.applyAngularImpulse(CGFloat.random(in: -0.05...0.05) * max(0.2, abs(impulse.dx + impulse.dy)))
        }
    }

    override func update(_ currentTime: TimeInterval) {
        if lastUpdateTimestamp == 0 {
            lastUpdateTimestamp = currentTime
            return
        }

        let delta = min(0.05, max(0, currentTime - lastUpdateTimestamp))
        lastUpdateTimestamp = currentTime

        if rainActive {
            spawnAccumulator += delta
            while spawnAccumulator >= spawnInterval {
                spawnGlyph()
                spawnAccumulator -= spawnInterval
            }
        }

        floatDriftPhase += delta
        applyAmbientFloatDrift(time: floatDriftPhase)
        cleanupOffscreenGlyphs()
        trimGlyphOverflowIfNeeded()
    }

    private func configureWalls(for sceneSize: CGSize) {
        for name in wallNodeNames {
            childNode(withName: name)?.removeFromParent()
        }

        let left = SKNode()
        left.name = wallNodeNames[0]
        left.physicsBody = SKPhysicsBody(edgeFrom: CGPoint(x: 0, y: -64), to: CGPoint(x: 0, y: sceneSize.height + 64))
        left.physicsBody?.isDynamic = false
        addChild(left)

        let right = SKNode()
        right.name = wallNodeNames[1]
        right.physicsBody = SKPhysicsBody(edgeFrom: CGPoint(x: sceneSize.width, y: -64), to: CGPoint(x: sceneSize.width, y: sceneSize.height + 64))
        right.physicsBody?.isDynamic = false
        addChild(right)
    }

    private func spawnGlyph() {
        guard size.width > 0, size.height > 0, laneCount > 0 else { return }

        let laneWidth = size.width / CGFloat(laneCount)
        let lane = Int.random(in: 0..<laneCount, using: &seededGenerator)
        let xJitter = CGFloat.random(in: -4...4, using: &seededGenerator)
        let x = (CGFloat(lane) + 0.5) * laneWidth + xJitter
        let y = size.height + CGFloat.random(in: 20...80, using: &seededGenerator)

        let glyph = String(phraseCycler.nextCharacter(skipSpaces: true))
        let fontName = fontNames.randomElement(using: &seededGenerator) ?? "AvenirNext-Medium"
        let fontSize = CGFloat.random(in: 24...38, using: &seededGenerator)
        let font = UIFont(name: fontName, size: fontSize) ?? UIFont.systemFont(ofSize: fontSize, weight: .medium)

        let label = SKLabelNode(fontNamed: font.fontName)
        label.name = glyphNodeName
        label.text = glyph
        label.fontSize = fontSize
        label.fontColor = (palette.randomElement(using: &seededGenerator) ?? .white)
            .withAlphaComponent(CGFloat.random(in: 0.58...0.80, using: &seededGenerator))
        label.position = CGPoint(x: x, y: y)
        label.horizontalAlignmentMode = .center
        label.verticalAlignmentMode = .center
        label.zRotation = CGFloat.random(in: -0.05...0.05, using: &seededGenerator)
        addChild(label)

        let sizeEstimate = NSString(string: glyph).size(withAttributes: [.font: font])
        let body = SKPhysicsBody(
            rectangleOf: CGSize(
                width: max(20, sizeEstimate.width * 1.16),
                height: max(24, sizeEstimate.height * 1.16)
            )
        )
        body.affectedByGravity = true
        body.allowsRotation = true
        body.restitution = CGFloat.random(in: 0.12...0.24, using: &seededGenerator)
        body.friction = CGFloat.random(in: 0.20...0.36, using: &seededGenerator)
        body.linearDamping = CGFloat.random(in: 0.52...0.85, using: &seededGenerator)
        body.angularDamping = CGFloat.random(in: 0.58...0.92, using: &seededGenerator)
        body.mass = max(0.035, (sizeEstimate.width * sizeEstimate.height) / 7_600)
        body.usesPreciseCollisionDetection = true
        body.velocity = CGVector(
            dx: CGFloat.random(in: -4...4, using: &seededGenerator),
            dy: CGFloat.random(in: -3 ... 1, using: &seededGenerator)
        )
        label.physicsBody = body

        label.run(
            .sequence([
                .wait(forDuration: TimeInterval.random(in: 4.0...6.0, using: &seededGenerator)),
                .fadeAlpha(to: 0.40, duration: 1.8)
            ])
        )
    }

    private func applyAmbientFloatDrift(time: TimeInterval) {
        let t = CGFloat(time)
        for node in children where node.name == glyphNodeName {
            guard let body = node.physicsBody else { continue }

            let sway = sin((node.position.y * 0.020) + (t * 1.8)) * 0.016
            let lift = cos((node.position.x * 0.014) + (t * 1.2)) * 0.010 + 0.016
            body.applyForce(CGVector(dx: sway, dy: lift))
        }
    }

    private func cleanupOffscreenGlyphs() {
        for node in children where node.name == glyphNodeName {
            if node.position.y < -140 || node.position.x < -120 || node.position.x > size.width + 120 {
                node.removeFromParent()
            }
        }
    }

    private func trimGlyphOverflowIfNeeded() {
        let glyphNodes = children.filter { $0.name == glyphNodeName }
        guard glyphNodes.count > maxGlyphNodes else { return }

        let overflow = glyphNodes.count - maxGlyphNodes
        let toRemove = glyphNodes
            .sorted { $0.position.y < $1.position.y }
            .prefix(overflow)
        for node in toRemove {
            node.removeFromParent()
        }
    }
}

private struct LCG: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        state = seed == 0 ? 0x9E37_79B9_7F4A_7C15 : seed
    }

    mutating func next() -> UInt64 {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return state
    }
}
