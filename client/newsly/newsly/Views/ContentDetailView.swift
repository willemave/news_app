//
//  ContentDetailView.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI
import MarkdownUI
import UIKit

// MARK: - Design Tokens
private enum DetailDesign {
    // Spacing
    static let horizontalPadding: CGFloat = 20
    static let sectionSpacing: CGFloat = 20
    static let cardPadding: CGFloat = 16

    // Corner radii
    static let cardRadius: CGFloat = 14
    static let buttonRadius: CGFloat = 10

    // Hero
    static let heroHeight: CGFloat = 220
}

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
    // Full image viewer
    @State private var showFullImage: Bool = false
    @State private var fullImageURL: URL?
    @State private var fullThumbnailURL: URL?
    // Swipe haptic feedback
    @State private var didTriggerSwipeHaptic: Bool = false
    // Transcript/Full Article collapsed state
    @State private var isTranscriptExpanded: Bool = false
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
                        // Modern hero header
                        heroHeader(content: content)

                        // Floating action bar
                        actionBar(content: content)
                            .padding(.horizontal, DetailDesign.horizontalPadding)
                            .padding(.top, 16)

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
                                        articleSummary: nil,
                                        articleSource: nil,
                                        hasPendingMessage: false,
                                        isFavorite: false,
                                        hasMessages: true
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
                            .padding(.horizontal, DetailDesign.horizontalPadding)
                            .padding(.top, 12)
                        }

                        // Detected feed subscription card (only for self-submitted content)
                        if let feed = content.detectedFeed, content.source == "self submission" {
                            DetectedFeedCard(
                                feed: feed,
                                isSubscribing: viewModel.isSubscribingToFeed,
                                hasSubscribed: viewModel.feedSubscriptionSuccess,
                                subscriptionError: viewModel.feedSubscriptionError,
                                onSubscribe: {
                                    Task { await viewModel.subscribeToDetectedFeed() }
                                }
                            )
                            .padding(.horizontal, DetailDesign.horizontalPadding)
                            .padding(.top, 12)
                        }

                        // Summary Section (interleaved or structured)
                        if let interleavedSummary = content.interleavedSummary {
                            InterleavedSummaryView(summary: interleavedSummary, contentId: content.id)
                                .padding(.horizontal, DetailDesign.horizontalPadding)
                                .padding(.top, DetailDesign.sectionSpacing)
                        } else if let structuredSummary = content.structuredSummary {
                            StructuredSummaryView(summary: structuredSummary, contentId: content.id)
                                .padding(.horizontal, DetailDesign.horizontalPadding)
                                .padding(.top, DetailDesign.sectionSpacing)
                        }

                        if content.contentTypeEnum == .news {
                            if let newsMetadata = content.newsMetadata {
                                modernSectionPlain(isPadded: false) {
                                    NewsDigestDetailView(content: content, metadata: newsMetadata)
                                }
                                .padding(.horizontal, DetailDesign.horizontalPadding)
                                .padding(.top, DetailDesign.sectionSpacing)
                            } else {
                                modernSectionPlain(isPadded: false) {
                                    VStack(alignment: .leading, spacing: 16) {
                                        sectionHeader("News Updates", icon: "newspaper")

                                        if let markdown = content.renderedMarkdown, !markdown.isEmpty {
                                            Markdown(markdown)
                                                .markdownTheme(.gitHub)
                                        } else if let items = content.newsItems, !items.isEmpty {
                                            VStack(alignment: .leading, spacing: 16) {
                                                ForEach(items) { item in
                                                    VStack(alignment: .leading, spacing: 8) {
                                                        if let url = URL(string: item.url) {
                                                            Link(item.title ?? item.url, destination: url)
                                                                .font(.subheadline)
                                                                .fontWeight(.medium)
                                                        } else {
                                                            Text(item.title ?? item.url)
                                                                .font(.subheadline)
                                                                .fontWeight(.medium)
                                                        }

                                                        if let summary = item.summary, !summary.isEmpty {
                                                            Text(summary)
                                                                .font(.footnote)
                                                                .foregroundColor(.secondary)
                                                        }
                                                    }

                                                    if item.id != items.last?.id {
                                                        Divider()
                                                            .opacity(0.5)
                                                    }
                                                }
                                            }
                                        } else {
                                            Text("No news metadata available.")
                                                .font(.subheadline)
                                                .foregroundColor(.secondary)
                                        }
                                    }
                                }
                                .padding(.horizontal, DetailDesign.horizontalPadding)
                                .padding(.top, DetailDesign.sectionSpacing)
                            }
                        }

                        // Full Content Section (collapsible, modern style)
                        if content.contentTypeEnum == .podcast, let podcastMetadata = content.podcastMetadata, let transcript = podcastMetadata.transcript {
                            modernExpandableSection(
                                title: "Transcript",
                                icon: "text.alignleft",
                                isExpanded: $isTranscriptExpanded
                            ) {
                                Markdown(transcript)
                                    .markdownTheme(.gitHub)
                            }
                            .padding(.horizontal, DetailDesign.horizontalPadding)
                            .padding(.top, DetailDesign.sectionSpacing)
                        } else if let fullMarkdown = content.fullMarkdown {
                            modernExpandableSection(
                                title: content.contentTypeEnum == .podcast ? "Transcript" : "Full Article",
                                icon: "doc.text",
                                isExpanded: $isTranscriptExpanded
                            ) {
                                Markdown(fullMarkdown)
                                    .markdownTheme(.gitHub)
                            }
                            .padding(.horizontal, DetailDesign.horizontalPadding)
                            .padding(.top, DetailDesign.sectionSpacing)
                        }

                        // Bottom spacing
                        Spacer()
                            .frame(height: 40)
                    }
                }
            }
        }
        .textSelection(.enabled)
        .overlay(alignment: .leading) {
            // Left edge indicator (previous)
            if dragAmount > 30 && currentIndex > 0 {
                swipeIndicator(direction: .previous, progress: min(1.0, dragAmount / 100))
            }
        }
        .overlay(alignment: .trailing) {
            // Right edge indicator (next)
            if dragAmount < -30 && currentIndex < allContentIds.count - 1 {
                swipeIndicator(direction: .next, progress: min(1.0, abs(dragAmount) / 100))
            }
        }
        .offset(x: dragAmount)
        .animation(.interactiveSpring(response: 0.3, dampingFraction: 0.8), value: dragAmount)
        .simultaneousGesture(
            DragGesture(minimumDistance: 50, coordinateSpace: .global)
                .onChanged { value in
                    let horizontalAmount = abs(value.translation.width)
                    let verticalAmount = abs(value.translation.height)

                    // Require horizontal swipe
                    if horizontalAmount > verticalAmount * 2 && horizontalAmount > 30 {
                        // More responsive drag with resistance at edges
                        let canGoLeft = currentIndex < allContentIds.count - 1
                        let canGoRight = currentIndex > 0

                        var newOffset = value.translation.width * 0.6

                        // Add resistance if can't navigate in that direction
                        if newOffset < 0 && !canGoLeft {
                            newOffset = newOffset * 0.2
                        } else if newOffset > 0 && !canGoRight {
                            newOffset = newOffset * 0.2
                        }

                        dragAmount = newOffset

                        // Haptic feedback when crossing threshold
                        if abs(newOffset) > 80 && !didTriggerSwipeHaptic {
                            let generator = UIImpactFeedbackGenerator(style: .light)
                            generator.impactOccurred()
                            didTriggerSwipeHaptic = true
                        }
                    }
                }
                .onEnded { value in
                    didTriggerSwipeHaptic = false
                    let horizontalAmount = abs(value.translation.width)
                    let verticalAmount = abs(value.translation.height)

                    if horizontalAmount > verticalAmount * 2 && horizontalAmount > 80 {
                        if value.translation.width > 80 && currentIndex > 0 {
                            // Swipe right - previous
                            let generator = UIImpactFeedbackGenerator(style: .medium)
                            generator.impactOccurred()
                            withAnimation(.easeOut(duration: 0.2)) {
                                dragAmount = UIScreen.main.bounds.width
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                                // Reset without animation, then navigate
                                var transaction = Transaction()
                                transaction.disablesAnimations = true
                                withTransaction(transaction) {
                                    dragAmount = 0
                                }
                                navigateToPrevious()
                            }
                            return
                        } else if value.translation.width < -80 && currentIndex < allContentIds.count - 1 {
                            // Swipe left - next
                            let generator = UIImpactFeedbackGenerator(style: .medium)
                            generator.impactOccurred()
                            withAnimation(.easeOut(duration: 0.2)) {
                                dragAmount = -UIScreen.main.bounds.width
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                                // Reset without animation, then navigate
                                var transaction = Transaction()
                                transaction.disablesAnimations = true
                                withTransaction(transaction) {
                                    dragAmount = 0
                                }
                                navigateToNext()
                            }
                            return
                        }
                    }

                    // Snap back
                    withAnimation(.interactiveSpring(response: 0.3, dampingFraction: 0.8)) {
                        dragAmount = 0
                    }
                }
        )
        .navigationBarTitleDisplayMode(.inline)
        // Hide the main tab bar while viewing details
        .toolbar(.hidden, for: .tabBar)
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
                    // Modern drag indicator
                    RoundedRectangle(cornerRadius: 2.5)
                        .fill(Color.secondary.opacity(0.3))
                        .frame(width: 36, height: 5)
                        .padding(.top, 8)

                    // Modern header
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("AI Chat")
                                .font(.title3)
                                .fontWeight(.bold)
                            Text("Choose how to explore this article")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }

                        Spacer()

                        Button {
                            showChatOptionsSheet = false
                        } label: {
                            Image(systemName: "xmark")
                                .font(.subheadline)
                                .fontWeight(.semibold)
                                .foregroundColor(.secondary)
                                .frame(width: 30, height: 30)
                                .background(Color(.tertiarySystemBackground))
                                .clipShape(Circle())
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 16)
                    .padding(.bottom, 20)

                    VStack(alignment: .leading, spacing: 10) {
                        if let chatError {
                            HStack(spacing: 8) {
                                Image(systemName: "exclamationmark.circle.fill")
                                    .foregroundColor(.red)
                                Text(chatError)
                                    .font(.footnote)
                                    .foregroundColor(.red)
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.red.opacity(0.1))
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                        }

                        chatPromptCard(
                            title: "Dig deeper",
                            icon: "doc.text.magnifyingglass",
                            iconColor: .blue,
                            prompt: deepDivePrompt(for: content),
                            contentId: content.id
                        )

                        chatPromptCard(
                            title: "Corroborate",
                            icon: "checkmark.shield",
                            iconColor: .green,
                            prompt: corroboratePrompt(for: content),
                            contentId: content.id
                        )

                        deepResearchCard(for: content)

                        audioPromptCard(for: content)

                        if isStartingChat {
                            HStack(spacing: 10) {
                                ProgressView()
                                    .scaleEffect(0.8)
                                Text("Starting conversation...")
                                    .font(.footnote)
                                    .foregroundColor(.secondary)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                        }
                    }
                    .padding(.horizontal, 20)

                    Spacer()
                }
                .background(Color(.systemBackground))
                .presentationDetents([.height(480)])
                .presentationDragIndicator(.hidden)
                .presentationCornerRadius(24)
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
        chatError = nil
        showChatOptionsSheet = true
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

    private func deepResearchPrompt(for content: ContentDetail) -> String {
        "Conduct comprehensive research on \(content.displayTitle). Find additional sources, verify claims, identify related developments, and provide a thorough analysis with citations."
    }

    private func startDeepResearchWithPrompt(_ prompt: String, contentId: Int) async {
        guard !isStartingChat else { return }
        guard let content = viewModel.content else { return }

        isStartingChat = true
        chatError = nil

        do {
            let session = try await ChatService.shared.startDeepResearch(contentId: contentId)
            let response = try await ChatService.shared.sendMessageAsync(
                sessionId: session.id,
                message: prompt
            )

            chatSessionManager.startTracking(
                session: session,
                contentId: contentId,
                contentTitle: content.displayTitle,
                messageId: response.messageId
            )

            deepDiveSession = session
            showChatOptionsSheet = false
        } catch {
            chatError = error.localizedDescription
        }

        isStartingChat = false
    }

    @ViewBuilder
    private func deepResearchCard(for content: ContentDetail) -> some View {
        Button {
            Task {
                await startDeepResearchWithPrompt(
                    deepResearchPrompt(for: content),
                    contentId: content.id
                )
            }
        } label: {
            modernChatOptionCard(
                icon: "magnifyingglass.circle.fill",
                iconColor: .purple,
                title: "Deep Research",
                subtitle: "Comprehensive analysis with sources",
                badge: "~2-5 min"
            )
        }
        .buttonStyle(.plain)
        .disabled(isStartingChat)
    }

    @ViewBuilder
    private func chatPromptCard(
        title: String,
        icon: String,
        iconColor: Color,
        prompt: String,
        contentId: Int
    ) -> some View {
        Button {
            Task { await startChatWithPrompt(prompt, contentId: contentId) }
        } label: {
            modernChatOptionCard(
                icon: icon,
                iconColor: iconColor,
                title: title,
                subtitle: chatSubtitle(for: title)
            )
        }
        .buttonStyle(.plain)
        .disabled(isStartingChat)
    }

    private func chatSubtitle(for title: String) -> String {
        switch title {
        case "Dig deeper":
            return "Explore key points in detail"
        case "Corroborate":
            return "Verify claims with sources"
        default:
            return "Start a conversation"
        }
    }

    @ViewBuilder
    private func modernChatOptionCard(
        icon: String,
        iconColor: Color,
        title: String,
        subtitle: String,
        badge: String? = nil
    ) -> some View {
        HStack(spacing: 12) {
            // Icon container
            Image(systemName: icon)
                .font(.system(size: 16, weight: .medium))
                .foregroundColor(iconColor)
                .frame(width: 32, height: 32)
                .background(iconColor.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 8))

            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.primary)
                Text(subtitle)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Spacer()

            if let badge = badge {
                Text(badge)
                    .font(.caption2)
                    .fontWeight(.medium)
                    .foregroundColor(.secondary)
            }

            Image(systemName: "chevron.right")
                .font(.caption2)
                .fontWeight(.bold)
                .foregroundColor(.secondary.opacity(0.4))
        }
        .padding(12)
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    @ViewBuilder
    private func audioPromptCard(for content: ContentDetail) -> some View {
        Button {
            Task { await toggleRecording() }
        } label: {
            HStack(spacing: 12) {
                Image(systemName: dictationService.isRecording ? "stop.circle.fill" : "mic.fill")
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(dictationService.isRecording ? .red : .orange)
                    .frame(width: 32, height: 32)
                    .background((dictationService.isRecording ? Color.red : Color.orange).opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 8))

                VStack(alignment: .leading, spacing: 1) {
                    Text(dictationService.isRecording ? "Stop Recording" : "Ask with Voice")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundColor(.primary)
                    Text(dictationService.isRecording ? "Tap to finish" : "Record your question")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption2)
                    .fontWeight(.bold)
                    .foregroundColor(.secondary.opacity(0.4))
            }
            .padding(12)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
        }
        .buttonStyle(.plain)
        .disabled(isStartingChat)

        if dictationService.isTranscribing {
            HStack(spacing: 10) {
                ProgressView()
                    .scaleEffect(0.8)
                Text("Transcribing...")
                    .font(.footnote)
                    .foregroundColor(.secondary)
            }
            .padding(.vertical, 8)
        } else if !audioTranscript.isEmpty {
            VStack(spacing: 10) {
                Text(audioTranscript)
                    .font(.footnote)
                    .foregroundColor(.primary.opacity(0.9))
                    .padding(12)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 10))

                Button {
                    Task { await startChatWithPrompt(audioPrompt(audioTranscript, content: content), contentId: content.id) }
                } label: {
                    Text("Send Question")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Color.accentColor)
                        .foregroundColor(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                }
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

    // MARK: - Modern Hero Header
    @ViewBuilder
    private func heroHeader(content: ContentDetail) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // Hero image (optional, tappable) - extends to top of screen
            if content.contentTypeEnum != .news,
               let imageUrlString = content.imageUrl,
               let imageUrl = buildImageURL(from: imageUrlString) {
                Button {
                    fullImageURL = imageUrl
                    fullThumbnailURL = content.thumbnailUrl.flatMap { buildImageURL(from: $0) }
                    showFullImage = true
                } label: {
                    let thumbnailUrl = content.thumbnailUrl.flatMap { buildImageURL(from: $0) }
                    GeometryReader { geo in
                        CachedAsyncImage(
                            url: imageUrl,
                            thumbnailUrl: thumbnailUrl
                        ) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(width: geo.size.width, height: geo.size.height + geo.safeAreaInsets.top)
                                .offset(y: -geo.safeAreaInsets.top)
                                .clipped()
                        } placeholder: {
                            Rectangle()
                                .fill(Color(.systemGray5))
                                .frame(width: geo.size.width, height: geo.size.height + geo.safeAreaInsets.top)
                                .offset(y: -geo.safeAreaInsets.top)
                                .overlay(ProgressView())
                        }
                    }
                    .frame(height: 220)
                }
                .buttonStyle(.plain)
            }

            // Title and metadata section
            VStack(alignment: .leading, spacing: 8) {
                // Title
                Text(content.displayTitle)
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundColor(.primary)
                    .fixedSize(horizontal: false, vertical: true)

                // Metadata row
                HStack(spacing: 6) {
                    HStack(spacing: 4) {
                        Image(systemName: contentTypeIcon(for: content))
                            .font(.caption2)
                        Text(content.contentTypeEnum?.rawValue.capitalized ?? "Article")
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .foregroundColor(.accentColor)

                    if let source = content.source {
                        Text("·")
                            .foregroundColor(.secondary.opacity(0.4))
                        Text(source)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    Text("·")
                        .foregroundColor(.secondary.opacity(0.4))

                    Text(formatDateSimple(content.createdAt))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, DetailDesign.horizontalPadding)
            .padding(.top, 16)
            .padding(.bottom, 16)
        }
        .fullScreenCover(isPresented: $showFullImage) {
            if let url = fullImageURL {
                FullImageView(imageURL: url, thumbnailURL: fullThumbnailURL, isPresented: $showFullImage)
            }
        }
    }

    @ViewBuilder
    private func heroPlaceholder(content: ContentDetail) -> some View {
        Rectangle()
            .fill(
                LinearGradient(
                    colors: [
                        Color(.systemGray4),
                        Color(.systemGray5)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .frame(height: DetailDesign.heroHeight)
            .overlay(
                Image(systemName: contentTypeIcon(for: content))
                    .font(.system(size: 56, weight: .ultraLight))
                    .foregroundColor(.white.opacity(0.3))
            )
    }

    private func contentTypeIcon(for content: ContentDetail) -> String {
        switch content.contentTypeEnum {
        case .article: return "doc.text"
        case .podcast: return "headphones"
        case .news: return "newspaper"
        case .none: return "doc.text"
        }
    }

    // MARK: - Modern Action Bar (Icon-only, compact)
    @ViewBuilder
    private func actionBar(content: ContentDetail) -> some View {
        HStack(spacing: 6) {
            // Primary action - Open in browser
            if let url = URL(string: content.url) {
                Link(destination: url) {
                    iconButton(icon: "safari", isPrimary: true)
                }
            }

            // Share
            Button(action: { showShareOptions = true }) {
                iconButton(icon: "square.and.arrow.up")
            }

            // Tweet
            Button(action: { showTweetSheet = true }) {
                iconButton(icon: "text.bubble")
            }

            // Convert (news only)
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
                            .frame(width: 36, height: 36)
                            .background(Color(.tertiarySystemFill))
                            .clipShape(Circle())
                    } else {
                        iconButton(icon: "arrow.right.circle")
                    }
                }
                .disabled(isConverting)
            }

            // Favorite + Deep Dive (combined action)
            // Tapping favorites the article and shows chat options
            Button(action: {
                Task {
                    // First, favorite if not already
                    if !content.isFavorited {
                        await viewModel.toggleFavorite()
                    }
                    // Then show chat options
                    await handleChatButtonTapped(content)
                }
            }) {
                iconButton(
                    icon: "brain.head.profile",
                    tint: content.isFavorited ? .yellow : nil
                )
            }
            .disabled(isCheckingChatSession)

            Spacer()

            // Navigation - Next
            if currentIndex < allContentIds.count - 1 {
                Button(action: {
                    withAnimation(.easeInOut) { navigateToNext() }
                }) {
                    HStack(spacing: 4) {
                        Text("Next")
                            .font(.footnote)
                            .fontWeight(.semibold)
                        Image(systemName: "chevron.right")
                            .font(.caption2)
                            .fontWeight(.bold)
                    }
                    .foregroundColor(.primary)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(Color(.tertiarySystemFill))
                    .clipShape(Capsule())
                }
            }
        }
    }

    @ViewBuilder
    private func iconButton(icon: String, isPrimary: Bool = false, tint: Color? = nil) -> some View {
        Image(systemName: icon)
            .font(.system(size: 16, weight: .medium))
            .foregroundColor(tint ?? (isPrimary ? .white : .primary))
            .frame(width: 36, height: 36)
            .background(isPrimary ? Color.accentColor : Color(.tertiarySystemFill))
            .clipShape(Circle())
    }

    // MARK: - Modern Section Components (Flat, no borders)
    @ViewBuilder
    private func modernSectionCard<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        content()
            .padding(DetailDesign.cardPadding)
            .background(
                RoundedRectangle(cornerRadius: DetailDesign.cardRadius)
                    .fill(Color(.systemBackground))
            )
            .overlay(
                RoundedRectangle(cornerRadius: DetailDesign.cardRadius)
                    .stroke(Color(.separator).opacity(0.6), lineWidth: 1)
            )
    }

    @ViewBuilder
    private func modernSectionPlain<Content: View>(isPadded: Bool = true, @ViewBuilder content: () -> Content) -> some View {
        content()
            .padding(isPadded ? DetailDesign.cardPadding : 0)
    }

    @ViewBuilder
    private func modernExpandableSection<Content: View>(
        title: String,
        icon: String,
        isExpanded: Binding<Bool>,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                withAnimation(.easeInOut(duration: 0.25)) {
                    isExpanded.wrappedValue.toggle()
                }
            } label: {
                HStack {
                    HStack(spacing: 8) {
                        Image(systemName: icon)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        Text(title)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .foregroundColor(.primary)
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption2)
                        .fontWeight(.bold)
                        .foregroundColor(.secondary.opacity(0.6))
                        .rotationEffect(.degrees(isExpanded.wrappedValue ? 90 : 0))
                }
                .padding(DetailDesign.cardPadding)
            }
            .buttonStyle(.plain)

            if isExpanded.wrappedValue {
                content()
                    .padding(.horizontal, DetailDesign.cardPadding)
                    .padding(.bottom, DetailDesign.cardPadding)
            }
        }
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: DetailDesign.cardRadius))
    }

    @ViewBuilder
    private func sectionHeader(_ title: String, icon: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.subheadline)
                .foregroundColor(.secondary)
            Text(title)
                .font(.subheadline)
                .fontWeight(.semibold)
        }
    }

    private func buildImageURL(from urlString: String) -> URL? {
        // If it's already a full URL, use it
        if urlString.hasPrefix("http://") || urlString.hasPrefix("https://") {
            return URL(string: urlString)
        }
        // Otherwise, it's a relative path - prepend base URL
        // Use string concatenation instead of appendingPathComponent to preserve path structure
        let baseURL = AppSettings.shared.baseURL
        let fullURL = urlString.hasPrefix("/") ? baseURL + urlString : baseURL + "/" + urlString
        return URL(string: fullURL)
    }

    // MARK: - Swipe Indicator
    private enum SwipeDirection {
        case previous, next
    }

    @ViewBuilder
    private func swipeIndicator(direction: SwipeDirection, progress: CGFloat) -> some View {
        let iconName = direction == .previous ? "chevron.left" : "chevron.right"

        VStack {
            Spacer()
            HStack {
                if direction == .next { Spacer() }
                Image(systemName: iconName)
                    .font(.system(size: 24, weight: .semibold))
                    .foregroundColor(.white)
                    .frame(width: 44, height: 44)
                    .background(
                        Circle()
                            .fill(Color.accentColor.opacity(0.9))
                    )
                    .scaleEffect(0.8 + (progress * 0.4))
                    .opacity(Double(progress))
                    .padding(.horizontal, 8)
                if direction == .previous { Spacer() }
            }
            Spacer()
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
