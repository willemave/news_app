    //
//  SearchView.swift
//  newsly
//
//  Created by Assistant on 9/15/25.
//

import SwiftUI

struct SearchView: View {
    @StateObject private var viewModel = SearchViewModel()

    var body: some View {
        VStack(spacing: 0) {
            Picker("Content Type", selection: $viewModel.selectedContentType) {
                ForEach(viewModel.contentTypeOptions, id: \.0) { value, label in
                    Text(label).tag(value)
                }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, Spacing.screenHorizontal)
            .padding(.top, 8)

            Group {
                if viewModel.isLoading {
                    LoadingView()
                } else if let error = viewModel.errorMessage {
                    ErrorView(message: error) {
                        viewModel.retrySearch()
                    }
                } else if viewModel.hasSearched && viewModel.results.isEmpty {
                    EmptyStateView(
                        icon: "magnifyingglass",
                        title: "No Results",
                        subtitle: "Try different keywords or filters."
                    )
                } else if !viewModel.hasSearched {
                    EmptyStateView(
                        icon: "magnifyingglass",
                        title: "Search Articles & Podcasts",
                        subtitle: "Type at least 2 characters to search titles, sources and summaries."
                    )
                } else {
                    List {
                        ForEach(viewModel.results, id: \.id) { item in
                            NavigationLink(destination: ContentDetailView(contentId: item.id)) {
                                HStack(spacing: 12) {
                                    Image(systemName: item.contentType == "podcast" ? "waveform" : "doc.text")
                                        .foregroundStyle(Color.textSecondary)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(item.displayTitle)
                                            .font(.listTitle)
                                            .lineLimit(3)
                                        HStack(spacing: 6) {
                                            if let source = item.source {
                                                Text(source)
                                                    .font(.listCaption)
                                                    .foregroundStyle(Color.textTertiary)
                                            }
                                            Text(item.contentType.capitalized)
                                                .font(.chipLabel)
                                                .foregroundStyle(Color.textTertiary)
                                        }
                                    }
                                    Spacer()
                                }
                                .padding(.vertical, 6)
                            }
                        }
                    }
                    .listStyle(.plain)
                }
            }
        }
        .screenContainer()
        .navigationTitle("Search")
        .searchable(text: $viewModel.searchText, prompt: "Search articles and podcasts")
        .autocorrectionDisabled()
        .textInputAutocapitalization(.never)
    }
}
