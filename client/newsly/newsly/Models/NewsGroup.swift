//
//  NewsGroup.swift
//  newsly
//
//  Created by Assistant on 10/12/25.
//

import Foundation
import UIKit

enum NewsRowTypography {
    static let title: UIFont = {
        let base = UIFont.preferredFont(forTextStyle: .body)
        return UIFont.systemFont(ofSize: base.pointSize, weight: .medium)
    }()
    static let summary: UIFont = UIFont.preferredFont(forTextStyle: .footnote)
    static let metadata: UIFont = UIFont.preferredFont(forTextStyle: .caption1)
}

enum NewsRowLayout {
    static let horizontalPadding: CGFloat = 24     // Card padding applied in PagedCardView
    static let verticalPadding: CGFloat = 16       // .padding(.vertical, 8)
    static let interStackSpacing: CGFloat = 8      // Two 4pt gaps inside the VStack
    static var dividerHeight: CGFloat { 1 / UIScreen.main.scale }
}

/// Represents a dynamically-sized group of news items displayed together
struct NewsGroup: Identifiable {
    let id: String
    let items: [ContentSummary]
    var isRead: Bool

    init(items: [ContentSummary]) {
        // Use the first item's ID as the group ID
        self.id = items.first.map { "\($0.id)" } ?? UUID().uuidString
        self.items = items
        // Group is read if ALL items are read
        self.isRead = items.allSatisfy { $0.isRead }
    }

    /// Update read status for all items in group
    func updatingAllAsRead(_ read: Bool) -> NewsGroup {
        let updatedItems = items.map { $0.updating(isRead: read) }
        return NewsGroup(items: updatedItems)
    }

    /// Update a single item in the group
    func updatingItem(id: Int, with updater: (ContentSummary) -> ContentSummary) -> NewsGroup {
        let updatedItems = items.map { item in
            item.id == id ? updater(item) : item
        }
        return NewsGroup(items: updatedItems)
    }
}

extension Array where Element == ContentSummary {
    /// Group news items into groups of 7
    func groupedBySeven() -> [NewsGroup] {
        return grouped(by: 7)
    }

    /// Group news items into dynamic-sized groups based on screen height
    func grouped(by size: Int) -> [NewsGroup] {
        var groups: [NewsGroup] = []
        for index in stride(from: 0, to: count, by: size) {
            let endIndex = Swift.min(index + size, count)
            let groupItems = Array(self[index..<endIndex])
            groups.append(NewsGroup(items: groupItems))
        }
        return groups
    }

    /// Estimated per-row height using the same layout as NewsGroupCard.
    /// Title is fully expanded; summary is assumed multi-line (up to two) with metadata on one line.
    static func estimatedRowHeight(averageTitleLines: CGFloat = 2.0,
                                   averageSummaryLines: CGFloat = 1.6) -> CGFloat {
        let titleBlock = NewsRowTypography.title.lineHeight * averageTitleLines
        let summaryBlock = NewsRowTypography.summary.lineHeight * averageSummaryLines
        let metaBlock = NewsRowTypography.metadata.lineHeight

        let baselineFudge: CGFloat = 2  // Protect against rounding drift on dynamic type sizes
        let row = titleBlock + summaryBlock + metaBlock
                  + NewsRowLayout.interStackSpacing + NewsRowLayout.verticalPadding
                  + NewsRowLayout.dividerHeight + baselineFudge
        return ceil(row)
    }

    /// Estimate the exact row height for a specific item at a given text width.
    /// Uses NSString bounding rect so wrapped titles are measured precisely.
    static func estimateRowHeight(for item: ContentSummary, textWidth: CGFloat) -> CGFloat {
        let titleFont = NewsRowTypography.title
        let summaryFont = NewsRowTypography.summary
        let metadataFont = NewsRowTypography.metadata

        let titleBounds = (item.displayTitle as NSString).boundingRect(
            with: CGSize(width: Swift.max(textWidth, 0), height: .greatestFiniteMagnitude),
            options: [.usesLineFragmentOrigin, .usesFontLeading],
            attributes: [.font: titleFont],
            context: nil
        )
        let titleHeight = ceil(titleBounds.height)

        var summaryHeight: CGFloat = 0
        if let summary = item.shortSummary, !summary.isEmpty {
            let summaryBounds = (summary as NSString).boundingRect(
                with: CGSize(width: Swift.max(textWidth, 0), height: .greatestFiniteMagnitude),
                options: [.usesLineFragmentOrigin, .usesFontLeading],
                attributes: [.font: summaryFont],
                context: nil
            )
            let maxSummaryHeight = ceil(summaryFont.lineHeight * 2)
            summaryHeight = Swift.min(ceil(summaryBounds.height), maxSummaryHeight)
        }

        let metaHeight = ceil(metadataFont.lineHeight)
        let stackSpacing: CGFloat = summaryHeight > 0 ? NewsRowLayout.interStackSpacing : 4

        return titleHeight + summaryHeight + metaHeight
            + stackSpacing + NewsRowLayout.verticalPadding
    }

