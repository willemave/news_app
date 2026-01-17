# SwiftUI List Views Refactor Spec

> Recommendations for aligning iOS list/scroll views with modern SwiftUI patterns (iOS 17+)

## Overview

Analysis of four main screens identified opportunities to simplify code, reduce complexity, and adopt modern SwiftUI APIs. The primary themes are:

1. **Stop fighting the framework** — use native components as designed or switch to alternatives
2. **Adopt iOS 17+ scroll APIs** — `scrollPosition(id:)`, `onScrollPhaseChange`, `defaultScrollAnchor`
3. **Modernize navigation** — replace deprecated `NavigationView` with `NavigationStack`

---

## 1. LongFormView.swift

**File**: `client/newsly/newsly/Views/LongFormView.swift` (170 lines)

### Current State

Uses `List` but heavily customizes it to look like cards:
- `.listRowInsets(EdgeInsets(...))`
- `.listRowSeparator(.hidden)`
- `.listRowBackground(Color.clear)`
- Manual `Divider()` between items
- Redundant manual chevron icons

### Problems

1. **Fighting List**: If you want card-style layout, `List` is the wrong tool
2. **Manual dividers**: Defeats the purpose of using List
3. **Redundant chevrons**: `NavigationLink` already shows disclosure indicator
4. **No scroll position tracking**: Loses position on view updates

### Recommended Refactor

**Option A**: Embrace native List styling (minimal change)
- Remove manual dividers
- Remove custom chevron icons
- Use `.listRowSeparatorTint()` if custom separator color needed
- Accept List's native appearance

**Option B**: Switch to ScrollView + LazyVStack (recommended for card UI)
```swift
ScrollView {
    LazyVStack(spacing: 12) {
        ForEach(viewModel.currentItems(), id: \.id) { content in
            ContentCard(content: content)
                .id(content.id)
                .contentShape(Rectangle())
                .onTapGesture {
                    onSelect(ContentDetailRoute(summary: content, allContentIds: ...))
                }
                .swipeActions { ... } // Note: swipeActions require List
        }
    }
    .padding(.horizontal)
}
.scrollPosition(id: $scrolledItemID)
.refreshable { viewModel.refreshTrigger.send(()) }
```

**Trade-off**: `swipeActions` modifier only works with `List`. If swipe actions are critical, keep List but simplify styling. If card UI is critical, drop swipe actions or implement custom swipe gesture.

### Effort

- Option A: ~30 min (remove redundant code)
- Option B: ~2 hours (rewrite scroll container, handle swipe alternative)

---

## 2. ShortFormView.swift

**File**: `client/newsly/newsly/Views/ShortFormView.swift` (290 lines)

### Current State

Custom scroll position detection for mark-as-read:
- `ScrollPositionDetector` struct with `GeometryReader`
- `ScrolledPastTopPreferenceKey` preference key
- Manual coordinate space tracking
- Unused `ScrollViewReader` proxy

### Problems

1. **Over-engineered**: 50+ lines of code for scroll detection that iOS 17 provides natively
2. **Dead code**: `ScrollViewReader { _ in` creates unused proxy
3. **Fragile**: GeometryReader-based detection can have timing issues

### Recommended Refactor

Replace custom detection with iOS 17 APIs:

```swift
struct ShortFormView: View {
    @ObservedObject var viewModel: ShortNewsListViewModel
    @State private var topVisibleItemID: Int?
    @State private var previousTopID: Int?

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 12) {
                ForEach(viewModel.currentItems(), id: \.id) { item in
                    ShortNewsRow(item: item)
                        .id(item.id)
                        .onTapGesture { ... }
                        .onAppear {
                            if item.id == viewModel.currentItems().last?.id {
                                viewModel.loadMoreTrigger.send(())
                            }
                        }
                }
                // ... loading more indicator
            }
            .scrollTargetLayout()
            .padding(.horizontal, 16)
        }
        .scrollPosition(id: $topVisibleItemID, anchor: .top)
        .onScrollPhaseChange { oldPhase, newPhase in
            // Mark items as read when scrolling stops
            if newPhase == .idle, let topID = topVisibleItemID {
                markItemsAboveAsRead(upTo: topID)
            }
        }
        .refreshable { ... }
    }

    private func markItemsAboveAsRead(upTo itemID: Int) {
        let items = viewModel.currentItems()
        guard let index = items.firstIndex(where: { $0.id == itemID }) else { return }

        let idsToMark = items.prefix(index)
            .filter { !$0.isRead }
            .map(\.id)

        if !idsToMark.isEmpty {
            viewModel.itemsScrolledPastTop(ids: Array(idsToMark))
        }
    }
}
```

### Code Removed

- `ScrollPositionDetector` struct (~20 lines)
- `ScrolledPastTopPreferenceKey` struct (~10 lines)
- `markedAsReadIds` state tracking (~15 lines)
- `.coordinateSpace(name:)` and `.onPreferenceChange()` (~10 lines)

**Net reduction**: ~50 lines, simpler mental model

### Effort

~1-2 hours

---

## 3. KnowledgeDiscoveryView.swift

**File**: `client/newsly/newsly/Views/KnowledgeDiscoveryView.swift` (498 lines)

### Current State

Well-structured but large file with inline state views and suggestion cards.

### Problems

1. **Large file**: 498 lines makes navigation difficult
2. **Manual spacers**: `Spacer().frame(height: X)` instead of padding
3. **No scroll position preservation**: Refresh loses position
4. **Inline private structs**: `DiscoverySuggestionCard` and `SafariTarget` could be extracted

### Recommended Refactor

**Extract subviews to separate files**:

