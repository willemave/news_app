//
//  ContentDetailView.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI
import MarkdownUI

struct ContentDetailView: View {
    let initialContentId: Int
    let allContentIds: [Int]
    @StateObject private var viewModel = ContentDetailViewModel()
    @Environment(\.dismiss) private var dismiss
    @State private var dragAmount: CGFloat = 0
    @State private var currentIndex: Int
    
    init(contentId: Int, allContentIds: [Int] = []) {
        self.initialContentId = contentId
        self.allContentIds = allContentIds.isEmpty ? [contentId] : allContentIds
        if let index = allContentIds.firstIndex(of: contentId) {
            self._currentIndex = State(initialValue: index)
        } else {
            self._currentIndex = State(initialValue: 0)
        }
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 10) {
                if viewModel.isLoading {
                    LoadingView()
                        .frame(minHeight: 400)
                } else if let error = viewModel.errorMessage {
                    ErrorView(message: error) {
                        Task { await viewModel.loadContent() }
                    }
                    .frame(minHeight: 400)
                } else if let content = viewModel.content {
                    VStack(alignment: .leading, spacing: 20) {
                    // Compact Header Section
                    VStack(alignment: .leading, spacing: 8) {
                        Text(content.displayTitle)
                            .font(.title2)
                            .fontWeight(.bold)
                        
                        // Compact Metadata Row
                        HStack(spacing: 12) {
                            if let contentType = content.contentTypeEnum {
                                ContentTypeBadge(contentType: contentType)
                            }
                            
                            if let source = content.source {
                                Text(source)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            
                            if let pubDate = content.publicationDate {
                                Text(formatDate(pubDate))
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            
                            Spacer()
                        }
                        
                        // Compact Action Buttons Row
                        HStack(spacing: 8) {
                            if let url = URL(string: content.url) {
                                Link(destination: url) {
                                    Image(systemName: "arrow.up.right.square")
                                        .font(.system(size: 20))
                                }
                                .buttonStyle(.borderedProminent)
                            }
                            
                            Button(action: { viewModel.shareContent() }) {
                                Image(systemName: "square.and.arrow.up")
                                    .font(.system(size: 20))
                            }
                            .buttonStyle(.bordered)
                            
                            // Copy button for podcasts only
                            if content.contentTypeEnum == .podcast {
                                Button(action: { viewModel.copyPodcastContent() }) {
                                    Image(systemName: "doc.on.doc")
                                        .font(.system(size: 20))
                                }
                                .buttonStyle(.bordered)
                            }
                            
                            // Favorite button
                            Button(action: { 
                                Task { 
                                    await viewModel.toggleFavorite() 
                                }
                            }) {
                                Image(systemName: content.isFavorited ? "star.fill" : "star")
                                    .font(.system(size: 20))
                                    .foregroundColor(content.isFavorited ? .yellow : .primary)
                            }
                            .buttonStyle(.bordered)
                            
                            Spacer()
                            
                            // Navigation indicators
                            if allContentIds.count > 1 {
                                Text("\(currentIndex + 1) / \(allContentIds.count)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding()
                    .background(Color(UIColor.secondarySystemBackground))
                    .cornerRadius(12)
                    
                    // Structured Summary Section
                    if let structuredSummary = content.structuredSummary {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Summary")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            StructuredSummaryView(summary: structuredSummary)
                        }
                        .padding()
                        .background(Color(UIColor.secondarySystemBackground))
                        .cornerRadius(12)
                    }
                    
                    // Full Content Section
                    if let fullMarkdown = content.fullMarkdown {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(content.contentTypeEnum == .podcast ? "Transcript" : "Full Article")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            Markdown(fullMarkdown)
                                .markdownTheme(.gitHub)
                        }
                        .padding()
                        .background(Color(UIColor.secondarySystemBackground))
                        .cornerRadius(12)
                    }
                }
                .padding()
            }
            }
        }
        .offset(x: dragAmount)
        .animation(.spring(), value: dragAmount)
        .gesture(
            DragGesture(minimumDistance: 30)
                .onChanged { value in
                    // Only allow horizontal swipes that are more horizontal than vertical
                    if abs(value.translation.width) > abs(value.translation.height) {
                        dragAmount = value.translation.width * 0.5 // Add some resistance
                    }
                }
                .onEnded { value in
                    
                    // Check if it's a horizontal swipe
                    if abs(value.translation.width) > abs(value.translation.height) {
                        if value.translation.width > 80 && currentIndex > 0 {
                            // Swipe right - previous article
                            withAnimation(.easeInOut(duration: 0.3)) {
                                dragAmount = UIScreen.main.bounds.width
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                dragAmount = 0
                                navigateToPrevious()
                            }
                        } else if value.translation.width < -80 && currentIndex < allContentIds.count - 1 {
                            // Swipe left - next article
                            withAnimation(.easeInOut(duration: 0.3)) {
                                dragAmount = -UIScreen.main.bounds.width
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                dragAmount = 0
                                navigateToNext()
                            }
                        } else {
                            // Snap back if not enough swipe
                            withAnimation(.spring()) {
                                dragAmount = 0
                            }
                        }
                    } else {
                        // Not a horizontal swipe, snap back
                        withAnimation(.spring()) {
                            dragAmount = 0
                        }
                    }
                }
        )
        .navigationBarTitleDisplayMode(.inline)
        .navigationBarBackButtonHidden(true)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                Button(action: { dismiss() }) {
                    HStack(spacing: 4) {
                        Image(systemName: "chevron.left")
                        Text("Back")
                    }
                }
            }
        }
        .task {
            let idToLoad = allContentIds.isEmpty ? initialContentId : allContentIds[currentIndex]
            viewModel.updateContentId(idToLoad)
            await viewModel.loadContent()
        }
        .onChange(of: currentIndex) { oldValue, newValue in
            Task {
                let newContentId = allContentIds[newValue]
                viewModel.updateContentId(newContentId)
                await viewModel.loadContent()
            }
        }
    }
    
    private var statusIcon: String {
        guard let content = viewModel.content else { return "circle" }
        switch content.status {
        case "completed":
            return "checkmark.circle.fill"
        case "failed":
            return "xmark.circle.fill"
        case "processing":
            return "arrow.clockwise.circle.fill"
        default:
            return "circle"
        }
    }
    
    private var statusColor: Color {
        guard let content = viewModel.content else { return .secondary }
        switch content.status {
        case "completed":
            return .green
        case "failed":
            return .red
        case "processing":
            return .orange
        default:
            return .secondary
        }
    }
    
    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        guard let date = formatter.date(from: dateString) else { return dateString }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .none
        return displayFormatter.string(from: date)
    }
    
    private func navigateToNext() {
        guard currentIndex < allContentIds.count - 1 else {
            return
        }
        currentIndex += 1
    }
    
    private func navigateToPrevious() {
        guard currentIndex > 0 else {
            return
        }
        currentIndex -= 1
    }
}