    /// Pack items into groups that fit within a fixed card height using measured row heights.
    /// Text width should be the actual width available to Text inside a row.
    func groupedToFit(availableHeight: CGFloat,
                      textWidth: CGFloat,
                      minCount: Int = 5,
                      maxCount: Int = 12) -> [NewsGroup] {
        guard availableHeight > 0, textWidth > 0 else {
            return grouped(by: minCount)
        }

        // Use pixel-perfect divider height matching SwiftUI's Divider (1 physical pixel)
        let dividerHeight = NewsRowLayout.dividerHeight
        // Small safety margin to avoid underfill from rounding errors
        let budget = Swift.max(availableHeight - 4, 0)
        var result: [NewsGroup] = []
        var bucket: [ContentSummary] = []
        var used: CGFloat = 0

        for item in self {
            let rowH = Self.estimateRowHeight(for: item, textWidth: textWidth)
            let add = rowH + (bucket.isEmpty ? 0 : dividerHeight)

            // If adding this row would overflow or exceed max, flush the bucket.
            if !bucket.isEmpty && (used + add > budget || bucket.count >= maxCount) {
                result.append(NewsGroup(items: bucket))
                bucket = [item]
                used = rowH
            } else {
                bucket.append(item)
                used += add
            }
        }

        if !bucket.isEmpty {
            result.append(NewsGroup(items: bucket))
        }
        return result
    }

    /// Calculate optimal group size for a given available height.
    /// Uses calibrated per-row estimate and an exact fit that includes N−1 dividers.
    static func calculateOptimalGroupSize(availableHeight: CGFloat,
                                          averageTitleLines: CGFloat = 2.0,
                                          averageSummaryLines: CGFloat = 1.6) -> Int {
        let minimumGroupSize = 5
        let maximumGroupSize = 12

        let rowH = estimatedRowHeight(
            averageTitleLines: averageTitleLines,
            averageSummaryLines: averageSummaryLines
        )
        let dividerH = NewsRowLayout.dividerHeight
        let usableHeight = Swift.max(availableHeight, 0)

        // First guess with a "row + divider" share to reduce bias.
        var count = Int(floor((usableHeight + dividerH) / (rowH + dividerH)))

        // Exact fit that respects N−1 dividers.
        func projected(_ n: Int) -> CGFloat {
            guard n > 0 else { return 0 }
            return CGFloat(n) * rowH + CGFloat(Swift.max(n - 1, 0)) * dividerH
        }
        while count < maximumGroupSize && projected(count + 1) <= usableHeight { count += 1 }
        while count > minimumGroupSize && projected(count) > usableHeight { count -= 1 }

        let clamped = Swift.max(minimumGroupSize, Swift.min(maximumGroupSize, count))

        print("📐 Group Size Calculation")
        print("  - Available height: \(availableHeight)")
        print("  - Usable height: \(usableHeight)")
        let tLH = NewsRowTypography.title.lineHeight
        let sLH = NewsRowTypography.summary.lineHeight
        let mLH = NewsRowTypography.metadata.lineHeight
        print("  - Typography (title/summary/meta): \(tLH)/\(sLH)/\(mLH)")
        print("  - Avg lines (title/summary): \(averageTitleLines)/\(averageSummaryLines)")
        print("  - Estimated row height: \(rowH)")
        print("  - Selected count: \(clamped)")
        print("  - Projected height @count: \(projected(clamped))")
        return clamped
    }
}
