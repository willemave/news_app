//
//  ContentCard.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct ContentCard: View {
    let content: ContentSummary
    let onMarkAsRead: () async -> Void
    
    @State private var isMarking = false
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header
            VStack(alignment: .leading, spacing: 4) {
                Text(content.displayTitle)
                    .font(.headline)
                    .foregroundColor(content.isRead ? .secondary : .primary)
                    .fixedSize(horizontal: false, vertical: true)
                
                if content.isRead {
                    Text("(read)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // Metadata
            HStack(spacing: 12) {
                Text(content.formattedDate)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                if let source = content.source {
                    Text("• \(source)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // Summary
            if let summary = content.shortSummary {
                Text(summary)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(3)
                    .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(UIColor.secondarySystemBackground))
        .cornerRadius(12)
        .opacity(content.isRead ? 0.75 : 1.0)
    }
}