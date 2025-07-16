//
//  ContentDetailView.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct ContentDetailView: View {
    let contentId: Int
    @StateObject private var viewModel: ContentDetailViewModel
    @Environment(\.dismiss) private var dismiss
    
    init(contentId: Int) {
        self.contentId = contentId
        self._viewModel = StateObject(wrappedValue: ContentDetailViewModel(contentId: contentId))
    }
    
    var body: some View {
        ScrollView {
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
                    // Header Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text(content.displayTitle)
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        
                        // URL
                        if let url = URL(string: content.url) {
                            HStack {
                                Text("URL:")
                                    .fontWeight(.medium)
                                Link(content.url, destination: url)
                                    .font(.caption)
                                    .foregroundColor(.accentColor)
                                    .lineLimit(2)
                            }
                        }
                        
                        // Metadata
                        HStack(spacing: 16) {
                            if let contentType = content.contentTypeEnum {
                                ContentTypeBadge(contentType: contentType)
                            }
                            
                            Label(content.status.capitalized, systemImage: statusIcon)
                                .font(.caption)
                                .foregroundColor(statusColor)
                            
                            if let source = content.source {
                                Label(source, systemImage: "newspaper")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        // Dates
                        VStack(alignment: .leading, spacing: 4) {
                            if let pubDate = content.publicationDate {
                                Label("Published: \(formatDate(pubDate))", systemImage: "calendar")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            
                            Label("Added: \(formatDate(content.createdAt))", systemImage: "clock")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        // Action Buttons
                        HStack(spacing: 12) {
                            if let url = URL(string: content.url) {
                                Link(destination: url) {
                                    Label("View Original", systemImage: "arrow.up.right.square")
                                        .font(.subheadline)
                                }
                                .buttonStyle(.borderedProminent)
                            }
                            
                            Button(action: { viewModel.shareContent() }) {
                                Label("Share", systemImage: "square.and.arrow.up")
                                    .font(.subheadline)
                            }
                            .buttonStyle(.bordered)
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
                            
                            Text(fullMarkdown)
                                .font(.body)
                        }
                        .padding()
                        .background(Color(UIColor.secondarySystemBackground))
                        .cornerRadius(12)
                    }
                }
                .padding()
            }
        }
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
            await viewModel.loadContent()
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
        displayFormatter.timeStyle = .short
        return displayFormatter.string(from: date)
    }
}

struct ContentDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ContentDetailViewPreview()
        }
    }
}

// Preview wrapper to provide mock data
private struct ContentDetailViewPreview: View {
    @StateObject private var mockViewModel = MockContentDetailViewModel()
    
    var body: some View {
        ScrollView {
            if let content = mockViewModel.content {
                VStack(alignment: .leading, spacing: 20) {
                    // Header Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text(content.displayTitle)
                            .font(.largeTitle)
                            .fontWeight(.bold)
                        
                        // URL
                        if let url = URL(string: content.url) {
                            HStack {
                                Text("URL:")
                                    .fontWeight(.medium)
                                Link(content.url, destination: url)
                                    .font(.caption)
                                    .foregroundColor(.accentColor)
                                    .lineLimit(2)
                            }
                        }
                        
                        // Metadata
                        HStack(spacing: 16) {
                            if let contentType = content.contentTypeEnum {
                                ContentTypeBadge(contentType: contentType)
                            }
                            
                            Label(content.status.capitalized, systemImage: "checkmark.circle.fill")
                                .font(.caption)
                                .foregroundColor(.green)
                            
                            if let source = content.source {
                                Label(source, systemImage: "newspaper")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        // Dates
                        VStack(alignment: .leading, spacing: 4) {
                            if let pubDate = content.publicationDate {
                                Label("Published: \(formatDate(pubDate))", systemImage: "calendar")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            
                            Label("Added: \(formatDate(content.createdAt))", systemImage: "clock")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        
                        // Action Buttons
                        HStack(spacing: 12) {
                            if let url = URL(string: content.url) {
                                Link(destination: url) {
                                    Label("View Original", systemImage: "arrow.up.right.square")
                                        .font(.subheadline)
                                }
                                .buttonStyle(.borderedProminent)
                            }
                            
                            Button(action: { }) {
                                Label("Share", systemImage: "square.and.arrow.up")
                                    .font(.subheadline)
                            }
                            .buttonStyle(.bordered)
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
                            Text("Full Article")
                                .font(.title2)
                                .fontWeight(.semibold)
                            
                            Text(fullMarkdown)
                                .font(.body)
                        }
                        .padding()
                        .background(Color(UIColor.secondarySystemBackground))
                        .cornerRadius(12)
                    }
                }
                .padding()
            }
        }
        .navigationBarTitleDisplayMode(.inline)
    }
    
    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        
        guard let date = formatter.date(from: dateString) else { return dateString }
        
        let displayFormatter = DateFormatter()
        displayFormatter.dateStyle = .medium
        displayFormatter.timeStyle = .short
        return displayFormatter.string(from: date)
    }
}

// Mock ViewModel for previews
private class MockContentDetailViewModel: ObservableObject {
    @Published var content: ContentDetail?
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    init() {
        // Create mock content
        self.content = ContentDetail(
            id: 1,
            contentType: "article",
            url: "https://example.com/article",
            title: "Sample Article Title",
            displayTitle: "Sample Article Title",
            source: "Example News",
            status: "completed",
            errorMessage: nil,
            retryCount: 0,
            metadata: [:],
            createdAt: "2025-07-09T10:00:00.000Z",
            updatedAt: "2025-07-09T10:30:00.000Z",
            processedAt: "2025-07-09T10:30:00.000Z",
            checkedOutBy: nil,
            checkedOutAt: nil,
            publicationDate: "2025-07-09T09:00:00.000Z",
            isRead: false,
            summary: "This is a sample article summary that demonstrates the preview functionality.",
            shortSummary: "Sample article summary",
            structuredSummary: StructuredSummary(
                title: "Sample Article",
                overview: "This article discusses important topics in technology and innovation.",
                bulletPoints: [
                    BulletPoint(text: "First key takeaway from the article", category: "Main Point"),
                    BulletPoint(text: "Second important point to remember", category: "Supporting Detail"),
                    BulletPoint(text: "Third crucial insight", category: "Conclusion")
                ],
                quotes: [
                    Quote(text: "This is an important quote from the article.", context: "Said during the keynote presentation")
                ],
                topics: ["Technology", "Innovation", "Future"],
                summarizationDate: "2025-07-09T10:30:00.000Z",
                classification: "technology"
            ),
            bulletPoints: [
                BulletPoint(text: "Main argument of the article", category: "Key Point"),
                BulletPoint(text: "Secondary point with evidence", category: "Supporting")
            ],
            quotes: [
                Quote(text: "This is a standalone quote from the article.", context: "Introduction paragraph")
            ],
            topics: ["tech", "news", "innovation"],
            fullMarkdown: "# Sample Article\n\nThis is the full content of the article in markdown format.\n\n## Section 1\n\nContent goes here...\n\n## Section 2\n\nMore content..."
        )
    }
}