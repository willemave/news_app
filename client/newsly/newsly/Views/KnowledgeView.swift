//
//  KnowledgeView.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import SwiftUI

struct KnowledgeView: View {
    let onSelectSession: ((ChatSessionRoute) -> Void)?
    let onSelectContent: ((ContentDetailRoute) -> Void)?
    @Binding private var prefersHistoryView: Bool

    @StateObject private var viewModel = ChatSessionsViewModel()
    @ObservedObject private var settings = AppSettings.shared
    @State private var showingNewChat = false
    @State private var selectedProvider: ChatModelProvider = .anthropic
    @State private var activeSessionId: Int?
    @State private var chatSearchText = ""
    @State private var isBootstrappingChat = false

    @AppStorage("knowledgeTabLastOpenedAt") private var lastOpenedTimestamp: Double = 0

    private var appTextSize: DynamicTypeSize {
        AppTextSize(index: settings.appTextSizeIndex).dynamicTypeSize
    }

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        if hour < 12 { return "Good morning," }
        if hour < 17 { return "Good afternoon," }
        return "Good evening,"
    }

    init(
        prefersHistoryView: Binding<Bool> = .constant(false),
        onSelectSession: ((ChatSessionRoute) -> Void)? = nil,
        onSelectContent: ((ContentDetailRoute) -> Void)? = nil
    ) {
        self._prefersHistoryView = prefersHistoryView
        self.onSelectSession = onSelectSession
        self.onSelectContent = onSelectContent
    }

    var body: some View {
        contentView
            .dynamicTypeSize(appTextSize)
            .background(Color.surfacePrimary.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if prefersHistoryView {
                    ToolbarItem(placement: .principal) {
                        greetingHeader
                    }
                    ToolbarItem(placement: .navigationBarTrailing) {
                        HStack(spacing: 12) {
                            Button {
                                showingNewChat = true
                            } label: {
                                Image(systemName: "square.and.pencil")
                                    .foregroundStyle(Color.terracottaPrimary)
                            }
                            .accessibilityIdentifier("knowledge.new_chat")
                        }
                    }
                }
            }
            .task {
                lastOpenedTimestamp = Date().timeIntervalSince1970
                await prepareDefaultChatIfNeeded()
            }
            .onChange(of: prefersHistoryView) { _, showingHistory in
                guard !showingHistory else {
                    Task { await viewModel.loadSessions() }
                    return
                }
                Task { await prepareDefaultChatIfNeeded() }
            }
            .sheet(isPresented: $showingNewChat) {
                NewChatSheet(
                    provider: selectedProvider,
                    isPresented: $showingNewChat,
                    onCreateSession: { session in
                        viewModel.sessions.removeAll { $0.id == session.id }
                        viewModel.sessions.insert(session, at: 0)
                        activeSessionId = session.id
                        prefersHistoryView = false
                    }
                )
                .dynamicTypeSize(appTextSize)
                .presentationDetents([.height(380)])
                .presentationDragIndicator(.hidden)
                .presentationCornerRadius(24)
            }
    }

    // MARK: - Greeting Header

    private var greetingHeader: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(Color.chatAccent.opacity(0.15))
                .frame(width: 32, height: 32)
                .overlay(
                    Image(systemName: "person.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(Color.chatAccent)
                )

            Text(greetingText)
                .font(.terracottaHeadlineItalic)
                .foregroundStyle(Color.chatAccent)
        }
    }

    @ViewBuilder
    private var contentView: some View {
        if prefersHistoryView {
            sessionListView
        } else {
            defaultChatView
        }
    }

    private var knowledgeSessions: [ChatSessionSummary] {
        viewModel.sessions.filter {
            $0.sessionType != "voice_live"
                && !$0.isLiveVoiceSession
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: 20) {
            Image(systemName: "brain.head.profile")
                .font(.system(size: 48, weight: .light))
                .foregroundStyle(Color.terracottaPrimary.opacity(0.7))

            VStack(spacing: 6) {
                Text("No chats yet")
                    .font(.terracottaHeadlineMedium)
                    .foregroundStyle(Color.onSurface)

                Text("Start a new chat here or open an article to jump into a contextual session.")
                    .font(.terracottaBodyMedium)
                    .foregroundStyle(Color.onSurfaceSecondary)
            }
            .multilineTextAlignment(.center)
            .frame(maxWidth: 280)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.surfacePrimary)
    }

    @ViewBuilder
    private var defaultChatView: some View {
        if let activeSessionId {
            ChatSessionView(
                sessionId: activeSessionId,
                onShowHistory: {
                    prefersHistoryView = true
                }
            )
        } else if isBootstrappingChat || viewModel.isLoading {
            LoadingView()
        } else if let error = viewModel.errorMessage {
            ErrorView(message: error) {
                Task { await prepareDefaultChat(forceRefresh: true) }
            }
        } else {
            LoadingView()
        }
    }

    private var sessionListView: some View {
        Group {
            if viewModel.isLoading && knowledgeSessions.isEmpty {
                LoadingView()
            } else if let error = viewModel.errorMessage, knowledgeSessions.isEmpty {
                ErrorView(message: error) {
                    Task { await viewModel.loadSessions() }
                }
            } else if knowledgeSessions.isEmpty {
                emptyStateView
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        chatSearchBarRow
                            .padding(.horizontal, 16)

                        ForEach(filteredSessions) { session in
                            Button {
                                activeSessionId = session.id
                                prefersHistoryView = false
                            } label: {
                                ChatSessionCard(session: session)
                            }
                            .buttonStyle(.plain)
                            .padding(.horizontal, 16)
                            .contextMenu {
                                Button(role: .destructive) {
                                    Task { await viewModel.deleteSessions(ids: [session.id]) }
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                        }

                        if shouldShowNoResults {
                            noResultsRow
                        }
                    }
                    .padding(.vertical, 8)
                }
                .refreshable {
                    await viewModel.loadSessions()
                }
            }
        }
    }

    private var filteredSessions: [ChatSessionSummary] {
        let trimmedQuery = chatSearchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedQuery.isEmpty else { return knowledgeSessions }
        return knowledgeSessions.filter { session in
            sessionMatchesSearch(session, query: trimmedQuery)
        }
    }

    private var shouldShowNoResults: Bool {
        let trimmedQuery = chatSearchText.trimmingCharacters(in: .whitespacesAndNewlines)
        return !trimmedQuery.isEmpty && filteredSessions.isEmpty
    }

    private func sessionMatchesSearch(_ session: ChatSessionSummary, query: String) -> Bool {
        let haystacks = [
            session.displayTitle,
            session.displaySubtitle ?? "",
            session.articleTitle ?? "",
            session.articleSource ?? "",
            session.topic ?? ""
        ]
        return haystacks.contains { $0.localizedCaseInsensitiveContains(query) }
    }

    private var chatSearchBarRow: some View {
        SearchBar(
            placeholder: "Search history...",
            text: $chatSearchText
        )
    }

    private var noResultsRow: some View {
        VStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: Spacing.iconSize))
                .foregroundStyle(Color.onSurfaceSecondary)
            Text("No matching chats")
                .font(.terracottaHeadlineSmall)
                .fontWeight(.semibold)
            Text("Try a different keyword.")
                .font(.terracottaBodySmall)
                .foregroundStyle(Color.onSurfaceSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.sectionTop)
    }

    private func prepareDefaultChatIfNeeded() async {
        guard !prefersHistoryView else { return }
        guard activeSessionId == nil else { return }
        await prepareDefaultChat(forceRefresh: true)
    }

    private func prepareDefaultChat(forceRefresh: Bool) async {
        guard !isBootstrappingChat else { return }
        isBootstrappingChat = true
        defer { isBootstrappingChat = false }

        if forceRefresh || viewModel.sessions.isEmpty {
            await viewModel.loadSessions()
        }

        if let existingSession = knowledgeSessions.first {
            activeSessionId = existingSession.id
            return
        }

        if let newSession = await viewModel.createSession(provider: selectedProvider) {
            activeSessionId = newSession.id
            prefersHistoryView = false
        }
    }
}

