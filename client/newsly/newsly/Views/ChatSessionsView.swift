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

    private let chatService = ChatService.shared

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("What would you like to discuss?", text: $initialMessage, axis: .vertical)
                        .lineLimit(3...6)
                } header: {
                    Text("Start a conversation")
                } footer: {
                    Text("Using \(provider.displayName)")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                    }
                }
            }
            .navigationTitle("New Chat")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        isPresented = false
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Start") {
                        Task { await createSession() }
                    }
                    .disabled(isCreating)
                }
            }
            .disabled(isCreating)
            .overlay {
                if isCreating {
                    ZStack {
                        Color.black.opacity(0.3)
                            .ignoresSafeArea()

                        VStack(spacing: 16) {
                            ZStack {
                                Circle()
                                    .fill(Color.blue.opacity(0.15))
                                    .frame(width: 70, height: 70)

                                Image(systemName: "brain.head.profile")
                                    .font(.system(size: 28))
                                    .foregroundColor(.blue)
                                    .symbolEffect(.pulse, options: .repeating)
                            }

                            Text("Starting chat...")
                                .font(.headline)
                                .foregroundColor(.primary)
                        }
                        .padding(32)
                        .background(.ultraThinMaterial)
                        .cornerRadius(16)
                    }
                }
            }
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
