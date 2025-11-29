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
    let maxWidth: CGFloat
    @Binding var calculatedHeight: CGFloat
    var onDigDeeper: ((String) -> Void)?

    init(
        _ text: String,
        textColor: UIColor = .label,
        font: UIFont = .preferredFont(forTextStyle: .callout),
        maxWidth: CGFloat = UIScreen.main.bounds.width,
        calculatedHeight: Binding<CGFloat> = .constant(.zero),
        onDigDeeper: ((String) -> Void)? = nil
    ) {
        self.text = text
        self.textColor = textColor
        self.font = font
        self.maxWidth = maxWidth
        self._calculatedHeight = calculatedHeight
        self.onDigDeeper = onDigDeeper
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(onDigDeeper: onDigDeeper)
    }

    func makeUIView(context: Context) -> DigDeeperTextView {
        let textView = DigDeeperTextView()
        textView.isEditable = false
        textView.isSelectable = true
        textView.isScrollEnabled = false
        textView.backgroundColor = .clear
        textView.textContainerInset = .zero
        textView.textContainer.lineFragmentPadding = 0
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        textView.dataDetectorTypes = [.link]
        textView.onDigDeeper = context.coordinator.onDigDeeper
        return textView
    }

    func updateUIView(_ uiView: DigDeeperTextView, context: Context) {
        uiView.text = text
        uiView.textColor = textColor
        uiView.font = font
        uiView.onDigDeeper = context.coordinator.onDigDeeper
        let fittingSize = uiView.sizeThatFits(CGSize(width: maxWidth, height: .greatestFiniteMagnitude))
        uiView.frame.size = fittingSize
        DispatchQueue.main.async {
            calculatedHeight = fittingSize.height
        }
    }

    class Coordinator {
        var onDigDeeper: ((String) -> Void)?

        init(onDigDeeper: ((String) -> Void)?) {
            self.onDigDeeper = onDigDeeper
        }
    }
}

/// Custom UITextView that adds "Dig Deeper" to the edit menu
class DigDeeperTextView: UITextView {
    var onDigDeeper: ((String) -> Void)?

    override func canPerformAction(_ action: Selector, withSender sender: Any?) -> Bool {
        if action == #selector(digDeeperAction(_:)) {
            return selectedRange.length > 0
        }
        return super.canPerformAction(action, withSender: sender)
    }

    override func buildMenu(with builder: any UIMenuBuilder) {
        super.buildMenu(with: builder)

        let digDeeperAction = UIAction(
            title: "Dig Deeper",
            image: UIImage(systemName: "magnifyingglass")
        ) { [weak self] _ in
            self?.performDigDeeper()
        }

        let menu = UIMenu(title: "", options: .displayInline, children: [digDeeperAction])
        builder.insertChild(menu, atStartOfMenu: .standardEdit)
    }

    @objc func digDeeperAction(_ sender: Any?) {
        performDigDeeper()
    }

    private func performDigDeeper() {
        guard let selectedTextRange = selectedTextRange,
              let selectedText = text(in: selectedTextRange),
              !selectedText.isEmpty else { return }

        onDigDeeper?(selectedText)
    }
}

struct SelectableAttributedText: UIViewRepresentable {
    let attributedText: NSAttributedString
    let textColor: UIColor
    let maxWidth: CGFloat
    @Binding var calculatedHeight: CGFloat
    var onDigDeeper: ((String) -> Void)?

    init(
        attributedText: NSAttributedString,
        textColor: UIColor,
        maxWidth: CGFloat = UIScreen.main.bounds.width,
        calculatedHeight: Binding<CGFloat> = .constant(.zero),
        onDigDeeper: ((String) -> Void)? = nil
    ) {
        self.attributedText = attributedText
        self.textColor = textColor
        self.maxWidth = maxWidth
        self._calculatedHeight = calculatedHeight
        self.onDigDeeper = onDigDeeper
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(onDigDeeper: onDigDeeper)
    }

    func makeUIView(context: Context) -> DigDeeperTextView {
        let textView = DigDeeperTextView()
        textView.isEditable = false
        textView.isSelectable = true
        textView.isScrollEnabled = false
        textView.backgroundColor = .clear
        textView.textContainerInset = .zero
        textView.textContainer.lineFragmentPadding = 0
        textView.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        textView.dataDetectorTypes = [.link]
        textView.onDigDeeper = context.coordinator.onDigDeeper
        return textView
    }

    func updateUIView(_ uiView: DigDeeperTextView, context: Context) {
        // Apply the attributed string with color override
        let mutableAttr = NSMutableAttributedString(attributedString: attributedText)
        mutableAttr.addAttribute(.foregroundColor, value: textColor, range: NSRange(location: 0, length: mutableAttr.length))
        uiView.attributedText = mutableAttr
        uiView.onDigDeeper = context.coordinator.onDigDeeper
        let fittingSize = uiView.sizeThatFits(CGSize(width: maxWidth, height: .greatestFiniteMagnitude))
        uiView.frame.size = fittingSize
        DispatchQueue.main.async {
            calculatedHeight = fittingSize.height
        }
    }