// MARK: - Session Card

struct ChatSessionCard: View {
    let session: ChatSessionSummary

    /// Whether this session was recently active (within last 5 minutes)
    private var isRecentlyActive: Bool {
        guard let dateStr = session.lastMessageAt else { return false }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        var date = formatter.date(from: dateStr)
        if date == nil {
            formatter.formatOptions = [.withInternetDateTime]
            date = formatter.date(from: dateStr)
        }
        guard let date else { return false }
        return Date().timeIntervalSince(date) < 300
    }

    private enum BadgeStyle {
        case thinking
        case ready
        case none
    }

    private var badgeStyle: BadgeStyle {
        if session.isProcessing { return .thinking }
        if !session.isProcessing && session.hasAnyMessages && isRecentlyActive { return .ready }
        return .none
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Header row: title + badge + arrow
            HStack(spacing: 8) {
                Text(session.displayTitle)
                    .font(.terracottaHeadlineSmall)
                    .foregroundColor(.onSurface)
                    .lineLimit(1)

                Spacer()

                statusBadge

                Image(systemName: "arrow.right")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundColor(.onSurfaceSecondary)
            }

            // Preview row
            previewRow
        }
        .padding(14)
        .background(Color.surfaceSecondary)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.outlineVariant.opacity(0.3), lineWidth: 1)
        )
    }

    @ViewBuilder
    private var statusBadge: some View {
        switch badgeStyle {
        case .thinking:
            HStack(spacing: 4) {
                ProgressView()
                    .scaleEffect(0.5)
                Text("THINKING")
                    .font(.terracottaLabelSmall)
                    .tracking(0.5)
            }
            .foregroundColor(.onSurfaceSecondary)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(Color.surfaceContainer)
            .cornerRadius(4)

        case .ready:
            Text("READY")
                .font(.terracottaLabelSmall)
                .tracking(0.5)
                .foregroundColor(.terracottaPrimary)
                .padding(.horizontal, 8)
                .padding(.vertical, 3)
                .background(Color.terracottaPrimary.opacity(0.1))
                .cornerRadius(4)

        case .none:
            EmptyView()
        }
    }

    @ViewBuilder
    private var previewRow: some View {
        if let preview = session.lastMessagePreview, !preview.isEmpty {
            let role = session.lastMessageRole ?? "assistant"
            let prefix = role == "user" ? "You: " : "AI: "
            let prefixColor: Color = role == "user" ? .onSurface : .terracottaPrimary

            (Text(prefix).foregroundColor(prefixColor).fontWeight(.medium) +
             Text(preview).foregroundColor(.onSurfaceSecondary))
                .font(.terracottaBodyMedium)
                .lineLimit(2)
        } else if session.isEmptyFavorite, let summary = session.articleSummary, !summary.isEmpty {
            Text(summary)
                .font(.terracottaBodyMedium)
                .foregroundColor(.onSurfaceSecondary)
                .lineLimit(2)
        } else if let subtitle = session.displaySubtitle {
            Text(subtitle)
                .font(.terracottaBodyMedium)
                .foregroundColor(.onSurfaceSecondary)
                .lineLimit(2)
        }
    }
}

