//
//  StructuredSummaryView.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct StructuredSummaryView: View {
    let summary: StructuredSummary
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            if !summary.bulletPoints.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Key Points")
                        .font(.headline)
                    
                    ForEach(summary.bulletPoints, id: \.text) { point in
                        HStack(alignment: .top, spacing: 8) {
                            Text("•")
                                .foregroundColor(.accentColor)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(point.text)
                                    .font(.body)
                                if let category = point.category {
                                    Text(category.replacingOccurrences(of: "_", with: " ").capitalized)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                    }
                }
            }
            
            if !summary.quotes.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Notable Quotes")
                        .font(.headline)
                    
                    ForEach(summary.quotes, id: \.text) { quote in
                        VStack(alignment: .leading, spacing: 8) {
                            HStack(alignment: .top, spacing: 8) {
                                Text("\u{201C}")
                                    .font(.largeTitle)
                                    .foregroundColor(.accentColor)
                                Text(quote.text)
                                    .font(.body)
                                    .italic()
                            }
                            if let context = quote.context {
                                Text("— \(context)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding()
                        .background(Color(UIColor.secondarySystemBackground))
                        .cornerRadius(8)
                    }
                }
            }
            
            if !summary.topics.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Topics")
                        .font(.headline)
                    
                    FlowLayout(spacing: 8) {
                        ForEach(summary.topics, id: \.self) { topic in
                            Text(topic)
                                .font(.caption)
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(Color.accentColor.opacity(0.1))
                                .foregroundColor(.accentColor)
                                .clipShape(Capsule())
                        }
                    }
                }
            }
        }
    }
}

// Simple flow layout for topics
struct FlowLayout: Layout {
    var spacing: CGFloat = 8
    
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = FlowResult(
            in: proposal.replacingUnspecifiedDimensions().width,
            subviews: subviews,
            spacing: spacing
        )
        return result.bounds
    }
    
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = FlowResult(
            in: bounds.width,
            subviews: subviews,
            spacing: spacing
        )
        for row in result.rows {
            for (frameIndex, subviewIndex) in row.indices.enumerated() {
                let frame = row.frames[frameIndex]
                let position = CGPoint(
                    x: bounds.minX + frame.minX,
                    y: bounds.minY + frame.minY
                )
                subviews[subviewIndex].place(at: position, proposal: ProposedViewSize(frame.size))
            }
        }
    }
    
    struct FlowResult {
        var bounds = CGSize.zero
        var rows = [Row]()
        
        struct Row {
            var indices: Range<Int>
            var frames: [CGRect]
        }
        
        init(in maxPossibleWidth: CGFloat, subviews: Subviews, spacing: CGFloat) {
            var itemsInRow = 0
            var remainingWidth = maxPossibleWidth.isFinite ? maxPossibleWidth : .greatestFiniteMagnitude
            var rowMinY: CGFloat = 0.0
            var rowHeight: CGFloat = 0.0
            var rows = [Row]()
            
            for (index, subview) in zip(subviews.indices, subviews) {
                let idealSize = subview.sizeThatFits(.unspecified)
                if index != 0 && widthInRow(index: index, idealWidth: idealSize.width, spacing: spacing) > remainingWidth {
                    finalizeRow(indices: index - itemsInRow..<index, y: rowMinY, rows: &rows)
                    
                    bounds.width = max(bounds.width, maxPossibleWidth - remainingWidth)
                    rowMinY += rowHeight + spacing
                    itemsInRow = 0
                    remainingWidth = maxPossibleWidth
                    rowHeight = 0
                }
                
                addToRow(index: index, idealSize: idealSize, spacing: spacing, &remainingWidth, &rowHeight)
                
                itemsInRow += 1
            }
            
            if itemsInRow > 0 {
                finalizeRow(indices: subviews.count - itemsInRow..<subviews.count, y: rowMinY, rows: &rows)
                bounds.width = max(bounds.width, maxPossibleWidth - remainingWidth)
            }
            
            bounds.height = rowMinY + rowHeight
            self.rows = rows
            
            func widthInRow(index: Int, idealWidth: CGFloat, spacing: CGFloat) -> CGFloat {
                idealWidth + (index == 0 ? 0 : spacing)
            }
            
            func addToRow(index: Int, idealSize: CGSize, spacing: CGFloat, _ remainingWidth: inout CGFloat, _ rowHeight: inout CGFloat) {
                let width = widthInRow(index: index, idealWidth: idealSize.width, spacing: spacing)
                
                remainingWidth -= width
                rowHeight = max(rowHeight, idealSize.height)
            }
            
            func finalizeRow(indices: Range<Int>, y: CGFloat, rows: inout [Row]) {
                var frames = [CGRect]()
                var x = 0.0
                for index in indices {
                    let idealSize = subviews[index].sizeThatFits(.unspecified)
                    let width = idealSize.width
                    let height = idealSize.height
                    frames.append(CGRect(x: x, y: y, width: width, height: height))
                    x += width + spacing
                }
                rows.append(Row(indices: indices, frames: frames))
            }
        }
    }
}

#Preview {
    StructuredSummaryView(summary: StructuredSummary(
        title: "Sample Title",
        overview: "This is a sample overview",
        bulletPoints: [
            BulletPoint(text: "Point 1", category: "key_finding"),
            BulletPoint(text: "Point 2", category: nil)
        ],
        quotes: [
            Quote(text: "Sample quote", context: "John Doe")
        ],
        topics: ["Topic 1", "Topic 2"],
        summarizationDate: nil,
        classification: "to_read"
    ))
    .padding()
}