//
//  ChatSessionsView.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import SwiftUI

struct ChatSessionsView: View {
    @StateObject private var viewModel = ChatSessionsViewModel()
    @State private var showingNewChat = false
    @State private var selectedProvider: ChatModelProvider = .google

    var body: some View {
        NavigationStack {
            ZStack {
                contentBody
            }
            .navigationTitle("Chats")
            .task {
                await viewModel.loadSessions()
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
            .sheet(isPresented: $showingNewChat) {
                NewChatSheet(
                    provider: selectedProvider,
                    isPresented: $showingNewChat,
                    onCreateSession: { session in
                        viewModel.sessions.insert(session, at: 0)
                    }
                )
                .presentationDetents([.height(320)])
                .presentationDragIndicator(.hidden)
                .presentationCornerRadius(20)
            }
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
                NavigationLink(destination: ChatSessionView(session: session)) {
                    ChatSessionRow(session: session)
                }
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
                Text(session.providerDisplayName)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color.secondary.opacity(0.1))
                    .cornerRadius(4)
            }

            if let subtitle = session.displaySubtitle {
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }

            HStack {
                if let sessionType = session.sessionType {
                    Text(sessionType.replacingOccurrences(of: "_", with: " ").capitalized)
                        .font(.caption2)
                        .foregroundColor(.blue)
                }
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

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Button("Cancel") {
                    isPresented = false
                }

                Spacer()

                Text("New Chat")
                    .font(.headline)

                Spacer()

                // Invisible spacer to balance Cancel button
                Text("Cancel")
                    .opacity(0)
            }
            .padding(.horizontal, 20)
            .padding(.top, 20)
            .padding(.bottom, 16)

            // Content
            VStack(spacing: 16) {
                TextField("Message", text: $initialMessage, axis: .vertical)
                    .lineLimit(3...5)
                    .textFieldStyle(.plain)
                    .padding(12)
                    .background(Color(.secondarySystemBackground))
                    .cornerRadius(10)
                    .focused($isTextFieldFocused)

                if let error = errorMessage {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                }

                HStack(spacing: 12) {
                    Button {
                        Task { await createSession() }
                    } label: {
                        Text("Just Chat")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)
                    .disabled(isCreating)

                    Button {
                        Task { await createSession() }
                    } label: {
                        Text("Start")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(isCreating || initialMessage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .padding(.horizontal, 20)

            Spacer()
        }
        .disabled(isCreating)
        .overlay {
            if isCreating {
                ZStack {
                    Color.black.opacity(0.3)
                        .ignoresSafeArea()

                    ProgressView()
                        .scaleEffect(1.2)
                        .padding(24)
                        .background(.ultraThinMaterial)
                        .cornerRadius(12)
                }
            }
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
