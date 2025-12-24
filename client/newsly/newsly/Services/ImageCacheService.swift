//
//  ImageCacheService.swift
//  newsly
//
//  Created by Assistant on 12/23/25.
//

import Foundation
import UIKit
import CryptoKit

/// Two-tier image caching service with memory (NSCache) and disk (FileManager) caching.
actor ImageCacheService {
    static let shared = ImageCacheService()
    
    // MARK: - Configuration
    
    private let maxDiskCacheSize: Int64 = 100 * 1024 * 1024 // 100MB
    private let maxCacheAge: TimeInterval = 7 * 24 * 60 * 60 // 7 days
    
    // MARK: - Private Properties
    
    private let memoryCache = NSCache<NSString, UIImage>()
    private let fileManager = FileManager.default
    private let cacheDirectory: URL
    private let diskCacheQueue = DispatchQueue(label: "com.newsly.imagecache.disk", qos: .utility)
    
    // MARK: - Initialization
    
    private init() {
        // Set up cache directory
        let cachesDirectory = fileManager.urls(for: .cachesDirectory, in: .userDomainMask).first!
        cacheDirectory = cachesDirectory.appendingPathComponent("ImageCache", isDirectory: true)
        
        // Create cache directory if needed
        try? fileManager.createDirectory(at: cacheDirectory, withIntermediateDirectories: true)
        
        // Configure memory cache
        memoryCache.countLimit = 100 // Max 100 images in memory
        memoryCache.totalCostLimit = 50 * 1024 * 1024 // 50MB memory limit
        
        // Clean up old entries on init (async)
        Task {
            await cleanupDiskCache()
        }
    }
    
    // MARK: - Public API
    
    /// Get an image from cache (memory first, then disk).
    func image(for url: URL) async -> UIImage? {
        let key = cacheKey(for: url)
        
        // Check memory cache first
        if let cachedImage = memoryCache.object(forKey: key as NSString) {
            return cachedImage
        }
        
        // Check disk cache
        if let diskImage = await loadFromDisk(key: key) {
            // Promote to memory cache
            let cost = diskImage.cgImage.map { $0.bytesPerRow * $0.height } ?? 0
            memoryCache.setObject(diskImage, forKey: key as NSString, cost: cost)
            return diskImage
        }
        
        return nil
    }
    
    /// Cache an image in both memory and disk.
    func cache(_ image: UIImage, for url: URL) async {
        let key = cacheKey(for: url)
        
        // Add to memory cache
        let cost = image.cgImage.map { $0.bytesPerRow * $0.height } ?? 0
        memoryCache.setObject(image, forKey: key as NSString, cost: cost)
        
        // Save to disk asynchronously
        await saveToDisk(image: image, key: key)
    }
    
    /// Prefetch multiple images in the background.
    func prefetch(urls: [URL]) async {
        await withTaskGroup(of: Void.self) { group in
            for url in urls {
                group.addTask {
                    // Only prefetch if not already cached
                    if await self.image(for: url) == nil {
                        await self.downloadAndCache(url: url)
                    }
                }
            }
        }
    }
    
    /// Clear all cached images.
    func clearCache() async {
        // Clear memory cache
        memoryCache.removeAllObjects()
        
        // Clear disk cache
        let fileURLs = (try? fileManager.contentsOfDirectory(
            at: cacheDirectory,
            includingPropertiesForKeys: nil
        )) ?? []
        
        for fileURL in fileURLs {
            try? fileManager.removeItem(at: fileURL)
        }
    }
    
    // MARK: - Private Methods
    
    private func cacheKey(for url: URL) -> String {
        // Use SHA256 hash of URL as cache key
        let data = Data(url.absoluteString.utf8)
        let hash = SHA256.hash(data: data)
        return hash.compactMap { String(format: "%02x", $0) }.joined()
    }
    
    private func diskCacheURL(for key: String) -> URL {
        cacheDirectory.appendingPathComponent("\(key).png")
    }
    
    private func loadFromDisk(key: String) async -> UIImage? {
        let fileURL = diskCacheURL(for: key)
        
        guard fileManager.fileExists(atPath: fileURL.path) else {
            return nil
        }
        
        // Check if file is too old
        if let attributes = try? fileManager.attributesOfItem(atPath: fileURL.path),
           let modificationDate = attributes[.modificationDate] as? Date,
           Date().timeIntervalSince(modificationDate) > maxCacheAge {
            // Remove stale entry
            try? fileManager.removeItem(at: fileURL)
            return nil
        }
        
        guard let data = try? Data(contentsOf: fileURL),
              let image = UIImage(data: data) else {
            return nil
        }
        
        return image
    }
    
    private func saveToDisk(image: UIImage, key: String) async {
        let fileURL = diskCacheURL(for: key)
        
        guard let data = image.pngData() else { return }
        
        do {
            try data.write(to: fileURL)
        } catch {
            print("ImageCacheService: Failed to save to disk: \(error)")
        }
    }
    
    private func downloadAndCache(url: URL) async {
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let image = UIImage(data: data) {
                await cache(image, for: url)
            }
        } catch {
            // Silently fail for prefetch operations
        }
    }
    
    private func cleanupDiskCache() async {
        guard let fileURLs = try? fileManager.contentsOfDirectory(
            at: cacheDirectory,
            includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey]
        ) else { return }
        
        var totalSize: Int64 = 0
        var filesToDelete: [URL] = []
        
        // Collect files and their info
        var fileInfos: [(url: URL, date: Date, size: Int64)] = []
        
        for fileURL in fileURLs {
            guard let attributes = try? fileManager.attributesOfItem(atPath: fileURL.path),
                  let modificationDate = attributes[.modificationDate] as? Date,
                  let fileSize = attributes[.size] as? Int64 else {
                continue
            }
            
            // Remove files older than max age
            if Date().timeIntervalSince(modificationDate) > maxCacheAge {
                filesToDelete.append(fileURL)
                continue
            }
            
            fileInfos.append((fileURL, modificationDate, fileSize))
            totalSize += fileSize
        }
        
        // If over size limit, remove oldest files until under limit
        if totalSize > maxDiskCacheSize {
            // Sort by date (oldest first)
            fileInfos.sort { $0.date < $1.date }
            
            var sizeToFree = totalSize - maxDiskCacheSize
            for fileInfo in fileInfos {
                if sizeToFree <= 0 { break }
                filesToDelete.append(fileInfo.url)
                sizeToFree -= fileInfo.size
            }
        }
        
        // Delete files
        for fileURL in filesToDelete {
            try? fileManager.removeItem(at: fileURL)
        }
    }
}
