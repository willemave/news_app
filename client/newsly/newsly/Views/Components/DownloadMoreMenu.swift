//
//  DownloadMoreMenu.swift
//  newsly
//

import SwiftUI

struct DownloadMoreMenu: View {
    let title: String
    let counts: [Int]
    let onSelect: (Int) -> Void

    init(
        title: String = "Download more",
        counts: [Int] = [3, 5, 10, 20],
        onSelect: @escaping (Int) -> Void
    ) {
        self.title = title
        self.counts = counts
        self.onSelect = onSelect
    }

    var body: some View {
        Menu {
            ForEach(counts, id: \.self) { count in
                Button("Download \(count) more") {
                    onSelect(count)
                }
            }
        } label: {
            Label(title, systemImage: "arrow.down.circle")
                .font(.subheadline)
                .fontWeight(.medium)
        }
        .buttonStyle(.plain)
    }
}
