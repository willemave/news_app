//
//  ChatSessionView.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import SwiftUI

struct ChatSessionView: View {
    @StateObject private var viewModel: ChatSessionViewModel
    @FocusState private var isInputFocused: Bool

    init(session: ChatSessionSummary) {
        _viewModel = StateObject(wrappedValue: ChatSessionViewModel(session: session))
    }

    init(sessionId: Int) {
        _viewModel = StateObject(wrappedValue: ChatSessionViewModel(sessionId: sessionId))
    }

    var body: some View {
        VStack(spacing: 0) {
            // Messages
            messageListView

            // Input area
            inputBar
        }
        .navigationTitle(viewModel.session?.displayTitle ?? "Chat")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await viewModel.loadSession()
        }
        .toolbar {
            if let session = viewModel.session {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Text(session.providerDisplayName)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.secondary.opacity(0.1))
                        .cornerRadius(6)
                }
            }
        }
    }

    // MARK: - Message List

    private var messageListView: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 12) {
                    if viewModel.isLoading {
                        ProgressView()
                            .padding()
                    } else if let error = viewModel.errorMessage, viewModel.messages.isEmpty {
                        VStack(spacing: 8) {
                            Image(systemName: "exclamationmark.triangle")
                                .font(.largeTitle)
                                .foregroundColor(.orange)
                            Text(error)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                            Button("Retry") {
                                Task { await viewModel.loadSession() }
                            }
                            .buttonStyle(.borderedProminent)
                        }
                        .padding()
                    } else if viewModel.allMessages.isEmpty {
                        VStack(spacing: 16) {
                            Image(systemName: "bubble.left.and.bubble.right")
                                .font(.system(size: 48))
                                .foregroundColor(.secondary.opacity(0.5))
                            Text("Start the conversation")
                                .font(.headline)
                                .foregroundColor(.secondary)
                            if let topic = viewModel.session?.topic {
                                Text("Topic: \(topic)")
                                    .font(.subheadline)
                                    .foregroundColor(.blue)
                            }
                        }
                        .padding(.top, 60)
                    } else {
                        ForEach(viewModel.allMessages) { message in
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }

                    // Anchor for scrolling
                    Color.clear
                        .frame(height: 1)
                        .id("bottom")
                }
                .padding()
            }
            .onChange(of: viewModel.allMessages.count) { _, _ in
                withAnimation(.easeOut(duration: 0.2)) {
                    proxy.scrollTo("bottom", anchor: .bottom)
                }
            }
        }
    }

    // MARK: - Input Bar

    private var inputBar: some View {
        HStack(alignment: .bottom, spacing: 12) {
            TextField("Message", text: $viewModel.inputText, axis: .vertical)
                .textFieldStyle(.plain)
                .lineLimit(1...5)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(Color(.systemGray6))
                .cornerRadius(20)
                .focused($isInputFocused)

            Button {
                Task { await viewModel.sendMessage() }
            } label: {
                Group {
                    if viewModel.isSending {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Image(systemName: "arrow.up")
                            .font(.system(size: 16, weight: .semibold))
                    }
                }
                .frame(width: 36, height: 36)
                .background(sendButtonDisabled ? Color.gray : Color.blue)
                .foregroundColor(.white)
                .clipShape(Circle())
            }
            .disabled(sendButtonDisabled)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(Color(.systemBackground))
        .overlay(
            Rectangle()
                .frame(height: 0.5)
                .foregroundColor(Color(.separator)),
            alignment: .top
        )
    }

    private var sendButtonDisabled: Bool {
        viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || viewModel.isSending
    }
}

// MARK: - Message Bubble

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack {
            if message.isUser {
                Spacer(minLength: 60)
            }

            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                messageContent
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(message.isUser ? Color.blue : Color(.systemGray5))
                    .foregroundColor(message.isUser ? .white : .primary)
                    .cornerRadius(18)

                if !message.formattedTime.isEmpty {
                    Text(message.formattedTime)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 4)
                }
            }

            if !message.isUser {
                Spacer(minLength: 60)
            }
        }
    }

    @ViewBuilder
    private var messageContent: some View {
        if message.isUser {
            // User messages: plain text (no markdown needed)
            Text(message.content)
        } else {
            // Assistant messages: render with markdown
            if let attributedString = try? AttributedString(markdown: message.content, options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)) {
                Text(attributedString)
            } else {
                Text(message.content)
            }
        }
    }
}

#Preview {
    NavigationStack {
        ChatSessionView(session: ChatSessionSummary(
            id: 1,
            contentId: nil,
            title: "Test Chat",
            sessionType: "ad_hoc",
            topic: nil,
            llmProvider: "openai",
            llmModel: "openai:gpt-5.1",
            createdAt: "2025-11-28T12:00:00Z",
            updatedAt: nil,
            lastMessageAt: nil,
            articleTitle: nil
        ))
    }
}