    class Coordinator {
        var onDigDeeper: ((String) -> Void)?

        init(onDigDeeper: ((String) -> Void)?) {
            self.onDigDeeper = onDigDeeper
        }
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
                        ChatLoadingView()
                            .frame(maxWidth: .infinity)
                            .padding(.top, 40)
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
                            if viewModel.isSending {
                                // Loading initial suggestions
                                InitialSuggestionsLoadingView()
                            } else {
                                Image(systemName: "bubble.left.and.bubble.right")
                                    .font(.system(size: 48))
                                    .foregroundColor(.secondary.opacity(0.5))
                                Text("Start the conversation")
                                    .font(.headline)
                                    .foregroundColor(.secondary)
                            }
                            if let topic = viewModel.session?.topic {
                                Text("Topic: \(topic)")
                                    .font(.subheadline)
                                    .foregroundColor(.blue)
                            }
                        }
                        .padding(.top, 60)
                    } else {
                        ForEach(viewModel.allMessages) { message in
                            MessageBubble(message: message) { selectedText in
                                Task { await viewModel.digDeeper(into: selectedText) }
                            }
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
            .textSelection(.enabled)
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

                Menu {
                    Button {
                        Task { await viewModel.sendCounterArgumentsPrompt() }
                    } label: {
                        Label("Find counterbalancing arguments online", systemImage: "globe")
                    }
                } label: {
                    Image(systemName: "magnifyingglass.circle.fill")
                        .font(.system(size: 22))
                        .foregroundColor(.blue)
                        .frame(width: 32, height: 32)
                        .background(Color(.systemGray6))
                        .clipShape(Circle())
                }
                .disabled(viewModel.isSending || viewModel.isRecording || viewModel.isTranscribing)
                .accessibilityLabel("Chat actions")

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
    var onDigDeeper: ((String) -> Void)?
    @State private var calculatedHeight: CGFloat = .zero

    var body: some View {
        HStack {
            if message.isUser {
                Spacer(minLength: 60)
            }

            VStack(alignment: message.isUser ? .trailing : .leading, spacing: 4) {
                messageContent
                    .frame(height: max(calculatedHeight, 0))
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

    private var messageContent: some View {
        GeometryReader { geo in
            let width = geo.size.width
            ZStack(alignment: message.isUser ? .trailing : .leading) {
                sizingText
                selectableView(maxWidth: width)
            }
        }
        .frame(maxWidth: .infinity, alignment: message.isUser ? .trailing : .leading)
    }

    @ViewBuilder
    private var sizingText: some View {
        // Invisible Text used only for SwiftUI layout to compute height/width
        let displayText: String = {
            if let attr = formattedMarkdown {
                return attr.string
            }
            return message.content
        }()

        Text(displayText)
            .font(.callout)
            .foregroundColor(.clear)
            .padding(.vertical, 2)
            .fixedSize(horizontal: false, vertical: true)
            .accessibilityHidden(true)
    }

    @ViewBuilder
    private func selectableView(maxWidth: CGFloat) -> some View {
        if let attr = formattedMarkdown {
            SelectableAttributedText(
                attributedText: attr,
                textColor: textColor,
                maxWidth: maxWidth,
                calculatedHeight: $calculatedHeight,
                onDigDeeper: onDigDeeper
            )
        } else {
            SelectableText(
                message.content,
                textColor: textColor,
                font: textFont,
                maxWidth: maxWidth,
                calculatedHeight: $calculatedHeight,
                onDigDeeper: onDigDeeper
            )
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

// MARK: - Initial Suggestions Loading View

struct InitialSuggestionsLoadingView: View {
    @State private var dotOffset: CGFloat = 0
    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        VStack(spacing: 20) {
            // Animated typing indicator style
            ZStack {
                // Background circle with pulse
                Circle()
                    .fill(Color.blue.opacity(0.08))
                    .frame(width: 80, height: 80)
                    .scaleEffect(pulseScale)

                // Three bouncing dots
                HStack(spacing: 6) {
                    ForEach(0..<3) { index in
                        Circle()
                            .fill(Color.blue.opacity(0.7))
                            .frame(width: 10, height: 10)
                            .offset(y: dotOffset)
                            .animation(
                                .easeInOut(duration: 0.4)
                                    .repeatForever(autoreverses: true)
                                    .delay(Double(index) * 0.12),
                                value: dotOffset
                            )
                    }
                }
            }
            .onAppear {
                dotOffset = -6
                withAnimation(.easeInOut(duration: 1.5).repeatForever(autoreverses: true)) {
                    pulseScale = 1.15
                }
            }

            VStack(spacing: 6) {
                Text("Preparing suggestions")
                    .font(.headline)
                    .foregroundColor(.primary)

                Text("Analyzing the article for you")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
        }
    }
}

#Preview("Loading State") {
    InitialSuggestionsLoadingView()
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
