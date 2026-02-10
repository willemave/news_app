//
//  SectionDivider.swift
//  newsly
//
//  Subtle divider between sections.
//

import SwiftUI

struct SectionDivider: View {
    var body: some View {
        Rectangle()
            .fill(Color.borderSubtle)
            .frame(height: 1 / UIScreen.main.scale) // Hairline
            .padding(.top, 8)
    }
}

struct RowDivider: View {
    var leadingInset: CGFloat = Spacing.rowDividerInset

    var body: some View {
        Divider()
            .padding(.leading, leadingInset)
    }
}

#Preview {
    VStack(spacing: 0) {
        Text("Section 1")
            .padding()
        SectionDivider()
        Text("Section 2")
            .padding()
        RowDivider()
        Text("Row 2")
            .padding()
    }
}
