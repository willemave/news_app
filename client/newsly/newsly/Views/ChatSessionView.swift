//
//  ChatSessionView.swift
//  newsly
//
//  Created by Assistant on 11/28/25.
//

import SwiftUI
import UIKit

// MARK: - Selectable Text (UITextView wrapper)

struct SelectableText: UIViewRepresentable {
    let text: String
    let textColor: UIColor
    let font: UIFont

    init(_ text: String, textColor: UIColor = .label, font: UIFont = .preferredFont(forTextStyle: .callout)) {
        self.text = text
        self.textColor = textColor
        self.font = font
    }

    func makeUIView(context: Context) -> UITextView {
        let textView = UITextView()
        textView.isEditable = false
        textView.isSelectable = true
        textView.isScrollEnabled = false
        textView.backgroundColor = .clear
        textView.textContainerInset = .zero
        textView.textContainer.lineFragmentPadding = 0
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return textView
    }

    func updateUIView(_ uiView: UITextView, context: Context) {
        uiView.text = text
        uiView.textColor = textColor
        uiView.font = font
    }
}

struct SelectableAttributedText: UIViewRepresentable {
    let attributedText: NSAttributedString
    let textColor: UIColor

    func makeUIView(context: Context) -> UITextView {
        let textView = UITextView()
        textView.isEditable = false
        textView.isSelectable = true
        textView.isScrollEnabled = false
        textView.backgroundColor = .clear
        textView.textContainerInset = .zero
        textView.textContainer.lineFragmentPadding = 0
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return textView
    }

    func updateUIView(_ uiView: UITextView, context: Context) {
        // Apply the attributed string with color override
        let mutableAttr = NSMutableAttributedString(attributedString: attributedText)
        mutableAttr.addAttribute(.foregroundColor, value: textColor, range: NSRange(location: 0, length: mutableAttr.length))
        uiView.attributedText = mutableAttr
    }
}

struct ChatSessionView: View {
    @StateObject private var viewModel: ChatSessionViewModel
    @FocusState private var isInputFocused: Bool
    @State private var showingModelPicker = false
    @State private var navigateToNewSession: ChatSessionSummary?

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
            await viewModel.checkAndRefreshVoiceDictation()
        }
        .toolbar {
            if let session = viewModel.session {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Menu {
                        Section {
                            Text("Current: \(session.providerDisplayName)")
                                .font(.caption)
                        }
                        Section("Switch Model") {
                            ForEach(ChatModelProvider.allCases, id: \.self) { provider in
                                Button {
                                    Task {
                                        await switchToProvider(provider)
                                    }
                                } label: {
                                    Label(provider.displayName, systemImage: provider.iconName)
                                }
                                .disabled(provider.rawValue == session.llmProvider)
                            }
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Text(session.providerDisplayName)
                            Image(systemName: "chevron.down")
                                .font(.caption2)
                        }
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
        .navigationDestination(item: $navigateToNewSession) { session in
            ChatSessionView(session: session)
        }
    }

    /// Switch to a different provider by creating a new session
    private func switchToProvider(_ provider: ChatModelProvider) async {
        guard let currentSession = viewModel.session else { return }

        // If this session has a content_id, create a new article chat with different provider
        // Otherwise create an ad-hoc chat
        do {
            let chatService = ChatService.shared
            let newSession: ChatSessionSummary

            if let contentId = currentSession.contentId {
                newSession = try await chatService.createSession(
                    contentId: contentId,
                    topic: currentSession.topic,
                    provider: provider
                )
            } else {
                newSession = try await chatService.createSession(
                    provider: provider
                )
            }

            navigateToNewSession = newSession
        } catch {
            viewModel.errorMessage = "Failed to switch model: \(error.localizedDescription)"
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
        VStack(spacing: 8) {
            // Transcribing status
            if viewModel.isTranscribing {
                HStack(spacing: 4) {
                    ProgressView()
                        .scaleEffect(0.7)
                    Text("Transcribing...")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            HStack(alignment: .bottom, spacing: 12) {
                TextField("Message", text: $viewModel.inputText, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...5)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color(.systemGray6))
                    .cornerRadius(20)
                    .focused($isInputFocused)

                // Microphone button
                if viewModel.voiceDictationAvailable {
                    Button {
                        Task {
                            if viewModel.isRecording {
                                await viewModel.stopVoiceRecording()
                            } else {
                                await viewModel.startVoiceRecording()
                            }
                        }
                    } label: {
                        Image(systemName: viewModel.isRecording ? "stop.circle.fill" : "mic.circle.fill")
                            .font(.system(size: 28))
                            .foregroundColor(viewModel.isRecording ? .red : .blue)
                            .symbolEffect(.pulse, isActive: viewModel.isRecording)
                    }
                    .disabled(viewModel.isTranscribing || viewModel.isSending)
                }

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
        viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
        viewModel.isSending ||
        viewModel.isRecording ||
        viewModel.isTranscribing
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

    private var textColor: UIColor {
        message.isUser ? .white : .label
    }

    private var textFont: UIFont {
        .preferredFont(forTextStyle: .callout)
    }

    @ViewBuilder
    private var messageContent: some View {
        if message.isUser {
            // User messages: plain text (no markdown needed)
            SelectableText(message.content, textColor: textColor, font: textFont)
        } else {
            // Assistant messages: render with markdown
            if let attributedString = formattedMarkdown {
                SelectableAttributedText(attributedText: attributedString, textColor: textColor)
            } else {
                SelectableText(message.content, textColor: textColor, font: textFont)
            }
        }
    }

    private var formattedMarkdown: NSAttributedString? {
        guard let attributedString = try? NSAttributedString(
            markdown: message.content,
            options: .init(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        ) else {
            return nil
        }
        let mutableAttr = NSMutableAttributedString(attributedString: attributedString)
        mutableAttr.addAttribute(.font, value: textFont, range: NSRange(location: 0, length: mutableAttr.length))
        return mutableAttr
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
