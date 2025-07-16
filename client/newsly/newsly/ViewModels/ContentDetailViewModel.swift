//
//  ContentDetailViewModel.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import Foundation
import SwiftUI

@MainActor
class ContentDetailViewModel: ObservableObject {
    @Published var content: ContentDetail?
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    private let contentService = ContentService.shared
    private let contentId: Int
    
    init(contentId: Int) {
        self.contentId = contentId
    }
    
    func loadContent() async {
        isLoading = true
        errorMessage = nil
        
        do {
            content = try await contentService.fetchContentDetail(id: contentId)
            
            // Auto-mark as read if not already read
            if let content = content, !content.isRead {
                try await contentService.markContentAsRead(id: contentId)
            }
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
    
    func shareContent() {
        guard let content = content, let url = URL(string: content.url) else { return }
        
        let activityVC = UIActivityViewController(
            activityItems: [url, content.displayTitle],
            applicationActivities: nil
        )
        
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let rootViewController = windowScene.windows.first?.rootViewController {
            rootViewController.present(activityVC, animated: true)
        }
    }
}