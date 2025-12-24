//
//  CachedAsyncImage.swift
//  newsly
//
//  Created by Assistant on 12/23/25.
//

import SwiftUI

/// A cached version of AsyncImage that uses ImageCacheService for memory and disk caching.
/// Supports progressive loading from thumbnail to full image.
struct CachedAsyncImage<Content: View, Placeholder: View>: View {
    let url: URL?
    let thumbnailUrl: URL?
    let scale: CGFloat
    @ViewBuilder let content: (Image) -> Content
    @ViewBuilder let placeholder: () -> Placeholder
    
    @State private var loadedImage: UIImage?
    @State private var thumbnailImage: UIImage?
    @State private var isLoading = false
    @State private var loadingTask: Task<Void, Never>?
    
    init(
        url: URL?,
        thumbnailUrl: URL? = nil,
        scale: CGFloat = 1.0,
        @ViewBuilder content: @escaping (Image) -> Content,
        @ViewBuilder placeholder: @escaping () -> Placeholder
    ) {
        self.url = url
        self.thumbnailUrl = thumbnailUrl
        self.scale = scale
        self.content = content
        self.placeholder = placeholder
    }
    
    var body: some View {
        Group {
            if let image = loadedImage {
                // Show full image
                content(Image(uiImage: image))
            } else if let thumbnail = thumbnailImage {
                // Show thumbnail while loading full image
                content(Image(uiImage: thumbnail))
            } else if isLoading {
                placeholder()
            } else {
                placeholder()
            }
        }
        .onAppear {
            loadImage()
        }
        .onDisappear {
            loadingTask?.cancel()
        }
        .onChange(of: url) { _, newUrl in
            // Reset state when URL changes
            loadedImage = nil
            thumbnailImage = nil
            loadingTask?.cancel()
            loadImage()
        }
    }
    
    private func loadImage() {
        guard let url = url else { return }
        
        isLoading = true
        
        loadingTask = Task {
            // Try to load from cache first
            if let cached = await ImageCacheService.shared.image(for: url) {
                await MainActor.run {
                    withAnimation(.easeIn(duration: 0.15)) {
                        loadedImage = cached
                        isLoading = false
                    }
                }
                return
            }
            
            // If we have a thumbnail URL and no cached full image, try thumbnail first
            if let thumbnailUrl = thumbnailUrl {
                // Try cached thumbnail
                if let cachedThumb = await ImageCacheService.shared.image(for: thumbnailUrl) {
                    await MainActor.run {
                        thumbnailImage = cachedThumb
                    }
                } else {
                    // Download thumbnail
                    if let thumbData = try? await URLSession.shared.data(from: thumbnailUrl).0,
                       let thumbImage = UIImage(data: thumbData) {
                        await ImageCacheService.shared.cache(thumbImage, for: thumbnailUrl)
                        await MainActor.run {
                            thumbnailImage = thumbImage
                        }
                    }
                }
            }
            
            // Download full image
            do {
                let (data, _) = try await URLSession.shared.data(from: url)
                if let image = UIImage(data: data) {
                    await ImageCacheService.shared.cache(image, for: url)
                    await MainActor.run {
                        withAnimation(.easeIn(duration: 0.2)) {
                            loadedImage = image
                            isLoading = false
                        }
                    }
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - Convenience Initializers

extension CachedAsyncImage where Placeholder == ProgressView<EmptyView, EmptyView> {
    /// Creates a CachedAsyncImage with a default ProgressView placeholder.
    init(
        url: URL?,
        thumbnailUrl: URL? = nil,
        scale: CGFloat = 1.0,
        @ViewBuilder content: @escaping (Image) -> Content
    ) {
        self.init(
            url: url,
            thumbnailUrl: thumbnailUrl,
            scale: scale,
            content: content,
            placeholder: { ProgressView() }
        )
    }
}

extension CachedAsyncImage where Content == Image, Placeholder == ProgressView<EmptyView, EmptyView> {
    /// Creates a CachedAsyncImage that displays the image directly.
    init(url: URL?, thumbnailUrl: URL? = nil, scale: CGFloat = 1.0) {
        self.init(
            url: url,
            thumbnailUrl: thumbnailUrl,
            scale: scale,
            content: { $0 },
            placeholder: { ProgressView() }
        )
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 20) {
        CachedAsyncImage(
            url: URL(string: "https://example.com/image.png")
        ) { image in
            image
                .resizable()
                .aspectRatio(contentMode: .fill)
                .frame(width: 100, height: 100)
                .clipShape(RoundedRectangle(cornerRadius: 8))
        } placeholder: {
            RoundedRectangle(cornerRadius: 8)
                .fill(Color.gray.opacity(0.3))
                .frame(width: 100, height: 100)
                .overlay(ProgressView())
        }
    }
    .padding()
}
