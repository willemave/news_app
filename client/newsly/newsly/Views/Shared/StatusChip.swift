//
//  StatusChip.swift
//  newsly
//
//  Linear-style status indicator chip.
//

import SwiftUI

struct StatusChip: View {
    let isActive: Bool

    var body: some View {
        HStack(spacing: 4) {
            Circle()
                .fill(isActive ? Color.statusActive : Color.statusInactive)
                .frame(width: 6, height: 6)

            Text(isActive ? "Active" : "Inactive")
                .font(.chipLabel)
                .foregroundStyle(isActive ? Color.textPrimary : Color.textTertiary)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(Color.surfaceSecondary)
        )
    }
}

#Preview {
    HStack(spacing: 16) {
        StatusChip(isActive: true)
        StatusChip(isActive: false)
    }
    .padding()
}
