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
    let onConvert: ((Int) async -> Void)?
    @StateObject private var viewModel = ContentDetailViewModel()
    @StateObject private var chatSessionManager = ActiveChatSessionManager.shared
    @EnvironmentObject var readingStateStore: ReadingStateStore
    @Environment(\.dismiss) private var dismiss
    @State private var dragAmount: CGFloat = 0
    @State private var currentIndex: Int
    // Navigation skipping state
    @State private var didTriggerNavigation: Bool = false
    @State private var navigationDirection: Int = 0 // +1 next, -1 previous
    // Convert button state
    @State private var isConverting: Bool = false
    // Tweet suggestions sheet state
    @State private var showTweetSheet: Bool = false
    // Chat sheet state
    @State private var showDeepDiveSheet: Bool = false
    @State private var deepDiveSession: ChatSessionSummary?
    @State private var showChatOptionsSheet: Bool = false
    @State private var isCheckingChatSession: Bool = false
    @State private var isStartingChat: Bool = false
    @State private var chatError: String?
    @State private var audioTranscript: String = ""
    @StateObject private var dictationService = VoiceDictationService.shared
    // Share sheet options
    @State private var showShareOptions: Bool = false

    init(contentId: Int, allContentIds: [Int] = [], onConvert: ((Int) async -> Void)? = nil) {
        self.initialContentId = contentId
        self.allContentIds = allContentIds.isEmpty ? [contentId] : allContentIds
        self.onConvert = onConvert
        if let index = allContentIds.firstIndex(of: contentId) {
            self._currentIndex = State(initialValue: index)
        } else {
            self._currentIndex = State(initialValue: 0)
        }
    }
    
    var body: some View {
        ScrollView {
            VStack(spacing: 0) {
                if viewModel.isLoading {
                    LoadingView()
                        .frame(minHeight: 400)
                } else if let error = viewModel.errorMessage {
                    ErrorView(message: error) {
                        Task { await viewModel.loadContent() }
                    }
                    .frame(minHeight: 400)
                } else if let content = viewModel.content {
                    VStack(alignment: .leading, spacing: 0) {
                    // Compact Header Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text(content.displayTitle)
                            .font(.title)
                            .fontWeight(.bold)

                        // Compact Metadata Row
                        HStack(spacing: 8) {
                            if let contentType = content.contentTypeEnum {
                                ContentTypeBadge(contentType: contentType)
                            }

                            if let source = content.source {
                                Text(source)
                                    .font(.callout)
                                    .foregroundColor(.secondary)
                            }

                            if content.source != nil && content.publicationDate != nil {
                                Text("•")
                                    .font(.callout)
                                    .foregroundColor(.secondary)
                            }

                            if let pubDate = content.publicationDate {
                                Text(formatDate(pubDate))
                                    .font(.callout)
                                    .foregroundColor(.secondary)
                            }

                            // Show created_at
                            Text("•")
                                .font(.callout)
                                .foregroundColor(.secondary)
                            Text(formatDateSimple(content.createdAt))
                                .font(.callout)
                                .foregroundColor(.secondary)

                            Spacer()
                        }

                        // Compact Action Buttons Row
                        HStack(spacing: 8) {
                            if let url = URL(string: content.url) {
                                Link(destination: url) {
                                    Image(systemName: "arrow.up.right.square")
                                        .font(.system(size: 18))
                                }
                                .buttonStyle(.borderedProminent)
                            }

                            Button(action: { showShareOptions = true }) {
                                Image(systemName: "square.and.arrow.up")
                                    .font(.system(size: 18))
                            }
                            .buttonStyle(.bordered)

                            // Deep Dive chat button
                            Button(action: {
                                Task { await handleChatButtonTapped(content) }
                            }) {
                                Image(systemName: "brain.head.profile")
                                    .font(.system(size: 18))
                            }
                            .buttonStyle(.bordered)
                            .disabled(isCheckingChatSession)

                            // Tweet button
                            Button(action: {
                                showTweetSheet = true
                            }) {
                                Image(systemName: "text.bubble")
                                    .font(.system(size: 18))
                            }
                            .buttonStyle(.bordered)

                            // Convert to article button for news only
                            if content.contentTypeEnum == .news, let onConvert = onConvert {
                                Button(action: {
                                    Task {
                                        isConverting = true
                                        await onConvert(content.id)
                                        isConverting = false
                                    }
                                }) {
                                    if isConverting {
                                        ProgressView()
                                            .scaleEffect(0.7)
                                    } else {
                                        Image(systemName: "arrow.right.circle")
                                            .font(.system(size: 18))
                                    }
                                }
                                .buttonStyle(.bordered)
                                .disabled(isConverting)
                            }

                            // Favorite button
                            Button(action: {
                                Task {
                                    await viewModel.toggleFavorite()
                                }
                            }) {
                                Image(systemName: content.isFavorited ? "star.fill" : "star")
                                    .font(.system(size: 18))
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
                    .padding(.horizontal, 20)
                    .padding(.vertical, 16)

                    // Chat status banner (inline, under header)
                    if let activeSession = chatSessionManager.getSession(forContentId: content.id) {
                        ChatStatusBanner(
                            session: activeSession,
                            onTap: {
                                let session = ChatSessionSummary(
                                    id: activeSession.id,
                                    contentId: activeSession.contentId,
                                    title: nil,
                                    sessionType: "article_brain",
                                    topic: nil,
                                    llmProvider: "google",
                                    llmModel: "gemini-2.0-flash",
                                    createdAt: ISO8601DateFormatter().string(from: Date()),
                                    updatedAt: nil,
                                    lastMessageAt: nil,
                                    articleTitle: activeSession.contentTitle,
                                    articleUrl: nil,
                                    hasPendingMessage: false
                                )
                                deepDiveSession = session
                                showDeepDiveSheet = true
                                chatSessionManager.stopTracking(contentId: content.id)
                            },
                            onDismiss: {
                                chatSessionManager.markAsViewed(contentId: content.id)
                            },
                            style: .inline
                        )
                    }

                    Divider()
                        .padding(.vertical, 8)

                    // Structured Summary Section
                    if let structuredSummary = content.structuredSummary {
                        StructuredSummaryView(summary: structuredSummary, contentId: content.id)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 12)
                    }

                    if content.contentTypeEnum == .news {
                        if let newsMetadata = content.newsMetadata {
                            Divider()
                                .padding(.vertical, 8)

                            NewsDigestDetailView(content: content, metadata: newsMetadata)
                                .padding(.horizontal, 20)
                        } else {
                            Divider()
                                .padding(.vertical, 8)

                            VStack(alignment: .leading, spacing: 16) {
                                Text("News Updates")
                                    .font(.title2)
                                    .fontWeight(.bold)

                                if let markdown = content.renderedMarkdown, !markdown.isEmpty {
                                    Markdown(markdown)
                                        .markdownTheme(.gitHub)
                                } else if let items = content.newsItems, !items.isEmpty {
                                    VStack(alignment: .leading, spacing: 16) {
                                        ForEach(items) { item in
                                            VStack(alignment: .leading, spacing: 8) {
                                                if let url = URL(string: item.url) {
                                                    Link(item.title ?? item.url, destination: url)
                                                        .font(.headline)
                                                } else {
                                                    Text(item.title ?? item.url)
                                                        .font(.headline)
                                                }

                                                if let summary = item.summary, !summary.isEmpty {
                                                    Text(summary)
                                                        .font(.callout)
                                                        .foregroundColor(.secondary)
                                                }
                                            }

                                            if item.id != items.last?.id {
                                                Divider()
                                                    .padding(.vertical, 4)
        }
    }

}
                                } else {
                                    Text("No news metadata available.")
                                        .font(.body)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding(.horizontal, 20)
                            .padding(.vertical, 12)
                        }
                    }

                    // Full Content Section
                    // For podcasts, check podcastMetadata.transcript first, then fall back to fullMarkdown
                    if content.contentTypeEnum == .podcast, let podcastMetadata = content.podcastMetadata, let transcript = podcastMetadata.transcript {
                        Divider()
                            .padding(.vertical, 8)

                        VStack(alignment: .leading, spacing: 12) {
                            Text("Transcript")
                                .font(.title2)
                                .fontWeight(.bold)

                            Markdown(transcript)
                                .markdownTheme(.gitHub)
                        }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 12)
                    } else if let fullMarkdown = content.fullMarkdown {
                        Divider()
                            .padding(.vertical, 8)

                        VStack(alignment: .leading, spacing: 12) {
                            Text(content.contentTypeEnum == .podcast ? "Transcript" : "Full Article")
                                .font(.title2)
                                .fontWeight(.bold)

                            Markdown(fullMarkdown)
                                .markdownTheme(.gitHub)
                        }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 12)
                    }
                }
            }
            }
        }
        .textSelection(.enabled)
        .offset(x: dragAmount)
        .animation(.spring(), value: dragAmount)
        .simultaneousGesture(
            DragGesture(minimumDistance: 80, coordinateSpace: .global)
                .onChanged { value in
                    // Only respond to fast, clearly horizontal swipes
                    let horizontalAmount = abs(value.translation.width)
                    let verticalAmount = abs(value.translation.height)

                    // Require the swipe to be significantly more horizontal than vertical
                    // Increased threshold to avoid interfering with text selection
                    if horizontalAmount > verticalAmount * 3 && horizontalAmount > 80 {
                        dragAmount = value.translation.width * 0.3
                    }
                }
                .onEnded { value in
                    let horizontalAmount = abs(value.translation.width)
                    let verticalAmount = abs(value.translation.height)

                    // Only process as navigation if it's a clear horizontal swipe
                    // Increased thresholds to better distinguish from text selection
                    if horizontalAmount > verticalAmount * 3 && horizontalAmount > 120 {
                        if value.translation.width > 120 && currentIndex > 0 {
                            // Swipe right - previous article
                            withAnimation(.easeInOut(duration: 0.3)) {
                                dragAmount = UIScreen.main.bounds.width
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                dragAmount = 0
                                navigateToPrevious()
                            }
                        } else if value.translation.width < -120 && currentIndex < allContentIds.count - 1 {
                            // Swipe left - next article
                            withAnimation(.easeInOut(duration: 0.3)) {
                                dragAmount = -UIScreen.main.bounds.width
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                dragAmount = 0
                                navigateToNext()
                            }
                        }
                    }

                    // Always snap back
                    withAnimation(.spring()) {
                        dragAmount = 0
                    }
                }
        )
        .navigationBarTitleDisplayMode(.inline)
        // Hide the main tab bar while viewing details
        .toolbar(.hidden, for: .tabBar)
        // Sticky bottom action bar
        .safeAreaInset(edge: .bottom) {
            bottomBar
        }
        .task {
            let idToLoad = allContentIds.isEmpty ? initialContentId : allContentIds[currentIndex]
            viewModel.updateContentId(idToLoad)
            await viewModel.loadContent()
        }
        .onChange(of: viewModel.content?.id) { _, newValue in
            guard let id = newValue, let type = viewModel.content?.contentTypeEnum else { return }
            readingStateStore.setCurrent(contentId: id, type: type)
        }
        // If user is navigating (chevrons or swipe), skip items that were already read
        .onChange(of: viewModel.wasAlreadyReadWhenLoaded) { _, wasRead in
            guard didTriggerNavigation, viewModel.content?.contentTypeEnum == .podcast else { return }
            if wasRead {
                let nextIndex = currentIndex + navigationDirection
                guard nextIndex >= 0 && nextIndex < allContentIds.count else {
                    // Reached the end; stop skipping further
                    didTriggerNavigation = false
                    navigationDirection = 0
                    return
                }
                currentIndex = nextIndex
                // Keep didTriggerNavigation/naviationDirection to allow cascading skips
            } else {
                // Landed on an unread item; reset navigation flags
                didTriggerNavigation = false
                navigationDirection = 0
            }
        }
        .onChange(of: currentIndex) { oldValue, newValue in
            Task {
                let newContentId = allContentIds[newValue]
                viewModel.updateContentId(newContentId)
                await viewModel.loadContent()
            }
        }
        .onDisappear {
            readingStateStore.clear()
        }
        .confirmationDialog("Share article", isPresented: $showShareOptions, titleVisibility: .visible) {
            Button("Light · Title + link") {
                viewModel.shareContent(option: .light)
            }
            Button("Medium · Key points, quotes, link") {
                viewModel.shareContent(option: .medium)
            }
            Button("Full · Article + transcript") {
                viewModel.shareContent(option: .full)
            }
            Button("Cancel", role: .cancel) { }
        }
        .sheet(isPresented: $showTweetSheet) {
            if let content = viewModel.content {
                TweetSuggestionsSheet(contentId: content.id)
            }
        }
        .sheet(isPresented: $showChatOptionsSheet, onDismiss: {
            dictationService.cancelRecording()
            audioTranscript = ""
            chatError = nil
        }) {
            if let content = viewModel.content {
                VStack(spacing: 0) {
                    // Header
                    HStack {
                        Button("Cancel") {
                            showChatOptionsSheet = false
                        }
                        Spacer()
                        Text("Start a Chat")
                            .font(.headline)
                        Spacer()
                        Text("Cancel").opacity(0)
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 20)
                    .padding(.bottom, 16)

                    VStack(alignment: .leading, spacing: 12) {
                        if let chatError {
                            Text(chatError)
                                .font(.footnote)
                                .foregroundColor(.red)
                        }

                        chatPromptCard(
                            title: "Dig deeper",
                            detail: nil,
                            prompt: deepDivePrompt(for: content),
                            contentId: content.id
                        )

                        chatPromptCard(
                            title: "Corroborate",
                            detail: nil,
                            prompt: corroboratePrompt(for: content),
                            contentId: content.id
                        )

                        audioPromptCard(for: content)

                        if isStartingChat {
                            HStack {
                                ProgressView()
                                    .scaleEffect(0.9)
                                Text("Starting...")
                                    .font(.footnote)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.top, 4)
                        }
                    }
                    .padding(.horizontal, 20)

                    Spacer()
                }
                .presentationDetents([.height(340)])
                .presentationDragIndicator(.hidden)
                .presentationCornerRadius(20)
            }
        }
        .sheet(isPresented: $showDeepDiveSheet) {
            if let session = deepDiveSession {
                NavigationStack {
                    ChatSessionView(session: session)
                }
            }
        }
    }

    // MARK: - Chat Helpers
    @MainActor
    private func handleChatButtonTapped(_ content: ContentDetail) async {
        guard !isCheckingChatSession else { return }
        isCheckingChatSession = true
        defer { isCheckingChatSession = false }

        do {
            if let existing = try await ChatService.shared.getSessionForContent(contentId: content.id) {
                deepDiveSession = existing
                showDeepDiveSheet = true
                showChatOptionsSheet = false
                return
            }
            showChatOptionsSheet = true
        } catch {
            chatError = error.localizedDescription
            showChatOptionsSheet = true
        }
    }

    private func startChatWithPrompt(_ prompt: String, contentId: Int) async {
        guard !isStartingChat else { return }
        guard let content = viewModel.content else { return }

        isStartingChat = true
        chatError = nil

        do {
            let session = try await ChatService.shared.startArticleChat(contentId: contentId)
            // Send message async (don't wait for completion)
            let response = try await ChatService.shared.sendMessageAsync(sessionId: session.id, message: prompt)

            // Register with manager for background polling - don't show sheet
            chatSessionManager.startTracking(
                session: session,
                contentId: contentId,
                contentTitle: content.displayTitle,
                messageId: response.messageId
            )

            deepDiveSession = session
            showChatOptionsSheet = false
            // Don't show sheet immediately - show banner instead
        } catch {
            chatError = error.localizedDescription
        }

        isStartingChat = false
    }

    private func deepDivePrompt(for content: ContentDetail) -> String {
        "Dig deeper into the key points of \(content.displayTitle). For each main point, explain reasoning, supporting evidence, and practical implications. Keep answers concise and numbered."
    }

    private func corroboratePrompt(for content: ContentDetail) -> String {
        "Corroborate the main claims in \(content.displayTitle) using recent, reputable sources. For each claim, list 2-3 supporting or conflicting sources with URLs, note disagreements, and flag gaps or weak evidence."
    }

    private func audioPrompt(_ transcript: String, content: ContentDetail) -> String {
        "User voice question about \(content.displayTitle): \(transcript)\nUse the article context first; if the answer is not in the source, say so and suggest where to look next."
    }

    @ViewBuilder
    private func chatPromptCard(title: String, detail: String?, prompt: String, contentId: Int) -> some View {
        Button {
            Task { await startChatWithPrompt(prompt, contentId: contentId) }
        } label: {
            HStack {
                Text(title)
                    .font(.body)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(10)
        }
        .buttonStyle(.plain)
        .disabled(isStartingChat)
    }

    @ViewBuilder
    private func audioPromptCard(for content: ContentDetail) -> some View {
        Button {
            Task { await toggleRecording() }
        } label: {
            HStack {
                Text("Ask with voice")
                    .font(.body)
                Spacer()
                Image(systemName: dictationService.isRecording ? "stop.circle.fill" : "mic")
                    .foregroundColor(dictationService.isRecording ? .red : .secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(Color(.secondarySystemBackground))
            .cornerRadius(10)
        }
        .buttonStyle(.plain)
        .disabled(isStartingChat)

        if dictationService.isTranscribing {
            HStack(spacing: 8) {
                ProgressView()
                    .scaleEffect(0.8)
                Text("Transcribing...")
                    .font(.caption)
            }
        } else if !audioTranscript.isEmpty {
            VStack(spacing: 8) {
                Text(audioTranscript)
                    .font(.caption)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(8)

                Button {
                    Task { await startChatWithPrompt(audioPrompt(audioTranscript, content: content), contentId: content.id) }
                } label: {
                    Text("Send")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(isStartingChat)
            }
        }
    }

    private func toggleRecording() async {
        do {
            if dictationService.isRecording {
                let transcript = try await dictationService.stopRecordingAndTranscribe()
                audioTranscript = transcript
            } else {
                try await dictationService.startRecording()
            }
        } catch {
            chatError = error.localizedDescription
        }
    }

    // MARK: - Bottom Bar
    private var bottomBar: some View {
        let canGoPrev = currentIndex > 0
        let canGoNext = currentIndex < allContentIds.count - 1

        return HStack(spacing: 12) {
            // Previous (icon only)
            Button {
                withAnimation(.easeInOut) { navigateToPrevious() }
            } label: {
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.blue)
            .disabled(!canGoPrev)
            .accessibilityLabel("Previous Article")

            // Favorite (icon only)
            Button {
                Task { await viewModel.toggleFavorite() }
            } label: {
                Image(systemName: (viewModel.content?.isFavorited ?? false) ? "star.fill" : "star")
                    .font(.system(size: 18, weight: .semibold))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .tint((viewModel.content?.isFavorited ?? false) ? .yellow : .gray)
            .accessibilityLabel("Favorite")

            // Next (icon only)
            Button {
                withAnimation(.easeInOut) { navigateToNext() }
            } label: {
                Image(systemName: "chevron.right")
                    .font(.system(size: 18, weight: .semibold))
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.blue)
            .disabled(!canGoNext)
            .accessibilityLabel("Next Article")
        }
        .padding(.horizontal)
        .padding(.top, 8)
        .padding(.bottom, 8)
        .background(.ultraThinMaterial)
        .overlay(
            Divider()
                .background(Color.secondary.opacity(0.4)), alignment: .top
        )
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
    
    private func formatDateSimple(_ dateString: String) -> String {
        let inputFormatter = DateFormatter()
        inputFormatter.locale = Locale(identifier: "en_US_POSIX")
        inputFormatter.timeZone = TimeZone(secondsFromGMT: 0)

        // Try with microseconds first
        inputFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"
        var date = inputFormatter.date(from: dateString)

        // Try with milliseconds
        if date == nil {
            inputFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS"
            date = inputFormatter.date(from: dateString)
        }

        // Try without fractional seconds
        if date == nil {
            inputFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
            date = inputFormatter.date(from: dateString)
        }

        // Try ISO8601 with Z
        if date == nil {
            let isoFormatter = ISO8601DateFormatter()
            isoFormatter.formatOptions = [.withInternetDateTime]
            date = isoFormatter.date(from: dateString)
        }

        guard let validDate = date else { return dateString }

        let displayFormatter = DateFormatter()
        displayFormatter.dateFormat = "MM-dd-yyyy"
        return displayFormatter.string(from: validDate)
    }

    private func formatDate(_ dateString: String) -> String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        var date = formatter.date(from: dateString)

        // Try without fractional seconds if first attempt fails
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: dateString)
        }

        guard let validDate = date else { return dateString }

        let now = Date()
        let timeInterval = now.timeIntervalSince(validDate)

        // Use relative formatting for dates within the last 7 days
        if timeInterval < 7 * 24 * 60 * 60 && timeInterval >= 0 {
            let relativeFormatter = RelativeDateTimeFormatter()
            relativeFormatter.unitsStyle = .short
            return relativeFormatter.localizedString(for: validDate, relativeTo: now)
        }

        // Use compact format for older dates
        let displayFormatter = DateFormatter()
        displayFormatter.dateFormat = "MMM d"

        // Add year if not current year
        let calendar = Calendar.current
        if !calendar.isDate(validDate, equalTo: now, toGranularity: .year) {
            displayFormatter.dateFormat = "MMM d, yyyy"
        }

        return displayFormatter.string(from: validDate)
    }
    
    private func navigateToNext() {
        guard currentIndex < allContentIds.count - 1 else {
            return
        }
        didTriggerNavigation = true
        navigationDirection = 1
        currentIndex += 1
    }
    
    private func navigateToPrevious() {
        guard currentIndex > 0 else {
            return
        }
        didTriggerNavigation = true
        navigationDirection = -1
        currentIndex -= 1
    }
}
