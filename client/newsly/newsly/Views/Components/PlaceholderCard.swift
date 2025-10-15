//
//  PlaceholderCard.swift
//  newsly
//
//  Placeholder card with simulated content lines
//

import SwiftUI

struct PlaceholderCard: View {
    let scale: CGFloat
    let yOffset: CGFloat

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header section
            HStack {
                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 80, height: 10)

                Spacer()

                RoundedRectangle(cornerRadius: 2)
                    .fill(Color.gray.opacity(0.2))
                    .frame(width: 50, height: 8)
            }
            .padding(.horizontal, 12)
            .padding(.top, 10)

            // Simulated content items
            ForEach(0..<6, id: \.self) { index in
                VStack(alignment: .leading, spacing: 4) {
                    // Title lines
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.gray.opacity(0.25))
                        .frame(height: 12)
                        .frame(maxWidth: .infinity)

                    // Second line with varying widths (deterministic based on index)
                    GeometryReader { geometry in
                        let widthMultipliers: [CGFloat] = [0.85, 0.70, 0.80, 0.75, 0.90, 0.65]
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.gray.opacity(0.2))
                            .frame(height: 12)
                            .frame(width: geometry.size.width * widthMultipliers[index])
                    }
                    .frame(height: 12)

                    // Metadata line
                    HStack {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.gray.opacity(0.15))
                            .frame(width: 60, height: 8)

                        Spacer()

                        RoundedRectangle(cornerRadius: 2)
                            .fill(Color.gray.opacity(0.15))
                            .frame(width: 40, height: 8)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)

                if index < 5 {
                    Divider()
                        .padding(.horizontal, 12)
                }
            }
            .padding(.bottom, 8)
        }
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.15), radius: 6, x: 0, y: 3)
        .scaleEffect(scale)
        .offset(y: yOffset)
        .opacity(0.8 - ((1.0 - scale) * 2.0))  // Fade out cards further back
    }
}