// MARK: - New Chat Sheet

struct NewChatSheet: View {
    let provider: ChatModelProvider
    @Binding var isPresented: Bool
    let onCreateSession: (ChatSessionSummary) -> Void

    @State private var initialMessage: String = ""
    @State private var isCreating = false
    @State private var errorMessage: String?
    @FocusState private var isTextFieldFocused: Bool

    private let chatService = ChatService.shared

    var body: some View {
        VStack(spacing: 0) {
            // Drag indicator
            RoundedRectangle(cornerRadius: 2.5)
                .fill(Color.outlineVariant)
                .frame(width: 36, height: 5)
                .padding(.top, 8)

            // Provider header
            VStack(spacing: 8) {
                // Provider icon
                ZStack {
                    Circle()
                        .fill(Color.terracottaPrimary.opacity(0.15))
                        .frame(width: 56, height: 56)

                    Image(provider.iconAsset)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: 28, height: 28)
                }

                VStack(spacing: 2) {
                    Text(provider.displayName)
                        .font(.terracottaHeadlineMedium)

                    Text(provider.tagline)
                        .font(.terracottaBodySmall)
                        .foregroundColor(.onSurfaceSecondary)
                }
            }
            .padding(.top, 16)
            .padding(.bottom, 20)

            // Message input
            VStack(alignment: .leading, spacing: 8) {
                ZStack(alignment: .topLeading) {
                    if initialMessage.isEmpty {
                        Text("What would you like to explore?")
                            .font(.terracottaBodyMedium)
                            .foregroundColor(Color(.placeholderText))
                            .padding(.horizontal, 16)
                            .padding(.vertical, 14)
                    }

                    TextEditor(text: $initialMessage)
                        .font(.terracottaBodyMedium)
                        .scrollContentBackground(.hidden)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .focused($isTextFieldFocused)
                }
                .frame(height: 100)
                .background(Color.surfaceContainer)
                .cornerRadius(16)

                if let error = errorMessage {
                    HStack(spacing: 4) {
                        Image(systemName: "exclamationmark.circle.fill")
                            .font(.terracottaBodySmall)
                        Text(error)
                            .font(.terracottaBodySmall)
                    }
                    .foregroundColor(.red)
                }
            }
            .padding(.horizontal, Spacing.screenHorizontal)

            HStack(spacing: 6) {
                Image(systemName: "star")
                    .font(.chipLabel)
                    .foregroundColor(.terracottaPrimary)
                Text("Favorite articles to chat about them with full context.")
                    .font(.terracottaBodySmall)
                    .foregroundColor(.onSurfaceSecondary)
            }
            .padding(.top, 10)
            .padding(.horizontal, Spacing.screenHorizontal)

            Spacer()

            // Action buttons
            VStack(spacing: 10) {
                Button {
                    Task { await createSession() }
                } label: {
                    HStack {
                        if isCreating {
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                                .scaleEffect(0.8)
                        } else {
                            Image(systemName: "paperplane.fill")
                        }
                        Text(initialMessage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                             ? "Start Chat"
                             : "Send")
                    }
                    .font(.terracottaBodyLarge)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(Color.terracottaPrimary)
                    .cornerRadius(25)
                }
                .disabled(isCreating)

                Button {
                    isPresented = false
                } label: {
                    Text("Cancel")
                        .font(.terracottaBodyMedium)
                        .foregroundColor(.onSurfaceSecondary)
                }
                .padding(.bottom, 8)
            }
            .padding(.horizontal, Spacing.screenHorizontal)
            .padding(.bottom, 16)
        }
        .background(Color.surfacePrimary)
        .onAppear {
            isTextFieldFocused = true
        }
    }

    private func createSession() async {
        isCreating = true
        errorMessage = nil

        do {
            let session = try await chatService.startAdHocChat(
                initialMessage: initialMessage.isEmpty ? nil : initialMessage,
                provider: provider
            )
            onCreateSession(session)
            isPresented = false
        } catch {
            errorMessage = error.localizedDescription
        }

        isCreating = false
    }
}

#Preview {
    KnowledgeView()
}
