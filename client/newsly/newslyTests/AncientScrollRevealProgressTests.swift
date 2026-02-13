//
//  AncientScrollRevealProgressTests.swift
//  newslyTests
//
//  Created by Assistant on 2/10/26.
//

import CoreGraphics
import XCTest
@testable import newsly

final class AncientScrollRevealProgressTests: XCTestCase {
    func testGlyphPhraseCyclerSkipsSpacesAndCycles() {
        var cycler = GlyphPhraseCycler(phrase: "Willem News")
        let output = (0..<10).map { _ in cycler.nextCharacter(skipSpaces: true) }
        XCTAssertEqual(String(output), "WillemNews")
        XCTAssertEqual(cycler.nextCharacter(skipSpaces: true), "W")
    }

    func testGlyphPhraseCyclerCanReturnSpacesWhenRequested() {
        var cycler = GlyphPhraseCycler(phrase: "A B")
        let chars = [
            cycler.nextCharacter(skipSpaces: false),
            cycler.nextCharacter(skipSpaces: false),
            cycler.nextCharacter(skipSpaces: false),
        ]
        XCTAssertEqual(chars, ["A", " ", "B"])
    }

    func testNormalizedImpulseFallsOffByDistance() {
        let near = SwipeImpulseModel.normalizedImpulse(distance: 10, influenceRadius: 100)
        let medium = SwipeImpulseModel.normalizedImpulse(distance: 50, influenceRadius: 100)
        let far = SwipeImpulseModel.normalizedImpulse(distance: 130, influenceRadius: 100)

        XCTAssertGreaterThan(near, medium)
        XCTAssertGreaterThan(medium, 0)
        XCTAssertEqual(far, 0)
    }

    func testImpulseVectorPushesAwayFromTouchPoint() {
        let vector = SwipeImpulseModel.impulseVector(
            from: CGPoint(x: 100, y: 100),
            to: CGPoint(x: 130, y: 100),
            dragVelocity: .zero,
            influenceRadius: 120,
            baseForce: 0.3
        )

        XCTAssertGreaterThan(vector.dx, 0)
    }

    func testImpulseVectorIncludesDragVelocityInfluence() {
        let noVelocity = SwipeImpulseModel.impulseVector(
            from: CGPoint(x: 120, y: 120),
            to: CGPoint(x: 120, y: 150),
            dragVelocity: .zero,
            influenceRadius: 120,
            baseForce: 0.3
        )
        let withVelocity = SwipeImpulseModel.impulseVector(
            from: CGPoint(x: 120, y: 120),
            to: CGPoint(x: 120, y: 150),
            dragVelocity: CGVector(dx: 1400, dy: -900),
            influenceRadius: 120,
            baseForce: 0.3
        )

        XCTAssertNotEqual(noVelocity.dx, withVelocity.dx)
        XCTAssertNotEqual(noVelocity.dy, withVelocity.dy)
    }
}
