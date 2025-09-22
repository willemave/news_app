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
        NavigationStack {
            VStack(spacing: 0) {
                // Filter
                Picker("Content Type", selection: $viewModel.selectedContentType) {
                    ForEach(viewModel.contentTypeOptions, id: \.0) { value, label in
                        Text(label).tag(value)
                    }
                }
                .pickerStyle(.segmented)
                .padding([.horizontal, .top])

                // Results / States
                Group {
                    if viewModel.isLoading {
                        ProgressView("Searching...")
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if let error = viewModel.errorMessage {
                        VStack(spacing: 12) {
                            Image(systemName: "exclamationmark.triangle")
                                .font(.system(size: 44))
                                .foregroundColor(.orange)
                            Text("Search Error")
                                .font(.title3)
                                .fontWeight(.semibold)
                            Text(error).font(.footnote).foregroundColor(.secondary).multilineTextAlignment(.center)
                            Button("Try Again") {
                                viewModel.retrySearch()
                            }.buttonStyle(.borderedProminent)
                        }
                        .padding()
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if viewModel.hasSearched && viewModel.results.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "magnifyingglass")
                                .font(.system(size: 44))
                                .foregroundColor(.secondary)
                            Text("No Results")
                                .font(.title3)
                                .fontWeight(.semibold)
                            Text("Try different keywords or filters.")
                                .font(.footnote)
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else if !viewModel.hasSearched {
                        VStack(spacing: 12) {
                            Image(systemName: "magnifyingglass")
                                .font(.system(size: 44))
                                .foregroundColor(.secondary)
                            Text("Search Articles & Podcasts")
                                .font(.title3)
                                .fontWeight(.semibold)
                            Text("Type at least 2 characters to search titles, sources and summaries.")
                                .font(.footnote)
                                .foregroundColor(.secondary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else {
                        List {
                            ForEach(viewModel.results, id: \.id) { item in
                                NavigationLink(destination: ContentDetailView(contentId: item.id)) {
                                    HStack(spacing: 12) {
                                        Image(systemName: item.contentType == "podcast" ? "waveform" : "doc.text")
                                            .foregroundStyle(.secondary)
                                        VStack(alignment: .leading, spacing: 4) {
                                            Text(item.displayTitle).font(.subheadline).fontWeight(.semibold).lineLimit(3)
                                            HStack(spacing: 6) {
                                                if let source = item.source { Text(source).font(.caption).foregroundStyle(.secondary) }
                                                Text(item.contentType.capitalized).font(.caption2).foregroundStyle(.secondary)
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
            .navigationTitle("Search")
            .toolbarBackground(Color(.systemBackground), for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
        }
        .searchable(text: $viewModel.searchText, prompt: "Search articles and podcasts")
        .autocorrectionDisabled()
        .textInputAutocapitalization(.never)
    }
}
