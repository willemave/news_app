//
//  ContentTypeBadge.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct ContentTypeBadge: View {
    let contentType: ContentType
    
    var body: some View {
        Text(contentType.displayName)
            .font(.caption)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(backgroundColor)
            .foregroundColor(foregroundColor)
            .clipShape(Capsule())
    }
    
    private var backgroundColor: Color {
        switch contentType {
        case .article:
            return Color.blue.opacity(0.1)
        case .podcast:
            return Color.purple.opacity(0.1)
        }
    }
    
    private var foregroundColor: Color {
        switch contentType {
        case .article:
            return .blue
        case .podcast:
            return .purple
        }
    }
}