```
Views/
  KnowledgeDiscoveryView.swift          (~200 lines, main view)
  Components/
    DiscoverySuggestionCard.swift       (~90 lines)
    DiscoveryStateViews.swift           (~100 lines: loading, error, empty)
    DiscoveryRunSection.swift           (~80 lines)
```

**Replace Spacer().frame() with padding**:
```swift
// Before
Spacer().frame(height: 100)
VStack { ... }
Spacer().frame(height: 200)

// After
VStack { ... }
    .padding(.top, 100)
    .padding(.bottom, 200)
```

**Add scroll position tracking**:
```swift
@State private var scrolledRunID: Int?

ScrollView {
    LazyVStack(spacing: 0) { ... }
        .scrollTargetLayout()
}
.scrollPosition(id: $scrolledRunID)
```

### Effort

~2-3 hours (mostly file reorganization)

---

## 4. SettingsView.swift

**File**: `client/newsly/newsly/Views/SettingsView.swift` (220 lines)

### Current State

Uses deprecated `NavigationView` with inline destinations and redundant chevrons.

### Problems

1. **Deprecated API**: `NavigationView` replaced by `NavigationStack` in iOS 16
2. **Redundant chevrons**: Manual `Image(systemName: "chevron.right")` when `NavigationLink` provides this
3. **Inline destinations**: Makes view body harder to read

### Recommended Refactor

```swift
struct SettingsView: View {
    @EnvironmentObject var authViewModel: AuthenticationViewModel
    @ObservedObject private var settings = AppSettings.shared
    @State private var showingAlert = false
    @State private var alertMessage = ""
    @State private var showMarkAllDialog = false
    @State private var isProcessingMarkAll = false
    @State private var showingDebugMenu = false

    var body: some View {
        NavigationStack {
            Form {
                accountSection
                displayPreferencesSection
                librarySection
                sourcesSection
                readStatusSection
                debugSection
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: SettingsDestination.self) { destination in
                switch destination {
                case .favorites:
                    FavoritesView()
                case .feedSources:
                    FeedSourcesView()
                case .podcastSources:
                    PodcastSourcesView()
                }
            }
            .alert("Settings", isPresented: $showingAlert) { ... }
            .confirmationDialog(...) { ... }
            .sheet(isPresented: $showingDebugMenu) { ... }
        }
    }

    // MARK: - Sections

    private var librarySection: some View {
        Section("Library") {
            NavigationLink(value: SettingsDestination.favorites) {
                Label("Favorites", systemImage: "star")
            }
        }
    }

    private var sourcesSection: some View {
        Section("Sources") {
            NavigationLink(value: SettingsDestination.feedSources) {
                Label("Feed Sources", systemImage: "list.bullet.rectangle")
            }
            NavigationLink(value: SettingsDestination.podcastSources) {
                Label("Podcast Sources", systemImage: "dot.radiowaves.left.and.right")
            }
        }
    }
}

// MARK: - Navigation

enum SettingsDestination: Hashable {
    case favorites
    case feedSources
    case podcastSources
}
```

### Changes

- Replace `NavigationView` → `NavigationStack`
- Replace inline `NavigationLink { Destination() }` → `NavigationLink(value:)` + `.navigationDestination(for:)`
- Remove manual chevron icons (NavigationLink provides them)
- Extract sections to computed properties for readability

### Effort

~1 hour

---

## 5. ChatSessionView.swift (Bonus)

**File**: `client/newsly/newsly/Views/ChatSessionView.swift` + `ChatScrollView.swift`

### Current State

Custom `UIViewControllerRepresentable` wrapping `UIScrollView` with `UIHostingController`.

### Problems

- Over-engineered for chat scroll behavior
- Manual intrinsic size invalidation
- `VStack` instead of `LazyVStack` (performance issue)

### Recommended Refactor

Replace with native SwiftUI:
```swift
ScrollViewReader { proxy in
    ScrollView {
        LazyVStack(spacing: 12) {
            ForEach(messages) { message in
                MessageBubble(message: message)
                    .id(message.id)
            }
        }
        .scrollTargetLayout()
        .padding()
    }
    .defaultScrollAnchor(.bottom)
    .scrollPosition(id: $scrolledMessageID)
    .onChange(of: messages.count) { _, _ in
        if let lastID = messages.last?.id {
            withAnimation { proxy.scrollTo(lastID, anchor: .bottom) }
        }
    }
}
```

**Delete**: `ChatScrollView.swift` entirely (~130 lines)

### Effort

~2 hours

---

## Priority Order

| Priority | Screen | Impact | Effort |
|----------|--------|--------|--------|
| 1 | **SettingsView** | Low risk, modernizes deprecated API | 1 hour |
| 2 | **ShortFormView** | High complexity reduction (~50 lines removed) | 1-2 hours |
| 3 | **ChatSessionView** | Deletes entire file, simplifies scroll | 2 hours |
| 4 | **LongFormView** | Medium impact, depends on swipe action needs | 1-2 hours |
| 5 | **KnowledgeDiscoveryView** | Code organization, lower priority | 2-3 hours |

---

## iOS Version Requirements

All recommendations require **iOS 17+**:
- `scrollPosition(id:)` — iOS 17
- `onScrollPhaseChange` — iOS 17
- `defaultScrollAnchor` — iOS 17
- `scrollTargetLayout()` — iOS 17
- `NavigationStack` — iOS 16

Verify deployment target before proceeding.

---

## Testing Checklist

After each refactor, verify:

- [ ] Pull-to-refresh works
- [ ] Infinite scroll / load more triggers correctly
- [ ] Scroll position preserved on tab switch
- [ ] Scroll position preserved on background/foreground
- [ ] Mark-as-read behavior (ShortFormView) triggers correctly
- [ ] Navigation transitions work smoothly
- [ ] VoiceOver accessibility maintained
- [ ] Memory usage stable during long scrolls (Instruments)
