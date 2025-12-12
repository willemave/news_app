//
//  ChatSessionsView.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import SwiftUI

struct ChatSessionsView: View {
    let onSelectSession: ((ChatSessionRoute) -> Void)?

    @StateObject private var viewModel = ChatSessionsViewModel()
    @State private var showingNewChat = false
    @State private var selectedProvider: ChatModelProvider = .google
    @State private var pendingNavigationRoute: ChatSessionRoute?

    init(onSelectSession: ((ChatSessionRoute) -> Void)? = nil) {
        self.onSelectSession = onSelectSession
    }

    var body: some View {
        ZStack {
            contentBody
        }
        .navigationTitle("Chats")
        .onAppear {
            Task { await viewModel.loadSessions() }
        }
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Menu {
                    ForEach(ChatModelProvider.allCases, id: \.self) { provider in
                        Button {
                            selectedProvider = provider
                            showingNewChat = true
                        } label: {
                            Label(provider.displayName, systemImage: provider.iconName)
                        }
                    }
                } label: {
                    Image(systemName: "plus.circle")
                }
                .accessibilityLabel("New Chat")
            }
        }
        .sheet(isPresented: $showingNewChat, onDismiss: {
            // Navigate after sheet dismisses to avoid conflicts
            if let route = pendingNavigationRoute {
                pendingNavigationRoute = nil
                onSelectSession?(route)
            }
        }) {
            NewChatSheet(
                provider: selectedProvider,
                isPresented: $showingNewChat,
                onCreateSession: { session in
                    viewModel.sessions.insert(session, at: 0)
                    // Queue navigation for after sheet dismisses
                    pendingNavigationRoute = ChatSessionRoute(sessionId: session.id)
                }
            )
            .presentationDetents([.height(380)])
            .presentationDragIndicator(.hidden)
            .presentationCornerRadius(24)
        }
    }

    @ViewBuilder
    private var contentBody: some View {
        if viewModel.isLoading && viewModel.sessions.isEmpty {
            LoadingView()
        } else if let error = viewModel.errorMessage, viewModel.sessions.isEmpty {
            ErrorView(message: error) {
                Task { await viewModel.loadSessions() }
            }
        } else if viewModel.sessions.isEmpty {
            emptyStateView
        } else {
            sessionListView
        }
    }

    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.largeTitle)
                .foregroundColor(.secondary)
            Text("No chats yet")
                .foregroundColor(.secondary)
            Text("Start a deep dive conversation about any article by tapping the brain icon, or create an ad-hoc chat.")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            Button {
                showingNewChat = true
            } label: {
                Label("New Chat", systemImage: "plus.circle.fill")
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
            }
            .buttonStyle(.borderedProminent)
            .padding(.top, 8)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var sessionListView: some View {
        List {
            ForEach(viewModel.sessions) { session in
                Button {
                    onSelectSession?(ChatSessionRoute(sessionId: session.id))
                } label: {
                    ChatSessionRow(session: session)
                }
                .buttonStyle(.plain)
                .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
            }
            .onDelete(perform: viewModel.deleteSession)
        }
        .listStyle(.plain)
        .refreshable {
            await viewModel.loadSessions()
        }
    }
}

// MARK: - Provider Icon

struct ProviderIcon: View {
    let session: ChatSessionSummary

    var body: some View {
        Group {
            if let assetName = session.providerIconAsset {
                Image(assetName)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: 18, height: 18)
            } else {
                Image(systemName: session.providerIconFallback)
                    .font(.system(size: 14))
                    .foregroundColor(.secondary)
            }
        }
        .frame(width: 26, height: 26)
        .background(Color.secondary.opacity(0.1))
        .cornerRadius(6)
    }
}

// MARK: - Session Row

struct ChatSessionRow: View {
    let session: ChatSessionSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(session.displayTitle)
                    .font(.headline)
                    .lineLimit(1)

                // Processing indicator
                if session.isProcessing {
                    HStack(spacing: 4) {
                        ProgressView()
                            .scaleEffect(0.6)
                        Text("Thinking...")
                            .font(.caption2)
                    }
                    .foregroundColor(.blue)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(4)
                }

                Spacer()
                ProviderIcon(session: session)
            }

            if let subtitle = session.displaySubtitle {
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }

            HStack(spacing: 6) {
                // Session type icon and label
                Image(systemName: session.sessionTypeIconName)
                    .font(.caption)
                    .foregroundColor(session.isDeepResearch ? .purple : .blue)
                Text(session.sessionTypeLabel)
                    .font(.caption2)
                    .foregroundColor(session.isDeepResearch ? .purple : .blue)

                Spacer()
                Text(session.formattedDate)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.vertical, 4)
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

    private var providerColor: Color {
        switch provider.accentColor {
        case "green": return .green
        case "orange": return .orange
        case "purple": return .purple
        default: return .blue
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Drag indicator
            RoundedRectangle(cornerRadius: 2.5)
                .fill(Color(.tertiaryLabel))
                .frame(width: 36, height: 5)
                .padding(.top, 8)

            // Provider header
            VStack(spacing: 8) {
                // Provider icon
                ZStack {
                    Circle()
                        .fill(providerColor.opacity(0.15))
                        .frame(width: 56, height: 56)

                    Image(provider.iconAsset)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(width: 28, height: 28)
                }

                VStack(spacing: 2) {
                    Text(provider.displayName)
                        .font(.title3)
                        .fontWeight(.semibold)

                    Text(provider.tagline)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .padding(.top, 16)
            .padding(.bottom, 20)

            // Message input
            VStack(alignment: .leading, spacing: 8) {
                ZStack(alignment: .topLeading) {
                    if initialMessage.isEmpty {
                        Text("What would you like to explore?")
                            .foregroundColor(Color(.placeholderText))
                            .padding(.horizontal, 16)
                            .padding(.vertical, 14)
                    }

                    TextEditor(text: $initialMessage)
                        .scrollContentBackground(.hidden)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .focused($isTextFieldFocused)
                }
                .frame(height: 100)
                .background(Color(.secondarySystemBackground))
                .cornerRadius(12)

                if let error = errorMessage {
                    HStack(spacing: 4) {
                        Image(systemName: "exclamationmark.circle.fill")
                            .font(.caption)
                        Text(error)
                            .font(.caption)
                    }
                    .foregroundColor(.red)
                }
            }
            .padding(.horizontal, 20)

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
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(providerColor)
                    .cornerRadius(12)
                }
                .disabled(isCreating)

                Button {
                    isPresented = false
                } label: {
                    Text("Cancel")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                .padding(.bottom, 8)
            }
            .padding(.horizontal, 20)
            .padding(.bottom, 16)
        }
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
    ChatSessionsView()
}
