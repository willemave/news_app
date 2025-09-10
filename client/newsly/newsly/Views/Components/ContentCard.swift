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
        VStack(alignment: .leading, spacing: 4) {
            // Header
            HStack(alignment: .top) {
                Text(content.displayTitle)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(content.isRead ? .secondary : .primary)
                    .fixedSize(horizontal: false, vertical: true)
                
                Spacer()
                
                HStack(spacing: 8) {
                    if content.isFavorited {
                        Image(systemName: "star.fill")
                            .font(.caption)
                            .foregroundColor(.yellow)
                    }
                    
                    if content.isRead {
                        Text("read")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.secondary.opacity(0.1))
                            .cornerRadius(4)
                    }
                }
            }
            
            // Metadata
            HStack(spacing: 8) {
                Text(content.formattedDate)
                    .font(.caption2)
                    .foregroundColor(.secondary)
                
                if let source = content.source {
                    HStack(spacing: 4) {
                        Text("•")
                            .font(.caption2)
                            .foregroundColor(.secondary)
                        
                        PlatformIcon(platform: content.platform)
                        
                        Text(source)
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            // Summary
            if let summary = content.shortSummary {
                Text(summary)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
                    .padding(.top, 2)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .opacity(content.isRead ? 0.7 : 1.0)
    }
}