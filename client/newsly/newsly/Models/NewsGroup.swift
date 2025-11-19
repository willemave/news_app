//
//  NewsGroup.swift
//  newsly
//
//  Created by Assistant on 10/12/25.
//

import Foundation
import UIKit

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
    /// Title is fully expanded; summary and metadata are single-line each.
    static func estimatedRowHeight(averageTitleLines: CGFloat = 1.8) -> CGFloat {
        let titleLineHeight = UIFont.preferredFont(forTextStyle: .subheadline).lineHeight
        let captionLineHeight = UIFont.preferredFont(forTextStyle: .caption2).lineHeight

        // NewsGroupCard spacings: 4 between title→summary and 4 between summary→meta.
        let verticalSpacing: CGFloat = 8
        let verticalPaddingPerItem: CGFloat = 16   // .padding(.vertical, 8)
        let dividerHeight: CGFloat = 1             // matches Divider()
        let baselineFudge: CGFloat = 2             // rounding/baseline

        let titleBlock = titleLineHeight * averageTitleLines
        let summaryBlock = captionLineHeight       // clamped to 1 line
        let metaBlock = captionLineHeight          // single line
        let row = titleBlock + summaryBlock + metaBlock
                  + verticalSpacing + verticalPaddingPerItem + dividerHeight + baselineFudge
        return ceil(row)
    }

    /// Estimate the exact row height for a specific item at a given text width.
    /// Uses NSString bounding rect so wrapped titles are measured precisely.
    static func estimateRowHeight(for item: ContentSummary, textWidth: CGFloat) -> CGFloat {
        let titleFont = UIFont.preferredFont(forTextStyle: .subheadline)
        let captionLine = ceil(UIFont.preferredFont(forTextStyle: .caption2).lineHeight)
        let verticalPadding: CGFloat = 16     // .padding(.vertical, 8)
        let verticalSpacing: CGFloat = 4      // inner VStack spacing

        let title = item.displayTitle as NSString
        let bounds = title.boundingRect(
            with: CGSize(width: Swift.max(textWidth, 0), height: .greatestFiniteMagnitude),
            options: [.usesLineFragmentOrigin, .usesFontLeading],
            attributes: [.font: titleFont],
            context: nil
        )
        let titleHeight = ceil(bounds.height)
        let summaryHeight = (item.shortSummary?.isEmpty ?? true) ? 0 : captionLine
        let metaHeight = captionLine

        return titleHeight + summaryHeight + metaHeight + verticalSpacing + verticalPadding
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
        let dividerHeight: CGFloat = 1 / UIScreen.main.scale
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
                                          averageTitleLines: CGFloat = 1.8) -> Int {
        let minimumGroupSize = 5
        let maximumGroupSize = 12

        let rowH = estimatedRowHeight(averageTitleLines: averageTitleLines)
        let dividerH: CGFloat = 1
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
        let tLH = UIFont.preferredFont(forTextStyle: .subheadline).lineHeight
        let cLH = UIFont.preferredFont(forTextStyle: .caption2).lineHeight
        print("  - Typography (title/caption): \(tLH)/\(cLH)")
        print("  - Avg title lines: \(averageTitleLines)")
        print("  - Estimated row height: \(rowH)")
        print("  - Selected count: \(clamped)")
        print("  - Projected height @count: \(projected(clamped))")
        return clamped
    }
}
