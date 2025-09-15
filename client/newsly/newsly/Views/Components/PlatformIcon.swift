//
//  PlatformIcon.swift
//  newsly
//
//  Created by Assistant on 6/9/25.
//

import SwiftUI

struct PlatformIcon: View {
    let platform: String?
    
    var body: some View {
        Group {
            if let platform = platform {
                switch platform.lowercased() {
                case "hackernews":
                    Text("Y")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundColor(.orange)
                        .frame(width: 14, height: 14)
                        .background(Color.orange.opacity(0.2))
                        .clipShape(RoundedRectangle(cornerRadius: 3))
                case "reddit":
                    Image(systemName: "arrow.up.circle.fill")
                        .foregroundColor(.orange)
                case "substack":
                    Image(systemName: "doc.text.fill")
                        .foregroundColor(.orange)
                case "podcast":
                    Image(systemName: "mic.fill")
                        .foregroundColor(.purple)
                case "twitter":
                    Image(systemName: "bird.fill")
                        .foregroundColor(.blue)
                default:
                    Image(systemName: "link.circle.fill")
                        .foregroundColor(.gray)
                }
            }
        }
        .font(.caption2)
    }
}

#Preview {
    VStack(spacing: 8) {
        HStack(spacing: 16) {
            VStack { PlatformIcon(platform: "hackernews"); Text("HackerNews").font(.caption2) }
            VStack { PlatformIcon(platform: "reddit"); Text("Reddit").font(.caption2) }
            VStack { PlatformIcon(platform: "substack"); Text("Substack").font(.caption2) }
        }
        HStack(spacing: 16) {
            VStack { PlatformIcon(platform: "podcast"); Text("Podcast").font(.caption2) }
            VStack { PlatformIcon(platform: "twitter"); Text("Twitter").font(.caption2) }
            VStack { PlatformIcon(platform: "unknown"); Text("Unknown").font(.caption2) }
        }
    }
    .padding()
}
