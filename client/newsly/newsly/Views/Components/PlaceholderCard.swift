//
//  PlaceholderCard.swift
//  newsly
//
//  Simple placeholder for background cards in stack
//

import SwiftUI

struct PlaceholderCard: View {
    let scale: CGFloat
    let yOffset: CGFloat

    var body: some View {
        Rectangle()
            .fill(Color(.systemBackground))
            .cornerRadius(12)
            .shadow(color: Color.black.opacity(0.1), radius: 4, x: 0, y: 2)
            .scaleEffect(scale)
            .offset(y: yOffset)
    }
}
